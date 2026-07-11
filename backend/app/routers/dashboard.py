"""
Dashboard endpoints — aggregated CRM + Voice + Omnichannel intelligence.

GET /dashboard/summary          — top-level KPI cards, monthly trend, activity feed
GET /dashboard/call-intelligence — deep call + voice analytics panel
"""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ── shared scope helpers ──────────────────────────────────────────────────────

def _scoped(db, Model, owner_filter, owner_col="owner_id"):
    q = db.query(Model)
    if owner_filter:
        q = q.filter(getattr(Model, owner_col) == owner_filter)
    return q


def _week_key(dt: datetime) -> str:
    """YYYY-WNN string for grouping by ISO week."""
    return dt.strftime("%Y-W%W") if dt else "unknown"


# ── GET /dashboard/summary ────────────────────────────────────────────────────

@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Single-request dashboard snapshot. Returns:
    - cards:          KPI strip (leads, calls, voice, deals, revenue, CSAT, gaps)
    - voice_now:      Real-time voice metrics (active sessions, channel breakdown)
    - omnichannel:    Message volume by channel (email / WhatsApp / voice / phone)
    - monthly:        Last 12 months — leads / calls / voice sessions / deals
    - intent_summary: Call intent breakdown across all completed calls
    - recent_activity: Last 10 events (leads, calls, voice calls, emails, escalations)
    """
    from app.models.leads import Lead
    from app.models.deal import Deal
    from app.models.call import Call, CallDirection, CallStatus
    from app.models.communication import Email
    from app.models.linkedin import LinkedInOutreach
    from app.models.email_account import EmailAccount
    from app.models.voice_session import VoiceSession, VoiceSessionStatus, VoiceCallFeedback
    from app.models.whatsapp_message import WhatsAppMessage

    now = datetime.now(timezone.utc)
    owner_filter = None if current_user.is_superuser else current_user.id

    def _lead_q():
        return _scoped(db, Lead, owner_filter)

    def _call_q():
        return _scoped(db, Call, owner_filter)

    def _deal_q():
        return _scoped(db, Deal, owner_filter)

    def _voice_q():
        return _scoped(db, VoiceSession, owner_filter)

    def _email_q():
        q = db.query(Email)
        if owner_filter:
            _accts = [a.id for a in db.query(EmailAccount.id)
                      .filter(EmailAccount.owner_id == owner_filter).all()]
            q = q.filter(Email.account_id.in_(_accts))
        return q

    def _wa_q():
        return _scoped(db, WhatsAppMessage, owner_filter)

    # ── KPI cards ──────────────────────────────────────────────────────────────
    total_leads     = _lead_q().count()
    qualified_leads = _lead_q().filter(Lead.classification == "HIGH").count()
    converted       = _lead_q().filter(Lead.status.ilike("%convert%")).count()
    conversion_rate = round(converted / total_leads * 100, 1) if total_leads else 0.0

    revenue = float(
        db.query(func.coalesce(func.sum(Deal.deal_value), 0))
        .filter(Deal.stage == "Closed Won",
                *([Deal.owner_id == owner_filter] if owner_filter else []))
        .scalar() or 0
    )

    total_calls     = _call_q().count()
    inbound_calls   = _call_q().filter(Call.direction == CallDirection.INBOUND).count()
    active_phone    = _call_q().filter(Call.status == CallStatus.ACTIVE,
                                       Call.voice_session_id.is_(None)).count()

    # Voice Bridge KPIs
    active_voice    = _voice_q().filter(VoiceSession.status == VoiceSessionStatus.ACTIVE).count()
    completed_voice = _voice_q().filter(VoiceSession.status == VoiceSessionStatus.COMPLETED).count()
    escalated_voice = _voice_q().filter(
        VoiceSession.escalation_type.in_(["gmeet", "office_call"])
    ).count()
    escalation_rate = round(escalated_voice / completed_voice * 100, 1) if completed_voice else 0.0

    # CSAT from voice feedback
    fb_rows    = db.query(VoiceCallFeedback)
    if owner_filter:
        fb_rows = fb_rows.join(VoiceSession, VoiceCallFeedback.session_id == VoiceSession.id)\
                         .filter(VoiceSession.owner_id == owner_filter)
    fb_ratings = [r.rating for r in fb_rows.all()]
    csat       = round(sum(fb_ratings) / len(fb_ratings), 2) if fb_ratings else None

    # Open knowledge gaps (email + call combined)
    email_gaps = sum(
        len([g for g in (e.followup_gaps or []) if not (g.get("resolved") if isinstance(g, dict) else False)])
        for e in _email_q().filter(Email.followup_gaps.isnot(None)).all()
    )
    call_gaps  = sum(
        len([g for g in (c.followup_gaps or []) if not (g.get("resolved") if isinstance(g, dict) else False)])
        for c in _call_q().filter(Call.followup_gaps.isnot(None)).all()
    )
    open_gaps  = email_gaps + call_gaps

    # Ready-to-buy signals from calls (voice + phone)
    ready_to_buy = _call_q().filter(Call.intent == "ready_to_buy").count()

    # ── Real-time voice ────────────────────────────────────────────────────────
    voice_by_channel = defaultdict(int)
    for s in _voice_q().filter(VoiceSession.status == VoiceSessionStatus.ACTIVE).all():
        voice_by_channel[s.channel_origin] += 1

    voice_now = {
        "active_sessions": active_voice,
        "by_channel":      dict(voice_by_channel),
        "completed_today": _voice_q().filter(
            VoiceSession.status == VoiceSessionStatus.COMPLETED,
            VoiceSession.ended_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
        ).count(),
        "escalation_rate": escalation_rate,
        "csat":            csat,
    }

    # ── Omnichannel volume (last 30 days) ─────────────────────────────────────
    thirty_ago = now - timedelta(days=30)
    omnichannel = {
        "email":     _email_q().filter(Email.received_at >= thirty_ago).count(),
        "whatsapp":  _wa_q().filter(WhatsAppMessage.created_at >= thirty_ago).count(),
        "voice":     _voice_q().filter(VoiceSession.created_at >= thirty_ago).count(),
        "phone":     _call_q().filter(
            Call.created_at >= thirty_ago,
            Call.voice_session_id.is_(None),
        ).count(),
    }

    # ── Monthly trend — last 12 months ────────────────────────────────────────
    monthly = []
    for i in range(11, -1, -1):
        ms = (now.replace(day=1) - timedelta(days=i * 30)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        me = (ms + timedelta(days=32)).replace(day=1)
        label = ms.strftime("%b")

        monthly.append({
            "month":  label,
            "leads":  _lead_q().filter(Lead.created_at >= ms, Lead.created_at < me).count(),
            "calls":  _call_q().filter(Call.started_at >= ms, Call.started_at < me).count(),
            "voice":  _voice_q().filter(VoiceSession.created_at >= ms, VoiceSession.created_at < me).count(),
            "deals":  _deal_q().filter(
                Deal.stage == "Closed Won",
                Deal.closed_at >= ms,
                Deal.closed_at < me,
            ).count() if hasattr(Deal, "closed_at") else 0,
        })

    # ── Intent summary (all calls with transcript) ─────────────────────────────
    intent_rows = _call_q().filter(Call.intent.isnot(None)).all()
    intent_counts: dict = defaultdict(int)
    for c in intent_rows:
        intent_counts[c.intent] += 1
    intent_summary = dict(intent_counts)

    # ── Recent activity — last 10 events ─────────────────────────────────────
    activity = []

    for l in _lead_q().order_by(Lead.created_at.desc()).limit(3).all():
        activity.append({
            "type":    "lead",
            "title":   f"New lead: {l.name}",
            "detail":  l.classification_reason or l.status,
            "channel": "crm",
            "time":    l.created_at.isoformat() if l.created_at else None,
        })

    # Voice sessions — COMPLETED with feedback or escalation
    for s in _voice_q().filter(
        VoiceSession.status.in_([VoiceSessionStatus.COMPLETED, VoiceSessionStatus.ESCALATED])
    ).order_by(VoiceSession.ended_at.desc()).limit(3).all():
        tag = ""
        if s.escalation_type != "none":
            tag = f" → escalated to {s.escalation_type}"
        activity.append({
            "type":    "voice",
            "title":   f"Voice call via {s.channel_origin}{tag}",
            "detail":  f"{s.duration_seconds or 0}s · {s.unanswered_count} gap(s)",
            "channel": s.channel_origin,
            "time":    s.ended_at.isoformat() if s.ended_at else None,
        })

    # Regular calls with AI summary
    for c in _call_q().filter(
        Call.ai_summary.isnot(None),
        Call.voice_session_id.is_(None),
    ).order_by(Call.created_at.desc()).limit(2).all():
        activity.append({
            "type":    "call",
            "title":   f"Call · {c.detected_product_name or 'product inquiry'} · {c.intent or 'intent unknown'}",
            "detail":  (c.ai_summary or "")[:100],
            "channel": "phone",
            "time":    (c.ended_at or c.created_at).isoformat() if (c.ended_at or c.created_at) else None,
        })

    # Inbound emails
    for e in _email_q().filter(
        Email.direction == "inbound"
    ).order_by(Email.received_at.desc()).limit(2).all():
        activity.append({
            "type":    "email",
            "title":   f"Email: {e.subject or '(no subject)'}",
            "detail":  f"{e.label.value if e.label else ''} — {e.status.value if e.status else ''}",
            "channel": "email",
            "time":    e.received_at.isoformat() if e.received_at else None,
        })

    activity.sort(key=lambda x: x["time"] or "", reverse=True)

    return {
        "cards": {
            # CRM
            "total_leads":      total_leads,
            "qualified_leads":  qualified_leads,
            "conversion_rate":  conversion_rate,
            "revenue":          revenue,
            # Calls
            "total_calls":      total_calls,
            "inbound_calls":    inbound_calls,
            "active_phone":     active_phone,
            "ready_to_buy":     ready_to_buy,
            # Voice Bridge
            "active_voice":     active_voice,
            "escalation_rate":  escalation_rate,
            "csat":             csat,
            # Knowledge
            "open_gaps":        open_gaps,
        },
        "voice_now":       voice_now,
        "omnichannel":     omnichannel,
        "monthly":         monthly,
        "intent_summary":  intent_summary,
        "recent_activity": activity[:10],
    }


# ── GET /dashboard/call-intelligence ─────────────────────────────────────────

@router.get("/call-intelligence")
def call_intelligence(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
):
    """
    Deep call + voice intelligence panel. All data is RBAC-scoped.

    Returns:
    - call_funnel:         total → transcribed → intent known → ready_to_buy → closed_deal
    - voice_vs_phone:      volume + intent comparison between Voice Bridge and regular calls
    - intent_by_week:      weekly ready_to_buy / exploring / not_interested counts
    - sentiment_by_week:   weekly POSITIVE / NEUTRAL / FRUSTRATED trend
    - top_products:        products most mentioned in calls + intent rate per product
    - top_gaps:            most common unanswered questions from calls + resolved status
    - channel_conversion:  email/WhatsApp/voice/phone → leads → deals conversion rates
    - escalation_analysis: why / when / how many escalations happened
    - csat_by_week:        avg feedback rating per week
    - voice_quality:       avg duration, avg unanswered questions, escalation rate, CSAT
    - knowledge_coverage:  unresolved vs resolved gap count by topic
    """
    from app.models.call import Call, CallDirection, CallStatus
    from app.models.deal import Deal
    from app.models.leads import Lead
    from app.models.voice_session import VoiceSession, VoiceSessionStatus, VoiceCallFeedback
    from app.models.communication import Email
    from app.models.whatsapp_message import WhatsAppMessage

    now    = datetime.now(timezone.utc)
    since  = now - timedelta(days=days)
    owner_filter = None if current_user.is_superuser else current_user.id

    def _call_q():
        q = db.query(Call).filter(Call.created_at >= since)
        if owner_filter:
            q = q.filter(Call.owner_id == owner_filter)
        return q

    def _voice_q():
        q = db.query(VoiceSession).filter(VoiceSession.created_at >= since)
        if owner_filter:
            q = q.filter(VoiceSession.owner_id == owner_filter)
        return q

    calls  = _call_q().all()
    voices = _voice_q().all()

    voice_ids = {s.id for s in voices}

    # ── Call funnel ─────────────────────────────────────────────────────────
    total_calls       = len(calls)
    with_transcript   = sum(1 for c in calls if c.transcript)
    intent_classified = sum(1 for c in calls if c.intent)
    ready_to_buy      = sum(1 for c in calls if c.intent == "ready_to_buy")

    # Calls linked to a Closed Won deal (via lead_id → deals)
    rtb_lead_ids = {c.lead_id for c in calls if c.intent == "ready_to_buy" and c.lead_id}
    closed_deals  = db.query(Deal).filter(
        Deal.lead_id.in_(rtb_lead_ids),
        Deal.stage == "Closed Won",
        *([Deal.owner_id == owner_filter] if owner_filter else []),
    ).count() if rtb_lead_ids else 0

    call_funnel = {
        "total_calls":       total_calls,
        "with_transcript":   with_transcript,
        "intent_classified": intent_classified,
        "ready_to_buy":      ready_to_buy,
        "closed_deal":       closed_deals,
        "transcript_rate":   round(with_transcript / total_calls * 100, 1) if total_calls else 0,
        "rtb_rate":          round(ready_to_buy / intent_classified * 100, 1) if intent_classified else 0,
        "close_rate":        round(closed_deals / ready_to_buy * 100, 1) if ready_to_buy else 0,
    }

    # ── Voice vs Phone ──────────────────────────────────────────────────────
    voice_calls  = [c for c in calls if c.voice_session_id in voice_ids]
    phone_calls  = [c for c in calls if c.voice_session_id not in voice_ids]

    def _intent_rate(lst, intent_val):
        classified = [c for c in lst if c.intent]
        if not classified:
            return 0.0
        return round(sum(1 for c in classified if c.intent == intent_val) / len(classified) * 100, 1)

    voice_vs_phone = {
        "voice": {
            "count":        len(voice_calls),
            "sessions":     len(voices),
            "rtb_rate":     _intent_rate(voice_calls, "ready_to_buy"),
            "avg_duration": _avg([s.duration_seconds for s in voices if s.duration_seconds]),
            "escalation_rate": round(
                sum(1 for s in voices if s.escalation_type != "none") / len(voices) * 100, 1
            ) if voices else 0.0,
        },
        "phone": {
            "count":        len(phone_calls),
            "rtb_rate":     _intent_rate(phone_calls, "ready_to_buy"),
            "avg_duration": _avg([c.duration_seconds for c in phone_calls if c.duration_seconds]),
        },
    }

    # ── Weekly intent trend ─────────────────────────────────────────────────
    intent_by_week: dict = defaultdict(lambda: defaultdict(int))
    for c in calls:
        if c.intent and c.created_at:
            wk = _week_key(c.created_at.replace(tzinfo=None) if c.created_at.tzinfo else c.created_at)
            intent_by_week[wk][c.intent] += 1
    intent_trend = [
        {"week": wk, **counts}
        for wk, counts in sorted(intent_by_week.items())
    ]

    # ── Weekly sentiment trend ───────────────────────────────────────────────
    sentiment_by_week: dict = defaultdict(lambda: defaultdict(int))
    for c in calls:
        if c.sentiment and c.created_at:
            wk = _week_key(c.created_at.replace(tzinfo=None) if c.created_at.tzinfo else c.created_at)
            sentiment_by_week[wk][c.sentiment] += 1
    sentiment_trend = [
        {"week": wk, **counts}
        for wk, counts in sorted(sentiment_by_week.items())
    ]

    # ── Top products mentioned in calls ────────────────────────────────────
    product_stats: dict = defaultdict(lambda: {"mentions": 0, "ready_to_buy": 0, "intent_classified": 0})
    for c in calls:
        if c.product_interest:
            product_stats[c.product_interest]["mentions"] += 1
            if c.intent:
                product_stats[c.product_interest]["intent_classified"] += 1
            if c.intent == "ready_to_buy":
                product_stats[c.product_interest]["ready_to_buy"] += 1

    top_products = sorted(
        [
            {
                "product":   name,
                "mentions":  s["mentions"],
                "rtb_count": s["ready_to_buy"],
                "rtb_rate":  round(s["ready_to_buy"] / s["intent_classified"] * 100, 1)
                             if s["intent_classified"] else 0.0,
            }
            for name, s in product_stats.items()
        ],
        key=lambda x: x["mentions"],
        reverse=True,
    )[:10]

    # ── Top knowledge gaps from calls ───────────────────────────────────────
    gap_counts: dict = defaultdict(lambda: {"count": 0, "resolved": 0, "topics": set()})
    for c in calls:
        for g in (c.followup_gaps or []):
            if not isinstance(g, dict):
                continue
            q_text = g.get("question", "")[:120]
            if not q_text:
                continue
            gap_counts[q_text]["count"] += 1
            if g.get("resolved"):
                gap_counts[q_text]["resolved"] += 1
            if g.get("topic"):
                gap_counts[q_text]["topics"].add(g["topic"])

    top_gaps = sorted(
        [
            {
                "question":      q,
                "occurrences":   v["count"],
                "resolved":      v["resolved"] > 0,
                "resolution_rate": round(v["resolved"] / v["count"] * 100, 1),
                "topics":        list(v["topics"]),
            }
            for q, v in gap_counts.items()
        ],
        key=lambda x: x["occurrences"],
        reverse=True,
    )[:10]

    # ── Channel → Lead → Deal conversion ────────────────────────────────────
    # Proxy: count leads created within the window by their first-contact channel
    # (email → lead from email_sender, WA → lead from phone, voice → lead from voice session)
    voice_lead_ids = {s.lead_id for s in voices if s.lead_id}
    wa_msgs        = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.created_at >= since,
        *([WhatsAppMessage.owner_id == owner_filter] if owner_filter else []),
    ).all()
    wa_lead_ids    = {m.lead_id for m in wa_msgs if m.lead_id}
    phone_lead_ids = {c.lead_id for c in phone_calls if c.lead_id}

    def _deal_count_for_leads(lead_ids):
        if not lead_ids:
            return 0
        return db.query(Deal).filter(
            Deal.lead_id.in_(lead_ids),
            Deal.stage == "Closed Won",
            *([Deal.owner_id == owner_filter] if owner_filter else []),
        ).count()

    channel_conversion = {
        "voice":     {"leads": len(voice_lead_ids), "closed_deals": _deal_count_for_leads(voice_lead_ids)},
        "whatsapp":  {"leads": len(wa_lead_ids),    "closed_deals": _deal_count_for_leads(wa_lead_ids)},
        "phone":     {"leads": len(phone_lead_ids), "closed_deals": _deal_count_for_leads(phone_lead_ids)},
    }
    for ch in channel_conversion.values():
        leads = ch["leads"]
        ch["conversion_rate"] = round(ch["closed_deals"] / leads * 100, 1) if leads else 0.0

    # ── Escalation analysis ─────────────────────────────────────────────────
    escalated = [s for s in voices if s.escalation_type != "none"]
    by_type: dict = defaultdict(int)
    esc_after: list[int] = []
    for s in escalated:
        by_type[s.escalation_type] += 1
        esc_after.append(s.unanswered_count)

    escalation_analysis = {
        "total":              len(escalated),
        "to_gmeet":           by_type.get("gmeet", 0),
        "to_office_call":     by_type.get("office_call", 0),
        "avg_questions_before_esc": _avg(esc_after),
        "escalation_rate":    round(len(escalated) / len(voices) * 100, 1) if voices else 0.0,
    }

    # ── CSAT by week ────────────────────────────────────────────────────────
    fb_q = db.query(VoiceCallFeedback)
    if owner_filter:
        fb_q = fb_q.join(VoiceSession, VoiceCallFeedback.session_id == VoiceSession.id)\
                   .filter(VoiceSession.owner_id == owner_filter)
    feedbacks = fb_q.all()

    csat_by_week: dict = defaultdict(list)
    for fb in feedbacks:
        if fb.submitted_at:
            wk = _week_key(fb.submitted_at.replace(tzinfo=None) if fb.submitted_at.tzinfo else fb.submitted_at)
            csat_by_week[wk].append(fb.rating)

    csat_trend = [
        {"week": wk, "avg_rating": round(sum(ratings) / len(ratings), 2), "responses": len(ratings)}
        for wk, ratings in sorted(csat_by_week.items())
    ]
    overall_csat = round(sum(fb.rating for fb in feedbacks) / len(feedbacks), 2) if feedbacks else None

    # ── Voice quality summary ────────────────────────────────────────────────
    completed_voices = [s for s in voices if s.status == VoiceSessionStatus.COMPLETED]
    voice_quality = {
        "total_sessions":         len(voices),
        "completed":              len(completed_voices),
        "avg_duration_seconds":   _avg([s.duration_seconds for s in completed_voices if s.duration_seconds]),
        "avg_unanswered":         _avg([s.unanswered_count for s in completed_voices]),
        "escalation_rate":        round(len(escalated) / len(voices) * 100, 1) if voices else 0.0,
        "csat":                   overall_csat,
        "feedback_count":         len(feedbacks),
        "channel_breakdown":      dict(_count_by(voices, "channel_origin")),
    }

    # ── Knowledge coverage by topic ─────────────────────────────────────────
    topic_stats: dict = defaultdict(lambda: {"total": 0, "resolved": 0})
    for c in calls:
        for g in (c.followup_gaps or []):
            if not isinstance(g, dict):
                continue
            topic = g.get("topic", "general")
            topic_stats[topic]["total"] += 1
            if g.get("resolved"):
                topic_stats[topic]["resolved"] += 1

    knowledge_coverage = [
        {
            "topic":           topic,
            "total_gaps":      s["total"],
            "resolved":        s["resolved"],
            "unresolved":      s["total"] - s["resolved"],
            "coverage_pct":    round(s["resolved"] / s["total"] * 100, 1) if s["total"] else 0,
        }
        for topic, s in sorted(topic_stats.items(), key=lambda x: x[1]["total"], reverse=True)
    ]

    return {
        "period_days":         days,
        "call_funnel":         call_funnel,
        "voice_vs_phone":      voice_vs_phone,
        "intent_trend":        intent_trend,
        "sentiment_trend":     sentiment_trend,
        "top_products":        top_products,
        "top_gaps":            top_gaps,
        "channel_conversion":  channel_conversion,
        "escalation_analysis": escalation_analysis,
        "csat_trend":          csat_trend,
        "voice_quality":       voice_quality,
        "knowledge_coverage":  knowledge_coverage,
    }


# ── utilities ─────────────────────────────────────────────────────────────────

def _avg(values: list) -> Optional[float]:
    clean = [v for v in values if v is not None]
    return round(sum(clean) / len(clean), 1) if clean else None


def _count_by(items: list, attr: str) -> dict:
    counts: dict = defaultdict(int)
    for item in items:
        counts[getattr(item, attr, "unknown")] += 1
    return counts
