import logging
import traceback
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.config import settings
from app.models.user import User

logger = logging.getLogger("rdl_app_logger")

router = APIRouter(prefix="/linkedin-accounts", tags=["LinkedIn Accounts"])


def _callback_uri(request: Request) -> str:
    base = settings.OAUTH_REDIRECT_BASE.rstrip("/") if settings.OAUTH_REDIRECT_BASE else "http://localhost:8001"
    return f"{base}/api/v1/linkedin-accounts/callback"


@router.get("/auth-url")
def get_auth_url(
    request: Request,
    _: User = Depends(get_current_user),
):
    """Return LinkedIn OAuth consent URL. Frontend redirects the user here."""
    if not settings.LINKEDIN_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="LINKEDIN_CLIENT_ID not configured. See backend/app/services/linkedin_oauth_service.py for setup.",
        )
    from app.services.linkedin_oauth_service import get_auth_url
    url = get_auth_url(redirect_uri=_callback_uri(request))
    return {"url": url}


@router.get("/callback")
def oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(None),
    db: Session = Depends(get_db),
):
    """
    LinkedIn redirects here after user grants consent.
    Exchanges code for token, stores account, redirects to Settings page.
    No auth guard — LinkedIn calls this directly.
    """
    try:
        from app.services.linkedin_oauth_service import exchange_code_and_save
        account = exchange_code_and_save(db=db, code=code, redirect_uri=_callback_uri(request))
        name = account.name or account.email or "account"
        frontend = settings.FRONTEND_URL.rstrip("/")
        return RedirectResponse(
            url=f"{frontend}/settings?linkedin_added={name}",
            status_code=302,
        )
    except Exception as e:
        logger.error(f"[LI OAUTH CALLBACK] Failed: {e}\n{traceback.format_exc()}")
        frontend = settings.FRONTEND_URL.rstrip("/")
        return RedirectResponse(
            url=f"{frontend}/settings?linkedin_error=1",
            status_code=302,
        )


@router.get("")
def list_accounts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.services.linkedin_oauth_service import list_accounts
    accounts = list_accounts(db)
    return {
        "items": [
            {
                "id":        str(a.id),
                "name":      a.name,
                "email":     a.email,
                "picture":   a.picture_url,
                "is_active": a.is_active,
                "connected_at": a.connected_at.isoformat() if a.connected_at else None,
            }
            for a in accounts
        ],
        "total": len(accounts),
    }


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.services.linkedin_oauth_service import disconnect_account
    if not disconnect_account(db, str(account_id)):
        raise HTTPException(status_code=404, detail="LinkedIn account not found")


# ── Scraper session (li_at cookie) ────────────────────────────────────────────

@router.post("/scraper-session")
def save_scraper_session(
    payload: dict,
    _: User = Depends(get_current_user),
):
    """
    Save the li_at LinkedIn session cookie so the headless scraper can use it.
    The cookie is saved to linkedin_profile_context/li_at.txt which the
    scraper injects before every search.
    """
    li_at = (payload.get("li_at") or "").strip()
    if not li_at:
        raise HTTPException(status_code=400, detail="li_at cookie value is required")

    from pathlib import Path
    session_dir = Path(__file__).resolve().parents[3] / "linkedin_profile_context"
    session_dir.mkdir(exist_ok=True)
    (session_dir / "li_at.txt").write_text(li_at)
    logger.info("[LI SCRAPER] li_at session cookie saved")
    return {"status": "ok", "message": "LinkedIn scraper session saved"}


@router.get("/scraper-session")
def get_scraper_session_status(
    _: User = Depends(get_current_user),
):
    """Check whether a scraper session cookie is saved."""
    from pathlib import Path
    li_at_file = Path(__file__).resolve().parents[3] / "linkedin_profile_context" / "li_at.txt"
    if li_at_file.exists() and li_at_file.read_text().strip():
        return {"configured": True}
    return {"configured": False}


@router.delete("/scraper-session", status_code=status.HTTP_204_NO_CONTENT)
def clear_scraper_session(
    _: User = Depends(get_current_user),
):
    """Remove the saved li_at cookie."""
    from pathlib import Path
    li_at_file = Path(__file__).resolve().parents[3] / "linkedin_profile_context" / "li_at.txt"
    if li_at_file.exists():
        li_at_file.unlink()
