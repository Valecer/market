"""Pydantic models for parsed supplier items."""
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from typing import Dict, Any
import json


class ParsedSupplierItem(BaseModel):
    """Validated supplier item parsed from data source.
    
    This model represents a single product item extracted from a supplier's
    price list (Google Sheets, CSV, Excel) with validated fields ready for
    database insertion.
    """
    
    supplier_sku: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Supplier's SKU identifier"
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Product name"
    )
    price: Decimal = Field(
        ...,
        ge=0,
        description="Current price (non-negative)"
    )
    characteristics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Flexible product attributes stored as JSONB"
    )
    
    @field_validator('price')
    @classmethod
    def validate_price_precision(cls, v: Decimal) -> Decimal:
        """Ensure price has at most 2 decimal places.
        
        Args:
            v: Price value to validate
        
        Returns:
            Price rounded to 2 decimal places
        
        Raises:
            ValueError: If price has more than 2 decimal places
        """
        # Get decimal tuple: (sign, digits, exponent)
        # exponent < -2 means more than 2 decimal places
        if v.as_tuple().exponent < -2:
            raise ValueError('Price must have at most 2 decimal places')
        # Quantize to 2 decimal places
        return v.quantize(Decimal('0.01'))
    
    @field_validator('characteristics')
    @classmethod
    def validate_characteristics_serializable(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure characteristics can be JSON serialized.
        
        Args:
            v: Characteristics dictionary to validate
        
        Returns:
            Validated characteristics dictionary
        
        Raises:
            ValueError: If characteristics cannot be JSON serialized
        """
        try:
            json.dumps(v)
        except (TypeError, ValueError) as e:
            raise ValueError(f'Characteristics must be JSON serializable: {e}')
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "supplier_sku": "ABC-12345",
                "name": "Cotton T-Shirt",
                "price": "19.99",
                "characteristics": {
                    "color": "blue",
                    "size": "M",
                    "material": "100% cotton"
                }
            }
        }
    }

