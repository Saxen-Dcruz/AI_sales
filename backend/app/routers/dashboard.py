"""
Dashboard summary endpoint — aggregates all CRM metrics into a single response
so the frontend Dashboard page can load everything in one request.
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.models.leads import Lead
    from app.models.deal import Deal
    from app.models.call import Call, CallDirection, CallStatus
    from app.models.communication import Email
    from app.models.linkedin import LinkedInOutreach
    from sqlalchemy import func, extract

    now = datetime.now(timezone.utc)

    # ── KPI cards ──────────────────────────────────────────────────────────────
    total_leads     = db.query(Lead).count()
    active_calls    = db.query(Call).filter(Call.status == CallStatus.ACTIVE).count()
    linkedin_leads  = db.query(LinkedInOutreach).count()
    inbound_calls   = db.query(Call).filter(Call.direction == CallDirection.INBOUND).count()
    outbound_calls  = db.query(Call).filter(Call.direction == CallDirection.OUTBOUND).count()
    qualified_leads = db.query(Lead).filter(Lead.classification == "HIGH").count()

    converted = db.query(Lead).filter(Lead.status.ilike("%convert%")).count()
    conversion_rate = round(converted / total_leads * 100, 1) if total_leads else 0.0

    from sqlalchemy import text
    revenue_row = db.execute(
        text("SELECT COALESCE(SUM(deal_value), 0) FROM deals WHERE stage = 'Closed Won'")
    ).fetchone()
    revenue = float(revenue_row[0]) if revenue_row else 0.0

    # ── Monthly breakdown — last 12 months ────────────────────────────────────
    monthly = []
    for i in range(11, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=i * 30)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        month_end = (month_start + timedelta(days=32)).replace(day=1)
        month_label = month_start.strftime("%b")

        leads_count = db.query(Lead).filter(
            Lead.created_at >= month_start,
            Lead.created_at < month_end,
        ).count()

        calls_count = db.query(Call).filter(
            Call.started_at >= month_start,
            Call.started_at < month_end,
        ).count()

        deals_count = db.query(Deal).filter(
            Deal.stage == "Closed Won",
            Deal.closed_at >= month_start,
            Deal.closed_at < month_end,
        ).count() if hasattr(Deal, 'closed_at') else 0

        monthly.append({
            "month":  month_label,
            "leads":  leads_count,
            "calls":  calls_count,
            "deals":  deals_count,
        })

    # ── Recent activity — last 10 events ─────────────────────────────────────
    activity = []

    recent_leads = db.query(Lead).order_by(Lead.created_at.desc()).limit(4).all()
    for l in recent_leads:
        activity.append({
            "type":   "lead",
            "title":  f"New lead: {l.name}",
            "detail": l.classification_reason or l.status,
            "time":   l.created_at.isoformat() if l.created_at else None,
        })

    recent_calls = db.query(Call).filter(
        Call.ai_summary.isnot(None)
    ).order_by(Call.created_at.desc()).limit(3).all()
    for c in recent_calls:
        activity.append({
            "type":   "call",
            "title":  f"Call completed — {c.detected_product_name or 'product inquiry'}",
            "detail": (c.ai_summary or "")[:100],
            "time":   (c.ended_at or c.created_at).isoformat() if (c.ended_at or c.created_at) else None,
        })

    recent_emails = db.query(Email).filter(
        Email.direction == "inbound"
    ).order_by(Email.received_at.desc()).limit(3).all()
    for e in recent_emails:
        activity.append({
            "type":   "email",
            "title":  f"Email: {e.subject or '(no subject)'}",
            "detail": f"{e.label.value if e.label else ''} — {e.status.value if e.status else ''}",
            "time":   e.received_at.isoformat() if e.received_at else None,
        })

    activity.sort(key=lambda x: x["time"] or "", reverse=True)
    activity = activity[:10]

    return {
        "cards": {
            "total_leads":      total_leads,
            "active_calls":     active_calls,
            "linkedin_leads":   linkedin_leads,
            "inbound_calls":    inbound_calls,
            "outbound_calls":   outbound_calls,
            "conversion_rate":  conversion_rate,
            "qualified_leads":  qualified_leads,
            "revenue":          revenue,
        },
        "monthly":          monthly,
        "recent_activity":  activity,
    }
