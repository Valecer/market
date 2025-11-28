# Data Model: Data Ingestion Infrastructure

**Date:** 2025-11-23  
**Feature:** 001-data-ingestion-infra  
**Status:** Draft

---

## Overview

This document defines the complete data model for the Data Ingestion Infrastructure, including database schema, SQLAlchemy ORM models, Pydantic validation models, and entity relationships.

---

## Entity Relationship Diagram

```
┌─────────────────┐
│   Categories    │
│─────────────────│
│ id (PK)         │──┐
│ name            │  │
│ parent_id (FK)  │──┘ (Self-referential for hierarchy)
│ created_at      │
└─────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────────┐
│      Products           │
│─────────────────────────│
│ id (PK)                 │
│ internal_sku (UNIQUE)   │
│ name                    │
│ category_id (FK)        │
│ status (ENUM)           │───── NEW: draft/active/archived
│ created_at              │
│ updated_at              │
└─────────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────────────────┐         ┌─────────────────┐
│       SupplierItems             │   N:1   │   Suppliers     │
│─────────────────────────────────│◄────────│─────────────────│
│ id (PK)                         │         │ id (PK)         │
│ supplier_id (FK)                │         │ name            │
│ product_id (FK, nullable)       │         │ source_type     │
│ supplier_sku                    │         │ contact_email   │
│ name                            │         │ metadata        │
│ current_price                   │         │ created_at      │
│ characteristics (JSONB)         │         │ updated_at      │
│ last_ingested_at                │         └─────────────────┘
│ created_at                      │
│ updated_at                      │
│ UNIQUE(supplier_id, supplier_sku)│
└─────────────────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────────┐
│    PriceHistory         │
│─────────────────────────│
│ id (PK)                 │
│ supplier_item_id (FK)   │
│ price                   │
│ recorded_at             │
└─────────────────────────┘

┌─────────────────────────┐
│    ParsingLogs          │───── NEW: Error tracking
│─────────────────────────│
│ id (PK)                 │
│ task_id                 │
│ supplier_id (FK)        │
│ error_type              │
│ error_message           │
│ row_number              │
│ row_data (JSONB)        │
│ created_at              │
└─────────────────────────┘
```

---

## Database Schema (PostgreSQL)

### 1. Suppliers Table

Stores external data sources providing price lists.

```sql
CREATE TABLE suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) NOT NULL CHECK (source_type IN ('google_sheets', 'csv', 'excel')),
    contact_email VARCHAR(255),
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_suppliers_source_type ON suppliers(source_type);
CREATE INDEX idx_suppliers_name ON suppliers(name);
```

**Fields:**
- `id`: Unique identifier (UUID)
- `name`: Supplier business name
- `source_type`: Data source format (google_sheets, csv, excel)
- `contact_email`: Optional supplier contact
- `metadata`: Flexible JSONB for source-specific config (sheet URLs, credentials, etc.)
- `created_at`: Record creation timestamp (UTC)
- `updated_at`: Last modification timestamp (UTC)

**Indexes:**
- Primary key on `id`
- Index on `source_type` for filtering by data source
- Index on `name` for lookups

---

### 2. Categories Table

Product classification hierarchy with self-referential parent-child relationships.

```sql
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    parent_id UUID REFERENCES categories(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_categories_parent ON categories(parent_id);
CREATE UNIQUE INDEX idx_categories_name_parent ON categories(name, COALESCE(parent_id, '00000000-0000-0000-0000-000000000000'::uuid));
```

**Fields:**
- `id`: Unique identifier (UUID)
- `name`: Category name (e.g., "Electronics", "Cables")
- `parent_id`: Reference to parent category (NULL for root categories)
- `created_at`: Record creation timestamp (UTC)

**Constraints:**
- Self-referential foreign key on `parent_id`
- Unique combination of `name` and `parent_id` (prevents duplicate categories at same level)
- CASCADE delete removes child categories when parent is deleted

**Indexes:**
- Primary key on `id`
- Index on `parent_id` for hierarchy traversal
- Composite unique index on `(name, parent_id)`

---

### 3. Products Table

Internal unified catalog with status tracking for draft/active states.

```sql
CREATE TYPE product_status AS ENUM ('draft', 'active', 'archived');

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    internal_sku VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(500) NOT NULL,
    category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
    status product_status NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_status ON products(status);
CREATE INDEX idx_products_name ON products(name varchar_pattern_ops);
CREATE INDEX idx_products_sku ON products(internal_sku);
```

