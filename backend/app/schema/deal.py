from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID


class DealCreate(BaseModel):
    deal_name: str
    company_id: UUID
    lead_id: Optional[UUID] = None
    deal_value: Optional[Decimal] = Decimal("0.00")
    stage: Optional[str] = "Prospect"
    win_probability: Optional[int] = 10
    loss_reason: Optional[str] = None
    expected_close_date: Optional[datetime] = None


class DealUpdate(BaseModel):
    deal_name: Optional[str] = None
    company_id: Optional[UUID] = None
    lead_id: Optional[UUID] = None
    deal_value: Optional[Decimal] = None
    stage: Optional[str] = None
    win_probability: Optional[int] = None
    loss_reason: Optional[str] = None
    expected_close_date: Optional[datetime] = None
    closed_at: Optional[datetime] = None


class DealOut(BaseModel):
    id: UUID
    deal_name: str
    company_id: UUID
    lead_id: Optional[UUID] = None
    deal_value: Decimal
    stage: str
    win_probability: Decimal
    loss_reason: Optional[str] = None
    expected_close_date: Optional[datetime] = None
    created_at: datetime
    closed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DealListResponse(BaseModel):
    items: List[DealOut]
    total: int
    page: int
    limit: int


class StageBreakdown(BaseModel):
    count: int
    total_value: float


class RevenueBreakdown(BaseModel):
    this_month: float
    last_month: float
    this_quarter: float
    ytd: float


class DealAnalyticsResponse(BaseModel):
    total_deals: int
    open_deals: int
    total_open_value: float
    avg_deal_size: float
    total_won: int
    total_lost: int
    total_won_value: float
    win_rate: float
    avg_sales_cycle_days: float
    pipeline_velocity: float
    by_stage: dict[str, StageBreakdown]
    revenue: RevenueBreakdown
