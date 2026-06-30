"""
Settings router — Gmail + WhatsApp account management.
All endpoints require authentication.
"""
import logging
import threading
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

logger = logging.getLogger("rdl_app_logger")
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.core import get_db
from app.models.email_account import EmailAccount
from app.models.user import User
from app.models.whatsapp_account import WhatsAppAccount
from app.schema.settings import (
    EmailAccountListResponse, EmailAccountOut, EmailAccountUpdate, OAuthUrlResponse
)
from app.schema.whatsapp import (
    WhatsAppAccountCreate, WhatsAppAccountListResponse,
    WhatsAppAccountOut, WhatsAppAccountUpdate,
)
from app.services import email_account_service as svc

router = APIRouter(prefix="/settings", tags=["Settings"])


def _trigger_batch_import(account_id: UUID, days: int = 30) -> None:
    """Start a 30-day historical import in a background thread.
    Safe to run alongside the regular poller — gmail_message_id deduplication prevents duplicates."""
    from app.database.core import SessionLocal
    from app.services.email_account_service import get_account
    from app.services.gmail_service import get_gmail_service, fetch_messages_since
    from app.services.workflows.email_workflow import run_email_workflow
    from datetime import datetime, timedelta, timezone

    def _run():
        db = SessionLocal()
        imported = 0
        try:
            acct = get_account(db, account_id)
            if not acct:
                return
            gmail_svc = get_gmail_service(account=acct)
            since_dt = datetime.now(timezone.utc) - timedelta(days=days)
            messages = fetch_messages_since(gmail_svc, since_dt, max_results=500)
            logger.info(f"[BATCH IMPORT] {acct.email_address}: fetched {len(messages)} messages for last {days}d")
            for raw_msg in messages:
                result = run_email_workflow(
                    db, raw_msg,
                    account_id=str(acct.id),
                    account_email=acct.email_address,
                )
                if result:
                    imported += 1
            logger.info(f"[BATCH IMPORT] {acct.email_address}: imported {imported} new emails")
        except Exception as e:
            logger.error(f"[BATCH IMPORT] Failed for {account_id}: {e}", exc_info=True)
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True, name=f"batch_import_{account_id}").start()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _callback_uri(request: Request) -> str:
    """
    Build the OAuth callback URL.
    Always uses localhost:8001 because Google OAuth rejects private LAN IPs
    (192.168.x.x) as redirect URIs for web applications.
    """
    from app.core.config import settings as cfg
    if cfg.OAUTH_REDIRECT_BASE:
        base = cfg.OAUTH_REDIRECT_BASE.rstrip("/")
    else:
        # Fall back to localhost regardless of what IP the request came in on
        base = "http://localhost:8001"
    return f"{base}/api/v1/settings/email-accounts/callback"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/email-accounts", response_model=EmailAccountListResponse)
def list_email_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Regular users see only their own accounts; super-admin sees all
    owner_filter = None if current_user.is_superuser else current_user.id
    accounts = svc.list_accounts(db, owner_id=owner_filter)
    return EmailAccountListResponse(items=accounts, total=len(accounts))


