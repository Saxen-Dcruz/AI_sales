import asyncio
import hashlib
import json
import time
from typing import Optional, List, AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine

# LangChain / AI Imports
from langchain_postgres import PGVector
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, Runnable
from langchain_core.output_parsers import StrOutputParser
from langchain_postgres import PostgresChatMessageHistory
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_community.document_compressors.flashrank_rerank import FlashrankRerank
from flashrank import Ranker
import redis.asyncio as aioredis
from psycopg_pool import ConnectionPool

# Local tool imports
from app.agents.tools.rag_callbacks import TokenUsageCallback
from app.agents.tools.rag_classifier import (
    CONTEXT_REF_MARKERS,
    is_catalog_query,
    classify_budget,
    get_chunk_type_filter,
    detect_product_ids,
)

# Project Imports
from app.agents.prompts.prompts import RDL_PROMPT
from app.core.config import settings
from app.database.core import SessionLocal
from app.models.product import Product

_KNOWLEDGE_GAP_PHRASES = [
    "i don't have", "i do not have", "not in my knowledge",
    "no information", "cannot find", "unable to find",
    "not available in", "outside my knowledge", "i'm not sure",
    "i am not sure", "don't have specific", "no specific information",
    "please contact", "reach out to", "speak with",
]


def _is_knowledge_gap(answer: str) -> bool:
    """Returns True if the answer signals the knowledge base was insufficient."""
    lower = answer.lower()
    return any(phrase in lower for phrase in _KNOWLEDGE_GAP_PHRASES)