**Fields:**
- `id`: Unique identifier (UUID)
- `internal_sku`: Unified SKU across all suppliers (unique)
- `name`: Product name (max 500 chars)
- `category_id`: Reference to category (nullable)
- `status`: Product lifecycle state (draft/active/archived)
- `created_at`: Record creation timestamp (UTC)
- `updated_at`: Last modification timestamp (UTC)

**Status Enum:**
- `draft`: Product not yet published to external systems
- `active`: Product available for use
- `archived`: Product no longer active but retained for history

**Constraints:**
- Unique constraint on `internal_sku`
- Foreign key to `categories` with SET NULL on delete (preserves products when category removed)

**Indexes:**
- Primary key on `id`
- Unique index on `internal_sku`
- Index on `category_id` for category-based queries
- Index on `status` for filtering by lifecycle state
- Pattern ops index on `name` for LIKE queries
-

---

### 4. SupplierItems Table

Raw product data from supplier price lists with flexible characteristics.

```sql
CREATE TABLE supplier_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    supplier_sku VARCHAR(255) NOT NULL,
    name VARCHAR(500) NOT NULL,
    current_price NUMERIC(10, 2) NOT NULL CHECK (current_price >= 0),
    characteristics JSONB NOT NULL DEFAULT '{}',
    last_ingested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_supplier_sku UNIQUE(supplier_id, supplier_sku)
);

CREATE INDEX idx_supplier_items_supplier ON supplier_items(supplier_id);
CREATE INDEX idx_supplier_items_product ON supplier_items(product_id);
CREATE INDEX idx_supplier_items_characteristics ON supplier_items USING GIN (characteristics);
CREATE INDEX idx_supplier_items_price ON supplier_items(current_price);
CREATE INDEX idx_supplier_items_last_ingested ON supplier_items(last_ingested_at DESC);
```

**Fields:**
- `id`: Unique identifier (UUID)
- `supplier_id`: Reference to supplier (NOT NULL, CASCADE delete)
- `product_id`: Reference to unified product (nullable, SET NULL on delete)
- `supplier_sku`: Supplier's SKU for this item
- `name`: Product name from supplier
- `current_price`: Latest price (2 decimal places, non-negative)
- `characteristics`: Flexible JSONB for attributes (color, size, material, etc.)
- `last_ingested_at`: Timestamp of last data ingestion
- `created_at`: Record creation timestamp (UTC)
- `updated_at`: Last modification timestamp (UTC)

**Constraints:**
- Unique combination of `(supplier_id, supplier_sku)` prevents duplicate items from same supplier
- Check constraint: `current_price >= 0`
- Foreign keys with appropriate ON DELETE behavior

**Indexes:**
- Primary key on `id`
- Index on `supplier_id` for supplier-based queries
- Index on `product_id` for product-based queries
- GIN index on `characteristics` for JSONB queries (e.g., `WHERE characteristics @> '{"color": "red"}'`)
- Index on `current_price` for price-based filtering
- Descending index on `last_ingested_at` for recent data queries

**Example Characteristics JSONB:**
```json
{
  "color": "red",
  "size": "XL",
  "material": "cotton",
  "weight_kg": 0.5,
  "dimensions_cm": {"length": 30, "width": 20, "height": 10},
  "origin_country": "China"
}
```

---

### 5. PriceHistory Table

Time-series tracking of price changes for supplier items.

```sql
CREATE TABLE price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_item_id UUID NOT NULL REFERENCES supplier_items(id) ON DELETE CASCADE,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_price_history_item ON price_history(supplier_item_id);
CREATE INDEX idx_price_history_recorded ON price_history(recorded_at DESC);
CREATE INDEX idx_price_history_item_recorded ON price_history(supplier_item_id, recorded_at DESC);
```

**Fields:**
- `id`: Unique identifier (UUID)
- `supplier_item_id`: Reference to supplier item (CASCADE delete)
- `price`: Historical price value (2 decimal places, non-negative)
- `recorded_at`: Timestamp when price was recorded (UTC)

**Constraints:**
- Foreign key to `supplier_items` with CASCADE delete
- Check constraint: `price >= 0`

**Indexes:**
- Primary key on `id`
- Index on `supplier_item_id` for item-based queries
- Descending index on `recorded_at` for chronological queries
- Composite index on `(supplier_item_id, recorded_at DESC)` for optimal timeline queries

**Usage Pattern:**
- Insert new record on every price change
- Query historical prices: `SELECT * FROM price_history WHERE supplier_item_id = ? ORDER BY recorded_at DESC`

