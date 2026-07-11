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
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.email_account import EmailAccount

logger = logging.getLogger("rdl_app_logger")

# Google retries undelivered pushes, and retries for the same account can arrive
# concurrently. Without serializing per-account, two overlapping requests both
# read the same stale watch_history_id, both fetch the same message range, and
# both run the email workflow on it — duplicate replies get sent to real leads.
_account_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_account_lock(email_address: str) -> threading.Lock:
    with _locks_guard:
        lock = _account_locks.get(email_address)
        if lock is None:
            lock = threading.Lock()
            _account_locks[email_address] = lock
        return lock


# This process runs with WEB_CONCURRENCY>1 uvicorn workers, each running its own
# copy of the FastAPI lifespan. Without cross-process serialization, every worker
# calls register_all_watches()/renew_expiring_watches() at (nearly) the same
# instant, and Gmail rejects the overlapping watch() calls for the same mailbox
# with "Only one user push notification client allowed per developer" — so the
# watch never gets registered and push notifications never arrive.
# A Postgres advisory lock serializes this across worker processes (and across
# containers, if ever scaled out): whichever worker gets there first registers
# watches for every account; the rest skip, since the first one already covered
# them all.
_WATCH_REGISTRATION_LOCK_KEY = 727100001


def _with_registration_lock(db: Session, label: str, fn) -> int:
    got_lock = db.execute(
        text("SELECT pg_try_advisory_lock(:key)"), {"key": _WATCH_REGISTRATION_LOCK_KEY}
    ).scalar()
    if not got_lock:
        logger.info(f"[GMAIL WEBHOOK] Another worker is already {label} — skipping")
        return 0
    try:
        return fn()
    finally:
        db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _WATCH_REGISTRATION_LOCK_KEY})


# ── Watch registration ─────────────────────────────────────────────────────────

def register_watch(db: Session, account: EmailAccount, topic_name: str) -> bool:
    """
    Register a Gmail push notification watch for `account`.
    Returns True on success, False on failure (token expired, API error, etc.).
    """
    from googleapiclient.errors import HttpError
    from app.services.email_account_service import get_gmail_service_for_account
    from app.services.gmail_service import ensure_labels_exist

    try:
        svc = get_gmail_service_for_account(db, account)
        ensure_labels_exist(svc, account_key=account.email_address)

        try:
            result = svc.users().watch(
                userId="me",
                body={
                    "topicName": topic_name,
                    "labelIds": ["INBOX"],
                    "labelFilterBehavior": "INCLUDE",
                },
            ).execute()
        except HttpError as e:
            # Gmail thinks a watch is already active on this mailbox — which happens
            # whenever we lose track of watch_history_id (e.g. it was never persisted
            # because an earlier registration attempt also failed) and retry watch()
            # without ever having called stop(). Gmail refuses a second concurrent
            # watch outright, so we must explicitly stop the old one before retrying,
            # or this account can never self-heal and silently stops receiving
            # notifications for good.
            if b"Only one user push notification client allowed" not in (e.content or b""):
                raise
            logger.warning(
                f"[GMAIL WEBHOOK] {account.email_address} already has an active watch — "
                "calling stop() and retrying"
            )
            svc.users().stop(userId="me").execute()
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


def _accounts_needing_watch(db: Session):
    """Active accounts with no watch, or one expiring within 25 hours.
    Accounts with a still-valid watch are excluded — Gmail's watch() API rejects
    a redundant re-registration on a mailbox that already has one active
    ("Only one user push notification client allowed per developer"), so calling
    it on a healthy watch only produces spurious errors without changing anything.
    """
    soon = datetime.now(timezone.utc) + timedelta(hours=25)
    return (
        db.query(EmailAccount)
        .filter(
            EmailAccount.is_active == True,
            (EmailAccount.watch_expiry == None) | (EmailAccount.watch_expiry < soon),
        )
        .all()
    )


def register_all_watches(db: Session) -> int:
    """Register watches for active accounts that don't already have a valid one.
    Returns count of successful registrations."""
    from app.core.config import settings
    topic = settings.GMAIL_PUBSUB_TOPIC
    if not topic:
        logger.warning("[GMAIL WEBHOOK] GMAIL_PUBSUB_TOPIC not configured — skipping watch registration")
        return 0

    def _do():
        accounts = _accounts_needing_watch(db)
        ok = 0
        for acct in accounts:
            if register_watch(db, acct, topic):
                ok += 1
        logger.info(f"[GMAIL WEBHOOK] Registered {ok}/{len(accounts)} watches")
        return ok

    return _with_registration_lock(db, "registering watches", _do)


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

    def _do():
        accounts = _accounts_needing_watch(db)
        renewed = 0
        for acct in accounts:
            if register_watch(db, acct, topic):
                renewed += 1
        if renewed:
            logger.info(f"[GMAIL WEBHOOK] Renewed {renewed} expiring watch(es)")
        return renewed

    return _with_registration_lock(db, "renewing watches", _do)


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
        # Verify signature/issuer/expiry via Google, but compare audience ourselves —
        # the GCP Pub/Sub subscription's configured audience has a trailing space baked
        # into every token it signs, which fails google-auth's strict equality check.
        idinfo = id_token.verify_oauth2_token(token, request)
        if idinfo.get("aud", "").strip() != expected_audience.strip():
            logger.warning(
                f"[GMAIL WEBHOOK] Token has wrong audience {idinfo.get('aud')!r}, "
                f"expected {expected_audience!r}"
            )
            return False
        return True
    except Exception as e:
        logger.warning(f"[GMAIL WEBHOOK] JWT verification failed: {e}")
        return False


