import os
import json
import glob
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Tell Python where the root 'backend' folder is so it can find 'app'
backend_dir = str(Path(__file__).resolve().parents[2])
sys.path.append(backend_dir)

# Import your custom database setup and models
from app.database.core import SessionLocal, engine 
from app.models.product import Base, Product, ProductEmbedding

# MUST IMPORT 'text' TO RUN RAW SQL
from sqlalchemy import text 

print("🏗️ Ensuring database tables exist...")

# STEP 1: Turn on the pgvector extension FIRST
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    conn.commit()

# STEP 2: Now that Postgres knows what a vector is, build the tables
Base.metadata.create_all(bind=engine)

# LangChain for embeddings
from langchain_huggingface import HuggingFaceEmbeddings

def clean_price(price_str: str) -> float:
    """Converts 'Rs 16,378' or 'Rs 8,231.00' into a clean float."""
    if not price_str:
        return 0.0
    # Remove everything except digits and decimals
    import re
    clean_str = re.sub(r'[^\d.]', '', str(price_str))
    return float(clean_str) if clean_str else 0.0

def extract_section_text(product_data: dict, section_name: str) -> str:
    """Extract text from a section if it exists, handling both string and dict values."""
    value = product_data.get(section_name)
    if isinstance(value, dict):
        # Convert nested dict to string representation
        return json.dumps(value, indent=2)
    elif isinstance(value, list):
        # Convert list to bullet points
        return '\n'.join([f"- {item}" for item in value])
    elif value:
        return str(value)
    return ""

