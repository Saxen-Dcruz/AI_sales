"""
WhatsApp Business Cloud API router.

Endpoints:
  Webhook
    GET  /whatsapp/webhook          — Meta webhook verification challenge
    POST /whatsapp/webhook          — Receive inbound messages from Meta

  Inbox
    GET  /whatsapp/                 — List messages (filter: label/status/account_id/needs_human)
    GET  /whatsapp/gaps             — Messages with unresolved RAG gaps (dashboard feed)
    GET  /whatsapp/analytics        — Aggregate stats
    GET  /whatsapp/{id}             — Get single message
    POST /whatsapp/{id}/read        — Mark opened/viewed by a human
    POST /whatsapp/{id}/approve-draft — Send AI draft via WhatsApp
    POST /whatsapp/{id}/discard-draft — Discard draft, flag for human
    POST /whatsapp/{id}/resolve     — Mark Support/Grievance resolved
    POST /whatsapp/{id}/gaps/resolve — Fill gap → embed into RAG
    POST /whatsapp/send             — Send outbound message

  Accounts (under /settings — see settings.py)
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.scoping import scope_query, assert_can_access
from app.database.core import get_db
from app.models.user import User
from app.models.whatsapp_account import WhatsAppAccount
from app.models.whatsapp_message import WhatsAppMessage, WALabel, WAStatus, WAHumanStatus
from app.schema.whatsapp import (
    WAAnalytics, WAApproveDraftRequest, WAGapResolveRequest,
    WASendRequest, WhatsAppGapNotificationListResponse, WhatsAppGapNotificationOut,
    WhatsAppMessageListResponse, WhatsAppMessageOut,
    # Phase 1 — Templates + Interactive
    WATemplateCreate, WATemplateUpdate, WATemplateOut, WATemplateListResponse,
    WASendTemplateRequest,
    WASendButtonsRequest, WASendListRequest, WASendMediaRequest,
    WASendReactionRequest, WABusinessProfileOut, WABusinessProfileUpdate,
)

logger = logging.getLogger("rdl_app_logger")

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])


# ── Webhook helpers ────────────────────────────────────────────────────────────

def _find_account_for_phone_number_id(
    db: Session, phone_number_id: str
) -> Optional[WhatsAppAccount]:
    return db.query(WhatsAppAccount).filter(
        WhatsAppAccount.phone_number_id == phone_number_id,
        WhatsAppAccount.is_active == True,
    ).first()


def _allowed_accounts(db: Session, user: User) -> Optional[list[UUID]]:
    """Return list of account IDs the user can see, or None for super-admin (sees all)."""
    if user.is_superuser:
        return None
    accts = db.query(WhatsAppAccount.id).filter(
        WhatsAppAccount.owner_id == user.id
    ).all()
    return [a.id for a in accts]


# ── Webhook endpoints (no auth — called by Meta) ───────────────────────────────

@router.get("/webhook", include_in_schema=False)
def webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    db: Session = Depends(get_db),
):
    """
    Meta calls this GET endpoint when you save the webhook URL in the dashboard.
    We verify the hub.verify_token matches any of our configured accounts.
    """
    from app.services.whatsapp_service import verify_webhook_challenge

    if hub_mode != "subscribe" or not hub_verify_token:
        raise HTTPException(status_code=400, detail="Invalid webhook verification request")

    # Check against any active account's verify_token
    account = db.query(WhatsAppAccount).filter(
        WhatsAppAccount.verify_token == hub_verify_token,
        WhatsAppAccount.is_active == True,
    ).first()

    if not account:
        logger.warning(f"[WA WEBHOOK] verify_token mismatch: {hub_verify_token}")
        raise HTTPException(status_code=403, detail="Verify token mismatch")

    logger.info(f"[WA WEBHOOK] verification OK for account {account.phone_number_id}")
    # Return challenge as plain int (Meta expects the raw challenge value)
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=hub_challenge or "")


@router.post("/webhook", status_code=200, include_in_schema=False)
async def webhook_receive(request: Request, db: Session = Depends(get_db)):
    """
    Meta sends inbound messages here. We parse and run through the AI pipeline.
    Must respond 200 quickly — processing runs synchronously (fast enough for
    typical message volumes; background task can be added for high load).
    """
    from app.services.whatsapp_service import parse_webhook_payload, verify_webhook_signature
    from app.services.workflows.whatsapp_workflow import run_whatsapp_workflow
    from app.core.config import settings as _cfg

    body_bytes = await request.body()

    # Validate Meta's HMAC signature if WHATSAPP_APP_SECRET is configured
    if _cfg.WHATSAPP_APP_SECRET:
        sig_header = request.headers.get("X-Hub-Signature-256", "")
        if not verify_webhook_signature(body_bytes, sig_header, _cfg.WHATSAPP_APP_SECRET):
            logger.warning("[WA WEBHOOK] signature verification failed — rejecting")
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    import json
    payload = json.loads(body_bytes)
    logger.info(f"[WA WEBHOOK] received payload object={payload.get('object')}")

    if payload.get("object") != "whatsapp_business_account":
        return {"status": "ignored"}

    parsed   = parse_webhook_payload(payload)
    messages = parsed.get("messages", [])
    statuses = parsed.get("statuses", [])
    processed = 0

    # ── Process inbound messages through AI workflow ───────────────────────────
    for raw_msg in messages:
        phone_number_id = raw_msg.get("phone_number_id", "")
        account = _find_account_for_phone_number_id(db, phone_number_id)
        if not account:
            logger.warning(f"[WA WEBHOOK] no account for phone_number_id={phone_number_id}")
            continue
        try:
            result = run_whatsapp_workflow(db, raw_msg, account=account)
            if result is not None:   # None = duplicate, skipped
                processed += 1
        except Exception as e:
            logger.error(f"[WA WEBHOOK] workflow error: {e}", exc_info=True)

    # ── Process delivery status updates ───────────────────────────────────────
    if statuses:
        _process_status_updates(db, statuses)

    return {"status": "ok", "processed": processed}


def _process_status_updates(db, statuses: list[dict]) -> None:
    """
    Handle Meta's delivery status callbacks (sent → delivered → read / failed).
    Updates WhatsAppMessage.delivery_status + delivered_at / read_at / failed_reason
    by matching on wa_sent_message_id.
    """
    from datetime import datetime, timezone
    from app.models.whatsapp_message import WhatsAppMessage
    from sqlalchemy.orm.attributes import flag_modified

    for st in statuses:
        wamid  = st.get("wa_message_id", "")
        status = st.get("status", "")
        ts     = st.get("timestamp", 0)
        if not wamid or not status:
            continue

        msg = db.query(WhatsAppMessage).filter(
            WhatsAppMessage.wa_sent_message_id == wamid
        ).first()
        if not msg:
            continue

        msg.delivery_status = status
        if status == "delivered" and not msg.delivered_at:
            msg.delivered_at = datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else datetime.now(timezone.utc)
        elif status == "read" and not msg.read_at:
            msg.read_at = datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else datetime.now(timezone.utc)
            if not msg.delivered_at:
                msg.delivered_at = msg.read_at
        elif status == "failed":
            msg.failed_reason = st.get("error_message") or f"error_code={st.get('error_code')}"

        logger.info(f"[WA STATUS] {wamid[:20]}… → {status}")

    try:
        db.commit()
    except Exception as e:
        logger.error(f"[WA STATUS] commit failed: {e}")


# ── Inbox endpoints ────────────────────────────────────────────────────────────

@router.get("/", response_model=WhatsAppMessageListResponse)
def list_messages(
    label:        Optional[str]  = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    needs_human:  Optional[bool] = Query(None),
    account_id:   Optional[UUID] = Query(None),
    direction:    Optional[str]  = Query(None),
    page:         int            = Query(1, ge=1),
    limit:        int            = Query(30, ge=1, le=100),
    db:           Session        = Depends(get_db),
    current_user: User           = Depends(get_current_user),
):
    allowed = _allowed_accounts(db, current_user)

    q = db.query(WhatsAppMessage)

    if allowed is not None:
        q = q.filter(WhatsAppMessage.account_id.in_(allowed))
    if account_id:
        q = q.filter(WhatsAppMessage.account_id == account_id)
    if label:
        q = q.filter(WhatsAppMessage.label == label)
    if status_filter:
        q = q.filter(WhatsAppMessage.status == status_filter)
    if needs_human is not None:
        q = q.filter(WhatsAppMessage.needs_human == needs_human)
    if direction:
        q = q.filter(WhatsAppMessage.direction == direction)

    total = q.count()
    # Sort priority is driven by human_status, not the AI's own `status` — an AI
    # auto-reply flips `status` straight to REPLIED without any human involvement,
    # so `status` alone can't distinguish "already handled" from "nobody has even
    # looked at this yet" (see WAHumanStatus). A message nobody has opened always
    # outranks the rest; within each tier, ordering is reverse-chronological.
    unread_priority = case(
        (WhatsAppMessage.human_status == WAHumanStatus.UNREAD.value, 2),
        (WhatsAppMessage.human_status == WAHumanStatus.READ.value, 1),
        else_=0,
    )
    items = (
        q.order_by(unread_priority.desc(), WhatsAppMessage.received_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return WhatsAppMessageListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/gaps", response_model=WhatsAppGapNotificationListResponse)
def list_gaps(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Dashboard notification feed — Sales messages with unresolved RAG gaps."""
    allowed = _allowed_accounts(db, current_user)

    q = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.status == WAStatus.DRAFT_READY,
        WhatsAppMessage.followup_gaps.isnot(None),
        WhatsAppMessage.label == WALabel.SALES,
    )
    if allowed is not None:
        q = q.filter(WhatsAppMessage.account_id.in_(allowed))

    msgs = q.order_by(WhatsAppMessage.received_at.desc()).all()

    from app.schema.gmail import GapItem
    items = []
    for m in msgs:
        raw_gaps = m.followup_gaps or []
        parsed = []
        for g in raw_gaps:
            if isinstance(g, dict) and not g.get("resolved", False):
                try:
                    parsed.append(GapItem(**g))
                except Exception:
                    pass
        if parsed:
            items.append(WhatsAppGapNotificationOut(
                message_id=m.id,
                from_number=m.from_number,
                body=m.body,
                received_at=m.received_at,
                gaps=parsed,
            ))

    return WhatsAppGapNotificationListResponse(items=items, total=len(items))


