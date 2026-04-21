import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schema.auth import RegisterRequest


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def hash_token(token: str) -> str:
    """SHA-256 hash of a token string. Tokens are high-entropy so no salt needed."""
    return hashlib.sha256(token.encode()).hexdigest()


def _make_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": subject,
        "type": token_type,
        "exp": expire,
        "jti": secrets.token_hex(16),  # unique per token — prevents hash collisions on same-second issuance
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str) -> str:
    return _make_token(
        subject, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(subject: str) -> str:
    return _make_token(
        subject, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )


def decode_token(token: str) -> dict:
    return jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )


def register_user(db: Session, payload: RegisterRequest) -> User:
    if db.query(User).filter(User.email == payload.email).first():
        raise ValueError("Email already registered")
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def store_refresh_token(db: Session, user_id, token: str) -> None:
    """Hash and persist a refresh token. Called after login and after rotation."""
    payload = decode_token(token)
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    db.add(RefreshToken(
        user_id=user_id,
        token_hash=hash_token(token),
        expires_at=expires_at,
    ))
    db.commit()


def validate_and_rotate_refresh_token(
    db: Session, token: str
) -> tuple[User, str, str]:
    """
    Validate a refresh token against the DB, then atomically rotate it:
    delete the old row, insert the new one.
    Returns (user, new_access_token, new_refresh_token).
    Raises ValueError for any validation failure.
    """
    try:
        payload = decode_token(token)
    except InvalidTokenError:
        raise ValueError("Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise ValueError("Invalid token type")

    db_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == hash_token(token)
    ).first()
    if not db_token:
        raise ValueError("Refresh token not found or already revoked")

    user = db.query(User).filter(User.email == payload["sub"]).first()
    if not user or not user.is_active:
        raise ValueError("User not found or inactive")

    new_access = create_access_token(user.email)
    new_refresh = create_refresh_token(user.email)

    new_payload = decode_token(new_refresh)
    expires_at = datetime.fromtimestamp(new_payload["exp"], tz=timezone.utc)

    db.delete(db_token)
    db.flush()  # send DELETE to DB before INSERT — avoids unique constraint race within same txn
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_refresh),
        expires_at=expires_at,
    ))
    db.commit()

    return user, new_access, new_refresh


def revoke_refresh_token(db: Session, token: str) -> None:
    """Delete the refresh token row from DB. No-op if already revoked."""
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == hash_token(token)
    ).first()
    if db_token:
        db.delete(db_token)
        db.commit()
