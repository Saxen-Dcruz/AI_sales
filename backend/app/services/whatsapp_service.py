"""
WhatsApp Business Cloud API (Meta Graph API v21.0) wrapper.

Responsibilities:
  - send_whatsapp_message()   — POST to Meta to send a text reply
  - verify_webhook()          — validate Meta's hub.verify_token challenge
  - parse_webhook_payload()   — extract message data from Meta push event
  - get_account()             — fetch a WhatsAppAccount by id or phone_number_id
"""
import hashlib
import hmac
import logging
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.models.whatsapp_account import WhatsAppAccount

logger = logging.getLogger("rdl_app_logger")

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


# ── Account helpers ────────────────────────────────────────────────────────────

def get_account_by_id(db: Session, account_id: UUID) -> Optional[WhatsAppAccount]:
    return db.query(WhatsAppAccount).filter(WhatsAppAccount.id == account_id).first()


def get_account_by_phone_number_id(db: Session, phone_number_id: str) -> Optional[WhatsAppAccount]:
    return db.query(WhatsAppAccount).filter(
        WhatsAppAccount.phone_number_id == phone_number_id,
        WhatsAppAccount.is_active == True,
    ).first()


def list_accounts(db: Session, owner_id: Optional[UUID] = None) -> list[WhatsAppAccount]:
    q = db.query(WhatsAppAccount)
    if owner_id:
        q = q.filter(WhatsAppAccount.owner_id == owner_id)
    return q.order_by(WhatsAppAccount.is_primary.desc(), WhatsAppAccount.created_at).all()


# ── Webhook verification ───────────────────────────────────────────────────────

def verify_webhook_challenge(
    hub_mode: str,
    hub_verify_token: str,
    hub_challenge: str,
    expected_verify_token: str,
) -> Optional[str]:
    """Return hub_challenge if verification passes, None otherwise."""
    if hub_mode == "subscribe" and hub_verify_token == expected_verify_token:
        return hub_challenge
    return None


