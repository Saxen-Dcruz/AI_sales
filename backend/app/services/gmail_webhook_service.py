"""
Gmail Push Notifications via Google Cloud Pub/Sub.

Flow:
  1. On startup: `register_all_watches(db)` calls Gmail users.watch() for every
     active EmailAccount, storing the returned historyId + expiry in the DB.
  2. Gmail detects a new message → publishes a Pub/Sub notification to the
     configured topic → Pub/Sub pushes to POST /gmail/webhook.
  3. `process_pubsub_notification(db, payload)` decodes the notification,
     calls users.history().list() to get the new message IDs, fetches each
     message, and runs it through `run_email_workflow`.
  4. `renew_expiring_watches(db)` is called periodically; renews any watch
     that expires within the next 25 hours.

Pub/Sub push payload format (from Google):
  {
    "message": {
      "data": "<base64({"emailAddress": "user@example.com", "historyId": "1234"})>",
      "messageId": "...",
      "publishTime": "..."
    },
    "subscription": "projects/PROJECT/subscriptions/SUB"
  }
"""
import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.email_account import EmailAccount

logger = logging.getLogger("rdl_app_logger")


# ── Watch registration ─────────────────────────────────────────────────────────

def register_watch(db: Session, account: EmailAccount, topic_name: str) -> bool:
    """
    Register a Gmail push notification watch for `account`.
    Returns True on success, False on failure (token expired, API error, etc.).
    """
    from app.services.email_account_service import get_gmail_service_for_account
    from app.services.gmail_service import ensure_labels_exist

    try:
        svc = get_gmail_service_for_account(db, account)
        ensure_labels_exist(svc, account_key=account.email_address)

        result = svc.users().watch(
            userId="me",
            body={
                "topicName": topic_name,
                "labelIds": ["INBOX"],
                "labelFilterBehavior": "INCLUDE",
            },
        ).execute()

        history_id  = str(result.get("historyId", ""))
        expiry_ms   = int(result.get("expiration", 0))
        expiry_dt   = datetime.fromtimestamp(expiry_ms / 1000, tz=timezone.utc) if expiry_ms else None

        account.watch_history_id = history_id
        account.watch_expiry     = expiry_dt
        db.commit()

        logger.info(
            f"[GMAIL WEBHOOK] watch registered: {account.email_address} "
            f"historyId={history_id} expires={expiry_dt}"
        )
        return True

    except Exception as e:
        logger.error(f"[GMAIL WEBHOOK] watch registration failed for {account.email_address}: {e}")
        return False


def register_all_watches(db: Session) -> int:
    """Register watches for all active accounts. Returns count of successful registrations."""
    from app.core.config import settings
    topic = settings.GMAIL_PUBSUB_TOPIC
    if not topic:
        logger.warning("[GMAIL WEBHOOK] GMAIL_PUBSUB_TOPIC not configured — skipping watch registration")
        return 0

    accounts = db.query(EmailAccount).filter(EmailAccount.is_active == True).all()
    ok = 0
    for acct in accounts:
        if register_watch(db, acct, topic):
            ok += 1
    logger.info(f"[GMAIL WEBHOOK] Registered {ok}/{len(accounts)} watches")
    return ok


def renew_expiring_watches(db: Session) -> int:
    """
    Renew watches that expire within the next 25 hours.
    Call this on a daily schedule (or hourly — it's idempotent).
    Returns count of renewed watches.
    """
    from app.core.config import settings
    topic = settings.GMAIL_PUBSUB_TOPIC
    if not topic:
        return 0

    soon = datetime.now(timezone.utc) + timedelta(hours=25)
    accounts = (
        db.query(EmailAccount)
        .filter(
            EmailAccount.is_active == True,
            (EmailAccount.watch_expiry == None) | (EmailAccount.watch_expiry < soon),
        )
        .all()
    )
    renewed = 0
    for acct in accounts:
        if register_watch(db, acct, topic):
            renewed += 1
    if renewed:
        logger.info(f"[GMAIL WEBHOOK] Renewed {renewed} expiring watch(es)")
    return renewed


# ── Pub/Sub notification processing ───────────────────────────────────────────

