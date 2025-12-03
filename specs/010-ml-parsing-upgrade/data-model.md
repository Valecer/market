# Data Model: ML Parsing Service Upgrade

**Date:** 2025-12-03

**Status:** Complete

---

## Overview

Data model extensions for the ML Parsing Service upgrade. This document defines new Pydantic models for two-stage parsing, extended NormalizedRow with pricing fields, and parsing metrics.

---

## Entity Relationship

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Parsing Flow                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   FileAnalysisRequest                                                        │
│         │                                                                    │
│         │ file_path                                                          │
│         ▼                                                                    │
│   ┌─────────────┐                                                            │
│   │ SecureFile  │ ◄─── Path validation                                       │
│   │ Reader      │      (prevent traversal)                                   │
│   └──────┬──────┘                                                            │
│          │                                                                   │
│          │ raw document data                                                 │
│          ▼                                                                   │
│   ┌─────────────────┐        ┌─────────────────────┐                        │
│   │ Stage A:        │        │ StructureAnalysis   │                        │
│   │ Structure       │───────►│ - header_rows       │                        │
│   │ Analysis        │        │ - data_start_row    │                        │
│   └─────────────────┘        │ - data_end_row      │                        │
│                              │ - column_mapping    │                        │
│                              │ - confidence        │                        │
│                              └──────────┬──────────┘                        │
│                                         │                                    │
│                                         │ column context                     │
│                                         ▼                                    │
│   ┌─────────────────┐        ┌─────────────────────┐                        │
│   │ Stage B:        │        │ NormalizedRow       │                        │
│   │ Data            │───────►│ (Extended)          │                        │
│   │ Extraction      │        │ - name              │                        │
│   └─────────────────┘        │ - retail_price      │                        │
│          │                   │ - wholesale_price   │                        │
│          │                   │ - currency_code     │                        │
│          │                   │ - category_path[]   │                        │
│          │                   │ - raw_composite     │                        │
│          │                   └─────────────────────┘                        │
│          │                                                                   │
│          │ metrics                                                           │
│          ▼                                                                   │
│   ┌─────────────────────┐                                                    │
│   │ ParsingMetrics      │                                                    │
│   │ - total_rows        │                                                    │
│   │ - parsed_rows       │                                                    │
│   │ - skipped_rows      │                                                    │
│   │ - stage_a_tokens    │                                                    │
│   │ - stage_b_tokens    │                                                    │
│   │ - duration_ms       │                                                    │
│   └─────────────────────┘                                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## New Models

### StructureAnalysis

**Purpose:** Stage A output capturing document structure understanding from LLM.

**Location:** `services/ml-analyze/src/schemas/domain.py`

