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
    current_user: User = Depends(get_current_user),
):
    from app.models.leads import Lead
    from app.models.deal import Deal
    from app.models.call import Call, CallDirection, CallStatus
    from app.models.communication import Email
    from app.models.linkedin import LinkedInOutreach
    from app.models.email_account import EmailAccount
    from sqlalchemy import func

    now = datetime.now(timezone.utc)
    owner_filter = None if current_user.is_superuser else current_user.id

    def _lead_q():
        q = db.query(Lead)
        if owner_filter:
            q = q.filter(Lead.owner_id == owner_filter)
        return q

    def _call_q():
        q = db.query(Call)
        if owner_filter:
            q = q.filter(Call.owner_id == owner_filter)
        return q

    def _deal_q():
        q = db.query(Deal)
        if owner_filter:
            q = q.filter(Deal.owner_id == owner_filter)
        return q

    def _email_q():
        q = db.query(Email)
        if owner_filter:
            _accts = [a.id for a in db.query(EmailAccount.id)
                      .filter(EmailAccount.owner_id == owner_filter).all()]
            q = q.filter(Email.account_id.in_(_accts))
        return q

    # ── KPI cards ──────────────────────────────────────────────────────────────
    total_leads     = _lead_q().count()
    active_calls    = _call_q().filter(Call.status == CallStatus.ACTIVE).count()
    linkedin_leads  = db.query(LinkedInOutreach).count()  # no owner_id on this table
    inbound_calls   = _call_q().filter(Call.direction == CallDirection.INBOUND).count()
    outbound_calls  = _call_q().filter(Call.direction == CallDirection.OUTBOUND).count()
    qualified_leads = _lead_q().filter(Lead.classification == "HIGH").count()

    converted = _lead_q().filter(Lead.status.ilike("%convert%")).count()
    conversion_rate = round(converted / total_leads * 100, 1) if total_leads else 0.0

    _rev_filters = [Deal.stage == "Closed Won"]
    if owner_filter:
        _rev_filters.append(Deal.owner_id == owner_filter)
    revenue = float(
        db.query(func.coalesce(func.sum(Deal.deal_value), 0)).filter(*_rev_filters).scalar() or 0
    )

    # ── Monthly breakdown — last 12 months ────────────────────────────────────
    monthly = []
    for i in range(11, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=i * 30)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        month_end = (month_start + timedelta(days=32)).replace(day=1)
        month_label = month_start.strftime("%b")

        leads_count = _lead_q().filter(
            Lead.created_at >= month_start,
            Lead.created_at < month_end,
        ).count()

        calls_count = _call_q().filter(
            Call.started_at >= month_start,
            Call.started_at < month_end,
        ).count()

        deals_count = _deal_q().filter(
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

    recent_leads = _lead_q().order_by(Lead.created_at.desc()).limit(4).all()
    for l in recent_leads:
        activity.append({
            "type":   "lead",
            "title":  f"New lead: {l.name}",
            "detail": l.classification_reason or l.status,
            "time":   l.created_at.isoformat() if l.created_at else None,
        })

    recent_calls = _call_q().filter(
        Call.ai_summary.isnot(None)
    ).order_by(Call.created_at.desc()).limit(3).all()
    for c in recent_calls:
        activity.append({
            "type":   "call",
            "title":  f"Call completed — {c.detected_product_name or 'product inquiry'}",
            "detail": (c.ai_summary or "")[:100],
            "time":   (c.ended_at or c.created_at).isoformat() if (c.ended_at or c.created_at) else None,
        })

    recent_emails = _email_q().filter(
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
