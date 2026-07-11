from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID


class EmailAccountOut(BaseModel):
    id:                UUID
    owner_id:          Optional[UUID]
    email_address:     str
    display_name:      Optional[str]
    is_active:         bool
    is_primary:        bool
    auto_send_enabled: bool = True
    scopes:            Optional[list]
    added_by:          Optional[str]
    created_at:        str

    model_config = {"from_attributes": True}


class EmailAccountListResponse(BaseModel):
    items: list[EmailAccountOut]
    total: int


class EmailAccountUpdate(BaseModel):
    display_name:      Optional[str]  = None
    is_active:         Optional[bool] = None
    is_primary:        Optional[bool] = None
    auto_send_enabled: Optional[bool] = None


class OAuthUrlResponse(BaseModel):
    url: str


class OAuthCallbackRequest(BaseModel):
    code:  str
    state: Optional[str] = None
