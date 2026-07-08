"""
Multi-account Gmail management service.
Handles OAuth token storage, account CRUD, and per-account credential loading.
"""
import base64
import logging
import os
import pickle
from typing import Optional
from uuid import UUID

# Allow Google to return a broader scope than requested (e.g. calendar scopes
# included via include_granted_scopes=true) without requests_oauthlib raising
# a scope-mismatch Warning as an exception.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session

from app.models.email_account import EmailAccount

logger = logging.getLogger("rdl_app_logger")

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]

# Requested together so a rep only has to go through the consent screen once
# to unlock both Gmail sending and Calendar invites under their own identity.
OAUTH_SCOPES = GMAIL_SCOPES + CALENDAR_SCOPES


# ── Token encoding ────────────────────────────────────────────────────────────

def _encode_token(creds) -> str:
    return base64.b64encode(pickle.dumps(creds)).decode()


def _decode_token(token_data: str):
    return pickle.loads(base64.b64decode(token_data.encode()))


# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_accounts(db: Session, owner_id: Optional[UUID] = None) -> list[EmailAccount]:
    q = db.query(EmailAccount)
    if owner_id is not None:
        q = q.filter(EmailAccount.owner_id == owner_id)
    return q.order_by(EmailAccount.is_primary.desc(), EmailAccount.created_at).all()


def get_account(db: Session, account_id: UUID) -> Optional[EmailAccount]:
    return db.query(EmailAccount).filter(EmailAccount.id == account_id).first()


def get_account_by_email(db: Session, email: str) -> Optional[EmailAccount]:
    return db.query(EmailAccount).filter(EmailAccount.email_address == email).first()


def get_primary_account(db: Session) -> Optional[EmailAccount]:
    return db.query(EmailAccount).filter(
        EmailAccount.is_primary == True, EmailAccount.is_active == True
    ).first()


def get_active_accounts(db: Session) -> list[EmailAccount]:
    return db.query(EmailAccount).filter(EmailAccount.is_active == True).all()


def update_account(db: Session, account_id: UUID, payload) -> Optional[EmailAccount]:
    account = get_account(db, account_id)
    if not account:
        return None
    data = payload.model_dump(exclude_none=True)
    # If setting this account as primary, clear all others first
    if data.get("is_primary"):
        db.query(EmailAccount).update({"is_primary": False})
    for k, v in data.items():
        setattr(account, k, v)
    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, account_id: UUID, archive_emails: bool = True) -> bool:
    account = get_account(db, account_id)
    if not account:
        return False
    from app.models.communication import Email, EmailStatus
    if archive_emails:
        # Mark all emails from this account as archived so they don't pollute
        # the active inbox or analytics after the account is removed.
        db.query(Email).filter(
            Email.account_id == account_id
        ).update(
            {"status": EmailStatus.ARCHIVED, "account_id": None},
            synchronize_session=False,
        )
    else:
        # Nullify FK only — emails remain visible as historical records
        db.query(Email).filter(
            Email.account_id == account_id
        ).update({"account_id": None}, synchronize_session=False)
    db.delete(account)
    db.commit()
    logger.info(
        f"[EMAIL ACCOUNTS] Deleted {account.email_address} — "
        f"{'archived' if archive_emails else 'kept'} associated emails"
    )
    return True


# ── OAuth flow ────────────────────────────────────────────────────────────────

def _get_flow(redirect_uri: str) -> Flow:
    from app.core.config import settings as cfg
    client_config = {
        "web": {
            "client_id":     cfg.GOOGLE_CLIENT_ID,
            "client_secret": cfg.GOOGLE_CLIENT_SECRET,
            "redirect_uris": [redirect_uri],
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
        }
    }
    return Flow.from_client_config(client_config, scopes=OAUTH_SCOPES, redirect_uri=redirect_uri)


def _redis_client():
    from app.core.config import settings as cfg
    import redis
    return redis.Redis(host=cfg.REDIS_HOST, port=cfg.REDIS_PORT, db=2, decode_responses=True)


def get_auth_url(redirect_uri: str, owner_id: Optional[UUID] = None) -> str:
    # autogenerate_code_verifier=True is the default in google-auth-oauthlib >= 1.0,
    # so flow.code_verifier is always set after authorization_url() is called.
    # Store it in Redis keyed by state so the callback can retrieve it.
    flow = _get_flow(redirect_uri)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    if flow.code_verifier:
        _redis_client().setex(f"oauth_pkce:{state}", 600, flow.code_verifier)
    if owner_id is not None:
        _redis_client().setex(f"oauth_owner:{state}", 600, str(owner_id))
    return auth_url


