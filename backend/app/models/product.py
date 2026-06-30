from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.database.core import Base
from app.core.utils import new_uuid


class Product(Base):
    __tablename__ = "products"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    order_code = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    category = Column(String, index=True)
    sub_category = Column(String, index=True, nullable=True)
    brand = Column(String)
    single_price = Column(Float, nullable=True)
    bulk_price = Column(Float, nullable=True)
    product_link = Column(String, nullable=True)
    datasheet_link = Column(String, nullable=True)
    user_manual_link = Column(String, nullable=True)
    sdk_link = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    coverage_score = Column(Float, nullable=True)   # % of RAG gaps resolved for this product

    categories = Column(JSONB, nullable=True)       # list[str] — multi-category support
    subcategories = Column(JSONB, nullable=True)    # list[str] — multi-subcategory support
    faqs = Column(JSONB, nullable=True)             # list[{question, answer}]
    bulk_pricing = Column(JSONB, nullable=True)      # list[{quantity, discount_percent}] — % off single_price per qty tier
    variations = Column(JSONB, nullable=True)       # list[{order_code, name, single_price, attributes}]
    order_information = Column(JSONB, nullable=True) # {order_codes: [..], rows: [{attribute, values: [..]}]}

    embeddings = relationship("ProductEmbedding", back_populates="product", cascade="all, delete-orphan")


class ProductEmbedding(Base):
    __tablename__ = "product_embeddings"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)
    product_id = Column(PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"))
    chunk_type = Column(String)
    text_content = Column(Text)
    embedding = Column(Vector(3072))

    product = relationship("Product", back_populates="embeddings")
