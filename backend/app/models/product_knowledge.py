from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.database.core import Base
from app.core.utils import new_uuid


class ProductKnowledge(Base):
    __tablename__ = "product_knowledge_entries"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    product_id = Column(PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String, nullable=False)   # warranty | compatibility | pricing | technical | general
    content = Column(Text, nullable=False)
    vector_doc_id = Column(String, nullable=True)  # pgvector doc ID — used for deletion
    added_by = Column(String, nullable=True)        # email of the sales rep who added it
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    product = relationship("Product", backref="knowledge_entries")
