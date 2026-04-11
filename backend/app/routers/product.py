from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from app.database.core import get_db
from app.schema.product import ProductCreate, ProductUpdate, ProductResponse
from app.services import product_service

router = APIRouter(prefix="/products", tags=["Knowledge Base"])

@router.post("/", response_model=ProductResponse)
async def add_product(product: ProductCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    return await product_service.create_product(db, product, background_tasks)

@router.get("/", response_model=List[ProductResponse])
def list_products(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return product_service.get_all_products(db, skip, limit)

@router.get("/{product_id}", response_model=ProductResponse)
def view_product(product_id: int, db: Session = Depends(get_db)):
    product = product_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.put("/{product_id}", response_model=ProductResponse)
async def edit_product(product_id: int, product: ProductUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    updated = await product_service.update_product(db, product_id, product, background_tasks)
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found")
    return updated

@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = product_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product) # Model cascade handles embedding deletion
    db.commit()
    return {"message": "Product and associated vectors deleted successfully"}