@router.get("/email-accounts/auth-url", response_model=OAuthUrlResponse)
def get_auth_url(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return Google OAuth consent URL. Frontend redirects user to this URL."""
    existing = (
        db.query(EmailAccount)
        .filter(EmailAccount.owner_id == current_user.id)
        .count()
    )
    if existing >= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a Gmail account connected. Remove it before adding a new one.",
        )
    url = svc.get_auth_url(redirect_uri=_callback_uri(request), owner_id=current_user.id)
    return OAuthUrlResponse(url=url)


@router.get("/email-accounts/callback")
def oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(None),
    db: Session = Depends(get_db),
):
    """
    Google redirects here after user consents.
    Exchanges code for token, stores in DB, redirects to Settings page.
    No auth guard — Google calls this directly.
    """
    try:
        account = svc.exchange_code_and_save(
            db=db,
            code=code,
            redirect_uri=_callback_uri(request),
            state=state,
            added_by="admin",
        )
        email_address = account.email_address
        logger.info(f"[OAUTH CALLBACK] SUCCESS — saved account: {email_address}")

        # Auto-trigger 30-day historical batch import in background.
        # Runs concurrently with the regular 120s poller — no overlap because
        # the workflow deduplicates on gmail_message_id.
        _trigger_batch_import(account.id)

        return RedirectResponse(
            url=f"http://localhost:5173/settings?email_added={email_address}",
            status_code=302,
        )
    except Exception as e:
        import traceback
        logger.error(
            f"[OAUTH CALLBACK] Failed to exchange code: {e}\n{traceback.format_exc()}"
        )
        return RedirectResponse(
            url="http://localhost:5173/settings?email_error=true",
            status_code=302,
        )


@router.patch("/email-accounts/{account_id}", response_model=EmailAccountOut)
def update_email_account(
    account_id: UUID,
    payload: EmailAccountUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    account = svc.update_account(db, account_id, payload)
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")
    return account


@router.delete("/email-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_email_account(
    account_id: UUID,
    # archive_emails=true (default): status→archived so they don't pollute inbox/analytics
    # archive_emails=false: keep emails as-is (account_id set to NULL by FK cascade)
    archive_emails: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not svc.delete_account(db, account_id, archive_emails=archive_emails):
        raise HTTPException(status_code=404, detail="Email account not found")


@router.post("/email-accounts/{account_id}/set-primary", response_model=EmailAccountOut)
def set_primary_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.schema.settings import EmailAccountUpdate
    account = svc.update_account(db, account_id, EmailAccountUpdate(is_primary=True))
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")
    return account


@router.post("/email-accounts/{account_id}/sync-history")
def sync_account_history(
    account_id: UUID,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Trigger a background import of the last N days of emails for an account.
    Returns immediately — safe to run alongside the regular 120s poller.
    """
    from app.services.email_account_service import get_account as get_acct
    account = get_acct(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found")
    _trigger_batch_import(account_id, days=days)
    return {"status": "started", "account_id": str(account_id), "days": days}


# ── WhatsApp account management ────────────────────────────────────────────────

@router.get("/whatsapp-accounts", response_model=WhatsAppAccountListResponse)
def list_whatsapp_accounts(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    owner_filter = None if current_user.is_superuser else current_user.id
    accounts = db.query(WhatsAppAccount)
    if owner_filter:
        accounts = accounts.filter(WhatsAppAccount.owner_id == owner_filter)
    accounts = accounts.order_by(WhatsAppAccount.is_primary.desc(), WhatsAppAccount.created_at).all()
    return WhatsAppAccountListResponse(items=accounts, total=len(accounts))


@router.post("/whatsapp-accounts", response_model=WhatsAppAccountOut, status_code=201)
def add_whatsapp_account(
    payload:      WhatsAppAccountCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    # One WhatsApp account per regular user
    if not current_user.is_superuser:
        existing_count = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.owner_id == current_user.id
        ).count()
        if existing_count >= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have a WhatsApp account connected. Remove it before adding a new one.",
            )

    # Validate no duplicate phone_number_id
    if db.query(WhatsAppAccount).filter(
        WhatsAppAccount.phone_number_id == payload.phone_number_id
    ).first():
        raise HTTPException(status_code=400, detail="This Phone Number ID is already registered.")

    account = WhatsAppAccount(
        owner_id        = current_user.id,
        phone_number_id = payload.phone_number_id,
        waba_id         = payload.waba_id,
        access_token    = payload.access_token,
        verify_token    = payload.verify_token,
        display_phone   = payload.display_phone,
        display_name    = payload.display_name,
        auto_send       = payload.auto_send,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    logger.info(f"[WA SETTINGS] Account added: {account.display_phone} for user {current_user.email}")
    return account


@router.patch("/whatsapp-accounts/{account_id}", response_model=WhatsAppAccountOut)
def update_whatsapp_account(
    account_id:   UUID,
    payload:      WhatsAppAccountUpdate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    account = db.query(WhatsAppAccount).filter(WhatsAppAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="WhatsApp account not found")
    if not current_user.is_superuser and account.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="WhatsApp account not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account


@router.delete("/whatsapp-accounts/{account_id}", status_code=204)
def delete_whatsapp_account(
    account_id:   UUID,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    account = db.query(WhatsAppAccount).filter(WhatsAppAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="WhatsApp account not found")
    if not current_user.is_superuser and account.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="WhatsApp account not found")
    db.delete(account)
    db.commit()


@router.post("/whatsapp-accounts/{account_id}/set-primary", response_model=WhatsAppAccountOut)
def set_primary_whatsapp_account(
    account_id:   UUID,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    account = db.query(WhatsAppAccount).filter(WhatsAppAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="WhatsApp account not found")
    if not current_user.is_superuser and account.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="WhatsApp account not found")

    # Clear other primaries for this user
    db.query(WhatsAppAccount).filter(
        WhatsAppAccount.owner_id == account.owner_id,
        WhatsAppAccount.id != account_id,
    ).update({"is_primary": False})
    account.is_primary = True
    db.commit()
    db.refresh(account)
    return account


# ── Company / Voice Settings ──────────────────────────────────────────────────
# Allows operators to update the company phone number shown to customers
# during AI voice escalations and in email/WhatsApp CTAs.

from pydantic import BaseModel as _BM

class CompanySettingsOut(_BM):
    company_phone: str
    voice_base_url: str
    voice_token_ttl_minutes: int
    voice_escalation_threshold: int

class CompanySettingsUpdate(_BM):
    company_phone: Optional[str] = None


@router.get("/company", response_model=CompanySettingsOut, summary="Get company / voice settings")
def get_company_settings(_: User = Depends(get_current_user)):
    from app.core.config import settings as _cfg
    return CompanySettingsOut(
        company_phone                = _cfg.COMPANY_PHONE,
        voice_base_url               = _cfg.VOICE_BASE_URL,
        voice_token_ttl_minutes      = _cfg.VOICE_TOKEN_TTL_MINUTES,
        voice_escalation_threshold   = _cfg.VOICE_ESCALATION_THRESHOLD,
    )


@router.patch("/company", response_model=CompanySettingsOut, summary="Update company phone number")
def update_company_settings(
    payload: CompanySettingsUpdate,
    current_user: User = Depends(get_current_user),
):
    """
    Update runtime company settings (phone number).
    Writes to the environment so the change is active immediately;
    does NOT persist across container restarts — add the env var to .env.local for permanence.
    Super-admin only.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Super-admin only")

    import os
    from app.core import config as _config_module

    if payload.company_phone:
        # Validate format — must start with + or be numeric
        phone = payload.company_phone.strip()
        if not (phone.startswith("+") or phone.replace("-", "").replace(" ", "").isdigit()):
            raise HTTPException(status_code=422, detail="Invalid phone number format")
        os.environ["COMPANY_PHONE"] = phone
        _config_module.settings.COMPANY_PHONE = phone  # type: ignore[attr-defined]
        logger.info(f"[SETTINGS] Company phone updated to {phone} by {current_user.email}")

    from app.core.config import settings as _cfg
    return CompanySettingsOut(
        company_phone                = _cfg.COMPANY_PHONE,
        voice_base_url               = _cfg.VOICE_BASE_URL,
        voice_token_ttl_minutes      = _cfg.VOICE_TOKEN_TTL_MINUTES,
        voice_escalation_threshold   = _cfg.VOICE_ESCALATION_THRESHOLD,
    )