```python
from pydantic import BaseModel, Field
from typing import Annotated, Literal

class ColumnMapping(BaseModel):
    """Mapping of column index to field purpose."""
    
    name_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for product name")
    ] = None
    sku_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for SKU/article")
    ] = None
    retail_price_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for retail price")
    ] = None
    wholesale_price_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for wholesale price")
    ] = None
    category_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for category")
    ] = None
    unit_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for unit of measure")
    ] = None
    description_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for description")
    ] = None
    brand_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for brand")
    ] = None


class StructureAnalysis(BaseModel):
    """
    Stage A output: Document structure analysis result.
    
    Captures LLM's understanding of document layout including
    header positions, data row boundaries, and column purposes.
    
    Attributes:
        header_rows: List of row indices containing headers (0-indexed)
        data_start_row: First row index with product data
        data_end_row: Last row index with product data (-1 for end of document)
        column_mapping: Mapping of columns to field purposes
        confidence: LLM's confidence in the analysis (0.0-1.0)
        detected_currency: Currency detected in headers or data sample
        has_merged_cells: Whether document appears to have merged cells
        notes: Optional LLM notes about document structure
    
    Example:
        {
            "header_rows": [0, 1],
            "data_start_row": 2,
            "data_end_row": -1,
            "column_mapping": {
                "name_column": 1,
                "sku_column": 0,
                "retail_price_column": 3
            },
            "confidence": 0.92
        }
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "header_rows": [0],
                "data_start_row": 1,
                "data_end_row": -1,
                "column_mapping": {
                    "name_column": 1,
                    "sku_column": 0,
                    "retail_price_column": 2,
                    "wholesale_price_column": 3,
                },
                "confidence": 0.95,
                "detected_currency": "RUB",
                "has_merged_cells": False,
            }
        }
    )
    
    header_rows: Annotated[
        list[int],
        Field(min_length=0, description="Row indices containing headers (0-indexed)")
    ]
    data_start_row: Annotated[
        int,
        Field(ge=0, description="First row with product data")
    ]
    data_end_row: Annotated[
        int,
        Field(description="Last row with product data (-1 = end of document)")
    ]
    column_mapping: Annotated[
        ColumnMapping,
        Field(description="Column index to field purpose mapping")
    ]
    confidence: Annotated[
        float,
        Field(ge=0.0, le=1.0, description="Analysis confidence score")
    ]
    detected_currency: Annotated[
        str | None,
        Field(default=None, max_length=3, description="ISO 4217 currency code if detected")
    ] = None
    has_merged_cells: Annotated[
        bool,
        Field(default=False, description="Document has merged cells")
    ] = False
    notes: Annotated[
        str | None,
        Field(default=None, max_length=500, description="LLM notes about structure")
    ] = None
```

---

### NormalizedRow (Extended)

**Purpose:** Extended normalized row with pricing and composite name support.

**Location:** `services/ml-analyze/src/schemas/domain.py` (modify existing)

```python
class NormalizedRow(BaseModel):
    """
    Normalized product data from file parser.
    
    Extended with:
    - Dual pricing (retail_price, wholesale_price)
    - Currency code
    - Category path hierarchy
    - Raw composite string preservation
    
    All parsers (Excel, PDF, CSV) output this format.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Shtenli Model Gt11",
                "description": "Li-ion 48V 15Ah electric bicycle",
                "price": 85000.00,  # Deprecated: use retail_price
                "retail_price": 95000.00,
                "wholesale_price": 85000.00,
                "currency_code": "RUB",
                "sku": "SHTGT11-48V",
                "category": "Electric Bicycle",  # Deprecated: use category_path
                "category_path": ["Electric Bicycle", "Adult"],
                "unit": "шт",
                "brand": "Shtenli",
                "characteristics": {"voltage": "48V", "battery": "15Ah"},
                "raw_composite": "Electric Bicycle | Shtenli Model Gt11 | Li-ion 48V 15Ah",
                "raw_data": {"col_a": "SHTGT11-48V", "col_b": "..."},
            }
        }
    )
    
    # Existing fields
    name: Annotated[
        str,
        Field(min_length=1, max_length=500, description="Product name"),
    ]
    description: Annotated[
        str | None,
        Field(default=None, max_length=2000, description="Product description"),
    ] = None
    price: Annotated[
        Decimal | None,
        Field(default=None, ge=0, description="Product price (deprecated, use retail_price)"),
    ] = None
    sku: Annotated[
        str | None,
        Field(default=None, max_length=255, description="Supplier SKU"),
    ] = None
    category: Annotated[
        str | None,
        Field(default=None, max_length=255, description="Category (deprecated, use category_path)"),
    ] = None
    unit: Annotated[
        str | None,
        Field(default=None, max_length=50, description="Unit of measure"),
    ] = None
    brand: Annotated[
        str | None,
        Field(default=None, max_length=255, description="Brand name"),
    ] = None
    characteristics: Annotated[
        dict[str, Any],
        Field(default_factory=dict, description="Additional attributes"),
    ]
    raw_data: Annotated[
        dict[str, Any] | None,
        Field(default=None, description="Original row data for debugging"),
    ] = None
    
    # NEW: Pricing fields (Phase 10)
    retail_price: Annotated[
        Decimal | None,
        Field(default=None, ge=0, description="End-customer retail price"),
    ] = None
    wholesale_price: Annotated[
        Decimal | None,
        Field(default=None, ge=0, description="Dealer/bulk wholesale price"),
    ] = None
    currency_code: Annotated[
        str | None,
        Field(default=None, min_length=3, max_length=3, description="ISO 4217 currency code"),
    ] = None
    
    # NEW: Composite name fields (Phase 10)
    category_path: Annotated[
        list[str],
        Field(default_factory=list, description="Hierarchical category path"),
    ]
    raw_composite: Annotated[
        str | None,
        Field(default=None, max_length=1000, description="Original composite string before parsing"),
    ] = None
    
    @model_validator(mode='after')
    def sync_deprecated_fields(self) -> 'NormalizedRow':
        """Sync deprecated fields with new fields for backward compatibility."""
        # If retail_price set but not price, copy to price
        if self.retail_price is not None and self.price is None:
            self.price = self.retail_price
        # If price set but not retail_price, copy to retail_price
        elif self.price is not None and self.retail_price is None:
            self.retail_price = self.price
            
        # If category_path set but not category, use first element
        if self.category_path and not self.category:
            self.category = self.category_path[0]
        # If category set but not category_path, create single-element list
        elif self.category and not self.category_path:
            self.category_path = [self.category]
            
        return self
```

