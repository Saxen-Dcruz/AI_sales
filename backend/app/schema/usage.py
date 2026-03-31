from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UsageMetrics(BaseModel):
    input_tokens: int
    output_tokens: int
    total_cost: float
    latency_ms: int

class RAGQueryRequest(BaseModel):
    question: str
    session_id: str = "default"

class RAGQueryResponse(BaseModel):
    answer: str
    sentiment: str
    metrics: UsageMetrics

class UsageLogOut(BaseModel):
    id: int
    session_id: str
    estimated_cost: float
    created_at: datetime

    class Config:
        from_attributes = True