from typing import Optional, List
from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LinkedGmailAccount(BaseModel):
    id: UUID
    email_address: str
    is_active: bool
    is_primary: bool
    auto_send_enabled: bool = True

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: UUID
    email: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    # Populated by the users router when called by super-admin
    gmail_accounts: List[LinkedGmailAccount] = []

    model_config = {"from_attributes": True}
