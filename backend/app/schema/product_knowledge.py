from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class KnowledgeEntryCreate(BaseModel):
    category: str   # warranty | compatibility | pricing | technical | general
    content: str


class KnowledgeEntryUpdate(BaseModel):
    category: Optional[str] = None
    content: Optional[str] = None


class ChunkUpdate(BaseModel):
    content: str


class KnowledgeEntryOut(BaseModel):
    id: UUID
    product_id: UUID
    category: str
    content: str
    added_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeEntryListResponse(BaseModel):
    items: list[KnowledgeEntryOut]
    total: int
