from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Numeric
from sqlalchemy.sql import func
from app.database.core import Base

class RAGUsageLog(Base):
    __tablename__ = "rag_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    question = Column(String)
    standalone_query = Column(String, nullable=True) # The rewritten question
    sentiment = Column(String, nullable=True)
    
    # Token Metrics
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # Financial Metrics (USD)
    estimated_cost = Column(Numeric(10, 6), default=0.0)
    
    # Performance Metrics
    latency_ms = Column(Integer)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())