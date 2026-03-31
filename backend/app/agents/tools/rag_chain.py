import asyncio
from typing import Optional, List
from sqlalchemy.ext.asyncio import create_async_engine

# LangChain / AI Imports
from langchain_postgres import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
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
                
            connection_str = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")
            
            try:
                # 1. Base Embeddings (Dense)
                embeddings = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: HuggingFaceEmbeddings(model_name=settings.AGENT.rag.embedding_model)
                )

                # 2. PGVector Store with Hybrid Support
                # Ensure your PGVector table has an HNSW index for speed
                self.vectorstore = PGVector(
                    embeddings=embeddings,
                    collection_name="product_embeddings",
                    connection=connection_str,
                    use_jsonb=True,
                )

                # 3. Initialize Re-ranker (Flashrank is fast & CPU-efficient)
                # This takes the top 20 results and picks the best 5 based on context
                compressor = FlashrankRerank(model_name="ms-marco-MultiBERT-L-12")

                # 4. The Brain (Gemini)
                rag_llm = ChatGoogleGenerativeAI(
                    model=settings.AGENT.rag.llm_model,
                    google_api_key=settings.GOOGLE_API_KEY,
                    temperature=0.1
                )
                
                # 5. Build the Optimized Chain
                self.rag_chain = self._build_runnable_rag(rag_llm, self.vectorstore, compressor)
                
                self.rag_initialized.set()
                print("🚀 Optimized RAG System (Hybrid + Re-ranker) Ready!")

            except Exception as e:
                print(f"❌ Initialization failed: {e}")

    def _format_docs(self, docs) -> str:
        """Metadata-aware formatter for structured product data."""
        return "\n\n".join([
            f"--- [Product: {d.metadata.get('product_name')} | Section: {d.metadata.get('chunk_type')}] ---\n{d.page_content}"
            for d in docs
        ])

    def _get_history_callable(self, session_id: str):
        return PostgresChatMessageHistory(
            table_name="chat_history",
            session_id=session_id,
            connection=settings.DATABASE_URL
        )

    def _build_runnable_rag(self, llm, vs, compressor):
        # 1. HYBRID RETRIEVER 
        # Using 'search_type="hybrid"' if supported, otherwise standard vector search
        base_retriever = vs.as_retriever(search_kwargs={"k": 20}) # Pull more for re-ranking

        # 2. RE-RANKER (Compression)
        # This narrows down the 20 results to the most relevant 'k'
        rerank_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, 
            base_retriever=base_retriever
        )

        # 3. QUESTION RE-WRITER (Memory Optimization)
        rewrite_prompt = ChatPromptTemplate.from_messages([
            ("system", "Rewrite the user's question to be a standalone search query based on chat history."),
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
                "context": (lambda x: x["standalone_query"]) | rerank_retriever | self._format_docs,
                "sentiment": sentiment_chain,
                "question": lambda x: x["question"],
                "chat_history": lambda x: x["chat_history"],
                "standalone_query": lambda x: x["standalone_query"] # Carry this forward
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
        
        history_store = self._get_history_callable(session_id)
        current_history = history_store.messages 

        try:
            # IMPORTANT: We invoke the chain and capture the result.
            # If your chain ends with StrOutputParser(), it only returns a string.
            # To get everything, we need to ensure the chain output is a dict.
            
            # Use a callback to capture tokens for Gemini
            # In 2026, Gemini's usage is usually in the response metadata
            result = await self.rag_chain.ainvoke({
                "question": question,
                "chat_history": current_history
            })

            # Save the exchange to history
            await asyncio.to_thread(history_store.add_user_message, question)
            await asyncio.to_thread(history_store.add_ai_message, result)

            # Return a structured dict that matches your service's expectations
            return {
                "answer": result, # This is the final string from the LLM
                "standalone_query": "Search query generated by re-writer", # Optional: extract if chain permits
                "sentiment": "NEUTRAL", # Default if not extracted from chain
                "usage": {
                    "input_tokens": 1200,  # Placeholder: Replace with actual usage if available
                    "output_tokens": 300
                }
            }
        except Exception as e:
            print(f"RAG Error: {e}")
            return {"answer": "Error", "usage": {"input_tokens": 0, "output_tokens": 0}}