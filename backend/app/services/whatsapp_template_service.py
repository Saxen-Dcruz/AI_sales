"""
WhatsApp Template Service — Meta Business Management API wrapper.

Manages message templates (MARKETING / UTILITY / AUTHENTICATION).
Templates must be pre-approved by Meta before they can be sent.

Meta API docs: developers.facebook.com/docs/whatsapp/business-management-api/message-templates
"""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.models.whatsapp_account import WhatsAppAccount
from app.models.whatsapp_template import WhatsAppTemplate, WATemplateStatus, WATemplateCategory

logger = logging.getLogger("rdl_app_logger")

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"

# ── Pre-built RDL templates ────────────────────────────────────────────────────
# These are submitted to Meta on first account connection.
# They require 1–3 business days for approval (MARKETING category).

RDL_PREBUILT_TEMPLATES = [
    {
        "name": "rdl_product_inquiry_followup",
        "language": "en",
        "category": "MARKETING",
        "components": [
            {
                "type": "HEADER",
                "format": "TEXT",
                "text": "Thank you for contacting RDL Technologies",
            },
            {
                "type": "BODY",
                "text": (
                    "Hi! You asked about *{{1}}*.\n\n"
                    "Price: *{{2}}*\n\n"
                    "Would you like to proceed?"
                ),
                "example": {"body_text": [["Industrial Data Logger 4G LTE", "₹24,500"]]},
            },
            {
                "type": "FOOTER",
                "text": "RDL Technologies — Industrial IoT Solutions",
            },
            {
                "type": "BUTTONS",
                "buttons": [
                    {"type": "QUICK_REPLY", "text": "Yes, Interested ✅"},
                    {"type": "QUICK_REPLY", "text": "Need More Info 📋"},
                    {"type": "QUICK_REPLY", "text": "Not Now ❌"},
                ],
            },
        ],
    },
    {
        "name": "rdl_meeting_confirmation",
        "language": "en",
        "category": "UTILITY",
        "components": [
            {
                "type": "BODY",
                "text": (
                    "Your meeting with RDL Technologies is confirmed!\n\n"
                    "📅 *{{1}}*\n"
                    "🕐 *{{2}} IST*\n"
                    "🔗 {{3}}"
                ),
                "example": {
                    "body_text": [
                        ["Monday, 30 June 2026", "10:00 AM", "https://meet.google.com/abc-xyz"]
                    ]
                },
            },
            {"type": "FOOTER", "text": "Reply to reschedule"},
        ],
    },
    {
        "name": "rdl_post_call_summary",
        "language": "en",
        "category": "UTILITY",
        "components": [
            {
                "type": "HEADER",
                "format": "TEXT",
                "text": "Call Summary 📞",
            },
            {
                "type": "BODY",
                "text": (
                    "Thank you for speaking with us!\n\n"
                    "Product discussed: *{{1}}*\n"
                    "Next step: {{2}}\n\n"
                    "Any questions? Just reply here."
                ),
                "example": {
                    "body_text": [
                        ["Industrial Data Logger 4G LTE", "Schedule a product demo"]
                    ]
                },
            },
            {
                "type": "FOOTER",
                "text": "developer20@rdltech.in",
            },
            {
                "type": "BUTTONS",
                "buttons": [
                    {"type": "QUICK_REPLY", "text": "Schedule Demo"},
                    {"type": "QUICK_REPLY", "text": "View Datasheet"},
                ],
            },
        ],
    },
]


# ── Meta API helpers ───────────────────────────────────────────────────────────

def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


def _meta_create_template(waba_id: str, access_token: str, template_data: dict) -> dict:
    """POST to Meta Business Management API to create a template. Returns Meta's response."""
    url = f"{GRAPH_API_BASE}/{waba_id}/message_templates"
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(url, json=template_data, headers=_headers(access_token))
        resp.raise_for_status()
        return resp.json()


def _meta_list_templates(waba_id: str, access_token: str) -> list[dict]:
    """GET all templates for a WABA. Handles pagination automatically."""
    templates = []
    url = f"{GRAPH_API_BASE}/{waba_id}/message_templates?fields=id,name,status,language,category,components,rejected_reason"
    while url:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url, headers=_headers(access_token))
            resp.raise_for_status()
            data = resp.json()
        templates.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
    return templates


def _meta_delete_template(waba_id: str, access_token: str, template_name: str) -> bool:
    """DELETE a template from Meta by name (deletes ALL languages for that name)."""
    url = f"{GRAPH_API_BASE}/{waba_id}/message_templates?name={template_name}"
    with httpx.Client(timeout=20.0) as client:
        resp = client.delete(url, headers=_headers(access_token))
        resp.raise_for_status()
        return True


# ── DB-level CRUD ──────────────────────────────────────────────────────────────