def exchange_code_and_save(
    db: Session,
    code: str,
    redirect_uri: str,
    state: str = None,
    added_by: str = "admin",
    owner_id: Optional[UUID] = None,
) -> EmailAccount:
    """Exchange OAuth authorization code for credentials, fetch email, store in DB.

    `owner_id` must be the UUID of the app user who connected this Gmail account.
    Required when owner_id is enforced NOT NULL. Each regular user may connect at
    most one Gmail account (a second attempt raises ValueError); super-admins are
    exempt and may connect any number.
    """
    flow = _get_flow(redirect_uri)
    # Retrieve PKCE code_verifier from Redis
    code_verifier = None
    if state:
        code_verifier = _redis_client().get(f"oauth_pkce:{state}")
        if code_verifier:
            _redis_client().delete(f"oauth_pkce:{state}")
            flow.code_verifier = code_verifier
        # Also recover owner_id stored in Redis alongside the PKCE verifier
        if owner_id is None:
            stored = _redis_client().get(f"oauth_owner:{state}")
            if stored:
                _redis_client().delete(f"oauth_owner:{state}")
                owner_id = UUID(stored)
    flow.fetch_token(code=code)
    creds = flow.credentials

    from googleapiclient.discovery import build
    oauth2_service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
    user_info = oauth2_service.userinfo().get().execute()
    email_address = user_info["email"]
    display_name = user_info.get("name", email_address)

    # Account already exists → refresh token (ownership stays as-is)
    existing = get_account_by_email(db, email_address)
    if existing:
        existing.token_data = _encode_token(creds)
        existing.scopes = list(creds.scopes or [])
        existing.is_active = True
        if owner_id and not existing.owner_id:
            existing.owner_id = owner_id
        db.commit()
        db.refresh(existing)
        _relink_orphaned_emails(db, existing)
        logger.info(f"[EMAIL ACCOUNTS] Token refreshed for {email_address}")
        return existing

    # 1-account-per-user cap: regular users may not connect more than one account.
    # Super-admins are exempt — they can connect and manage every account.
    if owner_id is not None:
        from app.models.user import User
        owner = db.query(User).filter(User.id == owner_id).first()
        if not (owner and owner.is_superuser):
            owns = db.query(EmailAccount).filter(EmailAccount.owner_id == owner_id).count()
            if owns >= 1:
                raise ValueError(
                    f"Each user may connect at most one Gmail account. "
                    f"Remove your existing account first."
                )

    is_first = db.query(EmailAccount).count() == 0
    account = EmailAccount(
        email_address=email_address,
        display_name=display_name,
        token_data=_encode_token(creds),
        is_active=True,
        is_primary=is_first,
        scopes=list(creds.scopes or []),
        added_by=added_by,
        owner_id=owner_id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    _relink_orphaned_emails(db, account)
    logger.info(f"[EMAIL ACCOUNTS] Added new account: {email_address} (owner={owner_id})")
    return account


def _restore_status_after_unarchive(email) -> "EmailStatus":
    """Best-effort status to restore an ARCHIVED email to, since the pre-archive
    status wasn't preserved. Inferred from signals still on the row:
    tracked/opened → it was sent (REPLIED); flagged for a human →
    PENDING_HUMAN; otherwise NEW — deliberately not DRAFT_READY even if an
    AI draft is present, so a batch of stale reconnected drafts doesn't flood
    the pending-approval queue. The email (and any unresolved knowledge gap
    on it) is still visible/unarchived; a rep can act on it manually."""
    from app.models.communication import EmailStatus
    if email.opened_at or email.open_count:
        return EmailStatus.REPLIED
    if email.needs_human:
        return EmailStatus.PENDING_HUMAN
    return EmailStatus.NEW


def _relink_orphaned_emails(db: Session, account: "EmailAccount") -> int:
    """
    Re-link emails that have account_email matching this account but account_id=NULL.
    This happens when an account is deleted (FK SET NULL) then re-added with a new UUID.
    Also un-archives emails that were archived during the delete if the account is re-added.
    """
    from app.models.communication import Email, EmailStatus
    matches = db.query(Email).filter(
        Email.account_email == account.email_address,
        Email.account_id.is_(None),
    ).all()
    for email in matches:
        email.account_id = account.id
        if email.status == EmailStatus.ARCHIVED:
            email.status = _restore_status_after_unarchive(email)
    updated = len(matches)
    if updated:
        logger.info(f"[EMAIL ACCOUNTS] Re-linked {updated} orphaned emails to {account.email_address}")
        db.commit()
    return updated


# ── Credential loading ────────────────────────────────────────────────────────

def load_credentials_for_account(db: Session, account: EmailAccount):
    """
    Load and auto-refresh OAuth credentials for a specific account.
    Raises ValueError if the stored token is invalid (corrupt / test stub / wrong format).
    The caller should catch this and deactivate the account.
    """
    try:
        creds = _decode_token(account.token_data)
    except Exception as e:
        # Token is corrupt or was created with a class not available at runtime.
        # Deactivate the account so the poller stops trying to use it.
        logger.warning(f"[EMAIL ACCOUNTS] Invalid token for {account.email_address} — deactivating: {e}")
        account.is_active = False
        db.commit()
        raise ValueError(f"Invalid token for {account.email_address}: {e}") from e

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        account.token_data = _encode_token(creds)
        db.commit()
    return creds


def get_gmail_service_for_account(db: Session, account: EmailAccount):
    from googleapiclient.discovery import build
    creds = load_credentials_for_account(db, account)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_calendar_service_for_account(db: Session, account: EmailAccount):
    """
    Build a Calendar service using this account's own OAuth credentials, so
    events are created on (and invites organized by) the connected rep's own
    Google account rather than the shared legacy calendar_token.json.

    Raises ValueError if the account was connected before Calendar scopes were
    requested — the caller should catch this and fall back to the legacy
    shared calendar, and the rep should reconnect their account to pick up
    Calendar access.
    """
    from googleapiclient.discovery import build
    if not account.scopes or "https://www.googleapis.com/auth/calendar.events" not in account.scopes:
        raise ValueError(
            f"{account.email_address} has not granted Calendar access — "
            f"reconnect this account to enable Calendar invites from it."
        )
    creds = load_credentials_for_account(db, account)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)
