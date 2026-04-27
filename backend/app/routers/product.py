from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.api.dependencies import get_current_user
from app.database.core import get_db
from app.models.user import User
from app.schema.product import ProductCreate, ProductResponse, ProductUpdate
from app.schema.product_knowledge import KnowledgeEntryCreate, KnowledgeEntryListResponse, KnowledgeEntryOut, KnowledgeEntryUpdate
from app.services import product_service
from app.services import product_knowledge_service

router = APIRouter(prefix="/products", tags=["Knowledge Base"])


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
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return product_service.get_all_products(db, skip, limit)


@router.get("/{product_id}", response_model=ProductResponse)
def view_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    product = product_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


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
