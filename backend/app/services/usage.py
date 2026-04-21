import json
import time
from typing import AsyncGenerator
from sqlalchemy.orm import Session
from app.models.usage import RAGUsageLog
from app.agents.tools.rag_chain import RAGManager

# Initialize the manager as a singleton
rag_engine = RAGManager()

async def execute_rag_flow(db: Session, question: str, session_id: str, source: str = "web_chat"):
    start_time = time.perf_counter()

    result = await rag_engine.query_rag_database(question, session_id)

    latency = int((time.perf_counter() - start_time) * 1000)
    in_tokens = result.get("usage", {}).get("input_tokens", 0)
    out_tokens = result.get("usage", {}).get("output_tokens", 0)
    # Gemini 2.5 Flash: $0.075/1M input, $0.30/1M output
    cost = round(((in_tokens / 1_000_000) * 0.075) + ((out_tokens / 1_000_000) * 0.30), 6)

    new_log = RAGUsageLog(
        session_id=session_id,
        question=question,
        standalone_query=result.get("standalone_query"),
        sentiment=result.get("sentiment"),
        source=source,
        token_tier=result.get("token_tier"),
        reranker_doc_count=result.get("reranker_doc_count"),
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        total_tokens=in_tokens + out_tokens,
        estimated_cost=cost,
        latency_ms=latency,
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
            "latency_ms": latency,
        },
    }


async def stream_rag_flow(
    db: Session, question: str, session_id: str, source: str = "web_chat"
) -> AsyncGenerator[str, None]:
    """
    Async generator that wraps RAGManager.stream_rag_database and formats SSE events.
    Saves usage log to DB when the stream ends (on the 'done' event).
    Yields SSE-formatted strings: 'data: <json>\\n\\n'
    """
    async for event in rag_engine.stream_rag_database(question, session_id):
        yield f"data: {json.dumps(event)}\n\n"

        if event["type"] == "done":
            latency = event.get("latency_ms", 0)
            in_tokens = event.get("usage", {}).get("input_tokens", 0)
            out_tokens = event.get("usage", {}).get("output_tokens", 0)
            cost = round(((in_tokens / 1_000_000) * 0.075) + ((out_tokens / 1_000_000) * 0.30), 6)
            new_log = RAGUsageLog(
                session_id=session_id,
                question=question,
                standalone_query=event.get("standalone_query", ""),
                sentiment=event.get("sentiment", "NEUTRAL"),
                source=source,
                token_tier=event.get("token_tier"),
                reranker_doc_count=event.get("reranker_doc_count"),
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                total_tokens=in_tokens + out_tokens,
                estimated_cost=cost,
                latency_ms=latency,
            )
            db.add(new_log)
            db.commit()