---

### 6. ParsingLogs Table (NEW)

Structured error logging for data parsing failures.

```sql
CREATE TABLE parsing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id VARCHAR(255) NOT NULL,
    supplier_id UUID REFERENCES suppliers(id) ON DELETE SET NULL,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    row_number INTEGER,
    row_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_parsing_logs_supplier ON parsing_logs(supplier_id);
CREATE INDEX idx_parsing_logs_task ON parsing_logs(task_id);
CREATE INDEX idx_parsing_logs_created ON parsing_logs(created_at DESC);
CREATE INDEX idx_parsing_logs_error_type ON parsing_logs(error_type);
```

**Fields:**
- `id`: Unique identifier (UUID)
- `task_id`: Parse task identifier for correlation
- `supplier_id`: Reference to supplier (nullable, SET NULL on delete)
- `error_type`: Error category (ValidationError, ParserError, DatabaseError, etc.)
- `error_message`: Detailed error description
- `row_number`: Row index in source data (nullable)
- `row_data`: Raw row data that caused error (JSONB, nullable)
- `created_at`: Error timestamp (UTC)

**Indexes:**
- Primary key on `id`
- Index on `supplier_id` for supplier-based error analysis
- Index on `task_id` for task-based error correlation
- Descending index on `created_at` for recent errors
- Index on `error_type` for error categorization

**Usage:**
```sql
-- Find all validation errors for a supplier in last 24 hours
SELECT * FROM parsing_logs 
WHERE supplier_id = ? 
  AND error_type = 'ValidationError'
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

---

## SQLAlchemy ORM Models

### Base Configuration

```python
# src/db/base.py
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import func
from datetime import datetime
from typing import Optional
import uuid