class RAGManager:
    # LATENCY-D: Redis retrieval cache settings
    _CACHE_KEY_PREFIX = "rag:retrieval:"
    _CACHE_TTL_SECONDS = 600  # 10 minutes

    # LATENCY-E: shared psycopg connection pool (class-level singleton)
    _chat_db_pool: Optional[ConnectionPool] = None

    def __init__(self):
        # Full chains (rewrite + answer) — for ainvoke path
        self.rag_chain_factual: Optional[Runnable] = None
        self.rag_chain_standard: Optional[Runnable] = None
        self.rag_chain_expanded: Optional[Runnable] = None
        # Bare answer chains (RDL_PROMPT | llm | parser) — for astream path (true token streaming)
        self.answer_chain_factual: Optional[Runnable] = None
        self.answer_chain_standard: Optional[Runnable] = None
        self.answer_chain_expanded: Optional[Runnable] = None
        # Shared sentiment chain — LATENCY-F: started as asyncio.create_task alongside streaming
        self.sentiment_chain: Optional[Runnable] = None
        self.rerank_retriever: Optional[Runnable] = None
        self.vectorstore: Optional[PGVector] = None
        # LATENCY-D: async Redis client for retrieval cache
        self._redis: Optional[aioredis.Redis] = None
        # Product name → id map for query-time product detection
        self._product_catalog: List[dict] = []
        self.rag_initialized = asyncio.Event()
        self._initialization_lock = asyncio.Lock()

    async def initialize_rag(self) -> None:
        async with self._initialization_lock:
            if self.rag_initialized.is_set():
                return

            connection_str = (
                settings.DATABASE_URL
                .replace("postgresql+psycopg://", "postgresql+psycopg_async://")
                .replace("postgresql://", "postgresql+psycopg_async://")
            )
            async_engine = create_async_engine(connection_str)

            try:
                embeddings = GoogleGenerativeAIEmbeddings(
                    model=settings.AGENT.rag.embedding_model,
                    google_api_key=settings.GOOGLE_API_KEY
                )

                self.vectorstore = PGVector(
                    embeddings=embeddings,
                    collection_name="product_embeddings",
                    connection=async_engine,
                    use_jsonb=True,
                    create_extension=False
                )

                ranker_client = Ranker(model_name="ms-marco-MultiBERT-L-12")
                compressor = FlashrankRerank(client=ranker_client, top_n=5, score_threshold=0.3)

                # Shared retriever — used directly in query_rag_database (single retrieval pass).
                base_retriever = self.vectorstore.as_retriever(search_kwargs={
                    "k": 8,
                    "filter": {"chunk_type": {"$ne": "frequently_bought_together"}},
                })
                self.rerank_retriever = ContextualCompressionRetriever(
                    base_compressor=compressor,
                    base_retriever=base_retriever,
                )

                # LATENCY-E: psycopg pool for chat history — create_tables runs once here,
                # not on every query. Pool min_size=2 keeps warm connections ready.
                if RAGManager._chat_db_pool is None:
                    sync_url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
                    RAGManager._chat_db_pool = ConnectionPool(
                        sync_url, min_size=2, max_size=10, open=True
                    )
                    with RAGManager._chat_db_pool.connection() as conn:
                        PostgresChatMessageHistory.create_tables(conn, "chat_history")
                    print("✅ psycopg pool ready (2–10 connections), chat_history table verified.")

                # LATENCY-D: async Redis client for retrieval cache
                redis_host = settings.REDIS_HOST if hasattr(settings, "REDIS_HOST") else "redis"
                redis_port = settings.REDIS_PORT if hasattr(settings, "REDIS_PORT") else 6379
                self._redis = aioredis.from_url(
                    f"redis://{redis_host}:{redis_port}/1",  # DB 1 — separate from pub/sub on DB 0
                    decode_responses=True,
                )
                print("✅ Redis retrieval cache connected (DB 1).")

                # Three LLM instances — identical except for token budget.
                # streaming=True enables true token streaming on the bare answer chains.
                def _make_llm(max_tokens: int) -> ChatGoogleGenerativeAI:
                    return ChatGoogleGenerativeAI(
                        model=settings.AGENT.rag.llm_model,
                        google_api_key=settings.GOOGLE_API_KEY,
                        temperature=0.1,
                        streaming=True,
                        max_output_tokens=max_tokens,
                    )

                # ISSUE-010: sentiment uses non-streaming LLM — streaming=True on a 64-token
                # response causes Gemini to return an empty stream, crashing the task.
                sentiment_llm = ChatGoogleGenerativeAI(
                    model=settings.AGENT.rag.llm_model,
                    google_api_key=settings.GOOGLE_API_KEY,
                    temperature=0.1,
                    streaming=False,
                    max_output_tokens=64,
                )
                sentiment_prompt = ChatPromptTemplate.from_template(
                    "Analyze sentiment: POSITIVE, NEUTRAL, or FRUSTRATED. Reply with ONE word.\nMsg: {question}"
                )
                self.sentiment_chain = sentiment_prompt | sentiment_llm | StrOutputParser()

                # LATENCY-C: dedicated rewrite LLM (256 tokens — enough for query rewriting).
                self._rewrite_llm = _make_llm(256)

                # Bare answer chains — used by stream_rag_database for true token streaming.
                self.answer_chain_factual  = RDL_PROMPT | _make_llm(256)  | StrOutputParser()
                self.answer_chain_standard = RDL_PROMPT | _make_llm(512)  | StrOutputParser()
                self.answer_chain_expanded = RDL_PROMPT | _make_llm(4096) | StrOutputParser()

                # Full chains (smart-rewrite + answer) — used by query_rag_database (ainvoke path).
                self.rag_chain_factual  = self._build_runnable_rag(self.answer_chain_factual)
                self.rag_chain_standard = self._build_runnable_rag(self.answer_chain_standard)
                self.rag_chain_expanded = self._build_runnable_rag(self.answer_chain_expanded)

                # Cache product names for query-time product detection
                def _load_catalog():
                    with SessionLocal() as session:
                        return session.query(Product.id, Product.name, Product.order_code).filter(Product.is_active == True).all()

                catalog = await asyncio.to_thread(_load_catalog)
                self._product_catalog = [
                    {"id": p.id, "name": p.name, "order_code": p.order_code or ""}
                    for p in catalog
                ]
                print(f"✅ Product catalog cached ({len(self._product_catalog)} products).")

                self.rag_initialized.set()
                print("🚀 RAG System Ready (pool + cache + true streaming).")

            except Exception as e:
                print(f"❌ Initialization failed: {e}")
                raise e

    def _format_docs(self, docs) -> str:
        print(f"\n[DEBUG] Re-ranker passed {len(docs)} documents to the LLM.")
        for i, d in enumerate(docs):
            print(f"  Doc {i}: {d.page_content[:150]}...")
        print("--------------------------------------------------\n")
        return "\n\n".join([
            f"--- [Product: {d.metadata.get('product_name')} | Section: {d.metadata.get('chunk_type')}] ---\n{d.page_content}"
            for d in docs
        ])

    def _get_history_callable(self, session_id: str):
        # LATENCY-E: borrow a pooled connection — no TCP handshake overhead.
        conn = RAGManager._chat_db_pool.getconn()
        conn.autocommit = True
        return PostgresChatMessageHistory("chat_history", session_id, sync_connection=conn), conn

    def _return_history_conn(self, conn) -> None:
        try:
            RAGManager._chat_db_pool.putconn(conn)
        except Exception as e:
            print(f"[POOL ERROR] Failed to return connection: {e}")

    def _build_runnable_rag(self, answer_chain: Runnable) -> Runnable:
        """
        Build the full ainvoke chain: smart rewrite → answer.
        Sentiment is NOT in this chain — it runs as asyncio.create_task in the entry points.
        """
        rewrite_prompt = ChatPromptTemplate.from_messages([
            ("system", "Rewrite the user's question to be a standalone search query based on chat history. Do not add conversational text."),
            MessagesPlaceholder("chat_history"),
            ("human", "{question}"),
        ])
        rewrite_chain = rewrite_prompt | self._rewrite_llm | StrOutputParser()

        async def _maybe_rewrite(x):
            # ISSUE-004: skip on first turn
            if not x.get("chat_history"):
                print("[REWRITER] No history — skipping")
                return x["question"]
            # LATENCY-C: skip when question is self-contained (no context references)
            q = " " + x["question"].lower() + " "
            if not any(m in q for m in CONTEXT_REF_MARKERS):
                print("[REWRITER] No context refs — skipping")
                return x["question"]
            print("[REWRITER] Context refs found — rewriting")
            return await rewrite_chain.ainvoke(x)

        return (
            RunnablePassthrough.assign(standalone_query=RunnableLambda(_maybe_rewrite))
            | {
                "answer": answer_chain,
                "standalone_query": lambda x: x["standalone_query"],
            }
        )

    def _get_chain(self, question: str, product_count: int = 0) -> tuple[Runnable, str]:
        """
        Route to the right token-budget chain.
        Returns (chain, tier_name) — tier_name is persisted in usage logs.
        """
        tier = classify_budget(question)

        if tier == "standard" and product_count > 1:
            tier = "expanded"
            print(f"[TOKEN BUDGET] bumped standard → expanded — {product_count} products retrieved")

        print(f"[TOKEN BUDGET] {tier}")
        if tier == "expanded":
            return self.rag_chain_expanded, "expanded"
        if tier == "factual":
            return self.rag_chain_factual, "factual"
        return self.rag_chain_standard, "standard"

    # -------------------------------------------------------------------------
    # DB QUERY HELPERS
    # -------------------------------------------------------------------------

    async def _fetch_structured_db_context(self, product_ids: List) -> str:
        """
        Fetch price, order code, category, and links for the given product IDs.
        Injected into the prompt so the LLM always has structured data alongside vector context.
        """
        if not product_ids:
            return ""

        def _query():
            import uuid as _uuid
            coerced = [_uuid.UUID(p) if isinstance(p, str) else p for p in product_ids]
            with SessionLocal() as session:
                return session.query(Product).filter(
                    Product.id.in_(coerced),
                    Product.is_active == True
                ).all()

        products = await asyncio.to_thread(_query)

        if not products:
            return ""

        lines = ["[Structured Product Data — from database]"]
        for p in products:
            parts = [f"Product: {p.name}"]
            if p.order_code:
                parts.append(f"Order Code: {p.order_code}")
            if p.single_price:
                parts.append(f"Price: ₹{p.single_price:,.2f}")
            if p.bulk_price:
                parts.append(f"Bulk Price: ₹{p.bulk_price:,.2f}")
            if p.category:
                parts.append(f"Category: {p.category}")
            if p.product_link:
                parts.append(f"Product Page URL: {p.product_link}")
            # Always emit the Datasheet field so the LLM knows whether it exists
            parts.append(f"Datasheet URL: {p.datasheet_link}" if p.datasheet_link else "Datasheet URL: not available")
            lines.append(" | ".join(parts))

        return "\n".join(lines)

    async def _handle_catalog_query(self, history_store) -> dict:
        """Return the full active product catalog grouped by category. Bypasses vector search."""
        def _query():
            with SessionLocal() as session:
                return (
                    session.query(Product)
                    .filter(Product.is_active == True)
                    .order_by(Product.category, Product.name)
                    .all()
                )

        products = await asyncio.to_thread(_query)

        if not products:
            answer = "No products are currently available in the catalog."
        else:
            by_category: dict = {}
            for p in products:
                cat = p.category or "General"
                by_category.setdefault(cat, []).append(p)

            lines = ["**RDL Technologies — Product Catalog**\n"]
            for cat, prods in sorted(by_category.items()):
                lines.append(f"**{cat}**")
                for p in prods:
                    price_str = f" — ₹{p.single_price:,.2f}" if p.single_price else ""
                    code_str = f" (Order Code: {p.order_code})" if p.order_code else ""
                    lines.append(f"- {p.name}{price_str}{code_str}")
                lines.append("")
            answer = "\n".join(lines)

        await asyncio.to_thread(history_store.add_user_message, "What are all your products?")
        await asyncio.to_thread(history_store.add_ai_message, answer)

        return {
            "answer": answer,
            "standalone_query": "Full product catalog listing",
            "sentiment": "NEUTRAL",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }

    # -------------------------------------------------------------------------
    # RETRIEVAL PIPELINE
    # -------------------------------------------------------------------------

    def _build_retriever(
        self,
        product_ids: Optional[List[str]] = None,
        chunk_filter: Optional[dict] = None,
    ) -> ContextualCompressionRetriever:
        """
        Build a reranking retriever with optional product-id and chunk-type filters.
        """
        f: dict = {}
        if product_ids:
            f["product_id"] = {"$in": product_ids}
        if chunk_filter:
            f.update(chunk_filter)
        base = self.vectorstore.as_retriever(search_kwargs={"k": 8, "filter": f or None})
        return ContextualCompressionRetriever(
            base_compressor=self.rerank_retriever.base_compressor,
            base_retriever=base,
        )

    async def _cached_retrieve(self, question: str) -> List[Document]:
        """
        LATENCY-D: Redis-backed retrieval cache.
        Key: MD5(question) — cache hit returns deserialized Document list directly.
        TTL: 10 minutes.

        Retrieval strategy:
        1. Product name detected → product + chunk-type filtered retrieval.
        2. No product detected → chunk-type filtered unfiltered retrieval.
        3. Smart refinement: if step 2 returns a single product, refine with product filter.
        4. Fallback: relax score threshold if reranker filtered everything.
        """
        cache_key = self._CACHE_KEY_PREFIX + hashlib.md5(question.encode()).hexdigest()
        try:
            cached = await self._redis.get(cache_key)
            if cached:
                print(f"[CACHE HIT] {cache_key}")
                raw = json.loads(cached)
                return [
                    Document(page_content=d["page_content"], metadata=d["metadata"])
                    for d in raw
                ]
        except Exception as e:
            print(f"[CACHE READ ERROR] {e}")

        chunk_filter = get_chunk_type_filter(question)
        detected_ids = detect_product_ids(question, self._product_catalog)

        if detected_ids:
            print(f"[PRODUCT FILTER] Matched {len(detected_ids)} product(s) — restricting retrieval")
            docs = await self._build_retriever(detected_ids, chunk_filter).ainvoke(question)
        else:
            docs = await self._build_retriever(chunk_filter=chunk_filter).ainvoke(question)

            # Smart refinement: single product emerged from unfiltered search →
            # re-run with product filter for higher precision.
            if docs:
                ids_in_docs = list({
                    d.metadata["product_id"] for d in docs
                    if d.metadata.get("product_id")
                })
                if len(ids_in_docs) == 1:
                    print(f"[SMART REFINE] Single product in results — refining with product filter")
                    refined = await self._build_retriever(ids_in_docs, chunk_filter).ainvoke(question)
                    if refined:
                        docs = refined

        # Fallback: if score threshold filtered everything, retry with relaxed threshold
        if not docs:
            print(f"[RETRIEVAL] No docs above threshold — retrying with relaxed threshold")
            fallback_compressor = FlashrankRerank(
                client=self.rerank_retriever.base_compressor.client,
                top_n=3,
                score_threshold=0.1,
            )
            fallback_base = self.vectorstore.as_retriever(search_kwargs={
                "k": 8,
                "filter": {"chunk_type": {"$ne": "frequently_bought_together"}},
            })
            fallback_retriever = ContextualCompressionRetriever(
                base_compressor=fallback_compressor,
                base_retriever=fallback_base,
            )
            docs = await fallback_retriever.ainvoke(question)

        try:
            def _clean_metadata(m: dict) -> dict:
                # Reranker injects float32 relevance_score — not JSON serializable
                return {k: float(v) if hasattr(v, "item") else v for k, v in m.items()}

            serialized = json.dumps([
                {"page_content": d.page_content, "metadata": _clean_metadata(d.metadata)}
                for d in docs
            ])
            await self._redis.setex(cache_key, self._CACHE_TTL_SECONDS, serialized)
        except Exception as e:
            print(f"[CACHE WRITE ERROR] {e}")

        return docs

    async def _ensure_initialized(self) -> None:
        """Trigger lazy initialization if not already done. Safe for concurrent callers."""
        if not self.rag_initialized.is_set():
            await self.initialize_rag()

    # -------------------------------------------------------------------------
    # PUBLIC ENTRY POINTS
    # -------------------------------------------------------------------------

    async def fetch_contexts_only(self, question: str) -> str:
        """
        Retrieve relevant chunks + DB enrichment WITHOUT running the answer LLM.
        Used by the email/call draft pipeline — the draft LLM does its own generation,
        so we only need the raw retrieved text, not a RAG-generated answer.
        Saves ~20s vs query_rag_database() which generates a full 4096-token answer.
        """
        await self._ensure_initialized()
        try:
            docs = await self._cached_retrieve(question)
            product_ids = list({
                d.metadata["product_id"] for d in docs
                if d.metadata.get("product_id")
            })
            db_context = await self._fetch_structured_db_context(product_ids)
            parts = [d.page_content for d in docs]
            if db_context:
                parts.append(db_context)
            return "\n\n---\n\n".join(parts)
        except Exception as e:
            print(f"[FETCH_CONTEXTS] Error: {e}")
            return ""

    async def query_rag_database(self, question: str, session_id: str = "default") -> dict:
        await self._ensure_initialized()

        history_store, conn = self._get_history_callable(session_id)

        try:
            if is_catalog_query(question):
                print(f"\n[ROUTER] Catalog intent detected — querying DB directly")
                return await self._handle_catalog_query(history_store)

            print(f"\n[RETRIEVAL] Querying vector DB for: '{question}'")
            product_ids: List[str] = []
            context = ""
            docs: List[Document] = []
            try:
                docs = await self._cached_retrieve(question)
                context = self._format_docs(docs)
                product_ids = list({
                    d.metadata["product_id"] for d in docs
                    if d.metadata.get("product_id")
                })
            except Exception as e:
                print(f"[RETRIEVAL ERROR] {e}")

            db_context = await self._fetch_structured_db_context(product_ids)
            if db_context:
                print(f"[DB ENRICHMENT] Injecting structured data for {len(product_ids)} product(s)")

            current_history = history_store.messages

            try:
                sentiment_task = asyncio.create_task(self.sentiment_chain.ainvoke({"question": question}))

                chain, token_tier = self._get_chain(question, product_count=len(product_ids))

                usage_cb = TokenUsageCallback()
                result = await chain.ainvoke(
                    {
                        "question": question,
                        "chat_history": current_history,
                        "context": context,
                        "db_context": db_context,
                    },
                    config={
                        "run_name": f"UserQuery_{session_id}",
                        "tags": ["production", "hybrid-search"],
                        "metadata": {"session_id": session_id},
                        "callbacks": [usage_cb],
                    }
                )

                await asyncio.to_thread(history_store.add_user_message, question)
                answer_text = result.get("answer", "")
                await asyncio.to_thread(history_store.add_ai_message, answer_text)

                print(f"[TOKENS] input={usage_cb.input_tokens} output={usage_cb.output_tokens} total={usage_cb.total_tokens}")

                try:
                    raw_sentiment = await sentiment_task
                    sentiment_val = raw_sentiment.strip() if raw_sentiment else "NEUTRAL"
                except Exception as ex:
                    print(f"[SENTIMENT ERROR] {ex}")
                    sentiment_val = "NEUTRAL"

                all_contexts = [d.page_content for d in docs]
                if db_context:
                    all_contexts.append(db_context)

                schedule_call = _is_knowledge_gap(answer_text)

                return {
                    "answer": answer_text,
                    "standalone_query": result.get("standalone_query", ""),
                    "sentiment": sentiment_val,
                    "token_tier": token_tier,
                    "reranker_doc_count": len(docs),
                    "contexts": all_contexts,
                    "schedule_call": schedule_call,
                    "usage": {
                        "input_tokens": usage_cb.input_tokens,
                        "output_tokens": usage_cb.output_tokens,
                    },
                }

            except Exception as e:
                uprint(f"RAG Error: {e}")
                return {
                    "answer": f"Error occurred: {e}",
                    "standalone_query": "Error",
                    "sentiment": "NEUTRAL",
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                }
        finally:
            self._return_history_conn(conn)

    async def stream_rag_database(
        self, question: str, session_id: str = "default"
    ) -> AsyncGenerator[dict, None]:
        """
        Async generator for SSE streaming.
        Yields dicts:
          {"type": "token",  "content": "<token>"}
          {"type": "done",   "sentiment": ..., "standalone_query": ..., "latency_ms": ...}
          {"type": "error",  "content": "<message>"}
        """
        await self._ensure_initialized()
        start_time = time.perf_counter()
        history_store, conn = self._get_history_callable(session_id)

        try:
            if is_catalog_query(question):
                print(f"\n[ROUTER] Catalog intent detected — querying DB directly")
                result = await self._handle_catalog_query(history_store)
                yield {"type": "token", "content": result["answer"]}
                yield {
                    "type": "done",
                    "sentiment": "NEUTRAL",
                    "standalone_query": result["standalone_query"],
                    "latency_ms": int((time.perf_counter() - start_time) * 1000),
                }
                return

            print(f"\n[RETRIEVAL] Streaming query: '{question}'")
            product_ids: List[str] = []
            context = ""
            docs: List[Document] = []
            try:
                docs = await self._cached_retrieve(question)
                context = self._format_docs(docs)
                product_ids = list({
                    d.metadata["product_id"] for d in docs
                    if d.metadata.get("product_id")
                })
            except Exception as e:
                print(f"[RETRIEVAL ERROR] {e}")
                yield {"type": "error", "content": str(e)}
                return

            db_context = await self._fetch_structured_db_context(product_ids)
            if db_context:
                print(f"[DB ENRICHMENT] {len(product_ids)} product(s)")

            current_history = history_store.messages

            sentiment_task = asyncio.create_task(self.sentiment_chain.ainvoke({"question": question}))

            chain, token_tier = self._get_chain(question, product_count=len(product_ids))

            usage_cb = TokenUsageCallback()

            full_answer = ""
            standalone_query = question

            try:
                async for chunk in chain.astream(
                    {
                        "question": question,
                        "chat_history": current_history,
                        "context": context,
                        "db_context": db_context,
                    },
                    config={
                        "run_name": f"StreamQuery_{session_id}",
                        "tags": ["production", "streaming"],
                        "metadata": {"session_id": session_id},
                        "callbacks": [usage_cb],
                    },
                ):
                    token = chunk.get("answer", "")
                    if token:
                        full_answer += token
                        yield {"type": "token", "content": token}

                    if chunk.get("standalone_query"):
                        standalone_query = chunk["standalone_query"]

                await asyncio.to_thread(history_store.add_user_message, question)
                await asyncio.to_thread(history_store.add_ai_message, full_answer)

                print(f"[TOKENS] input={usage_cb.input_tokens} output={usage_cb.output_tokens} total={usage_cb.total_tokens}")

                try:
                    raw_sentiment = await sentiment_task
                    sentiment_val = raw_sentiment.strip() if raw_sentiment else "NEUTRAL"
                except Exception as ex:
                    print(f"[SENTIMENT ERROR] {ex}")
                    sentiment_val = "NEUTRAL"

                yield {
                    "type": "done",
                    "sentiment": sentiment_val,
                    "standalone_query": standalone_query,
                    "answer": full_answer,
                    "latency_ms": int((time.perf_counter() - start_time) * 1000),
                    "token_tier": token_tier,
                    "reranker_doc_count": len(docs),
                    "schedule_call": _is_knowledge_gap(full_answer),
                    "usage": {
                        "input_tokens": usage_cb.input_tokens,
                        "output_tokens": usage_cb.output_tokens,
                    },
                }

            except Exception as e:
                print(f"RAG Stream Error: {e}")
                yield {"type": "error", "content": str(e)}
        finally:
            self._return_history_conn(conn)