def verify_webhook_signature(payload_bytes: bytes, signature_header: str, app_secret: str) -> bool:
    """Validate the X-Hub-Signature-256 header Meta sends on every webhook POST."""
    if not signature_header or not app_secret:
        return True   # skip if not configured — allow in dev/test
    expected = "sha256=" + hmac.new(
        app_secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


# ── Webhook payload parsing ────────────────────────────────────────────────────

def parse_webhook_payload(payload: dict) -> list[dict]:
    """
    Parse a Meta WhatsApp webhook push payload.
    Returns two lists via the result dict:
      "messages" → inbound messages (text, media, interactive replies, etc.)
      "statuses" → delivery status events (sent/delivered/read/failed)

    Each message entry:
      {phone_number_id, from_number, wa_message_id, body, media_url, timestamp, type,
       button_reply_id?, button_reply_title?, list_reply_id?, list_reply_title?}

    Each status entry:
      {wa_message_id, status, timestamp, recipient_id, error_code?, error_message?}
    """
    messages = []
    statuses = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if change.get("field") != "messages":
                continue

            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")

            # ── Inbound messages ───────────────────────────────────────────────
            for msg in value.get("messages", []):
                msg_type = msg.get("type", "text")
                body = ""
                media_url = None
                button_reply_id = button_reply_title = None
                list_reply_id = list_reply_title = None

                if msg_type == "text":
                    body = msg.get("text", {}).get("body", "")

                elif msg_type in ("image", "document", "audio", "video", "sticker"):
                    media = msg.get(msg_type, {})
                    media_url = media.get("link") or media.get("id")
                    caption = media.get("caption", "")
                    filename = media.get("filename", "")
                    body = caption or filename or f"[{msg_type} attachment]"

                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    sub_type = interactive.get("type", "")
                    if sub_type == "button_reply":
                        br = interactive.get("button_reply", {})
                        button_reply_id    = br.get("id", "")
                        button_reply_title = br.get("title", "")
                        body = button_reply_title
                    elif sub_type == "list_reply":
                        lr = interactive.get("list_reply", {})
                        list_reply_id    = lr.get("id", "")
                        list_reply_title = lr.get("title", "")
                        body = list_reply_title
                    else:
                        body = f"[interactive/{sub_type}]"

                elif msg_type == "reaction":
                    reaction = msg.get("reaction", {})
                    body = f"[reaction: {reaction.get('emoji', '?')}]"

                elif msg_type == "location":
                    loc = msg.get("location", {})
                    body = (f"[location: {loc.get('name', '')} "
                            f"{loc.get('latitude', '')},{loc.get('longitude', '')}]")

                elif msg_type == "contacts":
                    body = "[contact card]"

                else:
                    body = f"[{msg_type} message]"

                messages.append({
                    "phone_number_id":   phone_number_id,
                    "from_number":       msg.get("from", ""),
                    "wa_message_id":     msg.get("id", ""),
                    "body":              body,
                    "media_url":         media_url,
                    "timestamp":         int(msg.get("timestamp", 0)),
                    "type":              msg_type,
                    "button_reply_id":   button_reply_id,
                    "button_reply_title": button_reply_title,
                    "list_reply_id":     list_reply_id,
                    "list_reply_title":  list_reply_title,
                })

            # ── Delivery status updates ────────────────────────────────────────
            for st in value.get("statuses", []):
                error = (st.get("errors") or [{}])[0]
                statuses.append({
                    "wa_message_id":  st.get("id", ""),       # the sent message's wamid
                    "status":         st.get("status", ""),   # sent/delivered/read/failed
                    "timestamp":      int(st.get("timestamp", 0)),
                    "recipient_id":   st.get("recipient_id", ""),
                    "error_code":     error.get("code"),
                    "error_message":  error.get("message"),
                    "phone_number_id": phone_number_id,
                })

    # Legacy callers that only use .get("messages") still work since we return both
    return {"messages": messages, "statuses": statuses}


# ── Sending messages ───────────────────────────────────────────────────────────

def send_text_message(account: WhatsAppAccount, to_number: str, body: str) -> dict:
    """
    Send a plain-text WhatsApp message via the Meta Cloud API.
    Returns the API response dict (contains messages[].id on success).
    Raises httpx.HTTPStatusError on API error.
    """
    url = f"{GRAPH_API_BASE}/{account.phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {account.access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"body": body},
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def send_template_message(
    account: WhatsAppAccount,
    to_number: str,
    template_name: str,
    language_code: str = "en_US",
    components: Optional[list] = None,
) -> dict:
    """Send a pre-approved WhatsApp template message (required for outbound marketing)."""
    url = f"{GRAPH_API_BASE}/{account.phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {account.access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": components or [],
        },
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _post_message(account: WhatsAppAccount, payload: dict) -> dict:
    """Shared helper — POST to /{phone_number_id}/messages."""
    url = f"{GRAPH_API_BASE}/{account.phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {account.access_token}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def send_button_message(
    account: WhatsAppAccount,
    to_number: str,
    body: str,
    buttons: list[dict],           # [{"id": "...", "title": "..."}] — max 3
    header: Optional[str] = None,
    footer: Optional[str] = None,
) -> dict:
    """
    Send an interactive reply-button message (up to 3 quick-reply buttons).
    Each button: {"id": "<unique_id>", "title": "<≤20 chars>"}
    When the customer taps a button, the webhook delivers:
      interactive.type = "button_reply"
      interactive.button_reply = {"id": "...", "title": "..."}
    """
    if not 1 <= len(buttons) <= 3:
        raise ValueError("Reply button messages require 1–3 buttons")

    interactive: dict = {
        "type": "button",
        "body": {"text": body},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                for b in buttons
            ]
        },
    }
    if header:
        interactive["header"] = {"type": "text", "text": header}
    if footer:
        interactive["footer"] = {"text": footer}

    return _post_message(account, {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "interactive",
        "interactive": interactive,
    })


def send_list_message(
    account: WhatsAppAccount,
    to_number: str,
    body: str,
    sections: list[dict],          # [{"title": "...", "rows": [{"id": "...", "title": "...", "description": "..."}]}]
    button_text: str = "Select",   # text on the list-open button
    header: Optional[str] = None,
    footer: Optional[str] = None,
) -> dict:
    """
    Send an interactive list-picker message.
    Customer taps the button → sees a menu → selects a row.
    Webhook delivers: interactive.type = "list_reply"
                      interactive.list_reply = {"id": "...", "title": "...", "description": "..."}
    Limits: max 10 rows total, max 5 sections, section title ≤24 chars, row title ≤24 chars.
    """
    total_rows = sum(len(s.get("rows", [])) for s in sections)
    if not 1 <= total_rows <= 10:
        raise ValueError("List messages require 1–10 rows total")
    if len(sections) > 5:
        raise ValueError("List messages allow a maximum of 5 sections")

    interactive: dict = {
        "type": "list",
        "body": {"text": body},
        "action": {
            "button": button_text[:20],
            "sections": sections,
        },
    }
    if header:
        interactive["header"] = {"type": "text", "text": header}
    if footer:
        interactive["footer"] = {"text": footer}

    return _post_message(account, {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "interactive",
        "interactive": interactive,
    })


def send_image(account: WhatsAppAccount, to_number: str, url: str, caption: Optional[str] = None) -> dict:
    """Send an image from a public URL."""
    img: dict = {"link": url}
    if caption:
        img["caption"] = caption
    return _post_message(account, {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "image",
        "image": img,
    })


def send_document(
    account: WhatsAppAccount,
    to_number: str,
    url: str,
    filename: str,
    caption: Optional[str] = None,
) -> dict:
    """Send a document (PDF, XLSX, etc.) from a public URL. filename shown in chat."""
    doc: dict = {"link": url, "filename": filename}
    if caption:
        doc["caption"] = caption
    return _post_message(account, {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "document",
        "document": doc,
    })


def send_audio(account: WhatsAppAccount, to_number: str, url: str) -> dict:
    """Send an audio file from a public URL (MP3, OGG, etc.)."""
    return _post_message(account, {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "audio",
        "audio": {"link": url},
    })


def send_video(account: WhatsAppAccount, to_number: str, url: str, caption: Optional[str] = None) -> dict:
    """Send a video from a public URL (MP4, 3GP)."""
    vid: dict = {"link": url}
    if caption:
        vid["caption"] = caption
    return _post_message(account, {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "video",
        "video": vid,
    })


def send_reaction(account: WhatsAppAccount, to_number: str, message_id: str, emoji: str) -> dict:
    """React to an existing message with an emoji."""
    return _post_message(account, {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "reaction",
        "reaction": {"message_id": message_id, "emoji": emoji},
    })


def send_location(
    account: WhatsAppAccount,
    to_number: str,
    latitude: float,
    longitude: float,
    name: str,
    address: str,
) -> dict:
    """Send a location pin."""
    return _post_message(account, {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "location",
        "location": {
            "latitude":  latitude,
            "longitude": longitude,
            "name":      name,
            "address":   address,
        },
    })


def get_business_profile(account: WhatsAppAccount) -> dict:
    """Fetch the WhatsApp Business Profile for this account."""
    url = (
        f"{GRAPH_API_BASE}/{account.phone_number_id}/whatsapp_business_profile"
        "?fields=about,address,description,email,websites,vertical,profile_picture_url"
    )
    headers = {"Authorization": f"Bearer {account.access_token}"}
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json().get("data", [{}])[0] if resp.json().get("data") else resp.json()


def update_business_profile(account: WhatsAppAccount, fields: dict) -> dict:
    """Update the WhatsApp Business Profile."""
    url = f"{GRAPH_API_BASE}/{account.phone_number_id}/whatsapp_business_profile"
    headers = {"Authorization": f"Bearer {account.access_token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", **fields}
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def mark_message_read(account: WhatsAppAccount, wa_message_id: str) -> None:
    """Mark an inbound WhatsApp message as read (shows double blue tick to sender)."""
    url = f"{GRAPH_API_BASE}/{account.phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {account.access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": wa_message_id,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(url, json=payload, headers=headers)
    except Exception as e:
        logger.warning(f"[WA] mark_read failed for {wa_message_id}: {e}")