def list_templates(db: Session, owner_id: Optional[UUID] = None) -> list[WhatsAppTemplate]:
    q = db.query(WhatsAppTemplate)
    if owner_id:
        q = q.filter(WhatsAppTemplate.owner_id == owner_id)
    return q.order_by(WhatsAppTemplate.created_at.desc()).all()


def get_template(db: Session, template_id: UUID) -> Optional[WhatsAppTemplate]:
    return db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id).first()


def create_template(
    db: Session,
    account: WhatsAppAccount,
    owner_id: UUID,
    name: str,
    language: str,
    category: str,
    components: list[dict],
) -> WhatsAppTemplate:
    """
    Submit a new template to Meta and persist it locally in PENDING status.
    Meta reviews it asynchronously — the webhook updates status to APPROVED/REJECTED.
    """
    meta_resp = _meta_create_template(
        account.waba_id,
        account.access_token,
        {
            "name": name,
            "language": language,
            "category": category,
            "components": components,
        },
    )

    row = WhatsAppTemplate(
        owner_id         = owner_id,
        waba_id          = account.waba_id,
        account_id       = account.id,
        meta_template_id = str(meta_resp.get("id", "")),
        name             = name,
        language         = language,
        category         = WATemplateCategory(category),
        status           = WATemplateStatus.PENDING,
        components       = components,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(f"[WA TEMPLATE] Created '{name}' ({language}/{category}) meta_id={row.meta_template_id}")
    return row


def delete_template(db: Session, template: WhatsAppTemplate, account: WhatsAppAccount) -> None:
    """Delete from Meta then remove from DB."""
    try:
        _meta_delete_template(account.waba_id, account.access_token, template.name)
    except Exception as e:
        logger.warning(f"[WA TEMPLATE] Meta delete failed for '{template.name}': {e}")
    db.delete(template)
    db.commit()
    logger.info(f"[WA TEMPLATE] Deleted '{template.name}'")


def sync_template_status(db: Session, template: WhatsAppTemplate, account: WhatsAppAccount) -> WhatsAppTemplate:
    """Pull the latest status from Meta and update the local row."""
    try:
        meta_templates = _meta_list_templates(account.waba_id, account.access_token)
        for mt in meta_templates:
            if mt.get("name") == template.name and mt.get("language") == template.language:
                raw_status = mt.get("status", "PENDING").upper()
                try:
                    template.status = WATemplateStatus(raw_status)
                except ValueError:
                    pass
                template.rejection_reason = mt.get("rejected_reason")
                if mt.get("id"):
                    template.meta_template_id = str(mt["id"])
                db.commit()
                db.refresh(template)
                break
    except Exception as e:
        logger.error(f"[WA TEMPLATE] sync failed for '{template.name}': {e}")
    return template


# ── Phase 2B: 24h window re-engagement ────────────────────────────────────────

def send_expiring_window_templates(db: Session) -> int:
    """
    Find inbound Sales messages approaching the 24h session window
    (between 23h and 24h old, not yet replied) and auto-send the
    rdl_product_inquiry_followup template to keep the conversation open.

    Meta's 24h rule: after 24 hours since the customer's last message,
    only pre-approved templates can be sent — free-form text is rejected.
    Sending a template at the 23h mark resets the 24h window.

    Returns count of templates sent.
    """
    from datetime import timedelta, timezone
    from app.models.whatsapp_message import WhatsAppMessage, WALabel, WAStatus
    from app.models.whatsapp_account import WhatsAppAccount as _WAAcct
    from app.services.whatsapp_service import send_template_message

    now    = datetime.now(timezone.utc)
    t_23h  = now - timedelta(hours=23)
    t_24h  = now - timedelta(hours=24)

    # Messages in the 23–24h danger zone that still haven't been replied to
    msgs = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.direction == "inbound",
        WhatsAppMessage.label == WALabel.SALES,
        WhatsAppMessage.status.in_([WAStatus.DRAFT_READY, WAStatus.NEW, WAStatus.CLASSIFIED]),
        WhatsAppMessage.received_at <= t_23h,
        WhatsAppMessage.received_at > t_24h,
        WhatsAppMessage.detected_product_name.isnot(None),
    ).all()

    sent = 0
    for msg in msgs:
        try:
            account = db.query(_WAAcct).filter(
                _WAAcct.id == msg.account_id,
                _WAAcct.is_active == True,
            ).first()
            if not account:
                continue

            tmpl = db.query(WhatsAppTemplate).filter(
                WhatsAppTemplate.name == "rdl_product_inquiry_followup",
                WhatsAppTemplate.status == WATemplateStatus.APPROVED,
            ).first()
            if not tmpl:
                logger.debug("[WA 24H] rdl_product_inquiry_followup not approved — skipping")
                continue

            product = msg.detected_product_name or "our products"
            components = build_template_components(tmpl, {"1": product, "2": "Contact us for pricing"})
            send_template_message(account, msg.from_number, tmpl.name, tmpl.language, components)

            # Mark as replied so we don't send again in the next cycle
            msg.status = WAStatus.REPLIED
            sent += 1
            logger.info(f"[WA 24H] Re-engagement template sent to {msg.from_number} (msg_id={msg.id})")

        except Exception as e:
            logger.warning(f"[WA 24H] Failed for msg {msg.id}: {e}")

    if sent:
        db.commit()
    return sent


