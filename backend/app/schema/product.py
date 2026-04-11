from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any

class ProductBase(BaseModel):
    # Standard Fields
    name: str = Field(..., alias="Product_id") 
    order_code: str = Field(..., alias="Order Code")
    category: str = Field(..., alias="Category")
    sub_category: Optional[str] = Field(None, alias="Sub-category") # ADDED THIS
    brand: Optional[str] = Field(None, alias="Brand")
    single_price: Optional[float] = Field(0.0, alias="Price")
    
    # Links
    product_link: Optional[str] = Field(None, alias="Product Link")
    datasheet_link: Optional[str] = Field(None, alias="Data Sheet link")
    user_manual_link: Optional[str] = Field(None, alias="User Manual")
    sdk_link: Optional[str] = Field(None, alias="Learning Center SDK")
    
    bulk_price: Optional[float] = 0.0
    is_active: bool = True

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

class ProductCreate(ProductBase):
    # This captures all the extra text for the AI
    sections: Dict[str, Any] = Field(default_factory=dict) 

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, alias="Product_id")
    category: Optional[str] = Field(None, alias="Category")
    sub_category: Optional[str] = Field(None, alias="Sub-category") # ADDED THIS
    brand: Optional[str] = Field(None, alias="Brand")
    single_price: Optional[float] = Field(None, alias="Price")
    sections: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

class ProductResponse(ProductBase):
    id: int
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)