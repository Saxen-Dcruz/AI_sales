import base64
import logging
import pickle
import re
import uuid
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

# Per-account label caches: email_address → {label_name: label_id}
_label_caches: dict[str, dict[str, str]] = {}
_label_cache: dict[str, str] = {}  # backward-compat alias for single-account code


def _load_credentials():
    """Load credentials from the legacy gmail_token.json file (single-account fallback)."""
    if not GMAIL_TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"Gmail token not found at {GMAIL_TOKEN_PATH}. "
            "Either run app/scripts/google_auth.py or add an account via Settings."
        )
    with open(GMAIL_TOKEN_PATH, "rb") as f:
        creds = pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(GMAIL_TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
    return creds


def get_gmail_service(account=None):
    """
    Return a Gmail API service instance.
    - account: EmailAccount model instance → use DB-stored token
    - account=None → fall back to legacy gmail_token.json
    """
    if account is not None:
        from app.services.email_account_service import get_gmail_service_for_account
        from app.database.core import SessionLocal
        with SessionLocal() as db:
            return get_gmail_service_for_account(db, account)
    return build("gmail", "v1", credentials=_load_credentials(), cache_discovery=False)


# ── Label management ──────────────────────────────────────────────────────────

def _fetch_all_labels(service) -> dict[str, str]:
    result = service.users().labels().list(userId="me").execute()
    return {lbl["name"]: lbl["id"] for lbl in result.get("labels", [])}


def ensure_labels_exist(service, account_key: str = "__default__") -> None:
    """Ensure RDL/* labels exist. Uses per-account cache keyed by email address."""
    global _label_cache
    cache = _label_caches.setdefault(account_key, {})
    if cache:
        return
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
            logger.info(f"[{account_key}] Created Gmail label: {label_name}")
    _label_caches[account_key] = existing
    if account_key == "__default__":
        _label_cache = existing   # keep backward-compat alias


def get_label_id(service, label_name: str, account_key: str = "__default__") -> Optional[str]:
    cache = _label_caches.get(account_key, {})
    if not cache:
        ensure_labels_exist(service, account_key)
        cache = _label_caches.get(account_key, {})
    return cache.get(label_name)


# ── Email fetching ────────────────────────────────────────────────────────────

def fetch_thread_context(service, thread_id: str, current_message_id: str) -> Optional[str]:
    """
    For reply emails: return the body of the original message in the thread so
    the classifier can understand the full conversation context, not just the reply.
    Returns None if the thread has only one message or on any error.
    """
    try:
        thread = service.users().threads().get(
            userId="me", id=thread_id, format="full"
        ).execute()
        messages = thread.get("messages", [])
        # Take the earliest message that isn't the current reply
        others = [m for m in messages if m["id"] != current_message_id]
        if not others:
            return None
        parsed = parse_message(others[0])
        return (parsed.get("body_text") or "")[:2000] or None
    except Exception as e:
        logger.warning(f"[GMAIL] Could not fetch thread context for {thread_id}: {e}")
        return None


def fetch_messages_since(service, since_dt, max_results: int = 500) -> list[dict]:
    """
    Fetch all INBOX messages received after since_dt. Used for initial historical sync.
    Uses 'in:inbox' (not 'in:anywhere') so sent/spam/trash are excluded — only inbound
    emails that arrived in the inbox are returned. The regular poller handles new unread
    messages going forward; this function back-fills historical ones.
    """
    import math
    epoch = math.floor(since_dt.timestamp())
    # in:inbox after:<epoch> — inbox only, not sent/spam/trash
    query = f"in:inbox after:{epoch}"
    all_ids = []
    page_token = None
    while len(all_ids) < max_results:
        kwargs = dict(userId="me", q=query, maxResults=min(500, max_results - len(all_ids)))
        if page_token:
            kwargs["pageToken"] = page_token
        resp = service.users().messages().list(**kwargs).execute()
        all_ids.extend(resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    full = []
    for msg in all_ids:
        try:
            full.append(
                service.users().messages().get(
                    userId="me", id=msg["id"], format="full"
                ).execute()
            )
        except HttpError as e:
            logger.warning(f"[SYNC HISTORY] Failed to fetch message {msg['id']}: {e}")
    return full


def fetch_unread_messages(service, max_results: int = 20) -> list[dict]:
    """
    Return list of full message dicts for recent inbox emails.

    NOTE: This used to filter by labelIds=['INBOX', 'UNREAD'], which silently
    misses any message that was auto-marked-read by Gmail (e.g. when the user
    opens the thread in Gmail web UI, all messages in that thread become
    'read' and the poller never sees subsequent replies).

    Now we fetch recent INBOX messages regardless of read state. Caller is
    expected to dedupe against gmail_message_id in the DB so already-processed
    emails are skipped — the workflow's persist node already does this.
    """
    resp = service.users().messages().list(
        userId="me",
        q="in:inbox newer_than:7d",
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

    Gmail wraps the attribution block across two lines:
        On Wed, Apr 29, 2026 at 3:06 PM Sender <email@x.com>
        wrote: original text

    The old single-line regex missed this. We now stop at the first line that
    looks like a Gmail attribution header ('On [Weekday/Day], ...').
    """
    lines = body.split('\n')
    result = []
    for line in lines:
        # Gmail attribution starts with "On Mon," / "On 29 Apr" etc.
        if re.match(r'^On [A-Z][a-z]{2},?\s+', line):
            break
        # RFC 2822 quoted lines start with >
        if line.lstrip().startswith('>'):
            continue
        result.append(line)
    return '\n'.join(result).strip()


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
        "rfc_message_id": headers.get("message-id", ""),  # RFC 2822 Message-ID for In-Reply-To
        "rfc_references": headers.get("references", ""),  # full References chain for threading
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

def create_draft(service, to: str, subject: str, body: str,
                 thread_id: Optional[str] = None, reply_to_message_id: Optional[str] = None,
                 references: Optional[str] = None) -> dict:
    """Save a draft in Gmail. Returns the draft dict + a 'tracking_token' key (uuid str)
    that is already embedded as a pixel in the HTML body — caller should persist this on
    the Email row so opens can be attributed."""
    token = str(uuid.uuid4())
    msg = _build_mime(to, subject, body, reply_to_message_id=reply_to_message_id,
                      references=references, tracking_token=token)
    draft_body: dict = {"message": {"raw": msg}}
    if thread_id:
        draft_body["message"]["threadId"] = thread_id
    draft = service.users().drafts().create(userId="me", body=draft_body).execute()
    logger.info(f"Gmail draft created: {draft['id']} → {to}")
    draft["tracking_token"] = token
    return draft


def send_draft(service, draft_id: str) -> dict:
    """Send an existing Gmail draft by its draft id."""
    sent = service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
    logger.info(f"Gmail draft sent: {draft_id}")
    return sent


def send_email(service, to: str, subject: str, body: str,
               thread_id: Optional[str] = None, reply_to_message_id: Optional[str] = None,
               references: Optional[str] = None) -> dict:
    """Send immediately. Returns Gmail API result + 'tracking_token' key (uuid str) already
    embedded in the HTML body — caller should persist this on the outbound Email row."""
    token = str(uuid.uuid4())
    raw = _build_mime(to, subject, body, reply_to_message_id=reply_to_message_id,
                      references=references, tracking_token=token)
    msg_body: dict = {"raw": raw}
    if thread_id:
        msg_body["threadId"] = thread_id
    sent = service.users().messages().send(userId="me", body=msg_body).execute()
    logger.info(f"Email sent: {sent['id']} → {to}")
    sent["tracking_token"] = token
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


def _tracking_pixel_html(tracking_token: str) -> str:
    """Return a 1×1 transparent pixel img tag for open-tracking."""
    url = f"{settings.PUBLIC_API_URL}/gmail/track/open/{tracking_token}.png"
    return f'<img src="{url}" width="1" height="1" style="display:none;border:0" alt="">'


def _build_mime(to: str, subject: str, body: str, reply_to_message_id: Optional[str] = None,
                references: Optional[str] = None, tracking_token: Optional[str] = None) -> str:
    msg = MIMEMultipart("alternative")
    msg["to"] = to
    msg["subject"] = subject
    if reply_to_message_id:
        msg["In-Reply-To"] = reply_to_message_id
        # Build the full References chain: prior chain + this message's ID
        ref_chain = f"{references} {reply_to_message_id}".strip() if references else reply_to_message_id
        msg["References"] = ref_chain
    # plain text fallback (strips markdown syntax for clients that don't render HTML)
    plain = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', body)
    msg.attach(MIMEText(plain, "plain"))
    # HTML version — rendered in Gmail and most modern clients. Append tracking pixel if provided.
    html_body = _markdown_to_html(body)
    if tracking_token:
        html_body += _tracking_pixel_html(tracking_token)
    msg.attach(MIMEText(html_body, "html"))
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()
