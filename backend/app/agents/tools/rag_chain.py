import asyncio
from typing import Optional, List
from sqlalchemy.ext.asyncio import create_async_engine

# LangChain / AI Imports
from langchain_postgres import PGVector
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, Runnable
from langchain_core.output_parsers import StrOutputParser
from langchain_postgres import PostgresChatMessageHistory
from langchain_core.messages import trim_messages
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_community.document_compressors.flashrank_rerank import FlashrankRerank
from flashrank import Ranker # Required for the Ranker type hint

# Project Imports
from app.agents.prompts.prompts import RDL_PROMPT 
from app.core.config import settings
from app.database.core import engine
from sqlalchemy.ext.asyncio import create_async_engine
import psycopg
class RAGManager:
    def __init__(self):
        self.rag_chain: Optional[Runnable] = None 
        self.vectorstore: Optional[PGVector] = None
        self.rag_initialized = asyncio.Event()
        self._initialization_lock = asyncio.Lock()

    async def initialize_rag(self) -> None:
        async with self._initialization_lock:
            if self.rag_initialized.is_set():
                return
                
            connection_str = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql+psycopg_async://").replace("postgresql://", "postgresql+psycopg_async://")

            async_engine = create_async_engine(connection_str)
            
            try:
                # 1. Base Embeddings (Dense via Google Cloud)
                # 👇 CHANGED: Instant API initialization, no executor needed!
                embeddings = GoogleGenerativeAIEmbeddings(
                    model=settings.AGENT.rag.embedding_model,
                    google_api_key=settings.GOOGLE_API_KEY
                )

                # 2. PGVector Store with Hybrid Support
                # Ensure your PGVector table has an HNSW index for speed
                self.vectorstore = PGVector(
                    embeddings=embeddings,
                    collection_name="product_embeddings",
                    connection=async_engine,
                    use_jsonb=True,
                    create_extension=False  
                )

                # 3. Initialize Re-ranker (Flashrank is fast & CPU-efficient)
                # This takes the top 20 results and picks the best 5 based on context
                # 1. Initialize the base Flashrank client first
                ranker_client = Ranker(model_name="ms-marco-MultiBERT-L-12")

                # 2. Pass the client into LangChain's wrapper (and tell it to keep the top 5 results)
                compressor = FlashrankRerank(client=ranker_client, top_n=5) 

                # 4. The Brain (Gemini)
                rag_llm = ChatGoogleGenerativeAI(
                    model=settings.AGENT.rag.llm_model,
                    google_api_key=settings.GOOGLE_API_KEY,
                    temperature=0.1
                )
                
                # 5. Build the Optimized Chain
                self.rag_chain = self._build_runnable_rag(rag_llm, self.vectorstore, compressor)
                
                self.rag_initialized.set()
                print("🚀 Optimized RAG System (Google Vectors + Re-ranker) Ready!")

            except Exception as e:
                print(f"❌ Initialization failed: {e}")
                raise e

    def _format_docs(self, docs) -> str:
        """Metadata-aware formatter for structured product data."""
        # --- DEBUG: CHECK RE-RANKER OUTPUT ---
        print(f"\n[DEBUG] Re-ranker passed {len(docs)} documents to the LLM.")
        for i, d in enumerate(docs):
            print(f"  Doc {i}: {d.page_content[:150]}...")
        print("--------------------------------------------------\n")
        # -------------------------------------

        return "\n\n".join([
            f"--- [Product: {d.metadata.get('product_name')} | Section: {d.metadata.get('chunk_type')}] ---\n{d.page_content}"
            for d in docs
        ])

    def _get_history_callable(self, session_id: str):
        standard_url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
        
        conn = psycopg.connect(standard_url, autocommit=True)
        
        # The correct method: create_tables
        PostgresChatMessageHistory.create_tables(conn, "chat_history")
        
        return PostgresChatMessageHistory(
            "chat_history", 
            session_id,
            sync_connection=conn
        )

    def _build_runnable_rag(self, llm, vs, compressor):
        # 1. HYBRID RETRIEVER 
        base_retriever = vs.as_retriever(search_kwargs={"k": 20}) 

        # 2. RE-RANKER (Compression)
        rerank_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, 
            base_retriever=base_retriever
        )

        # 3. QUESTION RE-WRITER (Memory Optimization)
        # 👇 FIX 1: Stricter prompt so the LLM knows what to do on the first turn
        rewrite_prompt = ChatPromptTemplate.from_messages([
            ("system", "Rewrite the user's question to be a standalone search query based on chat history. If there is no chat history, simply return the user's exact question and nothing else. Do not add conversational text."),
            MessagesPlaceholder("chat_history"),
            ("human", "{question}"),
        ])
        rewrite_chain = rewrite_prompt | llm | StrOutputParser()

        # 4. SENTIMENT ANALYZER (Parallel Branch)
        sentiment_prompt = ChatPromptTemplate.from_template(
            "Analyze sentiment: POSITIVE, NEUTRAL, or FRUSTRATED. Reply with ONE word.\nMsg: {question}"
        )
        sentiment_chain = sentiment_prompt | llm | StrOutputParser()

        # 5. THE FINAL PIPELINE
        full_chain = (
            RunnablePassthrough.assign(
                standalone_query=rewrite_chain 
            )
            | RunnableParallel({
                # 👇 FIX 2: Fallback logic. If standalone_query is empty, use the original question.
                "context": (lambda x: x["standalone_query"].strip() if x["standalone_query"].strip() else x["question"]) | rerank_retriever | self._format_docs,
                "sentiment": sentiment_chain,
                "question": lambda x: x["question"],
                "chat_history": lambda x: x["chat_history"],
                "standalone_query": lambda x: x["standalone_query"]
            })
            | {
                "answer": RDL_PROMPT | llm | StrOutputParser(),
                "sentiment": lambda x: x["sentiment"],
                "standalone_query": lambda x: x["standalone_query"]
              }
        )
        return full_chain

    async def query_rag_database(self, question: str, session_id: str = "default") -> dict:
        """
        Modified to return the full trace (sentiment, standalone query, etc.)
        for the service layer to log into the database.
        """
        await self.rag_initialized.wait()
        
        # --- DEBUG: CHECK BASE RETRIEVER OUTPUT ---
        print(f"\n[DEBUG] Testing Raw Vector DB for: '{question}'")
        try:
            raw_docs = await self.vectorstore.asimilarity_search(question, k=5)
            print(f"[DEBUG] Base Retriever found {len(raw_docs)} documents.")
            for i, doc in enumerate(raw_docs[:3]): # Print first 3 to avoid clutter
                print(f"  Raw Doc {i}: {doc.page_content[:100]}...")
        except Exception as e:
            print(f"[DEBUG ERROR] Base Retriever failed: {e}")
        print("--------------------------------------------------\n")
        # ------------------------------------------

        history_store = self._get_history_callable(session_id)
        current_history = history_store.messages 

        try:
            # We pass a config dictionary to tag this specific trace in LangSmith
            result = await self.rag_chain.ainvoke(
                {
                    "question": question,
                    "chat_history": current_history
                },
                config={
                    "run_name": f"UserQuery_{session_id}",
                    "tags": ["production", "hybrid-search"],
                    "metadata": {
                        "session_id": session_id
                    }
                }
            )

            # Save the exchange to history
            await asyncio.to_thread(history_store.add_user_message, question)
            
            # Make sure you are saving just the answer string to the DB history, not the whole dict
            answer_text = result.get("answer", "")
            await asyncio.to_thread(history_store.add_ai_message, answer_text)

            return {
                "answer": answer_text, 
                "standalone_query": result.get("standalone_query", ""), 
                "sentiment": result.get("sentiment", "NEUTRAL"), 
                "usage": {
                    "input_tokens": 0,  
                    "output_tokens": 0
                }
            }
        except Exception as e:
            print(f"RAG Error: {e}")
            return {
                "answer": f"Error occurred: {e}", 
                "standalone_query": "Error",
                "sentiment": "NEUTRAL",
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }
        