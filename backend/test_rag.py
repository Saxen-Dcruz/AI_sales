import asyncio
import uuid
# Import your RAGManager (adjust the path if necessary)
from app.agents.tools.rag_chain import RAGManager

async def test_rag_pipeline():
    print("⏳ Initializing Advanced RDL Knowledge Base Pipeline...")
    rag_manager = RAGManager()
    
    # Initialize the pipeline (Embeddings, PGVector, Flashrank, LLM)
    await rag_manager.initialize_rag()
    print("✅ Pipeline Ready!\n")
    print("-" * 50)

    # Generate a unique session ID for this test run to test memory
    test_session_id = str(uuid.uuid4())
    print(f"🧠 Chat Memory Session Active (ID: {test_session_id})")
    print("Try asking a question, then ask a follow-up referencing it (e.g., 'What is it?').")
    print("-" * 50)

    while True:
        try:
            question = input("\n👤 Ask a question (or 'quit'): ")
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("Exiting pipeline test...")
                break
                
            if not question.strip():
                continue

            print("🤖 Processing (Rewriting -> Retrieving -> Re-ranking -> Generating)...")
            
            # Call the updated method signature
            result = await rag_manager.query_rag_database(
                question=question, 
                session_id=test_session_id
            )
            
            print("\n" + "="*50)
            print(f"📊 Sentiment Detected: {result.get('sentiment')}")
            print(f"🔍 Standalone Query:   {result.get('standalone_query').strip()}")
            print("-" * 50)
            print(f"📄 AI Answer:\n{result.get('answer')}")
            print("="*50 + "\n")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\n❌ Error during execution: {e}")

if __name__ == "__main__":
    asyncio.run(test_rag_pipeline())