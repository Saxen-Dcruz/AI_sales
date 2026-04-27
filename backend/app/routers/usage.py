from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.api.dependencies import get_current_user
from app.database.core import get_db
from app.models.usage import RAGUsageLog
from app.models.user import User
from app.schema.usage import (
    RAGQueryRequest, RAGQueryResponse, UsageLogOut,
    AnalyticsSummary, AnalyticsLogsResponse,
    GapAnalyticsSummary, GapTopicCount, GapProductCount, FrequentQuestion,
    ProductSentimentResponse, ProductSentimentOut,
)
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


@router.get("/analytics/gaps", response_model=GapAnalyticsSummary)
def get_gap_analytics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Aggregate RAG gap data from emails and calls.
    Shows which products/topics have the most unanswered questions
    and the gap resolution rate — tells you what to add to the knowledge base first.
    """
    # Pull all gap items from emails and calls
    rows = db.execute(text("""
        SELECT gap->>'question'     AS question,
               gap->>'topic'        AS topic,
               gap->>'product_name' AS product_name,
               (gap->>'resolved')::boolean AS resolved
        FROM (
            SELECT jsonb_array_elements(followup_gaps::jsonb) AS gap
            FROM   emails WHERE followup_gaps IS NOT NULL
            UNION ALL
            SELECT jsonb_array_elements(followup_gaps::jsonb) AS gap
            FROM   calls  WHERE followup_gaps IS NOT NULL
        ) sub
    """)).fetchall()

    if not rows:
        return GapAnalyticsSummary(
            total_gaps=0, resolved_gaps=0, unresolved_gaps=0, resolution_rate=0.0,
            by_topic=[], by_product=[], top_unanswered_questions=[],
        )

    total = len(rows)
    resolved = sum(1 for r in rows if r.resolved)
    rate = round(resolved / total * 100, 1) if total else 0.0

    # by topic
    from collections import Counter, defaultdict
    topic_counts: Counter = Counter(r.topic or "general" for r in rows)
    by_topic = [GapTopicCount(topic=t, count=c) for t, c in topic_counts.most_common()]

    # by product
    product_data: dict = defaultdict(lambda: {"total": 0, "resolved": 0})
    for r in rows:
        pn = r.product_name or "Unknown"
        product_data[pn]["total"] += 1
        if r.resolved:
            product_data[pn]["resolved"] += 1
    by_product = [
        GapProductCount(
            product_name=pn,
            total_gaps=v["total"],
            resolved_gaps=v["resolved"],
            resolution_rate=round(v["resolved"] / v["total"] * 100, 1),
        )
        for pn, v in sorted(product_data.items(), key=lambda x: -x[1]["total"])
    ]

    # top unanswered questions
    unresolved = [r for r in rows if not r.resolved]
    q_counts: Counter = Counter((r.question or "")[:150] for r in unresolved)
    top_qs = [
        FrequentQuestion(
            question=q,
            count=c,
            topic=next((r.topic or "general" for r in unresolved if (r.question or "")[:150] == q), "general"),
            product_name=next((r.product_name for r in unresolved if (r.question or "")[:150] == q), None),
        )
        for q, c in q_counts.most_common(10)
        if q
    ]

    return GapAnalyticsSummary(
        total_gaps=total,
        resolved_gaps=resolved,
        unresolved_gaps=total - resolved,
        resolution_rate=rate,
        by_topic=by_topic,
        by_product=by_product,
        top_unanswered_questions=top_qs,
    )


@router.get("/analytics/product-sentiment", response_model=ProductSentimentResponse)
def get_product_sentiment(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Aggregate sentiment mentions per product from emails and calls.
    Shows which products have high positive/frustrated sentiment.
    """
    rows = db.execute(text("""
        SELECT product_name, sentiment, COUNT(*) AS cnt
        FROM (
            SELECT detected_product_name AS product_name, sentiment FROM calls
            WHERE detected_product_name IS NOT NULL AND sentiment IS NOT NULL
            UNION ALL
            SELECT p.name AS product_name, 'NEUTRAL' AS sentiment
            FROM emails e
            JOIN products p ON p.id = (
                SELECT f->>'product_id' FROM (
                    SELECT jsonb_array_elements(e2.followup_gaps::jsonb) AS f
                    FROM emails e2 WHERE e2.id = e.id AND e2.followup_gaps IS NOT NULL
                    LIMIT 1
                ) sub
            )
            WHERE e.label = 'Sales'
        ) combined
        GROUP BY product_name, sentiment
    """)).fetchall()

    from collections import defaultdict
    data: dict = defaultdict(lambda: {"POSITIVE": 0, "NEUTRAL": 0, "FRUSTRATED": 0})
    for r in rows:
        s = (r.sentiment or "NEUTRAL").upper()
        if s in data[r.product_name]:
            data[r.product_name][s] += r.cnt

    items = []
    for pn, counts in sorted(data.items(), key=lambda x: -sum(x[1].values())):
        total = sum(counts.values()) or 1
        items.append(ProductSentimentOut(
            product_name=pn,
            total_mentions=total,
            positive_pct=round(counts["POSITIVE"] / total * 100, 1),
            neutral_pct=round(counts["NEUTRAL"] / total * 100, 1),
            frustrated_pct=round(counts["FRUSTRATED"] / total * 100, 1),
        ))

    return ProductSentimentResponse(items=items)
