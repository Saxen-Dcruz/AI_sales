import os
import json
import glob
import time
import sys
import re
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import text 

# Tell Python where the root 'backend' folder is so it can find 'app'
backend_dir = str(Path(__file__).resolve().parents[2])
sys.path.append(backend_dir)

# Import your custom database setup and models
from app.database.core import SessionLocal, engine 
from app.models.product import Base, Product
from app.core.config import settings 

# 👇 NEW: LangChain Imports for Vector Ingestion
from langchain_postgres import PGVector
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

print("🏗️ Ensuring database tables exist...")

# STEP 1: Turn on the pgvector extension FIRST
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    conn.commit()

# STEP 2: Now that Postgres knows what a vector is, build the tables
Base.metadata.create_all(bind=engine)

def clean_price(price_str: str) -> float:
    """Converts 'Rs 16,378' or 'Rs 8,231.00' into a clean float."""
    if not price_str:
        return 0.0
    clean_str = re.sub(r'[^\d.]', '', str(price_str))
    return float(clean_str) if clean_str else 0.0

def extract_section_text(product_data: dict, section_name: str) -> str:
    """Extract text from a section if it exists, handling both string and dict values."""
    value = product_data.get(section_name)
    if isinstance(value, dict):
        return json.dumps(value, indent=2)
    elif isinstance(value, list):
        return '\n'.join([f"- {item}" for item in value])
    elif value:
        return str(value)
    return ""