---

### ParsingMetrics

**Purpose:** Quality metrics for completed parsing job.

**Location:** `services/ml-analyze/src/schemas/domain.py`

```python
class ParsingMetrics(BaseModel):
    """
    Quality metrics for a parsing job.
    
    Tracks row counts, token usage, timing, and per-field extraction rates.
    
    Attributes:
        total_rows: Total rows in source document
        parsed_rows: Successfully parsed rows
        skipped_rows: Intentionally skipped rows (headers, totals, empty)
        error_rows: Rows with parsing errors
        stage_a_tokens: LLM tokens used for structure analysis
        stage_b_tokens: LLM tokens used for data extraction
        duration_ms: Total processing time in milliseconds
        file_read_ms: Time to read file
        stage_a_ms: Time for structure analysis
        stage_b_ms: Time for data extraction
        db_write_ms: Time for database writes
        field_extraction_rates: Per-field extraction success rates
    
    Example:
        {
            "total_rows": 500,
            "parsed_rows": 480,
            "skipped_rows": 15,
            "error_rows": 5,
            "stage_a_tokens": 1200,
            "stage_b_tokens": 8500,
            "duration_ms": 45000,
            "field_extraction_rates": {
                "name": 1.0,
                "sku": 0.95,
                "retail_price": 0.98,
                "category": 0.85
            }
        }
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_rows": 500,
                "parsed_rows": 480,
                "skipped_rows": 15,
                "error_rows": 5,
                "stage_a_tokens": 1200,
                "stage_b_tokens": 8500,
                "duration_ms": 45000,
            }
        }
    )
    
    # Row counts
    total_rows: Annotated[
        int,
        Field(ge=0, description="Total rows in source document")
    ]
    parsed_rows: Annotated[
        int,
        Field(ge=0, description="Successfully parsed rows")
    ]
    skipped_rows: Annotated[
        int,
        Field(ge=0, default=0, description="Intentionally skipped rows")
    ] = 0
    error_rows: Annotated[
        int,
        Field(ge=0, default=0, description="Rows with parsing errors")
    ] = 0
    
    # Token usage
    stage_a_tokens: Annotated[
        int,
        Field(ge=0, default=0, description="Tokens used in Stage A")
    ] = 0
    stage_b_tokens: Annotated[
        int,
        Field(ge=0, default=0, description="Tokens used in Stage B")
    ] = 0
    
    # Timing breakdown
    duration_ms: Annotated[
        int,
        Field(ge=0, description="Total processing time (ms)")
    ]
    file_read_ms: Annotated[
        int,
        Field(ge=0, default=0, description="File read time (ms)")
    ] = 0
    stage_a_ms: Annotated[
        int,
        Field(ge=0, default=0, description="Stage A duration (ms)")
    ] = 0
    stage_b_ms: Annotated[
        int,
        Field(ge=0, default=0, description="Stage B duration (ms)")
    ] = 0
    db_write_ms: Annotated[
        int,
        Field(ge=0, default=0, description="Database write time (ms)")
    ] = 0
    
    # Per-field extraction rates
    field_extraction_rates: Annotated[
        dict[str, float],
        Field(
            default_factory=dict,
            description="Per-field extraction success rate (0.0-1.0)"
        )
    ]
    
    @property
    def total_tokens(self) -> int:
        """Total LLM tokens used."""
        return self.stage_a_tokens + self.stage_b_tokens
    
    @property
    def success_rate(self) -> float:
        """Parsing success rate (0.0-1.0)."""
        if self.total_rows == 0:
            return 0.0
        return self.parsed_rows / self.total_rows
```

