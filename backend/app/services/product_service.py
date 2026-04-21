import asyncio
import json
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.models.product import Product, ProductEmbedding
from app.schema.product import ProductCreate, ProductUpdate
from app.core.config import settings

embedding_model = GoogleGenerativeAIEmbeddings(
    model=settings.AGENT.rag.embedding_model,
    google_api_key=settings.GOOGLE_API_KEY
)

async def _process_embeddings(product_id: int, product_name: str, sections: dict):
    """Background task to generate vectors using Google Gemini."""
    from app.database.core import SessionLocal
    db = SessionLocal()
    try:
        # 1. Clean up old vectors
        db.query(ProductEmbedding).filter(ProductEmbedding.product_id == product_id).delete()
        
        for section_name, section_content in sections.items():
            if not section_content: continue
            
            # Format content
            if isinstance(section_content, (list, dict)):
                section_content = json.dumps(section_content, indent=2)
            
            context_text = f"Product: {product_name}\nSection: {section_name}\n\n{section_content}"
            
            # 2. Call Google API in a thread to prevent blocking
            vector = await asyncio.to_thread(embedding_model.embed_query, context_text)
            
            embedding_entry = ProductEmbedding(
                product_id=product_id,
                chunk_type=section_name.lower().replace(" ", "_"),
                text_content=context_text,
                embedding=vector
            )
            db.add(embedding_entry)
        
        db.commit()
        print(f"✅ Vectors updated for Product ID: {product_id}")
    except Exception as e:
        print(f"❌ Embedding Error for Product {product_id}: {e}")
        db.rollback()
    finally:
        db.close()

def get_all_products(db: Session, skip: int, limit: int):
    return db.query(Product).offset(skip).limit(limit).all()

def get_product(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()

async def create_product(db: Session, product_in: ProductCreate, background_tasks: BackgroundTasks):
    # Fix: by_alias=False maps 'Product_id' alias back to 'name' column
    product_data = product_in.model_dump(exclude={"sections"}, by_alias=False)
    db_product = Product(**product_data)
    
    db.add(db_product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("Order code already exists")
    db.refresh(db_product)
    
    if product_in.sections:
        background_tasks.add_task(_process_embeddings, db_product.id, db_product.name, product_in.sections)
    
    return db_product

async def update_product(db: Session, product_id: int, product_in: ProductUpdate, background_tasks: BackgroundTasks):
    db_product = get_product(db, product_id)
    if not db_product: 
        return None
    
    # exclude_unset=True is vital so we don't overwrite existing data with None
    update_data = product_in.model_dump(exclude_unset=True, by_alias=False)
    sections = update_data.pop("sections", None)
    
    # Don't allow updating the primary key if it's in the payload
    update_data.pop("id", None)
    
    for key, value in update_data.items():
        setattr(db_product, key, value)
    
    db.commit()
    db.refresh(db_product)

    if sections is not None:
        background_tasks.add_task(_process_embeddings, db_product.id, db_product.name, sections)
    
    return db_product