GMAIL_NEW_EMAIL_CHANNEL = "gmail:new_email"


def _notify_owner_async(owner_id, message: dict) -> None:
    """Fan out a "new_email" event to every worker process via Redis pub/sub.

    This runs on a _webhook_executor worker thread (see app/routers/gmail.py),
    and the backend runs with multiple uvicorn worker *processes*
    (WEB_CONCURRENCY, see Dockerfile) — the owner's live WebSocket connection
    lives in the in-memory ConnectionManager of whichever process accepted it,
    which is very likely a different process than the one handling this
    webhook request. Publishing over Redis (instead of calling
    manager.notify_user directly) lets every process's own subscriber loop
    (see _gmail_redis_listener in app/main.py) deliver it locally to whichever
    one actually holds the connection.
    """
    import json
    from app.core.redis import get_sync_redis
    try:
        get_sync_redis().publish(
            GMAIL_NEW_EMAIL_CHANNEL,
            json.dumps({"owner_id": str(owner_id), "message": message}),
        )
    except Exception:
        logger.warning("[GMAIL WEBHOOK] Failed to publish new_email event", exc_info=True)


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

    # Serialize per-account: Google retries overlap, and without this lock two
    # concurrent requests both read the same stale watch_history_id, both fetch
    # the same message range, and both send duplicate replies to the same lead.
    with _get_account_lock(email_address):
        # Find the account. with_for_update() takes a Postgres row lock so a second
        # worker PROCESS (this backend runs with WEB_CONCURRENCY>1) handling an
        # overlapping/retried notification for the same account blocks here until
        # this transaction commits below, instead of racing on the same stale
        # watch_history_id — the in-process lock above only protects against
        # concurrent threads within a single worker, not across processes.
        account = db.query(EmailAccount).filter(
            EmailAccount.email_address == email_address,
            EmailAccount.is_active == True,
        ).with_for_update().first()

        if not account:
            logger.warning(f"[GMAIL WEBHOOK] No active account for {email_address}")
            return 0

        start_history_id = account.watch_history_id
        if not start_history_id:
            # No stored historyId — register watch to get one and bail (next notification will work)
            from app.core.config import settings
            register_watch(db, account, settings.GMAIL_PUBSUB_TOPIC)
            return 0

        # Google's retries aren't strictly ordered — a stale/out-of-order redelivery
        # can carry an older historyId than one we've already advanced past. Bail
        # early rather than rewinding the watermark, which would make every message
        # since look "new" again and re-run (and re-send replies for) all of them.
        try:
            if int(new_history_id) <= int(start_history_id):
                logger.info(
                    f"[GMAIL WEBHOOK] Ignoring stale historyId {new_history_id} "
                    f"(already at {start_history_id}) for {email_address}"
                )
                return 0
        except ValueError:
            pass  # non-numeric historyId (shouldn't happen) — fall through as before

        # Fetch message IDs via history.list
        try:
            svc = get_gmail_service_for_account(db, account)
            message_ids, latest_history_id = _fetch_new_message_ids(svc, start_history_id)
        except Exception as e:
            logger.error(f"[GMAIL WEBHOOK] history.list failed for {email_address}: {e}")
            return 0

        # Advance the watermark to Gmail's own history.list() checkpoint, not the
        # notification's historyId (see _fetch_new_message_ids docstring for why).
        account.watch_history_id = latest_history_id
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

        if processed:
            _notify_owner_async(account.owner_id, {
                "type": "new_email",
                "account": account.email_address,
                "count": processed,
            })

        logger.info(f"[GMAIL WEBHOOK] {email_address}: {processed}/{len(message_ids)} messages processed")
        return processed


def _fetch_new_message_ids(svc, start_history_id: str) -> tuple[list[str], str]:
    """
    Call users.history().list() from start_history_id, return (message_ids, latest_history_id).
    latest_history_id is Gmail's own checkpoint from the response — the correct value to persist
    as the new watermark. The historyId embedded in a Pub/Sub notification is just whichever
    checkpoint Google happened to attach to that particular push; during a retry backlog these
    arrive out of order, so using it as the watermark can move it backward and make already
    -processed messages look new again on the next call.
    """
    message_ids = []
    page_token = None
    latest_history_id = start_history_id

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

        if response.get("historyId"):
            latest_history_id = response["historyId"]

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return message_ids, latest_history_id
