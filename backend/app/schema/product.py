from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from uuid import UUID


class ProductBase(BaseModel):
    name: str = Field(..., alias="Product_id")
    order_code: str = Field(..., alias="Order Code")
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

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ProductCreate(ProductBase):
    sections: Dict[str, Any] = Field(default_factory=dict)


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, alias="Product_id")
    order_code: Optional[str] = Field(None, alias="Order Code")
    category: Optional[str] = Field(None, alias="Category")
    sub_category: Optional[str] = Field(None, alias="Sub-category")
    brand: Optional[str] = Field(None, alias="Brand")
    single_price: Optional[float] = Field(None, alias="Price")

    product_link: Optional[str] = Field(None, alias="Product Link")
    datasheet_link: Optional[str] = Field(None, alias="Data Sheet link")
    user_manual_link: Optional[str] = Field(None, alias="User Manual")
    sdk_link: Optional[str] = Field(None, alias="Learning Center SDK")

    bulk_price: Optional[float] = None
    is_active: Optional[bool] = None

    sections: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ProductResponse(ProductBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
