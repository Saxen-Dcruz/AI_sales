import asyncio
from typing import Optional, List
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select

# LangChain / AI Imports
from langchain_postgres import PGVector
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, Runnable
from langchain_core.output_parsers import StrOutputParser
from langchain_postgres import PostgresChatMessageHistory
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_community.document_compressors.flashrank_rerank import FlashrankRerank
from flashrank import Ranker

# Project Imports
from app.agents.prompts.prompts import RDL_PROMPT
from app.core.config import settings
from app.database.core import SessionLocal
from app.models.product import Product
import psycopg


class RAGManager:
    # Keywords that signal the user wants the full product catalog.
    # These queries are routed directly to the DB — no vector search, no LLM needed.
    # Patterns that unambiguously mean "give me the full product list."
    # Kept narrow on purpose — "what products do you have for X" must NOT trigger this.
    _CATALOG_KEYWORDS = [
        "all products",
        "all the products",
        "list all products",
        "list of products",
        "show all products",
        "full catalog",
        "product catalog",
        "every product you",
        "complete list of products",
        "what do you sell",
        "what do you offer",
    ]

    def __init__(self):
        self.rag_chain: Optional[Runnable] = None
        self.vectorstore: Optional[PGVector] = None
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
                compressor = FlashrankRerank(client=ranker_client, top_n=5)

                rag_llm = ChatGoogleGenerativeAI(
                    model=settings.AGENT.rag.llm_model,
                    google_api_key=settings.GOOGLE_API_KEY,
                    temperature=0.1
                )

                self.rag_chain = self._build_runnable_rag(rag_llm, self.vectorstore, compressor)
                self.rag_initialized.set()
                print("🚀 Optimized RAG System (Google Vectors + Re-ranker) Ready!")

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
        standard_url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
        conn = psycopg.connect(standard_url, autocommit=True)
        PostgresChatMessageHistory.create_tables(conn, "chat_history")
        return PostgresChatMessageHistory("chat_history", session_id, sync_connection=conn)

    def _build_runnable_rag(self, llm, vs, compressor):
        # 1. RETRIEVER — exclude frequently_bought_together noise chunks
        base_retriever = vs.as_retriever(search_kwargs={
            "k": 20,
            "filter": {"chunk_type": {"$ne": "frequently_bought_together"}},
        })

        # 2. RE-RANKER
        rerank_retriever = ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=base_retriever
        )

        # 3. QUERY REWRITER
        rewrite_prompt = ChatPromptTemplate.from_messages([
            ("system", "Rewrite the user's question to be a standalone search query based on chat history. If there is no chat history, return the user's exact question unchanged. Do not add conversational text."),
            MessagesPlaceholder("chat_history"),
            ("human", "{question}"),
        ])
        rewrite_chain = rewrite_prompt | llm | StrOutputParser()

        # 4. SENTIMENT ANALYZER
        sentiment_prompt = ChatPromptTemplate.from_template(
            "Analyze sentiment: POSITIVE, NEUTRAL, or FRUSTRATED. Reply with ONE word.\nMsg: {question}"
        )
        sentiment_chain = sentiment_prompt | llm | StrOutputParser()

        # 5. FULL PIPELINE
        # db_context is pre-fetched in query_rag_database and threaded through as passthrough.
        full_chain = (
            RunnablePassthrough.assign(standalone_query=rewrite_chain)
            | RunnableParallel({
                "context": (lambda x: x["standalone_query"].strip() if x["standalone_query"].strip() else x["question"]) | rerank_retriever | self._format_docs,
                "sentiment": sentiment_chain,
                "question": lambda x: x["question"],
                "chat_history": lambda x: x["chat_history"],
                "standalone_query": lambda x: x["standalone_query"],
                "db_context": lambda x: x.get("db_context", ""),
            })
            | {
                "answer": RDL_PROMPT | llm | StrOutputParser(),
                "sentiment": lambda x: x["sentiment"],
                "standalone_query": lambda x: x["standalone_query"],
            }
        )
        return full_chain

    # -------------------------------------------------------------------------
    # DB QUERY HELPERS
    # -------------------------------------------------------------------------

    def _is_catalog_query(self, question: str) -> bool:
        q = question.lower()
        return any(kw in q for kw in self._CATALOG_KEYWORDS)

    async def _fetch_structured_db_context(self, product_ids: List[int]) -> str:
        """
        Fetch price, order code, category, and links for the given product IDs.
        Injected into the prompt so the LLM always has structured data alongside vector context.
        """
        if not product_ids:
            return ""

        def _query():
            with SessionLocal() as session:
                return session.query(Product).filter(
                    Product.id.in_(product_ids),
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
                parts.append(f"Product Link: {p.product_link}")
            if p.datasheet_link:
                parts.append(f"Datasheet: {p.datasheet_link}")
            lines.append(" | ".join(parts))

        return "\n".join(lines)

    async def _handle_catalog_query(self, history_store) -> dict:
        """
        Return the full active product catalog grouped by category.
        Bypasses vector search and LLM entirely — pure DB query.
        """
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
    # MAIN ENTRY POINT
    # -------------------------------------------------------------------------

    async def query_rag_database(self, question: str, session_id: str = "default") -> dict:
        await self.rag_initialized.wait()

        history_store = self._get_history_callable(session_id)

        # --- CATALOG ROUTER: bypass vector search and LLM entirely ---
        if self._is_catalog_query(question):
            print(f"\n[ROUTER] Catalog intent detected — querying DB directly")
            return await self._handle_catalog_query(history_store)

        # --- VECTOR RETRIEVAL DEBUG + PRODUCT ID EXTRACTION ---
        # Reuses the top-5 retrieval to collect product_ids for DB enrichment.
        # The main chain still runs its own k=20 retrieval + rerank independently.
        print(f"\n[DEBUG] Testing Raw Vector DB for: '{question}'")
        product_ids: List[int] = []
        try:
            raw_docs = await self.vectorstore.asimilarity_search(
                question, k=5,
                filter={"chunk_type": {"$ne": "frequently_bought_together"}},
            )
            print(f"[DEBUG] Base Retriever found {len(raw_docs)} documents.")
            for i, doc in enumerate(raw_docs[:3]):
                print(f"  Raw Doc {i}: {doc.page_content[:100]}...")
            product_ids = list({
                doc.metadata["product_id"]
                for doc in raw_docs
                if doc.metadata.get("product_id")
            })
        except Exception as e:
            print(f"[DEBUG ERROR] Base Retriever failed: {e}")
        print("--------------------------------------------------\n")

        # --- DB ENRICHMENT: price, order code, links for retrieved products ---
        db_context = await self._fetch_structured_db_context(product_ids)
        if db_context:
            print(f"[DB ENRICHMENT] Injecting structured data for {len(product_ids)} product(s)")

        current_history = history_store.messages

        try:
            result = await self.rag_chain.ainvoke(
                {
                    "question": question,
                    "chat_history": current_history,
                    "db_context": db_context,
                },
                config={
                    "run_name": f"UserQuery_{session_id}",
                    "tags": ["production", "hybrid-search"],
                    "metadata": {"session_id": session_id},
                }
            )

            await asyncio.to_thread(history_store.add_user_message, question)
            answer_text = result.get("answer", "")
            await asyncio.to_thread(history_store.add_ai_message, answer_text)

            return {
                "answer": answer_text,
                "standalone_query": result.get("standalone_query", ""),
                "sentiment": result.get("sentiment", "NEUTRAL"),
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }

        except Exception as e:
            print(f"RAG Error: {e}")
            return {
                "answer": f"Error occurred: {e}",
                "standalone_query": "Error",
                "sentiment": "NEUTRAL",
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }
