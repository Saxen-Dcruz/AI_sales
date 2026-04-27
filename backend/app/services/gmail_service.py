import base64
import logging
import pickle
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings

logger = logging.getLogger("rdl_app_logger")

GMAIL_TOKEN_PATH = Path("gmail_token.json")

# Labels we create/manage in Gmail
MANAGED_LABELS = ["RDL/Sales", "RDL/Support", "RDL/Grievance", "RDL/Transactional", "RDL/Promotional", "RDL/Personal"]

_label_cache: dict[str, str] = {}  # name → Gmail label id


def _load_credentials():
    if not GMAIL_TOKEN_PATH.exists():
        raise FileNotFoundError(f"Gmail token not found at {GMAIL_TOKEN_PATH}. Run app/scripts/google_auth.py first.")
    with open(GMAIL_TOKEN_PATH, "rb") as f:
        creds = pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(GMAIL_TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
    return creds


def get_gmail_service():
    return build("gmail", "v1", credentials=_load_credentials(), cache_discovery=False)


# ── Label management ──────────────────────────────────────────────────────────

def _fetch_all_labels(service) -> dict[str, str]:
    result = service.users().labels().list(userId="me").execute()
    return {lbl["name"]: lbl["id"] for lbl in result.get("labels", [])}


def ensure_labels_exist(service) -> None:
    global _label_cache
    existing = _fetch_all_labels(service)
    for label_name in MANAGED_LABELS:
        if label_name not in existing:
            body = {
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            }
            created = service.users().labels().create(userId="me", body=body).execute()
            existing[label_name] = created["id"]
            logger.info(f"Created Gmail label: {label_name}")
    _label_cache = existing


def get_label_id(service, label_name: str) -> Optional[str]:
    if not _label_cache:
        ensure_labels_exist(service)
    return _label_cache.get(label_name)


# ── Email fetching ────────────────────────────────────────────────────────────

def fetch_unread_messages(service, max_results: int = 20) -> list[dict]:
    """Return list of full message dicts for unread inbox emails."""
    resp = service.users().messages().list(
        userId="me",
        labelIds=["INBOX", "UNREAD"],
        maxResults=max_results,
    ).execute()
    messages = resp.get("messages", [])
    full = []
    for msg in messages:
        try:
            full.append(
                service.users().messages().get(
                    userId="me", id=msg["id"], format="full"
                ).execute()
            )
        except HttpError as e:
            logger.warning(f"Failed to fetch message {msg['id']}: {e}")
    return full


def _strip_quoted_reply(body: str) -> str:
    """Strip Gmail reply-chain quotes so only the new message text is processed.
    Removes 'On [date] ... wrote:' blocks and lines starting with '>'.
    """
    # Gmail quote marker: "On Mon, 25 Apr 2026 at 1:26 AM ... wrote:"
    stripped = re.split(r'\nOn .{10,80}wrote:\s*\n', body)[0]
    # Also remove lines that start with > (RFC 2822 quoted text)
    lines = [l for l in stripped.split('\n') if not l.lstrip().startswith('>')]
    return '\n'.join(lines).strip()


def parse_message(message: dict) -> dict:
    """Extract structured fields from a raw Gmail message dict."""
    headers = {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}
    sender = headers.get("from", "")
    recipients = [r.strip() for r in headers.get("to", "").split(",") if r.strip()]
    subject = headers.get("subject", "")
    date_str = headers.get("date", "")

    body_text, body_html = _extract_body(message["payload"])
    # Strip quoted previous messages — only keep the new text the sender wrote
    body_text = _strip_quoted_reply(body_text) if body_text else ""

    return {
        "gmail_message_id": message["id"],
        "gmail_thread_id": message.get("threadId"),
        "sender": sender,
        "recipients": recipients,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "date_str": date_str,
    }


def _extract_body(payload: dict) -> tuple[str, str]:
    text, html = "", ""
    mime = payload.get("mimeType", "")

    if mime == "text/plain":
        text = _decode_data(payload.get("body", {}).get("data", ""))
    elif mime == "text/html":
        html = _decode_data(payload.get("body", {}).get("data", ""))
    elif "multipart" in mime:
        for part in payload.get("parts", []):
            t, h = _extract_body(part)
            text = text or t
            html = html or h
    return text, html


def _decode_data(data: str) -> str:
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_email_address(raw: str) -> str:
    """Pull bare email address from 'Name <email>' format."""
    match = re.search(r"<(.+?)>", raw)
    return match.group(1).strip() if match else raw.strip()


# ── Label application ─────────────────────────────────────────────────────────

def apply_label_to_message(service, message_id: str, label_name: str) -> None:
    label_id = get_label_id(service, label_name)
    if not label_id:
        logger.warning(f"Label '{label_name}' not found — skipping apply")
        return
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": [label_id]},
    ).execute()


def mark_as_read(service, message_id: str) -> None:
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()


def archive_message(service, message_id: str) -> None:
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": ["INBOX"]},
    ).execute()


# ── Draft management ──────────────────────────────────────────────────────────

def create_draft(service, to: str, subject: str, body: str, thread_id: Optional[str] = None) -> dict:
    """Save a draft in Gmail. Returns the draft object (includes draft id)."""
    msg = _build_mime(to, subject, body)
    draft_body: dict = {"message": {"raw": msg}}
    if thread_id:
        draft_body["message"]["threadId"] = thread_id
    draft = service.users().drafts().create(userId="me", body=draft_body).execute()
    logger.info(f"Gmail draft created: {draft['id']} → {to}")
    return draft


def send_draft(service, draft_id: str) -> dict:
    """Send an existing Gmail draft by its draft id."""
    sent = service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
    logger.info(f"Gmail draft sent: {draft_id}")
    return sent


def send_email(service, to: str, subject: str, body: str, thread_id: Optional[str] = None) -> dict:
    """Send immediately without saving a draft."""
    raw = _build_mime(to, subject, body)
    msg_body: dict = {"raw": raw}
    if thread_id:
        msg_body["threadId"] = thread_id
    sent = service.users().messages().send(userId="me", body=msg_body).execute()
    logger.info(f"Email sent: {sent['id']} → {to}")
    return sent


def _markdown_to_html(text: str) -> str:
    """Convert basic markdown to HTML for email rendering."""
    import re
    # Bold **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Bullet lines: *   text  or  -  text
    text = re.sub(r'^\*\s{1,4}(.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'^-\s{1,4}(.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    # Numbered items: 1. text
    text = re.sub(r'^\d+\.\s+(.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    # Wrap consecutive <li> blocks in <ul>
    text = re.sub(r'((?:<li>.+</li>\n?)+)', r'<ul>\1</ul>', text)
    # Paragraphs: blank line → new paragraph
    paragraphs = re.split(r'\n{2,}', text)
    html_parts = []
    for p in paragraphs:
        p = p.strip().replace('\n', '<br>')
        if p:
            html_parts.append(f'<p>{p}</p>' if not p.startswith('<ul>') else p)
    body_html = '\n'.join(html_parts)
    return (
        '<div style="font-family:Arial,sans-serif;font-size:14px;'
        'line-height:1.7;color:#333;max-width:700px">'
        f'{body_html}</div>'
    )


def _build_mime(to: str, subject: str, body: str) -> str:
    msg = MIMEMultipart("alternative")
    msg["to"] = to
    msg["subject"] = subject
    # plain text fallback (strips markdown syntax for clients that don't render HTML)
    plain = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', body)
    msg.attach(MIMEText(plain, "plain"))
    # HTML version — rendered in Gmail and most modern clients
    msg.attach(MIMEText(_markdown_to_html(body), "html"))
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()
