from pydantic import BaseModel
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID


class UsageMetrics(BaseModel):
    input_tokens: int
    output_tokens: int
    total_cost: float
    latency_ms: int


class RAGQueryRequest(BaseModel):
    question: str
    session_id: str = "default"
    source: Optional[str] = "web_chat"


class RAGQueryResponse(BaseModel):
    answer: str
    sentiment: str
    metrics: UsageMetrics


class UsageLogOut(BaseModel):
    id: UUID
    session_id: str
    question: Optional[str] = None
    source: Optional[str] = None
    user_id: Optional[UUID] = None
    token_tier: Optional[str] = None
    reranker_doc_count: Optional[int] = None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    latency_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalyticsSummary(BaseModel):
    total_queries: int
    total_cost_usd: float
    avg_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int
    by_source: Dict[str, int]
    by_tier: Dict[str, int]


class AnalyticsLogsResponse(BaseModel):
    items: List[UsageLogOut]
    total: int
    page: int
    limit: int
