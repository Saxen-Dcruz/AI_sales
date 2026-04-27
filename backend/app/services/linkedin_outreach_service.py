"""
LinkedIn outreach service — rate-limited connection requests and messages.

Rate limits (LinkedIn free account):
  - Connection requests: 20/day hard limit (safe target: 15/day)
  - Messages after connection: 100/week
  - Profile views before shadow-restriction: ~80-100/day

All limits stored in Redis with daily TTL so they reset at midnight UTC.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.linkedin import LinkedInOutreach
from app.services.linkedin_templates import (
    classify_role,
    classify_industry,
    get_connection_note,
    get_full_message,
    get_template_key,
)

logger = logging.getLogger("rdl_app_logger")

# ── Daily rate limit budget (per LinkedIn account) ────────────────────────────
_DAILY_CONNECTION_LIMIT = 15   # conservative — LinkedIn bans at ~20+/day
_DAILY_MESSAGE_LIMIT    = 40
_WEEKLY_MESSAGE_LIMIT   = 90   # LinkedIn's technical limit is ~100/week

_REDIS_KEY_CONNECTIONS = "linkedin:daily:connections"
_REDIS_KEY_MESSAGES    = "linkedin:daily:messages"
_REDIS_KEY_WEEKLY_MSG  = "linkedin:weekly:messages"
_REDIS_TTL_DAY         = 86_400   # 24h
_REDIS_TTL_WEEK        = 604_800  # 7 days


def _get_redis():
    from app.core.redis import get_sync_redis
    return get_sync_redis()


def _check_and_increment(redis_client, key: str, limit: int, ttl: int) -> bool:
    """Increment counter; return True if under limit, False if budget exhausted."""
    current = redis_client.get(key)
    count   = int(current) if current else 0
    if count >= limit:
        return False
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, ttl)
    pipe.execute()
    return True


def get_daily_budget(redis_client=None) -> dict:
    """Return current connection and message budgets for today."""
    r = redis_client or _get_redis()
    connections_used = int(r.get(_REDIS_KEY_CONNECTIONS) or 0)
    messages_used    = int(r.get(_REDIS_KEY_MESSAGES)    or 0)
    weekly_used      = int(r.get(_REDIS_KEY_WEEKLY_MSG)  or 0)
    return {
        "connections_used":       connections_used,
        "connections_remaining":  max(0, _DAILY_CONNECTION_LIMIT - connections_used),
        "connections_limit":      _DAILY_CONNECTION_LIMIT,
        "messages_used_today":    messages_used,
        "messages_remaining_today": max(0, _DAILY_MESSAGE_LIMIT - messages_used),
        "messages_used_week":     weekly_used,
        "messages_remaining_week": max(0, _WEEKLY_MESSAGE_LIMIT - weekly_used),
    }


# ── Outreach record management ─────────────────────────────────────────────────

def upsert_outreach_record(
    db: Session,
    linkedin_url: str,
    full_name: str,
    headline: str,
    location: str,
    company_name: str,
    industry_tag: str,
    city_tag: str,
    lead_id: Optional[UUID] = None,
    company_id: Optional[UUID] = None,
) -> LinkedInOutreach:
    """Create or return an existing outreach record for a LinkedIn profile."""
    existing = db.query(LinkedInOutreach).filter(LinkedInOutreach.linkedin_url == linkedin_url).first()
    if existing:
        return existing

    role_cat      = classify_role(headline)
    industry_bkt  = classify_industry(industry_tag)

    record = LinkedInOutreach(
        linkedin_url=linkedin_url,
        full_name=full_name,
        headline=headline,
        location=location,
        company_name=company_name,
        role_category=role_cat,
        industry_tag=industry_tag,
        city_tag=city_tag,
        lead_id=lead_id,
        company_id=company_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def queue_connection_request(db: Session, outreach_id: UUID) -> dict:
    """
    Mark a record as 'pending' connection (queued for the Playwright script to send).
    Checks the daily budget first and refuses if exhausted.
    """
    r = _get_redis()
    if not _check_and_increment(r, _REDIS_KEY_CONNECTIONS, _DAILY_CONNECTION_LIMIT, _REDIS_TTL_DAY):
        budget = get_daily_budget(r)
        return {"ok": False, "reason": f"Daily connection limit reached ({_DAILY_CONNECTION_LIMIT}/day). Resets in ~{_seconds_until_midnight()}s."}

    record = db.query(LinkedInOutreach).filter(LinkedInOutreach.id == outreach_id).first()
    if not record:
        return {"ok": False, "reason": "Record not found"}
    if record.connection_status not in ("not_sent", None):
        return {"ok": False, "reason": f"Already in status: {record.connection_status}"}

    role_cat     = record.role_category or classify_role(record.headline or "")
    industry_bkt = classify_industry(record.industry_tag or "")
    note         = get_connection_note(
        name=record.full_name or "",
        company=record.company_name or "",
        role_category=role_cat,
        industry_bucket=industry_bkt,
    )
    template_key = get_template_key(role_cat, industry_bkt)

    record.connection_status   = "pending"
    record.connection_sent_at  = datetime.now(timezone.utc)
    record.message_template_key = template_key
    # Store the note so the Playwright script can read it
    record.message_body        = note
    db.commit()

    logger.info(f"[OUTREACH] Queued connection to {record.full_name} at {record.company_name} | template={template_key}")
    return {"ok": True, "note": note, "template_key": template_key}


def queue_follow_up_message(db: Session, outreach_id: UUID) -> dict:
    """
    Queue a full follow-up message for a connected profile.
    Only allowed if connection_status == 'connected'.
    """
    r = _get_redis()
    if not _check_and_increment(r, _REDIS_KEY_MESSAGES, _DAILY_MESSAGE_LIMIT, _REDIS_TTL_DAY):
        return {"ok": False, "reason": f"Daily message limit reached ({_DAILY_MESSAGE_LIMIT}/day)."}
    if not _check_and_increment(r, _REDIS_KEY_WEEKLY_MSG, _WEEKLY_MESSAGE_LIMIT, _REDIS_TTL_WEEK):
        return {"ok": False, "reason": f"Weekly message limit reached ({_WEEKLY_MESSAGE_LIMIT}/week)."}

    record = db.query(LinkedInOutreach).filter(LinkedInOutreach.id == outreach_id).first()
    if not record:
        return {"ok": False, "reason": "Record not found"}
    if record.connection_status != "connected":
        return {"ok": False, "reason": f"Not connected yet — status: {record.connection_status}"}
    if record.message_status not in ("not_sent", None):
        return {"ok": False, "reason": f"Message already {record.message_status}"}

    role_cat     = record.role_category or classify_role(record.headline or "")
    industry_bkt = classify_industry(record.industry_tag or "")
    msg          = get_full_message(
        name=record.full_name or "",
        company=record.company_name or "",
        role_category=role_cat,
        industry_bucket=industry_bkt,
    )

    record.message_status   = "queued"
    record.message_sent_at  = datetime.now(timezone.utc)
    record.message_body     = msg
    db.commit()

    logger.info(f"[OUTREACH] Queued message to {record.full_name} at {record.company_name}")
    return {"ok": True, "message": msg}


def mark_connected(db: Session, outreach_id: UUID) -> LinkedInOutreach:
    record = db.query(LinkedInOutreach).filter(LinkedInOutreach.id == outreach_id).first()
    if record:
        record.connection_status = "connected"
        db.commit()
    return record


def mark_message_sent(db: Session, outreach_id: UUID) -> LinkedInOutreach:
    record = db.query(LinkedInOutreach).filter(LinkedInOutreach.id == outreach_id).first()
    if record:
        record.message_status  = "sent"
        record.message_sent_at = datetime.now(timezone.utc)
        db.commit()
    return record


def mark_reply_received(db: Session, outreach_id: UUID, reply_preview: str) -> LinkedInOutreach:
    record = db.query(LinkedInOutreach).filter(LinkedInOutreach.id == outreach_id).first()
    if record:
        record.message_status      = "replied"
        record.reply_received_at   = datetime.now(timezone.utc)
        record.reply_preview       = reply_preview[:500] if reply_preview else None
        db.commit()
    return record


def get_outreach_stats(db: Session) -> dict:
    total          = db.query(LinkedInOutreach).count()
    connected      = db.query(LinkedInOutreach).filter(LinkedInOutreach.connection_status == "connected").count()
    pending        = db.query(LinkedInOutreach).filter(LinkedInOutreach.connection_status == "pending").count()
    msgs_sent      = db.query(LinkedInOutreach).filter(LinkedInOutreach.message_status == "sent").count()
    msgs_replied   = db.query(LinkedInOutreach).filter(LinkedInOutreach.message_status == "replied").count()
    not_sent       = db.query(LinkedInOutreach).filter(LinkedInOutreach.connection_status == "not_sent").count()

    return {
        "total_discovered":    total,
        "connection_not_sent": not_sent,
        "connection_pending":  pending,
        "connection_accepted": connected,
        "connection_rate_pct": round(connected / total * 100, 1) if total else 0,
        "messages_sent":       msgs_sent,
        "messages_replied":    msgs_replied,
        "reply_rate_pct":      round(msgs_replied / msgs_sent * 100, 1) if msgs_sent else 0,
        "daily_budget":        get_daily_budget(),
    }


def list_outreach(
    db: Session,
    connection_status: Optional[str] = None,
    message_status: Optional[str] = None,
    role_category: Optional[str] = None,
    industry_tag: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list, int]:
    q = db.query(LinkedInOutreach)
    if connection_status:
        q = q.filter(LinkedInOutreach.connection_status == connection_status)
    if message_status:
        q = q.filter(LinkedInOutreach.message_status == message_status)
    if role_category:
        q = q.filter(LinkedInOutreach.role_category == role_category)
    if industry_tag:
        q = q.filter(LinkedInOutreach.industry_tag.ilike(f"%{industry_tag}%"))
    total = q.count()
    items = q.order_by(LinkedInOutreach.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return items, total


def _seconds_until_midnight() -> int:
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    next_midnight = midnight + timedelta(days=1)
    return int((next_midnight - now).total_seconds())
