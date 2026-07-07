from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.api.dependencies import get_current_user
from app.database.core import get_db
from app.models.product import Product
from app.models.user import User
from app.schema.product import ProductCreate, ProductResponse, ProductUpdate
from app.schema.product_knowledge import ChunkUpdate, KnowledgeEntryCreate, KnowledgeEntryListResponse, KnowledgeEntryOut, KnowledgeEntryUpdate
from app.services import product_service
from app.services import product_knowledge_service

router = APIRouter(prefix="/products", tags=["Knowledge Base"])


def _embedding_table_exists(db: Session) -> bool:
    """The pgvector `langchain_pg_embedding` table is created lazily on the first
    embed. Until something is ingested it won't exist, so guard reads against it
    to avoid a 500 (UndefinedTable) when no product has been embedded yet."""
    return db.execute(
        text("SELECT to_regclass('public.langchain_pg_embedding')")
    ).scalar() is not None


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def add_product(
    product: ProductCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        return await product_service.create_product(db, product, background_tasks)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/", response_model=List[ProductResponse])
def list_products(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return product_service.get_all_products(
        db, skip=skip, limit=limit,
        search=search, category=category, is_active=is_active,
    )


@router.get("/categories", summary="List distinct categories and subcategories for the Add Product form")
def list_categories(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return product_service.get_categories(db)


# ── Embedding inspection (must be before /{product_id} to avoid route shadowing) ──

@router.get("/embeddings", summary="List all products with their RAG embeddings and product details")
def list_all_embeddings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    products = db.query(Product).filter(Product.is_active == True).order_by(Product.name).all()
    rows = db.execute(text(
        "SELECT id, cmetadata, left(document, 500) AS doc_preview "
        "FROM langchain_pg_embedding ORDER BY cmetadata->>'product_id', cmetadata->>'chunk_type'"
    )).fetchall() if _embedding_table_exists(db) else []
    chunks_by_product: dict[str, list] = {}
    for row in rows:
        meta = row.cmetadata or {}
        pid = meta.get("product_id")
        if not pid:
            continue
        chunks_by_product.setdefault(pid, []).append({
            "chunk_id": str(row.id),
            "chunk_type": meta.get("chunk_type", "unknown"),
            "doc_preview": row.doc_preview,
        })
    result = []
    for p in products:
        pid = str(p.id)
        chunks = chunks_by_product.get(pid, [])
        result.append({
            "product_id": pid,
            "name": p.name,
            "order_code": p.order_code,
            "category": p.category,
            "single_price": p.single_price,
            "bulk_price": p.bulk_price,
            "brand": p.brand,
            "coverage_score": round((p.coverage_score or 0) * 100, 1),
            "is_active": p.is_active,
            "product_link": p.product_link,
            "datasheet_link": p.datasheet_link,
            "total_chunks": len(chunks),
            "chunk_types": sorted({c["chunk_type"] for c in chunks}),
            "chunks": chunks,
        })
    not_embedded = [r["name"] for r in result if r["total_chunks"] == 0]
    return {
        "total_products": len(result),
        "total_embeddings": len(rows),
        "not_embedded": not_embedded,
        "items": result,
    }


@router.get("/{product_id}", response_model=ProductResponse)
def view_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    product = product_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # Reconstruct sections from pgvector chunks so the edit form is pre-populated
    sections: dict = {}
    try:
        rows = db.execute(text(
            "SELECT cmetadata->>'chunk_type' AS chunk_type, document "
            "FROM langchain_pg_embedding "
            "WHERE cmetadata->>'product_id' = :pid"
        ), {"pid": str(product_id)}).fetchall() if _embedding_table_exists(db) else []
        for row in rows:
            ct = row.chunk_type or ""
            doc = row.document or ""
            if ct == "description" or ct == "product_description":
                # Strip the "Product Name: ... Section: Description\n\n" header
                body = doc.split("\n\n", 1)[-1].strip()
                sections["description"] = body
            elif ct == "features":
                body = doc.split("\n\n", 1)[-1].strip()
                # Each feature is a "- ..." line
                features = [
                    line.lstrip("- ").strip()
                    for line in body.splitlines()
                    if line.strip().startswith("-")
                ]
                if features:
                    sections["features"] = features
            elif ct in ("package_contains", "package_includes", "packagecontains"):
                body = doc.split("\n\n", 1)[-1].strip()
                items = [
                    line.lstrip("- ").strip()
                    for line in body.splitlines()
                    if line.strip().startswith("-")
                ]
                if items:
                    sections["packageContains"] = items
            elif ct in ("applications", "benefits", "enclosure_dimensions"):
                body = doc.split("\n\n", 1)[-1].strip()
                items = [
                    line.lstrip("- ").strip()
                    for line in body.splitlines()
                    if line.strip().startswith("-")
                ]
                if items:
                    sections[ct] = items
    except Exception:
        db.rollback()  # clear any aborted transaction; sections remain empty — not fatal

    # Build response dict manually so we can inject sections
    resp = ProductResponse.model_validate(product)
    data = resp.model_dump(by_alias=True, mode="json")
    data["sections"] = sections
    return data


@router.patch("/{product_id}", response_model=ProductResponse)
async def edit_product(
    product_id: UUID,
    product: ProductUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    updated = await product_service.update_product(db, product_id, product, background_tasks)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return updated


@router.patch("/{product_id}/availability", response_model=ProductResponse)
def toggle_availability(
    product_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Toggle a product between available (is_active=True) and unavailable (is_active=False).
    Unavailable products are excluded from RAG retrieval and the active catalog."""
    product = product_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product.is_active = not product.is_active
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    product = product_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    db.delete(product)
    db.commit()


# ── Product knowledge ─────────────────────────────────────────────────────────

@router.post("/{product_id}/knowledge", response_model=KnowledgeEntryOut, status_code=status.HTTP_201_CREATED)
def add_knowledge(
    product_id: UUID,
    payload: KnowledgeEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a knowledge entry for a product (warranty, compatibility, pricing, etc.)
    and embed it into the RAG vector store immediately."""
    try:
        return product_knowledge_service.add_entry(
            db=db,
            product_id=product_id,
            category=payload.category,
            content=payload.content,
            added_by=current_user.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{product_id}/knowledge", response_model=KnowledgeEntryListResponse)
def list_knowledge(
    product_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all knowledge entries for a product."""
    if not product_service.get_product(db, product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    items = product_knowledge_service.list_entries(db, product_id)
    return KnowledgeEntryListResponse(items=items, total=len(items))


@router.patch("/{product_id}/knowledge/{entry_id}", response_model=KnowledgeEntryOut)
def update_knowledge(
    product_id: UUID,
    entry_id: UUID,
    payload: KnowledgeEntryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Update a knowledge entry and re-embed it in the RAG vector store."""
    try:
        return product_knowledge_service.update_entry(
            db=db,
            entry_id=entry_id,
            category=payload.category,
            content=payload.content,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{product_id}/knowledge/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge(
    product_id: UUID,
    entry_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Remove a knowledge entry and delete it from the RAG vector store."""
    try:
        product_knowledge_service.delete_entry(db, entry_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{product_id}/embeddings", summary="Get all RAG chunks for a single product")
def get_product_embeddings(
    product_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Returns every pgvector chunk for the product with full document text and pricing."""
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    rows = db.execute(text(
        "SELECT id, cmetadata, document FROM langchain_pg_embedding "
        "WHERE cmetadata->>'product_id' = :pid ORDER BY cmetadata->>'chunk_type'"
    ), {"pid": str(product_id)}).fetchall() if _embedding_table_exists(db) else []
    chunks = [
        {
            "chunk_id": str(row.id),
            "chunk_type": (row.cmetadata or {}).get("chunk_type", "unknown"),
            "document": row.document,
        }
        for row in rows
    ]
    return {
        "product_id": str(p.id),
        "name": p.name,
        "order_code": p.order_code,
        "category": p.category,
        "sub_category": p.sub_category,
        "brand": p.brand,
        "single_price": p.single_price,
        "bulk_price": p.bulk_price,
        "coverage_score": round((p.coverage_score or 0) * 100, 1),
        "is_active": p.is_active,
        "product_link": p.product_link,
        "datasheet_link": p.datasheet_link,
        "user_manual_link": p.user_manual_link,
        "sdk_link": p.sdk_link,
        "total_chunks": len(chunks),
        "chunks": chunks,
    }


@router.patch("/{product_id}/chunks/{chunk_id}", summary="Edit a RAG chunk's text and re-embed it")
def update_chunk(
    product_id: UUID,
    chunk_id: str,
    payload: ChunkUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        product_knowledge_service.update_chunk(db, chunk_id, payload.content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"chunk_id": chunk_id, "document": payload.content}


@router.delete("/{product_id}/chunks/{chunk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chunk(
    product_id: UUID,
    chunk_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        product_knowledge_service.delete_chunk(db, chunk_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

