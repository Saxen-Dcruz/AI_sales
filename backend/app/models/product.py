# backend/app/models/product.py
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.database.core import Base

class Product(Base):
    __tablename__ = "products"

    # The Structured Data (For your React Frontend & filtering)
    id = Column(Integer, primary_key=True, index=True)
    order_code = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    category = Column(String, index=True)
    
    # 🆕 NEW: Added Sub-category
    sub_category = Column(String, index=True, nullable=True) 
    
    brand = Column(String)
    single_price = Column(Float, nullable=True)
    bulk_price = Column(Float, nullable=True)
    product_link = Column(String, nullable=True)
    datasheet_link = Column(String, nullable=True)
    
    # 🆕 NEW: Added Manual and SDK links
    user_manual_link = Column(String, nullable=True)
    sdk_link = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True)

    # Relationship to the AI embeddings
    embeddings = relationship("ProductEmbedding", back_populates="product", cascade="all, delete-orphan")

class ProductEmbedding(Base):
    __tablename__ = "product_embeddings"

    # The AI Data (For LangChain RAG)
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    chunk_type = Column(String) 
    text_content = Column(Text) 
    embedding = Column(Vector(1024)) 

    product = relationship("Product", back_populates="embeddings")