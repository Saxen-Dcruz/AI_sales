from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from uuid import UUID


class FaqItem(BaseModel):
    question: str
    answer: str


class BulkPricingTier(BaseModel):
    quantity: Optional[float] = None
    price: Optional[float] = None


class ProductVariation(BaseModel):
    order_code: Optional[str] = None
    single_price: Optional[float] = None
    bulk_pricing: Optional[List[BulkPricingTier]] = None
    attributes: Optional[Dict[str, Any]] = None


class ProductBase(BaseModel):
    name: str = Field(..., alias="Product_id")
    order_code: Optional[str] = Field(None, alias="Order Code")
    category: str = Field(..., alias="Category")
    sub_category: Optional[str] = Field(None, alias="Sub-category")
    brand: Optional[str] = Field(None, alias="Brand")
    single_price: Optional[float] = Field(0.0, alias="Price")

    product_link: Optional[str] = Field(None, alias="Product Link")
    datasheet_link: Optional[str] = Field(None, alias="Data Sheet link")
    user_manual_link: Optional[str] = Field(None, alias="User Manual")
    sdk_link: Optional[str] = Field(None, alias="Learning Center SDK")

    bulk_price: Optional[float] = 0.0
    is_active: bool = True
    coverage_score: Optional[float] = None

    categories: Optional[List[str]] = None
    subcategories: Optional[List[str]] = None
    faqs: Optional[List[FaqItem]] = None
    bulk_pricing: Optional[List[BulkPricingTier]] = None
    variations: Optional[List[ProductVariation]] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ProductCreate(ProductBase):
    sections: Dict[str, Any] = Field(default_factory=dict)


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    order_code: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    brand: Optional[str] = None
    single_price: Optional[float] = None
    bulk_price: Optional[float] = None
    product_link: Optional[str] = None
    datasheet_link: Optional[str] = None
    user_manual_link: Optional[str] = None
    sdk_link: Optional[str] = None
    is_active: Optional[bool] = None
    sections: Optional[Dict[str, Any]] = None

    categories: Optional[List[str]] = None
    subcategories: Optional[List[str]] = None
    faqs: Optional[List[FaqItem]] = None
    bulk_pricing: Optional[List[BulkPricingTier]] = None
    variations: Optional[List[ProductVariation]] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ProductResponse(ProductBase):
    id: UUID
    sections: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
