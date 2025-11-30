"""Pydantic models for feature extraction pipeline.

This module defines the data transfer objects for extracted
technical specifications from supplier item text.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional


class DimensionsCm(BaseModel):
    """Physical dimensions in centimeters.
    
    Attributes:
        length: Length in cm
        width: Width in cm
        height: Height in cm
    """
    
    length: float = Field(..., ge=0, le=100000, description="Length in cm")
    width: float = Field(..., ge=0, le=100000, description="Width in cm")
    height: float = Field(..., ge=0, le=100000, description="Height in cm")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "length": 30.0,
                "width": 20.0,
                "height": 10.0
            }
        }
    }


class ExtractedFeatures(BaseModel):
    """Features extracted from supplier item text.
    
    All fields are optional since extraction may not find all values.
    Values are validated to ensure they are within realistic ranges.
    
    Attributes:
        voltage: Electrical voltage (V)
        power_watts: Power consumption/output (W)
        weight_kg: Weight in kilograms
        dimensions_cm: Physical dimensions (L x W x H in cm)
        storage_gb: Storage capacity for electronics (GB)
        memory_gb: RAM/memory for electronics (GB)
    """
    
    # Electrical specifications
    voltage: Optional[int] = Field(
        default=None,
        ge=0,
        le=10000,
        description="Voltage in volts"
    )
    power_watts: Optional[int] = Field(
        default=None,
        ge=0,
        le=100000,
        description="Power in watts"
    )
    
    # Physical specifications
    weight_kg: Optional[float] = Field(
        default=None,
        ge=0,
        le=10000,
        description="Weight in kilograms"
    )
    dimensions_cm: Optional[DimensionsCm] = Field(
        default=None,
        description="Dimensions (length x width x height) in cm"
    )
    
    # Electronics specifications
    storage_gb: Optional[int] = Field(
        default=None,
        ge=0,
        le=100000,
        description="Storage capacity in GB"
    )
    memory_gb: Optional[int] = Field(
        default=None,
        ge=0,
        le=1000,
        description="Memory/RAM in GB"
    )
    
    @field_validator('voltage', mode='before')
    @classmethod
    def validate_voltage(cls, v):
        """Skip invalid voltage values."""
        if v is None:
            return None
        if isinstance(v, str):
            if v.lower() in ('tbd', 'n/a', 'na', '-', ''):
                return None
            try:
                v = int(float(v))
            except ValueError:
                return None
        if v < 0 or v > 10000:
            return None
        return v
    
    @field_validator('power_watts', mode='before')
    @classmethod
    def validate_power_watts(cls, v):
        """Skip invalid power values."""
        if v is None:
            return None
        if isinstance(v, str):
            if v.lower() in ('tbd', 'n/a', 'na', '-', ''):
                return None
            try:
                v = int(float(v))
            except ValueError:
                return None
        if v < 0 or v > 100000:
            return None
        return v
    
    @field_validator('weight_kg', mode='before')
    @classmethod
    def validate_weight(cls, v):
        """Skip invalid weight values."""
        if v is None:
            return None
        if isinstance(v, str):
            if v.lower() in ('tbd', 'n/a', 'na', '-', ''):
                return None
            try:
                v = float(v)
            except ValueError:
                return None
        if v < 0 or v > 10000:
            return None
        return v
    
    def to_characteristics(self) -> Dict[str, Any]:
        """Convert extracted features to characteristics JSONB format.
        
        Returns a flat dictionary suitable for merging with existing
        supplier_items.characteristics JSONB field.
        
        Returns:
            Dictionary with non-None values, dimensions flattened
        """
        result: Dict[str, Any] = {}
        
        if self.voltage is not None:
            result['voltage'] = self.voltage
        
        if self.power_watts is not None:
            result['power_watts'] = self.power_watts
        
        if self.weight_kg is not None:
            result['weight_kg'] = self.weight_kg
        
        if self.dimensions_cm is not None:
            result['dimensions_cm'] = {
                'length': self.dimensions_cm.length,
                'width': self.dimensions_cm.width,
                'height': self.dimensions_cm.height
            }
        
        if self.storage_gb is not None:
            result['storage_gb'] = self.storage_gb
        
        if self.memory_gb is not None:
            result['memory_gb'] = self.memory_gb
        
        return result
    
    def has_any_features(self) -> bool:
        """Check if any features were extracted.
        
        Returns:
            True if at least one feature has a value
        """
        return any([
            self.voltage is not None,
            self.power_watts is not None,
            self.weight_kg is not None,
            self.dimensions_cm is not None,
            self.storage_gb is not None,
            self.memory_gb is not None,
        ])
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "voltage": 220,
                "power_watts": 750,
                "weight_kg": 2.5,
                "dimensions_cm": {
                    "length": 30.0,
                    "width": 20.0,
                    "height": 10.0
                }
            }
        }
    }


class ExtractionResult(BaseModel):
    """Result of running extractors on a supplier item.
    
    Attributes:
        supplier_item_id: Item that was processed
        extracted: Features that were extracted
        extractors_applied: Names of extractors that found data
        source_text: Original text that was analyzed
    """
    
    supplier_item_id: str = Field(..., description="UUID of processed item")
    extracted: ExtractedFeatures
    extractors_applied: list[str] = Field(default_factory=list)
    source_text: str = Field(..., max_length=1000)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "supplier_item_id": "770e8400-e29b-41d4-a716-446655440000",
                "extracted": {
                    "voltage": 220,
                    "power_watts": 750
                },
                "extractors_applied": ["electronics"],
                "source_text": "Bosch Drill 750W 220V Professional"
            }
        }
    }