---

### CompositeNameResult

**Purpose:** Result of parsing a composite product name string.

**Location:** `services/ml-analyze/src/utils/name_parser.py` (new file)

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CompositeNameResult:
    """
    Result of parsing a composite product name string.
    
    Immutable data class for composite name parsing output.
    
    Attributes:
        category_path: Hierarchical categories (e.g., ["Electronics", "Phones"])
        name: Extracted product name
        description: Additional description/specs (may be None)
        raw_composite: Original string before parsing
    
    Example:
        Input: "Electronics | iPhone 15 Pro | 256GB Space Black"
        Output:
            category_path: ["Electronics"]
            name: "iPhone 15 Pro"
            description: "256GB Space Black"
            raw_composite: "Electronics | iPhone 15 Pro | 256GB Space Black"
    """
    
    category_path: list[str]
    name: str
    description: str | None
    raw_composite: str
```

---

### PriceResult

**Purpose:** Result of extracting price and currency from a string.

**Location:** `services/ml-analyze/src/utils/price_parser.py` (new file)

```python
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class PriceResult:
    """
    Result of price extraction.
    
    Attributes:
        amount: Decimal price value
        currency_code: ISO 4217 currency code (may be None if not detected)
        raw_value: Original string
    
    Example:
        Input: "₽ 25 500.00"
        Output:
            amount: Decimal("25500.00")
            currency_code: "RUB"
            raw_value: "₽ 25 500.00"
    """
    
    amount: Decimal
    currency_code: str | None
    raw_value: str
```

---

## Request/Response Models

### FileAnalysisRequest (Extended)

**Location:** `services/ml-analyze/src/schemas/requests.py` (modify existing)

```python
class FileAnalysisRequest(BaseModel):
    """
    Request body for POST /analyze/file endpoint.
    
    Extended with:
    - file_path: Direct path to file in shared volume
    - file_url: Deprecated but still supported for backward compatibility
    - default_currency: Supplier's default currency if not detected
    - delimiter: Custom delimiter for composite name parsing
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_path": "/shared/uploads/supplier_123_20251203_price-list.xlsx",
                "supplier_id": "123e4567-e89b-12d3-a456-426614174000",
                "file_type": "excel",
                "default_currency": "RUB",
                "composite_delimiter": "|",
            }
        }
    )
    
    # NEW: Direct file path (preferred)
    file_path: Annotated[
        str | None,
        Field(
            default=None,
            description="Path to file in shared volume (e.g., /shared/uploads/file.xlsx)",
            examples=["/shared/uploads/supplier-data.xlsx"],
        ),
    ] = None
    
    # Existing: URL-based (deprecated but supported)
    file_url: Annotated[
        HttpUrl | str | None,
        Field(
            default=None,
            description="HTTP URL or file:// path (deprecated, use file_path)",
            examples=["https://example.com/price-list.pdf"],
        ),
    ] = None
    
    supplier_id: Annotated[
        UUID,
        Field(description="UUID of the supplier this file belongs to"),
    ]
    file_type: Annotated[
        Literal["pdf", "excel", "csv"],
        Field(description="Type of file being analyzed"),
    ]
    
    # NEW: Parsing options
    default_currency: Annotated[
        str | None,
        Field(
            default=None,
            min_length=3,
            max_length=3,
            description="Default ISO 4217 currency code if not detected in document",
        ),
    ] = None
    composite_delimiter: Annotated[
        str,
        Field(
            default="|",
            min_length=1,
            max_length=5,
            description="Delimiter for composite product name strings",
        ),
    ] = "|"
    
    @model_validator(mode='after')
    def require_file_source(self) -> 'FileAnalysisRequest':
        """Ensure at least one file source is provided."""
        if not self.file_path and not self.file_url:
            raise ValueError("Either file_path or file_url must be provided")
        return self
```

---

### FileAnalysisResponse (Extended)

**Location:** `services/ml-analyze/src/schemas/responses.py` (modify existing)

```python
class FileAnalysisResponse(BaseModel):
    """
    Response for POST /analyze/file endpoint.
    
    Extended with metrics field for parsing quality information.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "message": "File analysis job enqueued successfully",
                "metrics": None,  # Populated when status is complete
            }
        }
    )
    
    job_id: Annotated[
        UUID,
        Field(description="Unique job identifier for status tracking"),
    ]
    status: Annotated[
        Literal["pending", "processing", "complete", "failed"],
        Field(description="Current job status"),
    ]
    message: Annotated[
        str,
        Field(description="Human-readable status message"),
    ]
    metrics: Annotated[
        ParsingMetrics | None,
        Field(default=None, description="Parsing metrics (populated when complete)"),
    ] = None
