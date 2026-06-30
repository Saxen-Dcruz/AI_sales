from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from uuid import UUID


class EmailTemplateCreate(BaseModel):
    name: str
    subject: str
    body: str


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


class EmailTemplateOut(BaseModel):
    id: UUID
    owner_id: Optional[UUID] = None
    name: str
    subject: str
    body: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EmailTemplateListResponse(BaseModel):
    items: List[EmailTemplateOut]
    total: int