@router.get("/analytics", response_model=WAAnalytics)
def get_analytics(
    account_id:   Optional[UUID] = Query(None),
    db:           Session        = Depends(get_db),
    current_user: User           = Depends(get_current_user),
):
    from datetime import timedelta, timezone
    import datetime as _dt

    allowed = _allowed_accounts(db, current_user)

    q = db.query(WhatsAppMessage)
    if allowed is not None:
        q = q.filter(WhatsAppMessage.account_id.in_(allowed))
    if account_id:
        q = q.filter(WhatsAppMessage.account_id == account_id)

    msgs = q.all()

    # ── Volume ─────────────────────────────────────────────────────────────────
    def lbl_eq(m, lbl: WALabel) -> bool:
        """Safe enum comparison — works even if DB returns raw strings."""
        val = m.label
        if val is None:
            return False
        if isinstance(val, str):
            return val == lbl.value
        return val == lbl

    def sts_in(m, statuses: set) -> bool:
        val = m.status
        if val is None:
            return False
        if isinstance(val, str):
            return val in {s.value for s in statuses}
        return val in statuses

    total     = len(msgs)
    inbound   = sum(1 for m in msgs if m.direction == "inbound")
    outbound  = total - inbound
    sales     = sum(1 for m in msgs if lbl_eq(m, WALabel.SALES))
    support   = sum(1 for m in msgs if lbl_eq(m, WALabel.SUPPORT))
    grievance = sum(1 for m in msgs if lbl_eq(m, WALabel.GRIEVANCE))

    # ── Pipeline performance ───────────────────────────────────────────────────
    _open_statuses = {WAStatus.NEW, WAStatus.CLASSIFIED, WAStatus.DRAFT_READY, WAStatus.PENDING_HUMAN}
    draft_r   = sum(1 for m in msgs if sts_in(m, {WAStatus.DRAFT_READY}))
    pending_h = sum(1 for m in msgs if sts_in(m, {WAStatus.PENDING_HUMAN}))
    nh_count  = sum(1 for m in msgs if m.needs_human)

    # Auto-sent = inbound Sales messages replied via AI (ai_draft present + replied)
    auto_sent = sum(
        1 for m in msgs
        if m.direction == "inbound" and lbl_eq(m, WALabel.SALES)
        and sts_in(m, {WAStatus.REPLIED}) and m.ai_draft
    )
    auto_sent_rate = round(auto_sent / sales * 100, 1) if sales > 0 else 0.0

    # ── Response time (inbound Sales → REPLIED, safe timezone comparison) ─────
    reply_times = []
    now_utc = _dt.datetime.now(timezone.utc)

    def _safe_dt_diff(received_at, updated_at) -> Optional[float]:
        """Return minutes between two datetimes, handling naive/aware mismatch."""
        if not received_at or not updated_at:
            return None
        try:
            # Make both timezone-aware if either is naive
            if received_at.tzinfo is None:
                received_at = received_at.replace(tzinfo=timezone.utc)
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            delta = (updated_at - received_at).total_seconds() / 60.0
            return delta if 0 < delta < 1440 else None
        except (TypeError, AttributeError):
            return None

    for m in msgs:
        if m.direction == "inbound" and lbl_eq(m, WALabel.SALES) and sts_in(m, {WAStatus.REPLIED}):
            d = _safe_dt_diff(m.received_at, m.updated_at)
            if d is not None:
                reply_times.append(d)
    avg_response_time = round(sum(reply_times) / len(reply_times), 1) if reply_times else 0.0

    # ── SLA breaches: Sales/Support inbound unresolved > 2h (timezone-safe) ───
    sla_cutoff = now_utc - timedelta(hours=2)
    sla_breaches = 0
    for m in msgs:
        if m.direction != "inbound":
            continue
        if not (lbl_eq(m, WALabel.SALES) or lbl_eq(m, WALabel.SUPPORT)):
            continue
        if not sts_in(m, _open_statuses):
            continue
        if not m.received_at:
            continue
        try:
            recv = m.received_at.replace(tzinfo=timezone.utc) if m.received_at.tzinfo is None else m.received_at
            if recv < sla_cutoff:
                sla_breaches += 1
        except (TypeError, AttributeError):
            pass

    # ── Knowledge gaps ─────────────────────────────────────────────────────────
    total_gaps    = 0
    resolved_gaps = 0
    for m in msgs:
        for g in (m.followup_gaps or []):
            total_gaps += 1
            if isinstance(g, dict) and g.get("resolved"):
                resolved_gaps += 1
    gap_count     = sum(1 for m in msgs if m.followup_gaps and any(
        not (g.get("resolved") if isinstance(g, dict) else False)
        for g in m.followup_gaps
    ))
    gap_res_rate  = round(resolved_gaps / total_gaps * 100, 1) if total_gaps > 0 else 0.0

    # ── Competitor mentions ────────────────────────────────────────────────────
    competitor_count = sum(1 for m in msgs if m.competitor_mention)

    # ── Breakdowns ─────────────────────────────────────────────────────────────
    by_label     = {}
    by_status    = {}
    by_direction = {"inbound": inbound, "outbound": outbound}
    for m in msgs:
        lbl_val = (m.label.value  if hasattr(m.label, "value")  else str(m.label))  if m.label  else "Unclassified"
        sts_val = (m.status.value if hasattr(m.status, "value") else str(m.status)) if m.status else "new"
        by_label[lbl_val]  = by_label.get(lbl_val, 0) + 1
        by_status[sts_val] = by_status.get(sts_val, 0) + 1

    # ── Top senders (by from_number) ───────────────────────────────────────────
    sender_map: dict = {}
    for m in msgs:
        if m.direction != "inbound":
            continue
        phone = m.from_number or "unknown"
        if phone not in sender_map:
            sender_map[phone] = {
                "from_number": phone, "total": 0, "labels": {},
                "last_at": None, "lead_id": None, "lead_name": None,
            }
        rec = sender_map[phone]
        rec["total"] += 1
        lbl_val = (m.label.value if hasattr(m.label, "value") else str(m.label)) if m.label else "Unclassified"
        rec["labels"][lbl_val] = rec["labels"].get(lbl_val, 0) + 1
        if m.received_at and (rec["last_at"] is None or m.received_at > rec["last_at"]):
            rec["last_at"] = m.received_at
        if m.lead_id and not rec["lead_id"]:
            rec["lead_id"] = str(m.lead_id)

    # Resolve lead names
    lead_ids_wa = [v["lead_id"] for v in sender_map.values() if v["lead_id"]]
    if lead_ids_wa:
        from uuid import UUID as _UUID2
        from app.models.leads import Lead as _Lead2
        leads_q2 = db.query(_Lead2.id, _Lead2.name).filter(
            _Lead2.id.in_([_UUID2(lid) for lid in lead_ids_wa])
        ).all()
        lead_nm2 = {str(r.id): r.name for r in leads_q2}
        for rec in sender_map.values():
            if rec["lead_id"]:
                rec["lead_name"] = lead_nm2.get(rec["lead_id"])

    top_senders_wa = sorted(sender_map.values(), key=lambda x: x["total"], reverse=True)[:20]
    for rec in top_senders_wa:
        if rec["last_at"]:
            rec["last_at"] = rec["last_at"].isoformat()

    # ── Top products mentioned in WhatsApp messages ────────────────────────────
    prod_map: dict = {}
    prod_conv: dict = {}
    for m in msgs:
        name = m.detected_product_name
        if name:
            prod_map[name] = prod_map.get(name, 0) + 1
            if sts_in(m, {WAStatus.REPLIED}):
                prod_conv[name] = prod_conv.get(name, 0) + 1
    top_products_wa = sorted(
        [{"name": n, "inquiries": c, "converted": prod_conv.get(n, 0),
          "conversion_pct": round(prod_conv.get(n, 0) / c * 100, 1)}
         for n, c in prod_map.items()],
        key=lambda x: x["inquiries"], reverse=True
    )[:15]

    return WAAnalytics(
        total_messages               = total,
        total_inbound                = inbound,
        total_outbound               = outbound,
        total_sales                  = sales,
        total_support                = support,
        total_grievance              = grievance,
        auto_sent                    = auto_sent,
        auto_sent_rate               = auto_sent_rate,
        drafted_for_review           = draft_r,
        pending_human                = pending_h,
        needs_human_count            = nh_count,
        avg_response_time_minutes    = avg_response_time,
        sla_breaches                 = sla_breaches,
        knowledge_gap_count          = gap_count,
        knowledge_gap_resolution_rate = gap_res_rate,
        competitor_mention_count     = competitor_count,
        by_label                     = by_label,
        by_status                    = by_status,
        by_direction                 = by_direction,
        top_senders                  = top_senders_wa,
        top_products                 = top_products_wa,
    )


