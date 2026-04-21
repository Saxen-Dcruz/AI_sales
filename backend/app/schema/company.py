from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from uuid import UUID


class CompanyCreate(BaseModel):
    name: str
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    headquarters: Optional[str] = None
    about: Optional[str] = None
    campaign_id: Optional[UUID] = None


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    headquarters: Optional[str] = None
    about: Optional[str] = None
    campaign_id: Optional[UUID] = None


class CompanyOut(BaseModel):
    id: UUID
    name: str
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    headquarters: Optional[str] = None
    about: Optional[str] = None
    campaign_id: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyListResponse(BaseModel):
    items: List[CompanyOut]
    total: int
    page: int
    limit: int
