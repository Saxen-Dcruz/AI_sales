"""
WhatsApp workflow node implementations.

Reuses the existing classifier + RAG + gap pipeline; only the send channel differs.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from sqlalchemy import String
from sqlalchemy.orm import Session

from app.models.whatsapp_account import WhatsAppAccount
from app.models.whatsapp_message import WhatsAppMessage, WALabel, WAStatus
from app.models.leads import Lead

logger = logging.getLogger("rdl_app_logger")

_THREAD_PRODUCT_TTL_DAYS = 5  # same rule as email thread


# ── Config helpers ─────────────────────────────────────────────────────────────

def _get_db(config: RunnableConfig) -> Session:
    return config["configurable"]["db"]


def _get_account(config: RunnableConfig) -> Optional[WhatsAppAccount]:
    return config["configurable"].get("account")


# ── Parse ──────────────────────────────────────────────────────────────────────

def node_parse(state: dict, config: RunnableConfig) -> dict:
    """Extract fields from the raw webhook message dict and check for duplicates."""
    db      = _get_db(config)
    raw     = state["raw_message"]

    wa_id   = raw.get("wa_message_id", "")
    body    = raw.get("body", "")
    ts      = raw.get("timestamp", 0)
    from_no = raw.get("from_number", "")
    to_no   = raw.get("to_number", raw.get("account_phone", ""))

    if not wa_id:
        return {"duplicate": True}

    exists = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.wa_message_id == wa_id
    ).first()
    if exists:
        logger.info(f"[WA PARSE] duplicate wa_message_id={wa_id} — skipping")
        return {"duplicate": True}

    received_at = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)

    effective_body = body.strip() if body.strip() else "(media message)"

    # Pass button/list reply fields through for Phase 2C handling
    return {
        "duplicate":         False,
        "wa_message_id":     wa_id,
        "from_number":       from_no,
        "to_number":         to_no,
        "body":              body,
        "effective_body":    effective_body,
        "media_url":         raw.get("media_url"),
        "received_at":       received_at,
        "message_type":      raw.get("type", "text"),
        "button_reply_id":   raw.get("button_reply_id"),
        "button_reply_title": raw.get("button_reply_title"),
        "list_reply_id":     raw.get("list_reply_id"),
        "list_reply_title":  raw.get("list_reply_title"),
        "is_interactive":    raw.get("type") == "interactive",
    }


# ── Classify ───────────────────────────────────────────────────────────────────

def node_classify(state: dict, config: RunnableConfig) -> dict:
    """Classify inbound WhatsApp message using same Gemini classifier as email."""
    from app.services.email_classifier_service import classify_email, _is_llm_cap_error

    body    = state.get("effective_body", "")
    sender  = state.get("from_number", "")

    try:
        result = classify_email(
            subject="WhatsApp message",
            body=body,
            sender=sender,
        )
        return {
            "label":                  result.get("label", "Unclassified"),
            "classifier_confidence":  result.get("confidence", ""),
            "classifier_reasoning":   result.get("reasoning", ""),
            "competitor_mention":     result.get("competitor_mention"),
            "llm_unavailable":        False,
        }
    except Exception as e:
        if _is_llm_cap_error(e):
            logger.warning("[WA CLASSIFY] LLM quota exceeded — deferring")
            return {"llm_unavailable": True, "label": "Unclassified"}
        logger.error(f"[WA CLASSIFY] classify_email failed: {e}")
        return {"label": "Unclassified", "llm_unavailable": False}


# ── Persist ────────────────────────────────────────────────────────────────────

def node_persist(state: dict, config: RunnableConfig) -> dict:
    """Persist the WhatsApp message to DB."""
    db      = _get_db(config)
    account = _get_account(config)

    label_str = state.get("label", "Unclassified")
    try:
        label = WALabel(label_str)
    except ValueError:
        label = WALabel.UNCLASSIFIED

    msg = WhatsAppMessage(
        wa_message_id         = state["wa_message_id"],
        account_id            = account.id if account else None,
        account_phone         = account.phone_number_id if account else None,
        direction             = "inbound",
        from_number           = state["from_number"],
        to_number             = state.get("to_number", ""),
        body                  = state.get("body", ""),
        media_url             = state.get("media_url"),
        received_at           = state["received_at"],
        label                 = label,
        status                = WAStatus.CLASSIFIED,
        classifier_confidence = state.get("classifier_confidence", ""),
        classifier_reasoning  = state.get("classifier_reasoning", ""),
        competitor_mention    = state.get("competitor_mention"),
    )
    db.add(msg)
    db.flush()
    logger.info(f"[WA PERSIST] saved message id={msg.id}, label={label}")
    return {"message_id": str(msg.id)}


# ── Upsert lead ───────────────────────────────────────────────────────────────

def node_upsert_lead(state: dict, config: RunnableConfig) -> dict:
    """Create or find lead from sender phone number."""
    db          = _get_db(config)
    account     = _get_account(config)
    from_number = state.get("from_number", "")

    existing = db.query(Lead).filter(Lead.phone == from_number).first()
    if existing:
        return {"lead_id": str(existing.id), "is_new_lead": False}

    # owner_id must match the WhatsApp account owner for RBAC compliance
    owner_id = account.owner_id if account else None
    lead = Lead(
        name=f"WhatsApp {from_number}",
        phone=from_number,
        status="new",
        owner_id=owner_id,
    )
    db.add(lead)
    db.flush()

    # Link message to lead
    _link_lead(db, state.get("message_id"), lead.id)
    logger.info(f"[WA UPSERT_LEAD] created lead id={lead.id} for {from_number}")
    return {"lead_id": str(lead.id), "is_new_lead": True}


def _link_lead(db: Session, message_id: Optional[str], lead_id) -> None:
    if not message_id:
        return
    try:
        msg = db.query(WhatsAppMessage).filter(
            WhatsAppMessage.id == UUID(message_id)
        ).first()
        if msg:
            msg.lead_id = lead_id
    except Exception:
        pass


# ── Detect product ─────────────────────────────────────────────────────────────

def node_detect_product(state: dict, config: RunnableConfig) -> dict:
    """3-phase product detection — identical logic to email pipeline."""
    from app.services.sales_gap_service import detect_product

    db   = _get_db(config)
    body = state.get("effective_body", "")

    try:
        pid, pname, confidence = detect_product(db, body)
        return {
            "product_id":         pid,
            "product_name":       pname,
            "product_confidence": confidence or "none",
        }
    except Exception as e:
        logger.warning(f"[WA DETECT_PRODUCT] error: {e}")
        return {"product_id": None, "product_name": None, "product_confidence": "none"}


# ── Fetch RAG ──────────────────────────────────────────────────────────────────

def node_fetch_rag(state: dict, config: RunnableConfig) -> dict:
    from app.services.sales_gap_service import fetch_rag_context
    body = state.get("effective_body", "")
    try:
        ctx = fetch_rag_context(body)
        return {"rag_context": ctx}
    except Exception as e:
        logger.warning(f"[WA FETCH_RAG] error: {e}")
        return {"rag_context": None}


# ── Generate draft ─────────────────────────────────────────────────────────────

def node_generate_draft(state: dict, config: RunnableConfig) -> dict:
    from app.services.workflows.email_nodes import generate_sales_draft
    body    = state.get("effective_body", "")
    sender  = state.get("from_number", "")
    rag_ctx = state.get("rag_context")
    try:
        draft = generate_sales_draft(
            sender  = sender,
            subject = "WhatsApp inquiry",
            body    = body,
            rag_context = rag_ctx,
        )
        return {"draft": draft}
    except Exception as e:
        logger.warning(f"[WA GENERATE_DRAFT] error: {e}")
        return {"draft": None}


# ── Extract gaps ──────────────────────────────────────────────────────────────

def node_extract_gaps(state: dict, config: RunnableConfig) -> dict:
    from app.services.sales_gap_service import extract_structured_gaps
    db          = _get_db(config)
    body        = state.get("effective_body", "")
    draft       = state.get("draft", "") or ""
    product_id  = state.get("product_id")
    product_name = state.get("product_name")

    try:
        gaps = extract_structured_gaps(
            body=body, draft=draft,
            product_name=product_name, product_id=product_id,
        )
    except Exception:
        gaps = []

    # Persist draft + gaps onto DB row
    msg_id = state.get("message_id")
    if msg_id:
        try:
            msg = db.query(WhatsAppMessage).filter(
                WhatsAppMessage.id == UUID(msg_id)
            ).first()
            if msg:
                msg.ai_draft              = draft
                msg.followup_gaps         = [g if isinstance(g, dict) else g.model_dump() for g in gaps]
                msg.detected_product_id   = product_id
                msg.detected_product_name = product_name
            else:
                logger.warning(f"[WA EXTRACT_GAPS] message {msg_id} not found in DB — draft/gaps not persisted")
        except Exception as e:
            logger.error(f"[WA EXTRACT_GAPS] failed to persist draft/gaps for message {msg_id}: {e}")

    return {"gaps": gaps or []}


# ── Auto send ─────────────────────────────────────────────────────────────────

def node_auto_send(state: dict, config: RunnableConfig) -> dict:
    """Send the AI draft via WhatsApp."""
    from app.services import whatsapp_service as wa_svc

    db      = _get_db(config)
    account = _get_account(config)
    draft   = state.get("draft") or ""
    to_no   = state.get("from_number", "")
    msg_id  = state.get("message_id")

    if not draft or not account:
        return {"action": "hold_draft"}

    try:
        wa_svc.send_text_message(account, to_no, draft)
        wa_svc.mark_message_read(account, state.get("wa_message_id", ""))
        if msg_id:
            _set_status(db, msg_id, WAStatus.REPLIED)
        logger.info(f"[WA AUTO_SEND] sent reply to {to_no}")
        return {"action": "auto_sent"}
    except Exception as e:
        logger.error(f"[WA AUTO_SEND] send failed: {e}")
        # Fall through to hold_draft
        if msg_id:
            _set_status(db, msg_id, WAStatus.DRAFT_READY, needs_human=True)
        return {"action": "hold_draft_on_error"}


# ── Hold draft ────────────────────────────────────────────────────────────────

def node_hold_draft(state: dict, config: RunnableConfig) -> dict:
    db     = _get_db(config)
    msg_id = state.get("message_id")
    if msg_id:
        _set_status(db, msg_id, WAStatus.DRAFT_READY)
    return {"action": "draft_held"}


# ── Send clarification ────────────────────────────────────────────────────────

def node_send_clarification(state: dict, config: RunnableConfig) -> dict:
    from app.services.sales_gap_service import find_similar_products
    from app.services import whatsapp_service as wa_svc

    db      = _get_db(config)
    account = _get_account(config)
    to_no   = state.get("from_number", "")
    body    = state.get("effective_body", "")

    # Build "did you mean one of these?" message
    similar = find_similar_products(db, body, limit=3)
    if similar:
        lines = ["Hi! Could you clarify which product you're asking about?\n"]
        for p in similar:
            lines.append(f"• {p['name']} ({p.get('order_code', '')})")
        lines.append("\nJust reply with the product name or order code.")
        text = "\n".join(lines)
    else:
        text = (
            "Hi! Thank you for reaching out to RDL Technologies. "
            "Could you please clarify which product you're interested in? "
            "Our team will be happy to assist you."
        )

    try:
        if account:
            wa_svc.send_text_message(account, to_no, text)
    except Exception as e:
        logger.warning(f"[WA SEND_CLARIFICATION] failed: {e}")

    msg_id = state.get("message_id")
    if msg_id:
        _set_status(db, msg_id, WAStatus.REPLIED)
    return {"action": "clarification_sent"}


# ── Flag human ────────────────────────────────────────────────────────────────

def node_flag_human(state: dict, config: RunnableConfig) -> dict:
    db     = _get_db(config)
    msg_id = state.get("message_id")
    if msg_id:
        _set_status(db, msg_id, WAStatus.PENDING_HUMAN, needs_human=True)
    return {"action": "flagged_human"}


# ── Archive ────────────────────────────────────────────────────────────────────

def node_archive(state: dict, config: RunnableConfig) -> dict:
    """Archive Promotional/Transactional/Personal WhatsApp messages.
    For Transactional messages with sales-relevant types (invoice, order, receipt)
    we also auto-create or update a Deal in the CRM pipeline.
    """
    db      = _get_db(config)
    account = _get_account(config)
    msg_id  = state.get("message_id")
    label   = state.get("label", "")

    if msg_id:
        _set_status(db, msg_id, WAStatus.ARCHIVED)

    # Auto-create/update Deal from invoice or purchase document
    if label == "Transactional":
        ttype   = state.get("transactional_type")
        tdata   = state.get("transactional_data") or {}
        lead_id = state.get("lead_id")
        if ttype and lead_id:
            try:
                from app.services.transaction_deal_service import process_transaction_for_deal
                owner_id = account.owner_id if account else None
                process_transaction_for_deal(
                    db             = db,
                    lead_id        = lead_id,
                    transactional_type = ttype,
                    transactional_data = tdata,
                    owner_id       = owner_id,
                    source_channel = "whatsapp",
                )
            except Exception as exc:
                logger.warning(f"[WA ARCHIVE] transaction→deal failed: {exc}")

    return {"action": "archived"}


# ── Update lead score ─────────────────────────────────────────────────────────

def node_update_lead_score(state: dict, config: RunnableConfig) -> dict:
    from app.services.lead_scoring_service import update_lead_score
    db      = _get_db(config)
    lead_id = state.get("lead_id")
    if lead_id:
        try:
            update_lead_score(db, UUID(lead_id))
        except Exception as e:
            logger.warning(f"[WA UPDATE_LEAD_SCORE] failed: {e}")
    return {}


# ── Commit ─────────────────────────────────────────────────────────────────────

def node_commit(state: dict, config: RunnableConfig) -> dict:
    db = _get_db(config)
    try:
        db.commit()
    except Exception as e:
        logger.error(f"[WA COMMIT] error: {e}")
        db.rollback()
    return {}


# ── Routing functions ─────────────────────────────────────────────────────────

# ── Phase 2C: Button/List reply handler ───────────────────────────────────────

# Button IDs we recognise from templates we send
_INTERESTED_IDS   = {"interested", "yes_interested", "yes,_interested_✅", "yes__interested_✅", "schedule_demo", "schedule demo"}
_MORE_INFO_IDS    = {"more_info", "need_more_info", "need_more_info_📋", "view_datasheet", "view datasheet"}
_NOT_NOW_IDS      = {"not_now", "not_interested", "not_now_❌"}


def node_handle_interactive_reply(state: dict, config: RunnableConfig) -> dict:
    """
    Phase 2C: Handle button/list replies from previous template messages.

    Button replies (from rdl templates):
      - interested → update lead to HIGH, create Deal if not exists, send confirmation
      - more_info  → send product datasheet / detailed info list
      - not_now    → update lead to LOW, send polite close

    List replies (from product catalog or clarification):
      - row.id = product order_code → set detected_product, run RAG
    """
    from app.services import whatsapp_service as wa_svc
    from app.services.lead_scoring_service import update_lead_score

    db      = _get_db(config)
    account = _get_account(config)
    raw     = state.get("raw_message", {})
    msg_type = raw.get("type", "")

    button_reply_id    = (raw.get("button_reply_id") or "").lower().replace(" ", "_")
    list_reply_id      = raw.get("list_reply_id") or ""
    from_no            = state.get("from_number", "")
    lead_id            = state.get("lead_id")
    msg_id             = state.get("message_id")

    # ── List reply → treat as product selection ────────────────────────────────
    if list_reply_id:
        # Find product by order_code or id fragment
        from app.models.product import Product
        product = (
            db.query(Product).filter(
                (Product.order_code == list_reply_id) |
                (Product.id.cast(String).like(f"{list_reply_id}%"))
            ).filter(Product.is_active == True).first()
        )
        if product:
            logger.info(f"[WA INTERACTIVE] list_reply selected product: {product.name}")
            return {
                "product_id":         str(product.id),
                "product_name":       product.name,
                "product_confidence": "high",
                "action":             "product_selected",
                "interactive_handled": False,  # continue to RAG
            }
        else:
            # Unknown list item — treat as text and continue
            return {"interactive_handled": False}

    # ── Button reply → lead action ─────────────────────────────────────────────
    if button_reply_id:
        if button_reply_id in _INTERESTED_IDS:
            # Customer is interested — upgrade lead, create deal
            _handle_interested(db, account, from_no, lead_id, state.get("product_name"), msg_id)
            return {"action": "interested_handled", "interactive_handled": True}

        elif button_reply_id in _MORE_INFO_IDS:
            # Send detailed product info as list message
            _handle_more_info(db, account, from_no, state.get("product_name"))
            if msg_id:
                _set_status(db, msg_id, WAStatus.REPLIED)
            return {"action": "more_info_sent", "interactive_handled": True}

        elif button_reply_id in _NOT_NOW_IDS:
            # Customer not interested — update lead score
            _handle_not_now(db, account, from_no, lead_id, msg_id)
            return {"action": "not_now_handled", "interactive_handled": True}

    return {"interactive_handled": False}


def _send_voice_invitation_wa(db, account, from_no: str, lead_id, owner_id) -> None:
    """Create a LiveKit room and send the join URL to the customer via WhatsApp."""
    try:
        from uuid import UUID as _UUID
        from app.services.voice_room_service import create_room
        from app.services import whatsapp_service as wa_svc
        from app.core.config import settings as _cfg

        _lead_id  = _UUID(str(lead_id)) if lead_id else None
        _owner_id = _UUID(str(owner_id)) if owner_id else None

        session, join_url = create_room(
            db,
            channel_origin = "whatsapp",
            owner_id       = _owner_id,
            lead_id        = _lead_id,
        )

        msg = (
            "🎙️ Want to talk to our AI assistant right now?\n\n"
            "Click the link below — your browser will open and our AI will be "
            "ready to answer all your questions in real time:\n\n"
            f"*{join_url}*\n\n"
            f"_(Link active for {_cfg.VOICE_TOKEN_TTL_MINUTES} minutes)_\n\n"
            f"Or call us directly: {_cfg.COMPANY_PHONE}"
        )
        wa_svc.send_text_message(account, from_no, msg)
        logger.info(f"[VOICE INVITE] WA invite sent: room={session.room_name} lead={lead_id}")
    except Exception as exc:
        logger.warning(f"[VOICE INVITE] WA invite failed: {exc}")


def _handle_interested(db, account, from_no: str, lead_id, product_name, msg_id) -> None:
    """Update lead to HIGH, create a deal, send confirmation + voice invitation."""
    from app.models.leads import Lead
    from app.models.deal import Deal
    from app.services.lead_scoring_service import update_lead_score

    _owner_id = account.owner_id if account else None

    if lead_id:
        try:
            from uuid import UUID
            lead = db.query(Lead).filter(Lead.id == UUID(lead_id)).first()
            if lead:
                lead.classification = "HIGH"
                # Create deal if none open
                open_deal = db.query(Deal).filter(
                    Deal.lead_id == lead.id,
                    Deal.stage.notin_(["Closed Won", "Closed Lost"]),
                ).first()
                if not open_deal:
                    deal = Deal(
                        lead_id     = lead.id,
                        company_id  = lead.company_id,
                        deal_name   = f"WhatsApp Interest — {product_name or 'Product Inquiry'}",
                        stage       = "Qualified",
                        win_probability = 50,
                        owner_id    = lead.owner_id,
                    )
                    db.add(deal)
                    _owner_id = lead.owner_id
                db.flush()
                update_lead_score(db, lead.id)
                logger.info(f"[WA INTERACTIVE] Lead {lead.id} upgraded to HIGH via button reply")
        except Exception as e:
            logger.warning(f"[WA INTERACTIVE] Lead upgrade failed: {e}")

    if account and from_no:
        try:
            from app.services import whatsapp_service as wa_svc
            msg = (
                "Thank you for your interest! 🎉\n\n"
                "Our sales team will contact you shortly to discuss your requirements "
                f"and provide a customized quote{f' for *{product_name}*' if product_name else ''}.\n\n"
                "You can also reach us directly at:\n"
                "📧 developer20@rdltech.in\n"
                "🌐 rdltech.in"
            )
            wa_svc.send_text_message(account, from_no, msg)
        except Exception as e:
            logger.warning(f"[WA INTERACTIVE] Confirmation send failed: {e}")

        # Offer an instant AI voice call
        if _owner_id:
            _send_voice_invitation_wa(db, account, from_no, lead_id, _owner_id)

    if msg_id:
        _set_status(db, msg_id, WAStatus.REPLIED)


def _handle_more_info(db, account, from_no: str, product_name) -> None:
    """Send product info as a list message or detailed text."""
    from app.services import whatsapp_service as wa_svc
    if not account or not from_no:
        return
    try:
        from app.services.whatsapp_template_service import build_product_catalog_sections
        sections = build_product_catalog_sections(db, category=None, limit=6)
        if sections:
            wa_svc.send_list_message(
                account, from_no,
                body=f"Here are our available products{f' related to *{product_name}*' if product_name else ''}. Select one to get details:",
                sections=sections,
                button_text="View Products",
                footer="RDL Technologies",
            )
        else:
            wa_svc.send_text_message(
                account, from_no,
                f"Please visit rdltech.in for our full product catalog, or reply with a specific product name."
            )
    except Exception as e:
        logger.warning(f"[WA INTERACTIVE] More info send failed: {e}")


def _handle_not_now(db, account, from_no: str, lead_id, msg_id) -> None:
    """Downgrade lead to LOW and send a polite message."""
    from app.services.lead_scoring_service import update_lead_score

    if lead_id:
        try:
            from uuid import UUID
            from app.models.leads import Lead
            lead = db.query(Lead).filter(Lead.id == UUID(lead_id)).first()
            if lead:
                lead.classification = "LOW"
                db.flush()
                update_lead_score(db, lead.id)
        except Exception as e:
            logger.warning(f"[WA INTERACTIVE] Lead downgrade failed: {e}")

    if account and from_no:
        try:
            from app.services import whatsapp_service as wa_svc
            wa_svc.send_text_message(
                account, from_no,
                "No worries at all! 😊\n\n"
                "Whenever you're ready to explore our IoT solutions, "
                "feel free to reach out. We're always here to help!\n\n"
                "Best regards,\nRDL Technologies"
            )
        except Exception as e:
            logger.warning(f"[WA INTERACTIVE] Not-now message failed: {e}")

    if msg_id:
        _set_status(db, msg_id, WAStatus.REPLIED)


# ── Phase 4: Post-send qualification buttons ───────────────────────────────────

def node_send_qualification_buttons(state: dict, config: RunnableConfig) -> dict:
    """
    Phase 4: After a successful auto-send of a Sales reply, send a
    follow-up button message to guide the next step in the sales cycle.

    Only fires when:
    - action = auto_sent (not hold_draft or error)
    - product was detected (product_name is set)
    - auto_send flag is True
    """
    account = _get_account(config)
    action  = state.get("action", "")
    product = state.get("product_name")
    from_no = state.get("from_number", "")

    # Only send if the previous step actually sent successfully
    if action != "auto_sent" or not account or not from_no:
        return {"action": action}

    try:
        from app.services import whatsapp_service as wa_svc
        buttons = [
            {"id": "interested",   "title": "Interested ✅"},
            {"id": "more_info",    "title": "More Info 📋"},
            {"id": "not_now",      "title": "Not Now ❌"},
        ]
        wa_svc.send_button_message(
            account=account,
            to_number=from_no,
            body=f"Would you like to proceed{f' with *{product}*' if product else ''}?",
            buttons=buttons,
            footer="RDL Technologies",
        )
        logger.info(f"[WA PHASE4] Qualification buttons sent to {from_no}")
    except Exception as e:
        # Non-fatal — don't disrupt the main flow
        logger.warning(f"[WA PHASE4] Qualification buttons failed: {e}")

    return {"action": action}


def route_after_parse(state: dict) -> str:
    if state.get("duplicate"):
        return "end_duplicate"
    # Phase 2C: button/list replies need special handling before classification
    if state.get("is_interactive"):
        return "handle_interactive"
    return "classify"


def route_after_classify(state: dict) -> str:
    label = state.get("label", "Unclassified")
    if label in ("Sales",):
        return "sales_branch"
    if label in ("Support", "Grievance"):
        return "support_branch"
    return "archive_branch"


def route_after_confidence(state: dict) -> str:
    conf = state.get("product_confidence", "none")
    if conf == "high":
        return "high"
    if conf == "unavailable":
        return "defer"
    return "low"


def route_after_gaps(state: dict) -> str:
    account = None  # account retrieved from config at runtime — use state flag instead
    # auto_send decision passed through state from config
    if state.get("auto_send") and not state.get("gaps"):
        return "auto_send"
    return "hold_draft"


# ── Helper ─────────────────────────────────────────────────────────────────────

def _set_status(
    db: Session,
    message_id: str,
    status: WAStatus,
    needs_human: bool = False,
) -> None:
    try:
        msg = db.query(WhatsAppMessage).filter(
            WhatsAppMessage.id == UUID(message_id)
        ).first()
        if msg:
            msg.status = status
            if needs_human:
                msg.needs_human = True
    except Exception as e:
        logger.warning(f"[WA _set_status] {e}")
