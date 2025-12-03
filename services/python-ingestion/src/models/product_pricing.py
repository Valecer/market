"""Pydantic models for product pricing validation.

Phase 9: Advanced Pricing & Categorization

These models validate pricing data for API requests and responses.
"""
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
import re
from typing import Optional


class ProductPricingUpdate(BaseModel):
    """Schema for updating product pricing fields.
    
    All fields are optional to support partial updates.
    
    Attributes:
        retail_price: End-customer price (must be >= 0)
        wholesale_price: Bulk/dealer price (must be >= 0)
        currency_code: ISO 4217 currency code (3 uppercase letters)
    """
    retail_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        decimal_places=2,
        description="End-customer price"
    )
    wholesale_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        decimal_places=2,
        description="Bulk/dealer price"
    )
    currency_code: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code (e.g., USD, EUR, RUB)"
    )
    
    @field_validator('currency_code')
    @classmethod
    def validate_currency_code(cls, v: str | None) -> str | None:
        """Validate currency code is 3 uppercase letters (ISO 4217 format)."""
        if v is None:
            return v
        if not re.match(r'^[A-Z]{3}$', v):
            raise ValueError('Currency code must be 3 uppercase letters (ISO 4217 format)')
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "retail_price": "99.99",
                    "wholesale_price": "79.99",
                    "currency_code": "USD"
                },
                {
                    "retail_price": "149.99"
                },
                {
                    "currency_code": "EUR"
                }
            ]
        }
    }


class ProductPricingResponse(BaseModel):
    """Schema for product pricing in API responses.
    
    Includes both aggregate pricing (min_price) and canonical pricing
    (retail_price, wholesale_price) for full product context.
    """
    id: str = Field(description="Product UUID")
    internal_sku: str = Field(description="Internal SKU code")
    name: str = Field(description="Product name")
    category_id: str | None = Field(description="Category UUID or null")
    status: str = Field(description="Product status (draft, active, archived)")
    
    # Aggregate fields (from supplier items)
    min_price: Decimal | None = Field(
        default=None,
        description="Lowest price among linked supplier items"
    )
    availability: bool = Field(
        default=False,
        description="TRUE if any linked supplier has stock"
    )
    mrp: Decimal | None = Field(
        default=None,
        description="Manufacturer's recommended price"
    )
    
    # Phase 9: Canonical pricing fields
    retail_price: Decimal | None = Field(
        default=None,
        description="End-customer price (canonical product-level)"
    )
    wholesale_price: Decimal | None = Field(
        default=None,
        description="Bulk/dealer price (canonical product-level)"
    )
    currency_code: str | None = Field(
        default=None,
        description="ISO 4217 currency code"
    )
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "internal_sku": "PROD-001",
                    "name": "USB-C Cable 2m",
                    "category_id": "660e8400-e29b-41d4-a716-446655440000",
                    "status": "active",
                    "min_price": "9.99",
                    "availability": True,
                    "mrp": "19.99",
                    "retail_price": "14.99",
                    "wholesale_price": "11.99",
                    "currency_code": "USD"
                }
            ]
        }
    }


class ProductPricingBulkUpdate(BaseModel):
    """Schema for bulk updating product pricing.
    
    Allows updating pricing for multiple products at once.
    """
    product_ids: list[str] = Field(
        min_length=1,
        description="List of product UUIDs to update"
    )
    retail_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        decimal_places=2,
        description="End-customer price to set"
    )
    wholesale_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        decimal_places=2,
        description="Bulk/dealer price to set"
    )
    currency_code: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code"
    )
    
    @field_validator('currency_code')
    @classmethod
    def validate_currency_code(cls, v: str | None) -> str | None:
        """Validate currency code is 3 uppercase letters (ISO 4217 format)."""
        if v is None:
            return v
        if not re.match(r'^[A-Z]{3}$', v):
            raise ValueError('Currency code must be 3 uppercase letters (ISO 4217 format)')
        return v