class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all ORM models"""
    pass

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

class UUIDMixin:
    """Mixin for UUID primary key"""
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid()
    )
```

---

### 1. Supplier Model

```python
# src/db/models/supplier.py
from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin, TimestampMixin
from typing import Dict, Any, List

class Supplier(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "suppliers"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, server_default='{}')
    
    # Relationships
    supplier_items: Mapped[List["SupplierItem"]] = relationship(
        back_populates="supplier",
        cascade="all, delete-orphan"
    )
    parsing_logs: Mapped[List["ParsingLog"]] = relationship(
        back_populates="supplier"
    )
    
    def __repr__(self) -> str:
        return f"<Supplier(id={self.id}, name='{self.name}', source_type='{self.source_type}')>"
```

---

### 2. Category Model

```python
# src/db/models/category.py
from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin
from datetime import datetime
from typing import List, Optional
import uuid

class Category(Base, UUIDMixin):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint('name', 'parent_id', name='uq_category_name_parent'),
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    
    # Relationships
    parent: Mapped[Optional["Category"]] = relationship(
        remote_side="Category.id",
        back_populates="children"
    )
    children: Mapped[List["Category"]] = relationship(
        back_populates="parent"
    )
    products: Mapped[List["Product"]] = relationship(
        back_populates="category"
    )
    
    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}')>"
```

---

### 3. Product Model

```python
# src/db/models/product.py
from sqlalchemy import String, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin, TimestampMixin
from enum import Enum as PyEnum
from typing import List, Optional
import uuid

class ProductStatus(PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"

class Product(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "products"
    
    internal_sku: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        index=True
    )
    status: Mapped[ProductStatus] = mapped_column(
        SQLEnum(ProductStatus, name="product_status"),
        nullable=False,
        server_default=ProductStatus.DRAFT.value,
        index=True
    )
    
    # Relationships
    category: Mapped[Optional["Category"]] = relationship(back_populates="products")
    supplier_items: Mapped[List["SupplierItem"]] = relationship(
        back_populates="product"
    )
    
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku='{self.internal_sku}', status='{self.status.value}')>"
```

---

### 4. SupplierItem Model

```python
# src/db/models/supplier_item.py
from sqlalchemy import String, ForeignKey, Numeric, JSON, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin, TimestampMixin
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Optional, List
import uuid

class SupplierItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "supplier_items"
    __table_args__ = (
        UniqueConstraint('supplier_id', 'supplier_sku', name='unique_supplier_sku'),
        CheckConstraint('current_price >= 0', name='check_positive_price'),
    )
    
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        index=True
    )
    supplier_sku: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    current_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        index=True
    )
    characteristics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        server_default='{}',
        index=True  # GIN index
    )
    last_ingested_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        index=True
    )
    
    # Relationships
    supplier: Mapped["Supplier"] = relationship(back_populates="supplier_items")
    product: Mapped[Optional["Product"]] = relationship(back_populates="supplier_items")
    price_history: Mapped[List["PriceHistory"]] = relationship(
        back_populates="supplier_item",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<SupplierItem(id={self.id}, sku='{self.supplier_sku}', price={self.current_price})>"
```

---

### 5. PriceHistory Model

```python
# src/db/models/price_history.py
from sqlalchemy import ForeignKey, Numeric, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import func
from src.db.base import Base, UUIDMixin
from decimal import Decimal
from datetime import datetime
import uuid

class PriceHistory(Base, UUIDMixin):
    __tablename__ = "price_history"
    __table_args__ = (
        CheckConstraint('price >= 0', name='check_positive_price'),
    )
    
    supplier_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Relationships
    supplier_item: Mapped["SupplierItem"] = relationship(back_populates="price_history")
    
    def __repr__(self) -> str:
        return f"<PriceHistory(id={self.id}, price={self.price}, recorded_at={self.recorded_at})>"
```

---

### 6. ParsingLog Model (NEW)

```python
# src/db/models/parsing_log.py
from sqlalchemy import String, ForeignKey, Text, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import func
from src.db.base import Base, UUIDMixin
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

class ParsingLog(Base, UUIDMixin):
    __tablename__ = "parsing_logs"
    
    task_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        index=True
    )
    error_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    row_number: Mapped[int | None] = mapped_column(Integer)
    row_data: Mapped[Dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Relationships
    supplier: Mapped[Optional["Supplier"]] = relationship(back_populates="parsing_logs")
    
    def __repr__(self) -> str:
        return f"<ParsingLog(id={self.id}, type='{self.error_type}', task='{self.task_id}')>"
```

---

## Pydantic Validation Models

### 1. Parsed Item Model

```python
# src/models/parsed_item.py
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from typing import Dict, Any

class ParsedSupplierItem(BaseModel):
    """Validated supplier item parsed from data source"""
    
    supplier_sku: str = Field(..., min_length=1, max_length=255, description="Supplier's SKU")
    name: str = Field(..., min_length=1, max_length=500, description="Product name")
    price: Decimal = Field(..., ge=0, description="Current price (non-negative)")
    characteristics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Flexible product attributes"
    )
    
    @field_validator('price')
    @classmethod
    def validate_price_precision(cls, v: Decimal) -> Decimal:
        """Ensure price has at most 2 decimal places"""
        if v.as_tuple().exponent < -2:
            raise ValueError('Price must have at most 2 decimal places')
        return v.quantize(Decimal('0.01'))
    
    @field_validator('characteristics')
    @classmethod
    def validate_characteristics_serializable(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure characteristics can be JSON serialized"""
        try:
            import json
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
```

---

### 2. Queue Message Model

```python
# src/models/queue_message.py
from pydantic import BaseModel, Field, HttpUrl
from typing import Dict, Any, Literal
from datetime import datetime

class ParseTaskMessage(BaseModel):
    """Message for queuing parse tasks"""
    
    task_id: str = Field(..., description="Unique task identifier")
    parser_type: Literal["google_sheets", "csv", "excel"] = Field(
        ...,
        description="Type of parser to use"
    )
    supplier_name: str = Field(..., min_length=1, max_length=255)
    source_config: Dict[str, Any] = Field(
        ...,
        description="Parser-specific configuration"
    )
    retry_count: int = Field(default=0, ge=0, description="Current retry attempt")
    max_retries: int = Field(default=3, ge=1, le=10, description="Maximum retry attempts")
    enqueued_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "task-2025-11-23-001",
                "parser_type": "google_sheets",
                "supplier_name": "Acme Wholesale",
                "source_config": {
                    "sheet_url": "https://docs.google.com/spreadsheets/d/abc123",
                    "sheet_name": "Price List",
                    "column_mapping": {
                        "sku": "A",
                        "name": "B",
                        "price": "C"
                    }
                },
                "retry_count": 0,
                "max_retries": 3
            }
        }
    }
```

---

### 3. Google Sheets Config Model

```python
# src/models/google_sheets_config.py
from pydantic import BaseModel, Field, HttpUrl
from typing import Dict, List

