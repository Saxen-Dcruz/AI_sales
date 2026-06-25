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

def _sync_category_fields(data: dict):
    """Keep legacy single-value category/sub_category columns in sync with the
    new categories/subcategories arrays so existing filters and search keep working."""
    categories = data.get("categories")
    if categories:
        data["category"] = categories[0]
    subcategories = data.get("subcategories")
    if subcategories:
        data["sub_category"] = subcategories[0]


def get_categories(db: Session):
    """Return the distinct set of categories and subcategories across all products,
    for populating the multi-select 'create new' dropdowns on the Add Product form."""
    categories: set[str] = set()
    subcategories: set[str] = set()
    for row in db.query(Product.category, Product.sub_category, Product.categories, Product.subcategories).all():
        category, sub_category, cats, subs = row
        if category:
            categories.add(category)
        if sub_category:
            subcategories.add(sub_category)
        for c in (cats or []):
            categories.add(c)
        for s in (subs or []):
            subcategories.add(s)
    return {
        "categories": sorted(categories),
        "subcategories": sorted(subcategories),
    }


def get_all_products(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    category: str | None = None,
    is_active: bool | None = None,
):
    q = db.query(Product)
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            Product.name.ilike(pattern)
            | Product.order_code.ilike(pattern)
            | Product.brand.ilike(pattern)
        )
    if category:
        q = q.filter(Product.category.ilike(f"%{category}%"))
    if is_active is not None:
        q = q.filter(Product.is_active == is_active)
    return q.order_by(Product.name).offset(skip).limit(limit).all()

def get_product(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()

async def create_product(db: Session, product_in: ProductCreate, background_tasks: BackgroundTasks):
    # Fix: by_alias=False maps 'Product_id' alias back to 'name' column
    product_data = product_in.model_dump(exclude={"sections"}, by_alias=False)
    _sync_category_fields(product_data)
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
    _sync_category_fields(update_data)

    # Don't allow updating the primary key if it's in the payload
    update_data.pop("id", None)
    
    for key, value in update_data.items():
        setattr(db_product, key, value)
    
    db.commit()
    db.refresh(db_product)

    if sections is not None:
        background_tasks.add_task(_process_embeddings, db_product.id, db_product.name, sections)
    
    return db_product