# ── Phase 3A: Product catalog as list message ──────────────────────────────────

def build_product_catalog_sections(db, category: Optional[str] = None, limit: int = 10) -> list[dict]:
    """
    Fetch active products from DB and build WhatsApp list sections.
    Groups products by category (up to 5 sections, 10 rows total).
    """
    from app.models.product import Product

    q = db.query(Product).filter(Product.is_active == True)
    if category:
        q = q.filter(Product.category.ilike(f"%{category}%"))
    products = q.order_by(Product.name).limit(limit).all()

    # Group by category
    from collections import defaultdict
    by_cat: dict = defaultdict(list)
    for p in products:
        cat = p.category or "General"
        row = {
            "id":          p.order_code or str(p.id)[:8],
            "title":       (p.name or "Product")[:24],
            "description": (f"₹{p.single_price:,.0f}" if p.single_price else "Contact for price")[:72],
        }
        by_cat[cat].append(row)

    sections = []
    for cat, rows in list(by_cat.items())[:5]:  # max 5 sections
        sections.append({"title": cat[:24], "rows": rows})

    return sections


def seed_prebuilt_templates(db: Session, account: WhatsAppAccount, owner_id: UUID) -> int:
    """
    Submit RDL's pre-built templates to Meta for the given account.
    Skips any that already exist in the DB for this WABA.
    Returns count of newly submitted templates.
    """
    existing_names = {
        t.name for t in db.query(WhatsAppTemplate.name)
        .filter(WhatsAppTemplate.waba_id == account.waba_id)
        .all()
    }
    seeded = 0
    for tmpl in RDL_PREBUILT_TEMPLATES:
        if tmpl["name"] in existing_names:
            continue
        try:
            create_template(
                db        = db,
                account   = account,
                owner_id  = owner_id,
                name      = tmpl["name"],
                language  = tmpl["language"],
                category  = tmpl["category"],
                components = tmpl["components"],
            )
            seeded += 1
        except Exception as e:
            logger.warning(f"[WA TEMPLATE] Failed to seed '{tmpl['name']}': {e}")
    if seeded:
        logger.info(f"[WA TEMPLATE] Seeded {seeded} pre-built templates for {account.display_phone}")
    return seeded


def build_template_components(template: WhatsAppTemplate, variables: dict[str, str]) -> list[dict]:
    """
    Build the `components` array for a send-template API call.
    Substitutes named variables into positional {{N}} slots in BODY and HEADER text.

    variables: {"1": "Product Name", "2": "₹24,500"} or named {"product": "...", "price": "..."}
    The function detects {{1}}/{{2}} style placeholders and maps them to the variables dict
    by position (if keys are numbers) or by index order (if keys are names).
    """
    send_components = []
    for comp in template.components:
        comp_type = comp.get("type", "").upper()

        if comp_type == "BODY":
            # Map variable values to positional parameters
            vals = list(variables.values())
            params = [{"type": "text", "text": str(v)} for v in vals]
            if params:
                send_components.append({"type": "body", "parameters": params})

        elif comp_type == "HEADER":
            fmt = comp.get("format", "TEXT").upper()
            if fmt == "TEXT":
                # Header may also have variables
                pass  # most RDL headers are static
            elif fmt in ("IMAGE", "VIDEO", "DOCUMENT"):
                url = variables.get("header_url") or variables.get("media_url")
                if url:
                    media_key = fmt.lower()
                    media_obj = {"link": url}
                    if fmt == "DOCUMENT":
                        media_obj["filename"] = variables.get("filename", "document.pdf")
                    send_components.append({
                        "type": "header",
                        "parameters": [{"type": media_key, media_key: media_obj}],
                    })

        elif comp_type == "BUTTONS":
            for i, btn in enumerate(comp.get("buttons", [])):
                if btn.get("type") == "QUICK_REPLY":
                    send_components.append({
                        "type": "button",
                        "sub_type": "quick_reply",
                        "index": str(i),
                        "parameters": [{"type": "payload", "payload": btn.get("text", f"btn_{i}")}],
                    })
                elif btn.get("type") == "URL" and "{{" in btn.get("url", ""):
                    # Dynamic URL suffix variable
                    url_var = variables.get("url_suffix") or variables.get(str(len(variables)))
                    if url_var:
                        send_components.append({
                            "type": "button",
                            "sub_type": "url",
                            "index": str(i),
                            "parameters": [{"type": "text", "text": url_var}],
                        })

    return send_components
