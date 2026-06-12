"""User management schemas — admin-side CRUD + self-service password change."""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Super-admin creates a new user account."""
    email: EmailStr
    password: str = Field(min_length=6)
    is_superuser: bool = False


class UserUpdate(BaseModel):
    """Super-admin updates someone else's account.

    All fields optional. `password`, when set, is a forced reset (no current
    password needed — that's the privileged path). For self-service password
    change use `PasswordChange` against `/users/me/password` instead.
    """
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6)


class PasswordChange(BaseModel):
    """A user changes their own password (must know the current one)."""
    current_password: str
    new_password: str = Field(min_length=6)