def process_knowledge_base():
    # 1. Setup Database and Embedding Model
    print("🤖 Loading BAAI/bge-m3 embedding model (this may take a moment)...")
    embedding_model = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")
    
    db: Session = SessionLocal()
    
    # Define the directory containing your JSON files
    directory_path = os.path.join(
        os.environ.get("USERPROFILE", os.environ.get("HOME")), 
        "Desktop", "AI_SALES", "data","knowledge_base"
    )
    
    # Find all .json files in the directory and subdirectories
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
        
        # Handle both single product and array of products
        products = data if isinstance(data, list) else [data]
        
        for product_data in products:
            # --- Extract Product Information ---
            product_name = product_data.get("Product_id", "")
            if not product_name:
                print(f"  ⚠️ Skipping product with no name in {file_path}")
                error_count += 1
                continue
            
            order_code = product_data.get("Order Code", f"TEMP-{hash(product_name)}")
            
            # --- UPSERT LOGIC (Database Check) ---
            existing_product = db.query(Product).filter(Product.order_code == order_code).first()
            
            # Prepare metadata fields (map from JSON to database model)
            category = product_data.get("Category")
            sub_category = product_data.get("Sub-category")
            brand = product_data.get("Brand")
            price = clean_price(product_data.get("Price"))
            product_link = product_data.get("Product Link")
            datasheet_link = product_data.get("Data Sheet link") or product_data.get("Data Sheet")
            user_manual_link = product_data.get("User Manual") or product_data.get("User manual Link")
            sdk_link = product_data.get("Learning Center / SDK") or product_data.get("Learning Center SDK")
            
            # Extract bulk pricing if exists
            bulk_pricing = product_data.get("Bulk Pricing")
            if bulk_pricing and isinstance(bulk_pricing, list):
                bulk_pricing_str = "\n".join(bulk_pricing)
            else:
                bulk_pricing_str = None
            
            if existing_product:
                # Update existing structured data
                existing_product.name = product_name
                existing_product.category = category
                existing_product.sub_category = sub_category
                existing_product.brand = brand
                existing_product.single_price = price
                existing_product.product_link = product_link
                existing_product.datasheet_link = datasheet_link
                existing_product.user_manual_link = user_manual_link
                existing_product.sdk_link = sdk_link
                
                # Delete old embeddings for this product
                db.query(ProductEmbedding).filter(ProductEmbedding.product_id == existing_product.id).delete()
                product = existing_product
                updated_products += 1
                print(f"  🔄 Updated: {product_name}")
            else:
                # Create brand new product
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
                db.flush()
                new_products += 1
                print(f"  ✨ Created: {product_name}")
            
            # --- Extract Text for AI & Generate Semantic Chunks ---
            # Define sections to extract and embed
            sections_to_embed = [
                "Description",
                "Product Description",
                "Descriptions",
                "DESCRIPTION",
                "Features",
                "FEATURES",
                "Specifications",
                "Specification",
                "Specs",
                "Applications",
                "Application",
                "Benefits",
                "Advantages",
                "Operational Benefits",
                "Scope of Learning Experiments",
                "Package Contains",
                "Package Includes",
                "Note",
                "Notes",
                "Optional",
                "Microcontroller Unit",
                "Peripheral Features",
                "Analog Features",
                "Supported IC",
                "Specification",
                "Specifications",
                "Pin Configuration"
            ]
            
            # Also handle nested sections like Features as object
            features_obj = product_data.get("Features")
            if features_obj and isinstance(features_obj, dict):
                for feature_name, feature_value in features_obj.items():
                    contextualized_text = f"Product Name: {product_name}\nSection: {feature_name}\n\n{feature_value}"
                    try:
                        vector = embedding_model.embed_query(contextualized_text)
                        new_embedding = ProductEmbedding(
                            product_id=product.id,
                            chunk_type=feature_name.lower().replace(" ", "_"),
                            text_content=contextualized_text,
                            embedding=vector
                        )
                        db.add(new_embedding)
                        processed_chunks += 1
                    except Exception as e:
                        print(f"  ❌ Failed to embed {product_name} ({feature_name}): {e}")
                        error_count += 1
            
            # Process standard sections
            for section in sections_to_embed:
                section_text = extract_section_text(product_data, section)
                if section_text:
                    contextualized_text = f"Product Name: {product_name}\nSection: {section}\n\n{section_text}"
                    try:
                        vector = embedding_model.embed_query(contextualized_text)
                        new_embedding = ProductEmbedding(
                            product_id=product.id,
                            chunk_type=section.lower().replace(" ", "_"),
                            text_content=contextualized_text,
                            embedding=vector
                        )
                        db.add(new_embedding)
                        processed_chunks += 1
                    except Exception as e:
                        print(f"  ❌ Failed to embed {product_name} ({section}): {e}")
                        error_count += 1
            
            # Process bulk pricing if exists
            if bulk_pricing_str:
                contextualized_text = f"Product Name: {product_name}\nSection: Bulk Pricing\n\n{bulk_pricing_str}"
                try:
                    vector = embedding_model.embed_query(contextualized_text)
                    new_embedding = ProductEmbedding(
                        product_id=product.id,
                        chunk_type="bulk_pricing",
                        text_content=contextualized_text,
                        embedding=vector
                    )
                    db.add(new_embedding)
                    processed_chunks += 1
                except Exception as e:
                    print(f"  ❌ Failed to embed bulk pricing for {product_name}: {e}")
                    error_count += 1
            
            # Process "Frequently Bought Together" if exists
            fbt = product_data.get("Frequently Bought Together") or product_data.get("FREQUENTLY BOUGHT TOGETHER") or product_data.get("frequently Bought Together")
            if fbt:
                contextualized_text = f"Product Name: {product_name}\nSection: Frequently Bought Together\n\n{fbt}"
                try:
                    vector = embedding_model.embed_query(contextualized_text)
                    new_embedding = ProductEmbedding(
                        product_id=product.id,
                        chunk_type="frequently_bought_together",
                        text_content=contextualized_text,
                        embedding=vector
                    )
                    db.add(new_embedding)
                    processed_chunks += 1
                except Exception as e:
                    print(f"  ❌ Failed to embed FBT for {product_name}: {e}")
                    error_count += 1

    # 3. Final Commit
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