"""
Lead scoring and classification service.

Score formula (0–100) — compute_score():
  Base:                       20
  Per inbound email:          +5 each, max +20
  Last email Sales label:     +15
  Last email Support/Grievance (open): -20
  Call outcome interested:    +15
  Call outcome converted:     +20
  Call outcome follow_up:     +5
  Call outcome not_interested:-15
  Call outcome no_answer:     -5
  Call sentiment POSITIVE:    +10
  Call sentiment FRUSTRATED:  -15
  Deal exists + stage > New:  +15
  Inactivity > 7 days:        -10

Classification — classify_lead():
  Tier boundaries after all signal boosts/penalties are applied:
  HIGH         ≥ 70
  MEDIUM       40–69
  LOW          < 40
  UNCLASSIFIED — no emails and no calls recorded

  Key signal overrides:
  intent=ready_to_buy      → score ≥ 75
  intent=not_interested    → score ≤ 35 (caps down)
  urgency=immediate        → score ≥ 70
  urgency=1-3_months       → score ≥ 50
  inbound first contact    → +10
  deal Proposal/Negotiation→ score ≥ 65
  deal Closed Won          → score = 100
  meetings scheduled       → score ≥ 55
  recent FRUSTRATED calls  → −10
  consistently POSITIVE    → +5
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger("rdl_app_logger")


def compute_score(db: Session, lead_id: UUID) -> int:
    from app.models.leads import Lead
    from app.models.communication import Email
    from app.models.call import Call
    from app.models.deal import Deal

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return 20

    score = 20

    # Email signals
    emails = (
        db.query(Email)
        .filter(Email.lead_id == lead_id, Email.direction == "inbound")
        .order_by(Email.received_at.desc())
        .all()
    )
    score += min(len(emails) * 5, 20)

    if emails:
        last_email = emails[0]
        if last_email.label and last_email.label.value == "Sales":
            score += 15
        if last_email.label and last_email.label.value in ("Support", "Grievance") and last_email.needs_human:
            score -= 20

    # Call signals
    calls = (
        db.query(Call)
        .filter(Call.lead_id == lead_id)
        .order_by(Call.created_at.desc())
        .all()
    )
    if calls:
        last_call = calls[0]
        if last_call.outcome:
            outcome_map = {
                "interested": +15, "converted": +20, "follow_up": +5,
                "not_interested": -15, "no_answer": -5,
            }
            score += outcome_map.get(last_call.outcome.value, 0)
        if last_call.sentiment:
            sentiment_map = {"POSITIVE": +10, "FRUSTRATED": -15, "NEUTRAL": 0}
            score += sentiment_map.get(last_call.sentiment.upper(), 0)

    # Deal signal
    deal = db.query(Deal).filter(Deal.lead_id == lead_id).order_by(Deal.created_at.desc()).first()
    if deal and deal.stage not in ("New", "Closed Lost"):
        score += 15

    # Inactivity penalty
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    last_contact = lead.last_contacted_at
    if not last_contact or (
        last_contact.replace(tzinfo=timezone.utc) if last_contact.tzinfo is None else last_contact
    ) < cutoff:
        score -= 10

    return max(0, min(100, score))


def classify_lead(db: Session, lead_id: UUID) -> Tuple[str, str, str]:
    """
    Classify a lead into HIGH / MEDIUM / LOW / UNCLASSIFIED.
    Returns (classification, reason, next_best_action).
    """
    from app.models.leads import Lead
    from app.models.communication import Email
    from app.models.call import Call, CallDirection
    from app.models.deal import Deal
    from app.models.calendar_event import CalendarEvent, EventStatus

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return "UNCLASSIFIED", "Lead not found", ""

    score = lead.engagement_score or 20
    reasons = []

    # All interactions
    emails = db.query(Email).filter(Email.lead_id == lead_id).all()
    calls = (
        db.query(Call)
        .filter(Call.lead_id == lead_id)
        .order_by(Call.created_at.desc())
        .all()
    )
    deal = (
        db.query(Deal)
        .filter(Deal.lead_id == lead_id)
        .order_by(Deal.created_at.desc())
        .first()
    )
    meetings = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.lead_id == lead_id,
            CalendarEvent.status == EventStatus.SCHEDULED,
        )
        .all()
    )

    # ── No interactions at all → UNCLASSIFIED ─────────────────────────────────
    if not emails and not calls:
        nba = "Make first contact — email or call to qualify"
        return "UNCLASSIFIED", "No interactions recorded yet", nba

    # ── Signal 1: Explicit call intent (strongest) ─────────────────────────────
    all_intents = [c.intent for c in calls if c.intent]
    if "ready_to_buy" in all_intents:
        score = max(score, 75)
        reasons.append("Expressed clear intent to buy on a call")
    elif "not_interested" in all_intents and "ready_to_buy" not in all_intents:
        score = min(score, 35)
        reasons.append("Expressed no interest on a call")

    # ── Signal 2: Urgency ─────────────────────────────────────────────────────
    all_urgencies = [c.urgency for c in calls if c.urgency]
    if "immediate" in all_urgencies:
        score = max(score, 70)
        reasons.append("Immediate purchase urgency stated")
    elif "1-3_months" in all_urgencies:
        score = max(score, 50)
        reasons.append("Near-term urgency (1-3 months)")
    elif "6+_months" in all_urgencies and not any(u in all_urgencies for u in ("immediate", "1-3_months")):
        score = min(score, 50)
        reasons.append("Long-horizon urgency (6+ months)")

    # ── Signal 3: Inbound vs outbound first contact ────────────────────────────
    inbound_emails = [e for e in emails if e.direction == "inbound"]
    inbound_calls  = [c for c in calls  if c.direction == CallDirection.INBOUND]
    is_inbound = bool(inbound_emails or inbound_calls)
    if is_inbound:
        score = min(score + 10, 100)
        reasons.append("They initiated contact (inbound) — higher intent signal")
    else:
        reasons.append("Outbound contact only — awaiting customer response")

    # ── Signal 4: Deal stage and win probability ───────────────────────────────
    if deal:
        if deal.stage == "Closed Won":
            score = 100
            reasons.append("Converted — deal closed won")
        elif deal.stage in ("Proposal", "Negotiation"):
            score = max(score, 65)
            reasons.append(f"Active deal in {deal.stage} stage")
        elif deal.stage not in ("New", "Closed Lost") and deal.stage:
            score = max(score, 45)
            reasons.append(f"Deal exists at {deal.stage} stage")
        if deal.win_probability and float(deal.win_probability) >= 60:
            score = max(score, 60)
            reasons.append(f"High win probability ({deal.win_probability}%)")

    # ── Signal 5: Meetings scheduled (commitment indicator) ────────────────────
    if meetings:
        score = max(score, 55)
        reasons.append(f"{len(meetings)} meeting(s) scheduled")

    # ── Signal 6: Sentiment trajectory from recent calls ──────────────────────
    recent_sentiments = [c.sentiment for c in calls[:3] if c.sentiment]
    if recent_sentiments:
        if "FRUSTRATED" in recent_sentiments:
            score = max(0, score - 10)
            reasons.append("Frustration detected in recent call(s)")
        elif all(s == "POSITIVE" for s in recent_sentiments):
            score = min(score + 5, 100)
            reasons.append("Consistently positive sentiment across recent calls")

    # ── Signal 7: Interaction recency ─────────────────────────────────────────
    all_times = []
    for e in emails:
        if e.received_at:
            t = e.received_at
            all_times.append(t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t)
    for c in calls:
        if c.started_at:
            t = c.started_at
            all_times.append(t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t)

    days_since = None
    if all_times:
        last_act = max(all_times)
        days_since = (datetime.now(timezone.utc) - last_act).days
        if days_since <= 3:
            score = min(score + 5, 100)
            reasons.append("Very recent activity (within 3 days)")
        elif days_since > 21:
            score = max(0, score - 5)
            reasons.append(f"Dormant — no activity for {days_since} days")

    # ── Signal 8: Engagement volume ────────────────────────────────────────────
    total_interactions = len(emails) + len(calls)
    if total_interactions >= 5:
        score = min(score + 5, 100)
        reasons.append(f"High engagement volume ({total_interactions} total interactions)")

    # ── Signal 9: RAG gaps (customer had unanswered questions) ─────────────────
    gap_calls   = [c for c in calls  if c.followup_gaps and any(not g.get("resolved") for g in c.followup_gaps)]
    gap_emails  = [e for e in emails if e.followup_gaps and any(
        not (g.get("resolved") if isinstance(g, dict) else False) for g in e.followup_gaps
    )]
    if gap_calls or gap_emails:
        reasons.append("Has unanswered product questions — review gaps before next contact")

    # ── Finalise ──────────────────────────────────────────────────────────────
    score = max(0, min(100, score))

    if score >= 70:
        classification = "HIGH"
        if deal and deal.stage in ("Proposal", "Negotiation"):
            nba = "Follow up on proposal — push for close this week"
        elif "ready_to_buy" in all_intents:
            nba = "Send formal proposal immediately"
        elif meetings:
            nba = "Prepare demo and agenda for scheduled meeting"
        else:
            nba = "Schedule a product demo or closing call"

    elif score >= 40:
        classification = "MEDIUM"
        if gap_calls or gap_emails:
            nba = "Resolve unanswered gaps — then send tailored follow-up"
        elif meetings:
            nba = "Confirm meeting attendance and send pre-meeting brief"
        elif is_inbound:
            nba = "Send detailed product info and pricing; propose a call"
        else:
            nba = "Re-engage with product brochure and a clear next step"

    else:
        classification = "LOW"
        if "FRUSTRATED" in recent_sentiments:
            nba = "Escalate to senior rep — address frustration before any sales pitch"
        elif "not_interested" in all_intents:
            nba = "Pause outreach — re-engage in 30 days with a different offering"
        elif days_since and days_since > 30:
            nba = "Long inactive — try a different channel (LinkedIn / WhatsApp)"
        else:
            nba = "Low engagement — nurture with educational content before pitching"

    reason_str = "; ".join(reasons) if reasons else "Based on engagement score only"
    return classification, reason_str, nba


def get_score_breakdown(db: Session, lead_id: UUID) -> Optional[dict]:
    """Return all raw scoring signals for a lead — used by the dashboard score-breakdown endpoint."""
    from app.models.leads import Lead
    from app.models.communication import Email
    from app.models.call import Call, CallDirection
    from app.models.deal import Deal
    from app.models.calendar_event import CalendarEvent, EventStatus

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return None

    emails  = db.query(Email).filter(Email.lead_id == lead_id).all()
    calls   = db.query(Call).filter(Call.lead_id == lead_id).order_by(Call.created_at.desc()).all()
    deal    = db.query(Deal).filter(Deal.lead_id == lead_id).order_by(Deal.created_at.desc()).first()
    meetings = db.query(CalendarEvent).filter(
        CalendarEvent.lead_id == lead_id,
        CalendarEvent.status == EventStatus.SCHEDULED,
    ).all()

    inbound_emails  = [e for e in emails if e.direction == "inbound"]
    outbound_emails = [e for e in emails if e.direction == "outbound"]
    inbound_calls   = [c for c in calls  if c.direction == CallDirection.INBOUND]
    outbound_calls  = [c for c in calls  if c.direction == CallDirection.OUTBOUND]
    is_inbound      = bool(inbound_emails or inbound_calls)

    # Last intent + urgency from calls
    intent   = next((c.intent   for c in calls if c.intent),   None)
    urgency  = next((c.urgency  for c in calls if c.urgency),  None)

    # Last activity
    all_times = []
    for e in emails:
        if e.received_at:
            t = e.received_at
            all_times.append(t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t)
    for c in calls:
        if c.started_at:
            t = c.started_at
            all_times.append(t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t)
    days_since = None
    if all_times:
        days_since = (datetime.now(timezone.utc) - max(all_times)).days

    # Gap counts
    gap_total = 0
    has_unresolved = False
    for c in calls:
        if c.followup_gaps:
            for g in c.followup_gaps:
                gap_total += 1
                if not g.get("resolved"):
                    has_unresolved = True
    for e in emails:
        if e.followup_gaps:
            for g in e.followup_gaps:
                gap_total += 1
                if isinstance(g, dict) and not g.get("resolved"):
                    has_unresolved = True

    # Call response rate (calls where outcome is not no_answer)
    call_response_count = len([c for c in calls if c.outcome and c.outcome.value != "no_answer"])

    return {
        "lead_id":               lead.id,
        "name":                  lead.name,
        "classification":        lead.classification or "UNCLASSIFIED",
        "engagement_score":      lead.engagement_score or 0,
        "classification_reason": lead.classification_reason,
        "next_best_action":      lead.next_best_action,
        "signals": {
            "intent":                 intent,
            "urgency":                urgency,
            "sentiment":              lead.overall_sentiment,
            "inbound_first_contact":  is_inbound,
            "total_emails":           len(emails),
            "inbound_emails":         len(inbound_emails),
            "outbound_emails":        len(outbound_emails),
            "total_calls":            len(calls),
            "inbound_calls":          len(inbound_calls),
            "outbound_calls":         len(outbound_calls),
            "total_meetings":         len(meetings),
            "days_since_last_activity": days_since,
            "active_deal_stage":      deal.stage if deal else None,
            "deal_win_probability":   float(deal.win_probability) if deal and deal.win_probability else None,
            "has_unresolved_gaps":    has_unresolved,
            "total_gap_count":        gap_total,
            "call_response_count":    call_response_count,
            "email_reply_count":      len(inbound_emails),
        },
    }


def update_lead_score(db: Session, lead_id: UUID) -> None:
    """Compute score, run classification, persist both. Called after every interaction."""
    from app.models.leads import Lead

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return

    new_score = compute_score(db, lead_id)
    classification, reason, nba = classify_lead(db, lead_id)

    lead.engagement_score       = new_score
    lead.classification         = classification
    lead.classification_reason  = reason
    lead.next_best_action       = nba
    lead.last_contacted_at      = datetime.now(timezone.utc)
    db.commit()
    logger.info(f"[SCORING] Lead {lead_id} → score={new_score} | tier={classification}")