# ── Helper: resolve account + RBAC check ──────────────────────────────────────

def _get_account_for_user(db, account_id: UUID, current_user: User) -> WhatsAppAccount:
    """Fetch a WA account and assert the current user can use it."""
    account = db.query(WhatsAppAccount).filter(WhatsAppAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="WhatsApp account not found")
    if not current_user.is_superuser and account.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="WhatsApp account not found")
    return account


def _log_outbound(
    db, account: WhatsAppAccount, to_number: str, body: str,
    meta_resp: dict, message_type: str = "text", template_name: str = None,
) -> WhatsAppMessage:
    """Persist an outbound WhatsApp message to DB and store Meta's wamid."""
    from datetime import datetime, timezone
    from app.models.whatsapp_message import WALabel, WAStatus
    import uuid as _uuid_mod
    wa_sent_id = (meta_resp.get("messages") or [{}])[0].get("id")
    msg = WhatsAppMessage(
        wa_message_id      = wa_sent_id or f"out_{_uuid_mod.uuid4().hex}",
        account_id         = account.id,
        account_phone      = account.phone_number_id,
        direction          = "outbound",
        from_number        = account.display_phone,
        to_number          = to_number,
        body               = body,
        received_at        = datetime.now(timezone.utc),
        label              = WALabel.UNCLASSIFIED,
        status             = WAStatus.REPLIED,
        message_type       = message_type,
        wa_sent_message_id = wa_sent_id,
        delivery_status    = "sent",
        template_name      = template_name,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# ── Template endpoints ─────────────────────────────────────────────────────────

@router.get("/templates", response_model=WATemplateListResponse)
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all message templates for the current user's WA accounts."""
    from app.services.whatsapp_template_service import list_templates as _list
    owner_id = None if current_user.is_superuser else current_user.id
    items = _list(db, owner_id=owner_id)
    return WATemplateListResponse(items=items, total=len(items))


@router.post("/templates", response_model=WATemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: WATemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create and submit a new message template to Meta for approval."""
    from app.services.whatsapp_template_service import create_template as _create
    account = _get_account_for_user(db, payload.account_id, current_user)
    try:
        return _create(
            db=db, account=account, owner_id=current_user.id,
            name=payload.name, language=payload.language,
            category=payload.category, components=payload.components,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Template creation failed: {e}")


@router.patch("/templates/{template_id}", response_model=WATemplateOut)
def update_template(
    template_id: UUID,
    payload: WATemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit a PENDING template's components and resubmit to Meta."""
    from app.models.whatsapp_template import WhatsAppTemplate, WATemplateStatus
    tmpl = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if not current_user.is_superuser and tmpl.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.status != WATemplateStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only PENDING templates can be edited")
    tmpl.components = payload.components
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a template from Meta and remove from DB."""
    from app.models.whatsapp_template import WhatsAppTemplate
    from app.services.whatsapp_template_service import delete_template as _delete
    tmpl = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if not current_user.is_superuser and tmpl.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Template not found")
    account = db.query(WhatsAppAccount).filter(
        WhatsAppAccount.waba_id == tmpl.waba_id, WhatsAppAccount.is_active == True
    ).first()
    if not account:
        raise HTTPException(status_code=400, detail="No active WA account found for this template's WABA")
    _delete(db, tmpl, account)


@router.post("/templates/{template_id}/sync", response_model=WATemplateOut)
def sync_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pull latest template status from Meta (PENDING → APPROVED or REJECTED)."""
    from app.models.whatsapp_template import WhatsAppTemplate
    from app.services.whatsapp_template_service import sync_template_status
    tmpl = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if not current_user.is_superuser and tmpl.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Template not found")
    account = db.query(WhatsAppAccount).filter(
        WhatsAppAccount.waba_id == tmpl.waba_id, WhatsAppAccount.is_active == True
    ).first()
    if not account:
        raise HTTPException(status_code=400, detail="No active WA account found for this template's WABA")
    return sync_template_status(db, tmpl, account)


@router.post("/templates/{template_id}/send", response_model=WhatsAppMessageOut)
def send_template_to_contact(
    template_id: UUID,
    payload: WASendTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send an approved template to a phone number with variable substitution."""
    from app.models.whatsapp_template import WhatsAppTemplate, WATemplateStatus
    from app.services.whatsapp_template_service import build_template_components
    from app.services.whatsapp_service import send_template_message

    tmpl = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if not current_user.is_superuser and tmpl.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Template not found")
    from app.models.whatsapp_template import WATemplateStatus as _WTS
    if tmpl.status != _WTS.APPROVED:
        status_val = tmpl.status.value if hasattr(tmpl.status, "value") else str(tmpl.status)
        raise HTTPException(status_code=400, detail=f"Template is {status_val}, must be APPROVED to send")

    account = _get_account_for_user(db, payload.to_number and tmpl.account_id, current_user) \
        if tmpl.account_id else None
    if not account:
        # Fall back to any active account for this WABA
        account = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.waba_id == tmpl.waba_id, WhatsAppAccount.is_active == True
        ).first()
    if not account:
        raise HTTPException(status_code=400, detail="No active WA account found for this template")

    components = build_template_components(tmpl, payload.variables)
    try:
        meta_resp = send_template_message(
            account, payload.to_number, tmpl.name, tmpl.language, components
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Meta API error: {e}")

    body = f"[Template: {tmpl.name}] " + " | ".join(f"{k}={v}" for k, v in payload.variables.items())
    return _log_outbound(db, account, payload.to_number, body, meta_resp, "template", tmpl.name)


# ── Interactive message endpoints ──────────────────────────────────────────────

@router.post("/send-buttons", response_model=WhatsAppMessageOut, status_code=status.HTTP_201_CREATED)
def send_buttons(
    payload: WASendButtonsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send an interactive reply-button message (1–3 quick-reply buttons)."""
    from app.services.whatsapp_service import send_button_message
    account = _get_account_for_user(db, payload.account_id, current_user)
    buttons = [b.model_dump() for b in payload.buttons]
    try:
        meta_resp = send_button_message(
            account, payload.to_number, payload.body, buttons,
            payload.header, payload.footer,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Meta API error: {e}")
    body_log = payload.body + " [buttons: " + " / ".join(b["title"] for b in buttons) + "]"
    return _log_outbound(db, account, payload.to_number, body_log, meta_resp, "button")


@router.post("/send-list", response_model=WhatsAppMessageOut, status_code=status.HTTP_201_CREATED)
def send_list(
    payload: WASendListRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send an interactive list-picker message (menu with up to 10 items)."""
    from app.services.whatsapp_service import send_list_message
    account = _get_account_for_user(db, payload.account_id, current_user)
    sections = [s.model_dump() for s in payload.sections]
    try:
        meta_resp = send_list_message(
            account, payload.to_number, payload.body, sections,
            payload.button_text, payload.header, payload.footer,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Meta API error: {e}")
    total_rows = sum(len(s.get("rows", [])) for s in sections)
    return _log_outbound(db, account, payload.to_number,
                         f"{payload.body} [list: {total_rows} options]", meta_resp, "list")


@router.post("/send-media", response_model=WhatsAppMessageOut, status_code=status.HTTP_201_CREATED)
def send_media(
    payload: WASendMediaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a media message — image, document (PDF), audio, or video."""
    from app.services import whatsapp_service as _ws
    account = _get_account_for_user(db, payload.account_id, current_user)

    SUPPORTED = {"image", "document", "audio", "video"}
    if payload.media_type not in SUPPORTED:
        raise HTTPException(status_code=422, detail=f"media_type must be one of {SUPPORTED}")

    try:
        if payload.media_type == "image":
            meta_resp = _ws.send_image(account, payload.to_number, payload.url, payload.caption)
        elif payload.media_type == "document":
            meta_resp = _ws.send_document(
                account, payload.to_number, payload.url,
                payload.filename or "document.pdf", payload.caption,
            )
        elif payload.media_type == "audio":
            meta_resp = _ws.send_audio(account, payload.to_number, payload.url)
        else:
            meta_resp = _ws.send_video(account, payload.to_number, payload.url, payload.caption)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Meta API error: {e}")

    body = payload.caption or f"[{payload.media_type}: {payload.url}]"
    return _log_outbound(db, account, payload.to_number, body, meta_resp, payload.media_type)


@router.post("/send-reaction", status_code=status.HTTP_200_OK)
def send_reaction(
    payload: WASendReactionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """React to an existing message with an emoji."""
    from app.services.whatsapp_service import send_reaction as _send_reaction
    account = _get_account_for_user(db, payload.account_id, current_user)
    try:
        result = _send_reaction(account, payload.to_number, payload.message_id, payload.emoji)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Meta API error: {e}")
    return {"status": "ok", "result": result}


# ── Business Profile endpoints ─────────────────────────────────────────────────

@router.get("/business-profile/{account_id}", response_model=WABusinessProfileOut)
def get_business_profile(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch the WhatsApp Business Profile for a connected account."""
    from app.services.whatsapp_service import get_business_profile as _gbp
    account = _get_account_for_user(db, account_id, current_user)
    try:
        data = _gbp(account)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Meta API error: {e}")
    return WABusinessProfileOut(
        about=data.get("about"), address=data.get("address"),
        description=data.get("description"), email=data.get("email"),
        websites=data.get("websites") or [], vertical=data.get("vertical"),
    )


@router.patch("/business-profile/{account_id}", response_model=WABusinessProfileOut)
def update_business_profile(
    account_id: UUID,
    payload: WABusinessProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the WhatsApp Business Profile (about, address, email, website)."""
    from app.services.whatsapp_service import update_business_profile as _ubp
    account = _get_account_for_user(db, account_id, current_user)
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=422, detail="No fields provided to update")
    try:
        _ubp(account, fields)
        data = __import__("app.services.whatsapp_service", fromlist=["get_business_profile"]).get_business_profile(account)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Meta API error: {e}")
    return WABusinessProfileOut(
        about=data.get("about"), address=data.get("address"),
        description=data.get("description"), email=data.get("email"),
        websites=data.get("websites") or [], vertical=data.get("vertical"),
    )



# ── Phase 3A: Product Catalog as List Message ─────────────────────────────────

@router.post("/send-catalog", response_model=WhatsAppMessageOut, status_code=status.HTTP_201_CREATED)
def send_product_catalog(
    account_id: UUID,
    to_number: str,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Phase 3A: Send the active product catalog as a WhatsApp list message.
    Groups products by category (≤5 sections, ≤10 rows).
    When the customer selects a product, the list_reply arrives via webhook
    and the workflow automatically detects the product and runs RAG.
    """
    from app.services.whatsapp_service import send_list_message
    from app.services.whatsapp_template_service import build_product_catalog_sections

    account  = _get_account_for_user(db, account_id, current_user)
    sections = build_product_catalog_sections(db, category=category, limit=10)
    total_rows = sum(len(s.get("rows", [])) for s in sections)

    if not sections or total_rows == 0:
        raise HTTPException(status_code=404, detail="No active products found")

    try:
        meta_resp = send_list_message(
            account     = account,
            to_number   = to_number,
            body        = "Explore our IoT & automation product range. Select a product to get pricing and specifications:",
            sections    = sections,
            button_text = "Browse Products",
            header      = "Our Products",
            footer      = "RDL Technologies — Industrial IoT Solutions",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Meta API error: {e}")

    return _log_outbound(db, account, to_number,
                         f"[Product Catalog — {total_rows} products]", meta_resp, "list")

@router.get("/{message_id}", response_model=WhatsAppMessageOut)
def get_message(
    message_id:   UUID,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    allowed = _allowed_accounts(db, current_user)
    if allowed is not None and msg.account_id not in allowed:
        raise HTTPException(status_code=404, detail="Message not found")
    return msg


@router.post("/{message_id}/read", response_model=WhatsAppMessageOut)
def mark_message_read(
    message_id:   UUID,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Mark a message as opened/viewed by a human, independent of its workflow status."""
    msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    allowed = _allowed_accounts(db, current_user)
    if allowed is not None and msg.account_id not in allowed:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.human_status == WAHumanStatus.UNREAD:
        msg.human_status = WAHumanStatus.READ
        db.commit()
        db.refresh(msg)
    return msg


@router.post("/{message_id}/approve-draft", response_model=WhatsAppMessageOut)
def approve_draft(
    message_id:   UUID,
    payload:      WAApproveDraftRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    from app.services import whatsapp_service as wa_svc

    msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    allowed = _allowed_accounts(db, current_user)
    if allowed is not None and msg.account_id not in allowed:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.status != WAStatus.DRAFT_READY:
        raise HTTPException(status_code=400, detail=f"Message is not in draft_ready state (current: {msg.status})")

    account = db.query(WhatsAppAccount).filter(WhatsAppAccount.id == msg.account_id).first()
    if not account:
        raise HTTPException(status_code=400, detail="WhatsApp account not found")

    body = payload.edit_body if payload.edit_body else msg.ai_draft
    if not body:
        raise HTTPException(status_code=400, detail="No draft body to send")

    try:
        wa_svc.send_text_message(account, msg.from_number, body)
        wa_svc.mark_message_read(account, msg.wa_message_id)
    except Exception as e:
        logger.error(f"[WA APPROVE_DRAFT] send failed: {e}")
        raise HTTPException(status_code=500, detail=f"WhatsApp send failed: {e}")

    msg.status       = WAStatus.REPLIED
    msg.ai_draft     = body  # store the final sent version
    msg.human_status = WAHumanStatus.REPLIED
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/{message_id}/discard-draft", response_model=WhatsAppMessageOut)
def discard_draft(
    message_id:   UUID,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    allowed = _allowed_accounts(db, current_user)
    if allowed is not None and msg.account_id not in allowed:
        raise HTTPException(status_code=404, detail="Message not found")

    msg.ai_draft   = None
    msg.status     = WAStatus.PENDING_HUMAN
    msg.needs_human = True
    # Discarding still leaves a manual reply owed (needs_human=True above) — not
    # resolved/replied yet, just acknowledged, so READ (not RESOLVED/REPLIED).
    if msg.human_status == WAHumanStatus.UNREAD:
        msg.human_status = WAHumanStatus.READ
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/{message_id}/resolve", response_model=WhatsAppMessageOut)
def resolve_message(
    message_id:   UUID,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Mark a Support/Grievance message as handled by a human."""
    msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    allowed = _allowed_accounts(db, current_user)
    if allowed is not None and msg.account_id not in allowed:
        raise HTTPException(status_code=404, detail="Message not found")

    from datetime import datetime, timezone
    msg.needs_human  = False
    msg.resolved_by  = current_user.email
    msg.resolved_at  = datetime.now(timezone.utc)
    msg.status       = WAStatus.REPLIED
    msg.human_status = WAHumanStatus.RESOLVED
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/{message_id}/gaps/resolve", response_model=WhatsAppMessageOut)
def resolve_gap(
    message_id:   UUID,
    payload:      WAGapResolveRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Fill a knowledge gap → embeds answer into pgvector RAG immediately."""
    from app.services.product_knowledge_service import add_entry
    from app.schema.product_knowledge import KnowledgeEntryCreate

    msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    allowed = _allowed_accounts(db, current_user)
    if allowed is not None and msg.account_id not in allowed:
        raise HTTPException(status_code=404, detail="Message not found")

    gaps = msg.followup_gaps or []
    if payload.gap_index >= len(gaps):
        raise HTTPException(status_code=400, detail="gap_index out of range")

    gap = gaps[payload.gap_index]
    if isinstance(gap, dict) and gap.get("resolved"):
        raise HTTPException(status_code=400, detail="Gap already resolved")

    # Embed into pgvector
    product_id = gap.get("product_id") if isinstance(gap, dict) else None
    if product_id:
        try:
            from uuid import UUID as _UUID
            entry = KnowledgeEntryCreate(
                content=f"Q: {gap.get('question','')}\nA: {payload.answer}",
                category=payload.category or "general",
            )
            add_entry(db, _UUID(product_id), entry, added_by=current_user.email)
        except Exception as e:
            logger.warning(f"[WA RESOLVE_GAP] embed failed: {e}")

    # Build a fully new list with a fully new dict at the resolved index so
    # SQLAlchemy detects the JSON change (in-place mutation is not tracked).
    updated = []
    for i, g in enumerate(gaps):
        if i == payload.gap_index and isinstance(g, dict):
            updated.append({**g, "resolved": True, "answer": payload.answer,
                             "resolved_by": current_user.email})
        else:
            updated.append(dict(g) if isinstance(g, dict) else g)
    msg.followup_gaps = updated
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(msg, "followup_gaps")
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/send", response_model=WhatsAppMessageOut)
def send_message(
    payload:      WASendRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Send an outbound WhatsApp message and log it."""
    from app.services import whatsapp_service as wa_svc
    from datetime import datetime, timezone

    account = db.query(WhatsAppAccount).filter(WhatsAppAccount.id == payload.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="WhatsApp account not found")
    if not current_user.is_superuser and account.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="WhatsApp account not found")

    try:
        wa_svc.send_text_message(account, payload.to_number, payload.body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WhatsApp send failed: {e}")

    msg = WhatsAppMessage(
        wa_message_id = f"out_{payload.to_number}_{int(datetime.now().timestamp())}",
        account_id    = account.id,
        account_phone = account.phone_number_id,
        direction     = "outbound",
        from_number   = account.display_phone,
        to_number     = payload.to_number,
        body          = payload.body,
        received_at   = datetime.now(timezone.utc),
        label         = WALabel.UNCLASSIFIED,
        status        = WAStatus.REPLIED,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.get("/conversations/{phone_number:path}", response_model=WhatsAppMessageListResponse)
def get_phone_conversation(
    phone_number: str,
    page:  int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db:    Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """All WhatsApp messages from/to a specific phone number — full conversation history."""
    allowed = _allowed_accounts(db, current_user)
    q = db.query(WhatsAppMessage).filter(WhatsAppMessage.from_number == phone_number)
    if allowed is not None:
        q = q.filter(WhatsAppMessage.account_id.in_(allowed))
    total = q.count()
    items = q.order_by(WhatsAppMessage.received_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return WhatsAppMessageListResponse(items=items, total=total, page=page, limit=limit)