class GoogleSheetsConfig(BaseModel):
    """Configuration for Google Sheets parser"""
    
    sheet_url: HttpUrl = Field(..., description="Google Sheets URL")
    sheet_name: str = Field(default="Sheet1", description="Sheet tab name")
    column_mapping: Dict[str, str] | None = Field(
        default=None,
        description="Manual column mapping (overrides auto-detection)"
    )
    characteristic_columns: List[str] | None = Field(
        default=None,
        description="Columns to merge into characteristics JSONB"
    )
    header_row: int = Field(default=1, ge=1, description="Row number containing headers")
    data_start_row: int = Field(default=2, ge=2, description="First row of data")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "sheet_url": "https://docs.google.com/spreadsheets/d/abc123",
                "sheet_name": "November 2025",
                "column_mapping": {
                    "sku": "Product Code",
                    "name": "Description",
                    "price": "Unit Price"
                },
                "characteristic_columns": ["Color", "Size", "Material"],
                "header_row": 1,
                "data_start_row": 2
            }
        }
    }
```

---

## State Transitions

### Product Status Lifecycle

```
        create()
           │
           ▼
       ┌────────┐
       │ DRAFT  │◄────┐
       └────┬───┘     │
            │         │ revert_to_draft()
     publish() │         │
            │         │
            ▼         │
       ┌────────┐    │
       │ ACTIVE │────┘
       └────┬───┘
            │
      archive() │
            ▼
       ┌─────────┐
       │ARCHIVED │
       └─────────┘
```

**Transitions:**
- `DRAFT → ACTIVE`: Product validated and published (`publish()`)
- `ACTIVE → DRAFT`: Product unpublished for modifications (`revert_to_draft()`)
- `ACTIVE → ARCHIVED`: Product discontinued (`archive()`)
- `ARCHIVED → [final]`: No transitions out (soft delete)

**Business Rules:**
- New products default to `DRAFT`
- Only `ACTIVE` products visible to external systems
- `ARCHIVED` products retained for historical queries
- `DRAFT` products can be deleted without side effects

---

## Validation Rules

### Database-Level Constraints

1. **Price Validation:**
   - Must be ≥ 0 (CHECK constraint)
   - Maximum 2 decimal places (enforced by NUMERIC(10, 2))

2. **SKU Uniqueness:**
   - `products.internal_sku` must be unique globally
   - `supplier_items.(supplier_id, supplier_sku)` must be unique per supplier

3. **Referential Integrity:**
   - Supplier deletion cascades to supplier_items and price_history
   - Product deletion sets supplier_items.product_id to NULL (preserves data)
   - Category deletion sets products.category_id to NULL

4. **JSONB Validation:**
   - characteristics and metadata must be valid JSON (enforced by PostgreSQL)

### Application-Level Validation (Pydantic)

1. **Field Length Limits:**
   - Supplier SKU: 1-255 characters
   - Product name: 1-500 characters
   - Supplier name: 1-255 characters

2. **Price Precision:**
   - Automatically rounds to 2 decimal places
   - Rejects negative values

3. **Characteristics:**
   - Must be JSON-serializable (validated before insert)
   - Keys should be strings, values can be any JSON type

4. **Configuration Validation:**
   - Google Sheets URLs must be valid HTTP/HTTPS URLs
   - Column mappings must reference valid field names

---

## Indexing Strategy

### Query Patterns & Indexes

| Query Pattern | Index |
|---------------|-------|
| Find items by supplier | `idx_supplier_items_supplier` |
| Find items by product | `idx_supplier_items_product` |
| Search characteristics | `idx_supplier_items_characteristics` (GIN) |
| Filter by price range | `idx_supplier_items_price` |
| Recent ingestions | `idx_supplier_items_last_ingested` |
| Price history timeline | `idx_price_history_item_recorded` |
| Recent parsing errors | `idx_parsing_logs_created` |
| Errors by supplier | `idx_parsing_logs_supplier` |
| Products by status | `idx_products_status` |

### Index Maintenance

- GIN indexes on JSONB columns require more storage but enable fast containment queries
- Use `EXPLAIN ANALYZE` to verify index usage in production queries
- Monitor index bloat with `pg_stat_user_indexes`
- Consider `REINDEX` if index size grows significantly

---

## Data Integrity Rules

### Insert Operations

1. **Supplier Item Upsert:**
   ```sql
   INSERT INTO supplier_items (supplier_id, supplier_sku, name, current_price, characteristics)
   VALUES (?, ?, ?, ?, ?)
   ON CONFLICT (supplier_id, supplier_sku)
   DO UPDATE SET
     name = EXCLUDED.name,
     current_price = EXCLUDED.current_price,
     characteristics = EXCLUDED.characteristics,
     last_ingested_at = NOW(),
     updated_at = NOW();
   ```

2. **Price History on Update:**
   - Trigger insert into `price_history` when `supplier_items.current_price` changes
   - Implementation via application logic or database trigger

3. **Supplier Creation:**
   - Use `get_or_create` pattern: SELECT first, INSERT if not exists
   - Transaction ensures atomicity

### Delete Operations

1. **Cascading Deletes:**
   - Deleting supplier removes all associated supplier_items, price_history, and parsing_logs
   - Deleting supplier_item removes all associated price_history entries

2. **Soft Deletes:**
   - Products use `status = 'archived'` instead of hard delete
   - Preserves relationships with supplier_items

### Update Operations

1. **Timestamp Management:**
   - `updated_at` automatically updated on row modification (database trigger or ORM)
   - `created_at` immutable after insert

2. **Price Changes:**
   - Always create new `price_history` entry before updating `current_price`
   - Ensures audit trail completeness

---

## Example Queries

### 1. Get All Supplier Items with Current Prices

```sql
SELECT 
    si.id,
    si.supplier_sku,
    si.name,
    si.current_price,
    s.name AS supplier_name,
    p.internal_sku AS product_sku
