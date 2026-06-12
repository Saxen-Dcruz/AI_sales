"""User management — super-admin CRUD + self-service password change.

Super-admin (is_superuser=True) endpoints — manage every account:
    GET    /users              list all users
    POST   /users              create a new user
    PATCH  /users/{id}         update is_active / is_superuser / forced password reset
    DELETE /users/{id}         soft-deactivate (sets is_active=False, keeps owned rows)

Any-authenticated-user endpoint — manage own credentials:
    PATCH  /users/me/password  change own password (requires current password)
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, require_admin
from app.models.user import User
from app.schema.auth import LinkedGmailAccount, UserOut
from app.schema.users import PasswordChange, UserCreate, UserUpdate
from app.services.auth_service import hash_password, verify_password

router = APIRouter(prefix="/users", tags=["Users"])


# ── Self-service ─────────────────────────────────────────────────────────────
# Note: /me/password is declared BEFORE /{user_id} so FastAPI doesn't treat
# "me" as a UUID path arg and 422.

@router.patch("/me/password", response_model=UserOut)
def change_own_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Authenticated user changes their own password.

    The current password must verify or the request is rejected — this prevents
    a stolen access token from being used to lock the user out of their account.
    """
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    db.refresh(current_user)
    return current_user


# ── Super-admin CRUD ─────────────────────────────────────────────────────────

def _attach_gmail_accounts(db: Session, users: list[User]) -> list[UserOut]:
    """Enrich each UserOut with the Gmail accounts that user owns."""
    from app.models.email_account import EmailAccount
    # Single query: fetch all accounts for all user IDs at once
    ids = [u.id for u in users]
    accounts = db.query(EmailAccount).filter(EmailAccount.owner_id.in_(ids)).all()
    by_owner: dict = {}
    for a in accounts:
        by_owner.setdefault(a.owner_id, []).append(a)

    result = []
    for u in users:
        out = UserOut.model_validate(u)
        out.gmail_accounts = [
            LinkedGmailAccount.model_validate(a)
            for a in by_owner.get(u.id, [])
        ]
        result.append(out)
    return result


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    users = db.query(User).order_by(User.email).all()
    return _attach_gmail_accounts(db, users)


@router.get("/{user_id}/accounts", response_model=list[LinkedGmailAccount])
def list_user_accounts(
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Return all Gmail accounts linked to a specific user (super-admin only)."""
    from app.models.email_account import EmailAccount
    return db.query(EmailAccount).filter(EmailAccount.owner_id == user_id).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        is_superuser=payload.is_superuser,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Guardrail: prevent the only super-admin from demoting / deactivating themselves
    # and being unable to undo it. If they want to step down, another super-admin
    # has to do it.
    if user.id == admin.id:
        if payload.is_superuser is False or payload.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A super-admin cannot demote or deactivate themselves. Ask another super-admin.",
            )

    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_superuser is not None:
        user.is_superuser = payload.is_superuser
    if payload.password is not None:
        user.hashed_password = hash_password(payload.password)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", response_model=UserOut)
def deactivate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Soft-delete: sets is_active=False. We don't hard-delete because every
    Lead/Deal/Email/Call/CalendarEvent has owner_id FK → users(id); a hard
    delete would either cascade (lose data) or set owner_id NULL (orphan rows
    that the scoping logic would then drop). Deactivation preserves the audit
    trail and the super-admin can still reassign or reactivate later."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A super-admin cannot deactivate themselves.",
        )
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user
