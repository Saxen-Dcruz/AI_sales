from sqlalchemy import Column, Integer, String, Float, DateTime, Numeric
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import func
from app.database.core import Base
from app.core.utils import new_uuid


class RAGUsageLog(Base):
    __tablename__ = "rag_usage_logs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    session_id = Column(String, index=True)
    question = Column(String)
    standalone_query = Column(String, nullable=True)
    sentiment = Column(String, nullable=True)

    source = Column(String, nullable=True, index=True)
    user_id = Column(PGUUID(as_uuid=True), nullable=True, index=True)

    token_tier = Column(String, nullable=True)
    reranker_doc_count = Column(Integer, nullable=True)

    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

    estimated_cost = Column(Numeric(10, 6), default=0.0)
    latency_ms = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