FROM supplier_items si
JOIN suppliers s ON si.supplier_id = s.id
LEFT JOIN products p ON si.product_id = p.id
WHERE s.id = ?
ORDER BY si.name;
```

### 2. Get Price History for Item

```sql
SELECT 
    ph.price,
    ph.recorded_at
FROM price_history ph
WHERE ph.supplier_item_id = ?
ORDER BY ph.recorded_at DESC
LIMIT 10;
```

### 3. Find Items with Specific Characteristic

```sql
SELECT * FROM supplier_items
WHERE characteristics @> '{"color": "red"}'::jsonb;
```

### 4. Recent Parsing Errors by Supplier

```sql
SELECT 
    pl.error_type,
    pl.error_message,
    pl.row_number,
    pl.created_at
FROM parsing_logs pl
WHERE pl.supplier_id = ?
  AND pl.created_at > NOW() - INTERVAL '7 days'
ORDER BY pl.created_at DESC;
```

### 5. Active Products with Supplier Count

```sql
SELECT 
    p.internal_sku,
    p.name,
    p.status,
    COUNT(DISTINCT si.supplier_id) AS supplier_count,
    MIN(si.current_price) AS min_price,
    MAX(si.current_price) AS max_price
FROM products p
LEFT JOIN supplier_items si ON p.id = si.product_id
WHERE p.status = 'active'
GROUP BY p.id, p.internal_sku, p.name, p.status
HAVING COUNT(si.id) > 0
ORDER BY supplier_count DESC;
```

---

## Migration Plan

### Phase 1: Initial Schema (Alembic Migration)

```python
# migrations/versions/001_initial_schema.py
def upgrade():
    # Create enum
    op.execute("CREATE TYPE product_status AS ENUM ('draft', 'active', 'archived')")
    
    # Create tables in dependency order
    op.create_table('suppliers', ...)
    op.create_table('categories', ...)
    op.create_table('products', ...)
    op.create_table('supplier_items', ...)
    op.create_table('price_history', ...)
    op.create_table('parsing_logs', ...)
    
    # Create indexes
    op.create_index('idx_supplier_items_characteristics', 'supplier_items', 
                   ['characteristics'], postgresql_using='gin')
    # ... other indexes

def downgrade():
    op.drop_table('parsing_logs')
    op.drop_table('price_history')
    op.drop_table('supplier_items')
    op.drop_table('products')
    op.drop_table('categories')
    op.drop_table('suppliers')
    op.execute("DROP TYPE product_status")
```

### Phase 2: Sample Data (Optional)

```sql
-- Insert test supplier
INSERT INTO suppliers (name, source_type, contact_email)
VALUES ('Test Supplier', 'google_sheets', 'test@example.com');

-- Insert test category
INSERT INTO categories (name) VALUES ('Electronics');

-- Insert draft product
INSERT INTO products (internal_sku, name, status)
VALUES ('PROD-001', 'Test Product', 'draft');
```

---

## Next Steps

1. ✅ Database schema designed
2. ✅ SQLAlchemy models defined
3. ✅ Pydantic validation models created
4. ⏭️ Create API contracts (Phase 1 continued)
5. ⏭️ Generate quickstart documentation

---

**Approval:**
- [x] Data Model Complete - Ready for Contracts Phase

