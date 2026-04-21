from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.dependencies import get_current_user
from app.database.core import get_db
from app.models.usage import RAGUsageLog
from app.models.user import User
from app.schema.usage import RAGQueryRequest, RAGQueryResponse, UsageLogOut, AnalyticsSummary, AnalyticsLogsResponse
from app.services.usage import execute_rag_flow, stream_rag_flow

router = APIRouter(prefix="/ai", tags=["RAG"])


@router.post("/query", response_model=RAGQueryResponse)
async def ask_ai(payload: RAGQueryRequest, db: Session = Depends(get_db)):
    try:
        return await execute_rag_flow(
            db=db,
            question=payload.question,
            session_id=payload.session_id,
            source=payload.source,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream")
async def stream_ai(payload: RAGQueryRequest, db: Session = Depends(get_db)):
    """
    SSE streaming endpoint. Returns tokens as they are generated.
      data: {"type": "token", "content": "<token>"}
      data: {"type": "done",  "sentiment": "...", "latency_ms": ...}
      data: {"type": "error", "content": "<message>"}
    """
    return StreamingResponse(
        stream_rag_flow(db=db, question=payload.question, session_id=payload.session_id, source=payload.source),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ─── Analytics (auth required) ────────────────────────────────────────────────

@router.get("/analytics", response_model=AnalyticsSummary)
def get_analytics_summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    total_queries = db.query(func.count(RAGUsageLog.id)).scalar() or 0
    total_cost = float(db.query(func.sum(RAGUsageLog.estimated_cost)).scalar() or 0)
    avg_latency = float(db.query(func.avg(RAGUsageLog.latency_ms)).scalar() or 0)
    total_input_tokens = db.query(func.sum(RAGUsageLog.input_tokens)).scalar() or 0
    total_output_tokens = db.query(func.sum(RAGUsageLog.output_tokens)).scalar() or 0

    by_source = (
        db.query(RAGUsageLog.source, func.count(RAGUsageLog.id).label("count"))
        .group_by(RAGUsageLog.source)
        .all()
    )
    by_tier = (
        db.query(RAGUsageLog.token_tier, func.count(RAGUsageLog.id).label("count"))
        .group_by(RAGUsageLog.token_tier)
        .all()
    )

    return AnalyticsSummary(
        total_queries=total_queries,
        total_cost_usd=round(total_cost, 6),
        avg_latency_ms=round(avg_latency, 1),
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        by_source={row.source or "unknown": row.count for row in by_source},
        by_tier={row.token_tier or "unknown": row.count for row in by_tier},
    )


@router.get("/analytics/logs", response_model=AnalyticsLogsResponse)
def get_analytics_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    source: str = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(RAGUsageLog)
    if source:
        q = q.filter(RAGUsageLog.source == source)
    total = q.count()
    items = q.order_by(RAGUsageLog.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return AnalyticsLogsResponse(items=items, total=total, page=page, limit=limit)