```

---

## Database Considerations

### No Schema Changes Required

The Phase 9 schema already includes the necessary fields:
- `supplier_items.retail_price` - DECIMAL(10,2)
- `supplier_items.wholesale_price` - DECIMAL(10,2)
- `supplier_items.currency_code` - VARCHAR(3)

The `characteristics` JSONB field can store:
- `category_path` - Hierarchical category array
- `raw_composite` - Original composite string

### Sample characteristics JSONB

```json
{
  "voltage": "48V",
  "battery": "15Ah",
  "category_path": ["Electric Bicycle", "Adult"],
  "raw_composite": "Electric Bicycle | Shtenli Model Gt11 | Li-ion 48V 15Ah"
}
```

---

## Validation Rules

### StructureAnalysis
- `header_rows`: Must be valid 0-indexed row numbers
- `data_start_row`: Must be ≥ max(header_rows) when headers exist
- `data_end_row`: Must be > data_start_row (or -1 for end)
- `confidence`: Must be between 0.0 and 1.0

### NormalizedRow (Extended)
- `currency_code`: Must be exactly 3 uppercase letters (ISO 4217)
- `retail_price`, `wholesale_price`: Must be ≥ 0 if provided
- `category_path`: Each element max 255 characters
- `raw_composite`: Preserved for debugging, max 1000 chars

### ParsingMetrics
- `parsed_rows + skipped_rows + error_rows` should equal `total_rows`
- `duration_ms` ≥ sum of all timing breakdown fields
- Token counts are estimates from LLM response metadata

---

## Migration Notes

### Backward Compatibility

1. **`price` field**: Still populated for backward compatibility, synced from `retail_price`
2. **`category` field**: Still populated, uses first element of `category_path`
3. **`file_url` parameter**: Still accepted, deprecated in favor of `file_path`
4. **Existing parsers**: Will work unchanged, new fields are optional

### Deprecation Timeline

| Field/Parameter | Status | Removal Target |
|-----------------|--------|----------------|
| `NormalizedRow.price` | Deprecated | Phase 12 |
| `NormalizedRow.category` | Deprecated | Phase 12 |
| `FileAnalysisRequest.file_url` | Deprecated | Phase 12 |

---

## References

- Phase 7 ML-Analyze Spec: `/specs/007-ml-analyze/spec.md`
- Phase 9 Pricing Schema: `/specs/009-advanced-pricing-categories/spec.md`
- Research Document: `./research.md`

