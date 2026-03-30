import asyncio
from functools import partial
from typing import Optional, Tuple
from app.core.config import settings


# LangChain imports
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate 
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable



class RAGManager:
    def __init__(self):
        # Changed type hint to a more general Runnable as the chain can be complex
        self.rag_chain: Optional[Runnable] = None 
        self.memory: Optional[ConversationBufferMemory] = None
        self.vectorstore: Optional[FAISS] = None
        self.rag_initialized = asyncio.Event()
        self._initialization_lock = asyncio.Lock()

    async def initialize_rag(self) -> None:
        """Initialize RAG components asynchronously at startup with optimizations"""
        async with self._initialization_lock:
            if self.rag_initialized.is_set():
                return
                
            print("Pre-loading RAG system...")

            # Use dot-notation from your Pydantic settings!
            index_path = settings.AGENT.rag.vectorstore_path
            embedding_model_name = settings.AGENT.rag.embedding_model
            retrieval_k = settings.AGENT.rag.retrieval_k
            llm_model = settings.AGENT.rag.llm_model
            google_api_key = settings.GOOGLE_API_KEY

            if not index_path:
                raise ValueError("Missing vectorstore_path in configuration")

            try:
                self.vectorstore = await asyncio.wait_for(
                    self._load_vectorstore_async(index_path, embedding_model_name),
                    timeout=60.0
                )

                rag_llm = ChatGoogleGenerativeAI(
                    model=llm_model,
                    google_api_key=google_api_key,
                    temperature=0.1,
                    max_retries=5 
                )
                
                self.rag_chain, self.memory = await asyncio.get_event_loop().run_in_executor(
                    None, self._build_runnable_rag, rag_llm, self.vectorstore, retrieval_k
                )
                
                self.rag_initialized.set()
                print("RAG system pre-loaded and ready!")

            except Exception as e:
                print(f"RAG initialization error: {e}")
                self.rag_initialized.set()

    async def _load_vectorstore_async(self, index_path: str, embedding_model_name: str) -> FAISS:
        """Asynchronously load vectorstore with better error handling"""
        print(f"📚 Loading FAISS vector store from: {index_path}")
        
        # Loading the embedding model (which might download weights)
        embedding_model = await asyncio.get_event_loop().run_in_executor(
            None,
            partial(HuggingFaceEmbeddings, model_name=embedding_model_name)
        )
        
        # Load vectorstore
        vectorstore = await asyncio.get_event_loop().run_in_executor(
            None,
            partial(
                FAISS.load_local,
                index_path,
                embeddings=embedding_model,
                allow_dangerous_deserialization=True
            )
        )
        
        print("✅ Vector store loaded.")
        return vectorstore

    def _build_runnable_rag(self, llm: ChatGoogleGenerativeAI, vs: FAISS, k: int = 3) -> Tuple[Runnable, ConversationBufferMemory]:
        retriever = vs.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k, "fetch_k": min(20, k * 3)}
        )

        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=False, # Set to False so it returns a clean string for the prompt
            output_key="answer",
            input_key="question" # Explicitly tell memory what the input is
        )

        try:
            from prompts import RDL_PROMPT 
        except ImportError:
            # Added chat_history to fallback prompt
            RDL_PROMPT = ChatPromptTemplate.from_template("History: {chat_history}\nContext: {context}\n\nQuestion: {question}\n\nAnswer:")

        # Helper to extract memory inside LCEL
        def load_memory(input_dict):
            return memory.load_memory_variables({})["chat_history"]

        rag_chain = (
            RunnableParallel({
                # Input is now a dict, so we extract the "question" key
                "context": (lambda x: x["question"]) | retriever | (lambda docs: "\n\n".join([doc.page_content for doc in docs])),
                "question": lambda x: x["question"],
                "chat_history": load_memory # Inject memory here!
            })
            | RDL_PROMPT 
            | llm        
            | StrOutputParser() 
        )
        
        return rag_chain, memory

    async def query_rag_database(self, question: str) -> str:
        """
        OPTIMIZED RAG query: Uses rag_chain.ainvoke() for native asynchronous execution,
        eliminating the synchronous thread-pool bottleneck.
        """
        try:
            
            await asyncio.wait_for(self.rag_initialized.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            return "RAG system is still initializing. Please try again in a moment."

        if self.rag_chain is None or self.memory is None:
            return "I apologize, but the knowledge base is currently unavailable."

        if not question or len(question.strip()) < 2:
            return "Please provide a more specific question."

        try:
            # OPTIMIZATION: Direct asynchronous invocation. 
            # Timeout increased to 15.0s based on previous log analysis.
            final_answer = await asyncio.wait_for(
                self.rag_chain.ainvoke({"question": question}), # Asynchronous call is correctly used
                timeout=15.0 
            )
            
            
            if final_answer and len(final_answer.strip()) > 10:
                await asyncio.get_event_loop().run_in_executor(
                    None, 
                    partial(self.memory.save_context, {"question": question}, {"answer": final_answer})
                )
            
            return final_answer
            
        except asyncio.TimeoutError:
            return "The query is taking longer than expected. Please try a more specific question."
        except Exception as e:
            # Catches LLM API errors, retriever errors, etc.
            print(f" RAG query error: {e}")
            return "I encountered an error while searching the knowledge base. Please try again."

 

    async def get_conversation_history(self) -> list:
        """Get current conversation history"""
        if self.memory:
            # Memory access is fast and safe to call directly
            return self.memory.chat_memory.messages
        return []

    async def clear_memory(self) -> None:
        """Clear conversation memory"""
        if self.memory:
            # Memory clear is fast and safe to call directly
            self.memory.clear()

    def is_ready(self) -> bool:
        """Check if RAG system is ready"""
        return self.rag_initialized.is_set() and self.rag_chain is not None