def process_knowledge_base():
    # 1. Setup Database and Embedding Model
    print(f"☁️ Loading Google Cloud Embedding Model: {settings.AGENT.rag.embedding_model}...")
    embedding_model = GoogleGenerativeAIEmbeddings(
        model=settings.AGENT.rag.embedding_model,
        google_api_key=settings.GOOGLE_API_KEY
    )
    
    # 👇 NEW: Initialize LangChain's Vector Store for ingestion
    # We must use the sync psycopg driver for this script
    sync_connection_str = settings.DATABASE_URL.replace("postgresql+psycopg_async://", "postgresql+psycopg://").replace("postgresql://", "postgresql+psycopg://")
    
    vectorstore = PGVector(
        embeddings=embedding_model,
        collection_name="product_embeddings",
        connection=sync_connection_str,
        use_jsonb=True,
    )
    
    db: Session = SessionLocal()
    
    # Define the directory containing your JSON files
    directory_path = os.path.join(
        os.environ.get("USERPROFILE", os.environ.get("HOME")), 
        "Desktop", "AI_SALES", "data", "knowledge_base" 
    )
    
    file_paths = glob.glob(os.path.join(directory_path, "**/*.json"), recursive=True)
    
    if not file_paths:
        print(f"❌ No .json files found in {directory_path}")
        return

    print(f"📂 Found {len(file_paths)} JSON files to process.")

    processed_chunks = 0
    updated_products = 0
    new_products = 0
    error_count = 0

    # 2. Process Each JSON File
    for file_path in file_paths:
        print(f"\n📄 Reading: {os.path.basename(file_path)}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as e:
            print(f"  ❌ Error parsing JSON file {file_path}: {e}")
            error_count += 1
            continue
        
        products = data if isinstance(data, list) else [data]
        
        for product_data in products:
            product_name = product_data.get("Product_id", "")
            if not product_name:
                print(f"  ⚠️ Skipping product with no name in {file_path}")
                error_count += 1
                continue
            
            order_code = product_data.get("Order Code", f"TEMP-{hash(product_name)}")
            
            # --- RELATIONAL DATABASE LOGIC (Keep this for your standard app features) ---
            existing_product = db.query(Product).filter(Product.order_code == order_code).first()
            
            category = product_data.get("Category")
            sub_category = product_data.get("Sub-category")
            brand = product_data.get("Brand")
            price = clean_price(product_data.get("Price"))
            product_link = product_data.get("Product Link")
            datasheet_link = product_data.get("Data Sheet link") or product_data.get("Data Sheet")
            user_manual_link = product_data.get("User Manual") or product_data.get("User manual Link")
            sdk_link = product_data.get("Learning Center / SDK") or product_data.get("Learning Center SDK")
            
            bulk_pricing = product_data.get("Bulk Pricing")
            bulk_pricing_str = "\n".join(bulk_pricing) if bulk_pricing and isinstance(bulk_pricing, list) else None
            
            if existing_product:
                existing_product.name = product_name
                existing_product.category = category
                existing_product.sub_category = sub_category
                existing_product.brand = brand
                existing_product.single_price = price
                existing_product.product_link = product_link
                existing_product.datasheet_link = datasheet_link
                existing_product.user_manual_link = user_manual_link
                existing_product.sdk_link = sdk_link
                
                product = existing_product
                updated_products += 1
                print(f"  🔄 Updated Relational DB: {product_name}")
            else:
                product = Product(
                    name=product_name,
                    order_code=order_code,
                    category=category,
                    sub_category=sub_category,
                    brand=brand,
                    single_price=price,
                    product_link=product_link,
                    datasheet_link=datasheet_link,
                    user_manual_link=user_manual_link,
                    sdk_link=sdk_link,
                    is_active=True
                )
                db.add(product)
                db.flush() # Get the product.id immediately
                new_products += 1
                print(f"  ✨ Created Relational DB: {product_name}")
            
            # --- VECTOR DATABASE LOGIC (LangChain Integration) ---
            docs_to_add =[]
            ids_to_add = []

            sections_to_embed =[
                "Description", "Product Description", "Descriptions", "DESCRIPTION",
                "Features", "FEATURES", "Specifications", "Specification", "Specs",
                "Applications", "Application", "Benefits", "Advantages", "Operational Benefits",
                "Scope of Learning Experiments", "Package Contains", "Package Includes",
                "Note", "Notes", "Optional", "Microcontroller Unit", "Peripheral Features",
                "Analog Features", "Supported IC", "Pin Configuration"
            ]
            
            # 1. Nested Features
            features_obj = product_data.get("Features")
            if features_obj and isinstance(features_obj, dict):
                for feature_name, feature_value in features_obj.items():
                    chunk_type = f"feature_{feature_name.lower().replace(' ', '_')}"
                    contextualized_text = f"Product Name: {product_name}\nSection: {feature_name}\n\n{feature_value}"
                    
                    docs_to_add.append(Document(
                        page_content=contextualized_text,
                        metadata={"product_id": product.id, "product_name": product_name, "chunk_type": chunk_type}
                    ))
                    ids_to_add.append(f"{product.id}_{chunk_type}")
            
            # 2. Standard Sections
            for section in sections_to_embed:
                section_text = extract_section_text(product_data, section)
                if section_text:
                    chunk_type = section.lower().replace(" ", "_")
                    contextualized_text = f"Product Name: {product_name}\nSection: {section}\n\n{section_text}"
                    
                    docs_to_add.append(Document(
                        page_content=contextualized_text,
                        metadata={"product_id": product.id, "product_name": product_name, "chunk_type": chunk_type}
                    ))
                    ids_to_add.append(f"{product.id}_{chunk_type}")
            
            # 3. Bulk Pricing
            if bulk_pricing_str:
                contextualized_text = f"Product Name: {product_name}\nSection: Bulk Pricing\n\n{bulk_pricing_str}"
                docs_to_add.append(Document(
                    page_content=contextualized_text,
                    metadata={"product_id": product.id, "product_name": product_name, "chunk_type": "bulk_pricing"}
                ))
                ids_to_add.append(f"{product.id}_bulk_pricing")
            
            # 4. Frequently Bought Together
            fbt = product_data.get("Frequently Bought Together") or product_data.get("FREQUENTLY BOUGHT TOGETHER") or product_data.get("frequently Bought Together")
            if fbt:
                contextualized_text = f"Product Name: {product_name}\nSection: Frequently Bought Together\n\n{fbt}"
                docs_to_add.append(Document(
                    page_content=contextualized_text,
                    metadata={"product_id": product.id, "product_name": product_name, "chunk_type": "frequently_bought_together"}
                ))
                ids_to_add.append(f"{product.id}_frequently_bought_together")

            # 👇 BATCH INSERT TO LANGCHAIN PGVECTOR
            if docs_to_add:
                try:
                    # Passing 'ids' ensures that if we run this script again, it updates existing vectors instead of duplicating!
                    vectorstore.add_documents(documents=docs_to_add, ids=ids_to_add)
                    processed_chunks += len(docs_to_add)
                    print(f"  ✅ Embedded {len(docs_to_add)} chunks for {product_name}")
                    
                    # Sleep once per product to respect Google API limits
                    time.sleep(1.0) 
                except Exception as e:
                    print(f"  ❌ Failed to embed vectors for {product_name}: {e}")
                    error_count += 1

    print("\n💾 Committing all changes to the database...")
    db.commit()
    db.close()

    print("\n✅ --- INGESTION COMPLETE ---")
    print(f"New Products Added: {new_products}")
    print(f"Existing Products Updated: {updated_products}")
    print(f"Embeddings Generated: {processed_chunks}")
    print(f"Errors Encountered: {error_count}")

if __name__ == "__main__":
    process_knowledge_base()