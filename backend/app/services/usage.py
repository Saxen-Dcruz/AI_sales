import time
from sqlalchemy.orm import Session
from app.models.usage import RAGUsageLog
from app.agents.tools.rag_chain import RAGManager # The class we built

# Initialize the manager as a singleton
rag_engine = RAGManager()

async def execute_rag_flow(db: Session, question: str, session_id: str):
    start_time = time.perf_counter()
    
    # 1. Run the RAG Chain
    # Assuming RAGManager.query_rag_database returns a dict with answer, metadata, etc.
    result = await rag_engine.query_rag_database(question, session_id)
    
    latency = int((time.perf_counter() - start_time) * 1000)
    
    # 2. Extract metrics (In 2026, Gemini provides this in the response)
    # If using LangChain, this usually comes from 'response_metadata'
    in_tokens = result.get("usage", {}).get("input_tokens", 0)
    out_tokens = result.get("usage", {}).get("output_tokens", 0)
    
    # Cost calculation formula:
    # Cost = (In/1M * 2.50) + (Out/1M * 10.00)
    cost = round(((in_tokens / 1_000_000) * 2.50) + ((out_tokens / 1_000_000) * 10.00), 6)

    # 3. Save to Database
    new_log = RAGUsageLog(
        session_id=session_id,
        question=question,
        standalone_query=result.get("standalone_query"),
        sentiment=result.get("sentiment"),
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        total_tokens=in_tokens + out_tokens,
        estimated_cost=cost,
        latency_ms=latency
    )
    
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    
    return {
        "answer": result["answer"],
        "sentiment": result.get("sentiment", "NEUTRAL"),
        "metrics": {
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "total_cost": float(cost),
            "latency_ms": latency
        }
    }