def verify_pubsub_token(auth_header: str, expected_audience: str) -> bool:
    """
    Verify the OIDC Bearer token that Pub/Sub attaches to every push.
    Returns True if the token is valid and the audience matches.
    Falls back to True if GMAIL_PUBSUB_AUDIENCE is not configured (dev mode).
    """
    if not expected_audience:
        logger.debug("[GMAIL WEBHOOK] No audience configured — skipping JWT verification (dev mode)")
        return True

    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("[GMAIL WEBHOOK] Missing or malformed Authorization header")
        return False

    token = auth_header[7:]
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        request = google_requests.Request()
        id_token.verify_oauth2_token(token, request, audience=expected_audience)
        return True
    except Exception as e:
        logger.warning(f"[GMAIL WEBHOOK] JWT verification failed: {e}")
        return False


def process_pubsub_notification(db: Session, payload: dict) -> int:
    """
    Handle one Pub/Sub push payload — decode it, fetch new messages via history API,
    run each through the email workflow.
    Returns the number of new messages processed.
    """
    from app.services.gmail_service import get_gmail_service
    from app.services.email_account_service import get_gmail_service_for_account
    from app.services.workflows.email_workflow import run_email_workflow

    # Decode the Pub/Sub message
    message = payload.get("message", {})
    raw_data = message.get("data", "")
    if not raw_data:
        logger.warning("[GMAIL WEBHOOK] Empty Pub/Sub message data")
        return 0

    try:
        decoded = json.loads(base64.b64decode(raw_data).decode("utf-8"))
    except Exception as e:
        logger.error(f"[GMAIL WEBHOOK] Failed to decode Pub/Sub data: {e}")
        return 0

    email_address = decoded.get("emailAddress", "")
    new_history_id = str(decoded.get("historyId", ""))

    if not email_address or not new_history_id:
        logger.warning(f"[GMAIL WEBHOOK] Missing emailAddress or historyId in payload: {decoded}")
        return 0

    logger.info(f"[GMAIL WEBHOOK] Notification for {email_address} historyId={new_history_id}")

    # Find the account
    account = db.query(EmailAccount).filter(
        EmailAccount.email_address == email_address,
        EmailAccount.is_active == True,
    ).first()

    if not account:
        logger.warning(f"[GMAIL WEBHOOK] No active account for {email_address}")
        return 0

    start_history_id = account.watch_history_id
    if not start_history_id:
        # No stored historyId — register watch to get one and bail (next notification will work)
        from app.core.config import settings
        register_watch(db, account, settings.GMAIL_PUBSUB_TOPIC)
        return 0

    # Fetch message IDs via history.list
    try:
        svc = get_gmail_service_for_account(db, account)
        message_ids = _fetch_new_message_ids(svc, start_history_id)
    except Exception as e:
        logger.error(f"[GMAIL WEBHOOK] history.list failed for {email_address}: {e}")
        return 0

    # Update stored historyId to the latest one from the notification
    account.watch_history_id = new_history_id
    db.commit()

    if not message_ids:
        logger.info(f"[GMAIL WEBHOOK] No new INBOX messages for {email_address}")
        return 0

    # Fetch full messages and run through workflow
    processed = 0
    for msg_id in message_ids:
        try:
            raw = svc.users().messages().get(userId="me", id=msg_id, format="full").execute()
            result = run_email_workflow(
                db, raw,
                account_id=str(account.id),
                account_email=account.email_address,
            )
            if result:
                processed += 1
                logger.info(f"[GMAIL WEBHOOK] Processed msg {msg_id} for {email_address}")
        except Exception as e:
            logger.error(f"[GMAIL WEBHOOK] Failed to process msg {msg_id}: {e}", exc_info=True)

    logger.info(f"[GMAIL WEBHOOK] {email_address}: {processed}/{len(message_ids)} messages processed")
    return processed


def _fetch_new_message_ids(svc, start_history_id: str) -> list[str]:
    """
    Call users.history().list() from start_history_id, return IDs of new INBOX messages.
    Handles pagination automatically.
    """
    message_ids = []
    page_token = None

    while True:
        kwargs = {
            "userId":         "me",
            "startHistoryId": start_history_id,
            "historyTypes":   ["messageAdded"],
            "labelId":        "INBOX",
        }
        if page_token:
            kwargs["pageToken"] = page_token

        try:
            response = svc.users().history().list(**kwargs).execute()
        except Exception as e:
            # historyId too old (410 Gone) — force re-registration on next startup
            logger.warning(f"[GMAIL WEBHOOK] history.list error (historyId may be stale): {e}")
            break

        for entry in response.get("history", []):
            for msg in entry.get("messagesAdded", []):
                labels = msg.get("message", {}).get("labelIds", [])
                msg_id = msg.get("message", {}).get("id")
                if msg_id and "INBOX" in labels:
                    message_ids.append(msg_id)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return message_ids
