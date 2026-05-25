"""
LinkedIn OAuth 2.0 (OpenID Connect) service.

Setup (one-time):
  1. Go to https://www.linkedin.com/developers/apps/new
  2. Create an app (any name/logo)
  3. Under "Auth" tab — copy Client ID and Client Secret
  4. Under "Auth" tab — add Redirect URL:
       http://localhost:8001/api/v1/linkedin-accounts/callback
  5. Under "Products" tab — request "Sign In with LinkedIn using OpenID Connect"
     (approved instantly for most apps)
  6. Add to .env.local:
       LINKEDIN_CLIENT_ID=your_client_id
       LINKEDIN_CLIENT_SECRET=your_client_secret
  7. Restart backend
"""
import logging
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.linkedin import LinkedInOAuthAccount

logger = logging.getLogger("rdl_app_logger")

_AUTH_URL   = "https://www.linkedin.com/oauth/v2/authorization"
_TOKEN_URL  = "https://www.linkedin.com/oauth/v2/accessToken"
_INFO_URL   = "https://api.linkedin.com/v2/userinfo"
_SCOPES     = "openid profile email"


def get_auth_url(redirect_uri: str) -> str:
    params = {
        "response_type": "code",
        "client_id":     settings.LINKEDIN_CLIENT_ID,
        "redirect_uri":  redirect_uri,
        "scope":         _SCOPES,
        "state":         "rdl_linkedin_oauth",
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def exchange_code_and_save(db: Session, code: str, redirect_uri: str) -> LinkedInOAuthAccount:
    """Exchange OAuth code for token, fetch profile, upsert DB row."""
    # Exchange code for access token
    resp = httpx.post(
        _TOKEN_URL,
        data={
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  redirect_uri,
            "client_id":     settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()
    access_token = token_data["access_token"]

    # Fetch profile info
    info_resp = httpx.get(
        _INFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    info_resp.raise_for_status()
    info = info_resp.json()

    member_id = info.get("sub", "")
    name      = info.get("name", "")
    email     = info.get("email", "")
    picture   = info.get("picture", "")

    # Upsert
    account = db.query(LinkedInOAuthAccount).filter(
        LinkedInOAuthAccount.linkedin_member_id == member_id
    ).first()

    if account:
        account.access_token = access_token
        account.name         = name
        account.email        = email
        account.picture_url  = picture
        account.is_active    = True
    else:
        account = LinkedInOAuthAccount(
            linkedin_member_id=member_id,
            name=name,
            email=email,
            picture_url=picture,
            access_token=access_token,
        )
        db.add(account)

    db.commit()
    db.refresh(account)
    logger.info(f"[LI OAUTH] Connected: {name} ({email})")
    return account


def list_accounts(db: Session) -> list[LinkedInOAuthAccount]:
    return db.query(LinkedInOAuthAccount).order_by(LinkedInOAuthAccount.connected_at.desc()).all()


def disconnect_account(db: Session, account_id: str) -> bool:
    account = db.query(LinkedInOAuthAccount).filter(
        LinkedInOAuthAccount.id == account_id
    ).first()
    if not account:
        return False
    db.delete(account)
    db.commit()
    return True
