from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.api.dependencies import get_current_user
from app.database.core import get_db
from app.models.user import User
from app.schema.leads import (
    LeadClassificationSummary,
    LeadCreate,
    LeadListResponse,
    LeadOut,
    LeadScoreBreakdown,
    LeadScoreSignals,
    LeadUpdate,
)
from app.services import leads_service

router = APIRouter(prefix="/leads", tags=["Leads"])


class SentimentPoint(BaseModel):
    date: datetime
    sentiment: str
    source: str     # email | call
    subject: Optional[str] = None


class SentimentTimeline(BaseModel):
    lead_id: UUID
    points: List[SentimentPoint]
    current_sentiment: str


@router.post("/", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return leads_service.create_lead(db, payload)


@router.get("/classification-summary", response_model=LeadClassificationSummary)
def classification_summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Count and average score per tier (HIGH / MEDIUM / LOW / UNCLASSIFIED)."""
    return leads_service.get_classification_summary(db)


@router.get("/", response_model=LeadListResponse)
def list_leads(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    at_risk: Optional[bool] = Query(default=None, description="Leads with score <40 and no activity in 7+ days"),
    classification: Optional[str] = Query(default=None, description="Filter by tier: HIGH, MEDIUM, LOW, UNCLASSIFIED"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = leads_service.list_leads(
        db, page=page, limit=limit, status=status, search=search,
        at_risk=at_risk, classification=classification,
    )
    return LeadListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/{lead_id}/score-breakdown", response_model=LeadScoreBreakdown)
def score_breakdown(
    lead_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Full scoring signal breakdown for a lead.
    Shows every metric used to compute the classification tier:
    intent, urgency, inbound/outbound contact split, deal stage, meetings,
    sentiment trajectory, gap count, recency, interaction volume.
    """
    from app.services.lead_scoring_service import get_score_breakdown
    data = get_score_breakdown(db, lead_id)
    if not data:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadScoreBreakdown(
        lead_id=data["lead_id"],
        name=data["name"],
        classification=data["classification"],
        engagement_score=data["engagement_score"],
        classification_reason=data["classification_reason"],
        next_best_action=data["next_best_action"],
        signals=LeadScoreSignals(**data["signals"]),
    )


@router.post("/{lead_id}/reclassify", response_model=LeadOut)
def reclassify_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Manually trigger a full score + classification refresh for a lead.
    Useful after manually updating interactions or resolving gaps.
    """
    lead = leads_service.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    from app.services.lead_scoring_service import update_lead_score
    update_lead_score(db, lead_id)
    return leads_service.get_lead(db, lead_id)


@router.get("/{lead_id}/sentiment-timeline", response_model=SentimentTimeline)
def get_sentiment_timeline(
    lead_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Cross-channel sentiment timeline: merges email + call sentiments for a lead."""
    from app.models.communication import Email
    from app.models.call import Call

    lead = leads_service.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    points = []

    # Email sentiments (stored via RAG pipeline on inbound emails)
    emails = (
        db.query(Email)
        .filter(Email.lead_id == lead_id, Email.classifier_confidence.isnot(None))
        .order_by(Email.received_at)
        .all()
    )
    for e in emails:
        # Extract sentiment from followup_gaps or use overall_sentiment proxy
        sentiment = "NEUTRAL"
        if e.followup_gaps:
            # Emails with gaps tend to be NEUTRAL (missing info)
            sentiment = "NEUTRAL"
        if e.classifier_confidence == "high" and e.label and e.label.value == "Sales":
            sentiment = "POSITIVE"
        if e.needs_human and e.label and e.label.value in ("Support", "Grievance"):
            sentiment = "FRUSTRATED"
        points.append(SentimentPoint(
            date=e.received_at,
            sentiment=sentiment,
            source="email",
            subject=e.subject,
        ))

    # Call sentiments (from transcript analysis)
    calls = (
        db.query(Call)
        .filter(Call.lead_id == lead_id, Call.sentiment.isnot(None))
        .order_by(Call.started_at)
        .all()
    )
    for c in calls:
        points.append(SentimentPoint(
            date=c.started_at or c.created_at,
            sentiment=c.sentiment or "NEUTRAL",
            source="call",
            subject=f"Call ({c.direction.value}, {c.duration_seconds}s)",
        ))

    points.sort(key=lambda p: p.date)
    current = points[-1].sentiment if points else (lead.overall_sentiment or "NEUTRAL")

    return SentimentTimeline(lead_id=lead_id, points=points, current_sentiment=current)


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    lead = leads_service.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    lead = leads_service.update_lead(db, lead_id, payload)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not leads_service.delete_lead(db, lead_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
