# Data Model: Product Matching & Data Enrichment Pipeline

**Date:** 2025-11-30  
**Feature:** 004-product-matching-pipeline  
**Status:** Complete

---

## Overview

This document defines the data model extensions for Phase 4: Product Matching & Data Enrichment Pipeline. It builds on the existing Phase 1 schema, adding new fields and tables for match tracking, review queues, and aggregate calculations.

---

## Entity Relationship Diagram

```
┌─────────────────────────┐
│      Products           │
│─────────────────────────│
│ id (PK)                 │
│ internal_sku (UNIQUE)   │
│ name                    │
│ category_id (FK)        │
│ status (ENUM)           │
│ min_price (NEW)         │◄──────┐ Calculated from linked items
│ availability (NEW)      │◄──────┘
│ mrp (NEW, nullable)     │
│ created_at              │
│ updated_at              │
└─────────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────────────────┐
│       SupplierItems             │
│─────────────────────────────────│
│ id (PK)                         │
│ supplier_id (FK)                │
│ product_id (FK, nullable)       │
│ supplier_sku                    │
│ name                            │
│ current_price                   │
│ characteristics (JSONB)         │
│ match_status (NEW)              │◄─── ENUM: unmatched, auto_matched, potential_match, verified_match
│ match_score (NEW)               │◄─── Confidence score 0-100
│ match_candidates (NEW)          │◄─── JSONB: [{product_id, score, name}]
│ last_ingested_at                │
│ created_at                      │
│ updated_at                      │
│ UNIQUE(supplier_id, supplier_sku)│
└─────────────────────────────────┘
         │
         │ 1:1
         ▼
┌─────────────────────────────────┐
│     MatchReviewQueue (NEW)      │
│─────────────────────────────────│
│ id (PK)                         │
│ supplier_item_id (FK, UNIQUE)   │◄─── One review per item
│ candidate_products (JSONB)      │◄─── [{product_id, score, name}]
│ status (ENUM)                   │◄─── pending, approved, rejected, expired, needs_category
│ reviewed_by (FK to users)       │
│ reviewed_at                     │
│ created_at                      │
│ expires_at                      │
└─────────────────────────────────┘
```

---

## Database Schema Changes

### 1. New ENUM: match_status

```sql
-- Migration: Add match_status enum type
CREATE TYPE match_status AS ENUM (
    'unmatched',
    'auto_matched',
    'potential_match',
    'verified_match'
);
```

### 2. New ENUM: review_status

```sql
-- Migration: Add review_status enum type
CREATE TYPE review_status AS ENUM (
    'pending',
    'approved',
    'rejected',
    'expired',
    'needs_category'
);
```

### 3. Modified: products Table

```sql
-- Migration: Add aggregate columns to products table
ALTER TABLE products 
ADD COLUMN min_price NUMERIC(10, 2),
ADD COLUMN availability BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN mrp NUMERIC(10, 2);

-- Index for aggregate queries
CREATE INDEX idx_products_min_price ON products(min_price) WHERE min_price IS NOT NULL;
CREATE INDEX idx_products_availability ON products(availability);
```

**New Fields:**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `min_price` | NUMERIC(10,2) | Yes | NULL | Lowest price among linked active supplier items |
| `availability` | BOOLEAN | No | FALSE | TRUE if any linked supplier has stock |
| `mrp` | NUMERIC(10,2) | Yes | NULL | Manufacturer's recommended price (placeholder) |

### 4. Modified: supplier_items Table

```sql
-- Migration: Add matching columns to supplier_items table
ALTER TABLE supplier_items
ADD COLUMN match_status match_status NOT NULL DEFAULT 'unmatched',
ADD COLUMN match_score DECIMAL(5, 2),
ADD COLUMN match_candidates JSONB;

-- Indexes for matching queries
CREATE INDEX idx_supplier_items_match_status ON supplier_items(match_status);
CREATE INDEX idx_supplier_items_unmatched ON supplier_items(product_id) 
    WHERE product_id IS NULL AND match_status = 'unmatched';
CREATE INDEX idx_supplier_items_match_score ON supplier_items(match_score DESC) 
    WHERE match_score IS NOT NULL;

-- Constraint: match_score must be 0-100 when set
ALTER TABLE supplier_items
ADD CONSTRAINT check_match_score CHECK (
    match_score IS NULL OR (match_score >= 0 AND match_score <= 100)
);
```

**New Fields:**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `match_status` | match_status | No | 'unmatched' | Current matching state |
| `match_score` | DECIMAL(5,2) | Yes | NULL | Confidence score of last match (0-100) |
| `match_candidates` | JSONB | Yes | NULL | Array of potential matches for review |

**match_candidates JSONB Schema:**

```json
[
    {
        "product_id": "uuid",
        "product_name": "Samsung Galaxy A54 5G 128GB",
        "score": 85.5
    },
    {
        "product_id": "uuid", 
        "product_name": "Samsung Galaxy A54 5G 256GB",
        "score": 78.2
    }
]
```

### 5. New Table: match_review_queue

```sql
-- Migration: Create match_review_queue table
CREATE TABLE match_review_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_item_id UUID NOT NULL UNIQUE REFERENCES supplier_items(id) ON DELETE CASCADE,
    candidate_products JSONB NOT NULL DEFAULT '[]',
    status review_status NOT NULL DEFAULT 'pending',
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Indexes
CREATE INDEX idx_review_queue_status ON match_review_queue(status);
CREATE INDEX idx_review_queue_expires ON match_review_queue(expires_at) WHERE status = 'pending';
CREATE INDEX idx_review_queue_created ON match_review_queue(created_at DESC);

-- Composite index for common query patterns
CREATE INDEX idx_review_queue_status_expires ON match_review_queue(status, expires_at) 
    WHERE status = 'pending';
```

**Fields:**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | No | gen_random_uuid() | Primary key |
| `supplier_item_id` | UUID | No | - | Reference to supplier item (unique) |
| `candidate_products` | JSONB | No | '[]' | Array of {product_id, score, name} |
| `status` | review_status | No | 'pending' | Review queue status |
| `reviewed_by` | UUID | Yes | NULL | User who actioned the review |
| `reviewed_at` | TIMESTAMPTZ | Yes | NULL | When review was completed |
| `created_at` | TIMESTAMPTZ | No | NOW() | When item was added to queue |
| `expires_at` | TIMESTAMPTZ | No | - | Auto-expiration timestamp |

---

## SQLAlchemy ORM Models

### 1. Updated Product Model

```python
# src/db/models/product.py (additions)
from sqlalchemy import String, ForeignKey, Enum as SQLEnum, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin, TimestampMixin
from enum import Enum as PyEnum
from decimal import Decimal
from typing import List, Optional
import uuid


class ProductStatus(PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Product(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "products"
    
    internal_sku: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[ProductStatus] = mapped_column(
        SQLEnum(ProductStatus, name="product_status"),
        nullable=False,
        server_default=ProductStatus.DRAFT.value,
        index=True
    )
    
    # NEW: Aggregate fields
    min_price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True, index=True
    )
    availability: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default='false'
    )
    mrp: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    
    # Relationships
    category: Mapped[Optional["Category"]] = relationship(back_populates="products")
    supplier_items: Mapped[List["SupplierItem"]] = relationship(
        back_populates="product"
    )
    
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku='{self.internal_sku}', status='{self.status.value}')>"
```

### 2. Updated SupplierItem Model

```python
# src/db/models/supplier_item.py (additions)
from sqlalchemy import String, ForeignKey, Numeric, JSON, CheckConstraint, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin, TimestampMixin
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum as PyEnum
import uuid


class MatchStatus(PyEnum):
    UNMATCHED = "unmatched"
    AUTO_MATCHED = "auto_matched"
    POTENTIAL_MATCH = "potential_match"
    VERIFIED_MATCH = "verified_match"


class SupplierItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "supplier_items"
    __table_args__ = (
        UniqueConstraint('supplier_id', 'supplier_sku', name='unique_supplier_sku'),
        CheckConstraint('current_price >= 0', name='check_positive_price'),
        CheckConstraint(
            'match_score IS NULL OR (match_score >= 0 AND match_score <= 100)',
            name='check_match_score'
        ),
    )
    
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    supplier_sku: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    current_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, index=True
    )
    characteristics: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, server_default='{}'
    )
    last_ingested_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), index=True
    )
    
    # NEW: Matching fields
    match_status: Mapped[MatchStatus] = mapped_column(
        SQLEnum(MatchStatus, name="match_status"),
        nullable=False,
        server_default=MatchStatus.UNMATCHED.value,
        index=True
    )
    match_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    match_candidates: Mapped[Dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    
    # Relationships
    supplier: Mapped["Supplier"] = relationship(back_populates="supplier_items")
    product: Mapped[Optional["Product"]] = relationship(back_populates="supplier_items")
    price_history: Mapped[List["PriceHistory"]] = relationship(
        back_populates="supplier_item", cascade="all, delete-orphan"
    )
    review_queue_item: Mapped[Optional["MatchReviewQueue"]] = relationship(
        back_populates="supplier_item", uselist=False
    )
    
    def __repr__(self) -> str:
        return f"<SupplierItem(id={self.id}, sku='{self.supplier_sku}', status='{self.match_status.value}')>"
```

### 3. New MatchReviewQueue Model

```python
# src/db/models/match_review_queue.py
from sqlalchemy import String, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import func
from src.db.base import Base, UUIDMixin
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum as PyEnum
import uuid


class ReviewStatus(PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    NEEDS_CATEGORY = "needs_category"


class MatchReviewQueue(Base, UUIDMixin):
    __tablename__ = "match_review_queue"
    
    supplier_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    candidate_products: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, server_default='[]'
    )
    status: Mapped[ReviewStatus] = mapped_column(
        SQLEnum(ReviewStatus, name="review_status"),
        nullable=False,
        server_default=ReviewStatus.PENDING.value,
        index=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    
    # Relationships
    supplier_item: Mapped["SupplierItem"] = relationship(
        back_populates="review_queue_item"
    )
    reviewer: Mapped[Optional["User"]] = relationship()
    
    def __repr__(self) -> str:
        return f"<MatchReviewQueue(id={self.id}, status='{self.status.value}')>"
```

---

## Pydantic Validation Models

### 1. Match Result Models

```python
# src/models/matching.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from enum import Enum


class MatchStatusEnum(str, Enum):
    UNMATCHED = "unmatched"
    AUTO_MATCHED = "auto_matched"
    POTENTIAL_MATCH = "potential_match"
    VERIFIED_MATCH = "verified_match"


class MatchCandidate(BaseModel):
    """A potential product match for a supplier item."""
    
    product_id: UUID
    product_name: str = Field(..., max_length=500)
    score: float = Field(..., ge=0, le=100)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "product_id": "550e8400-e29b-41d4-a716-446655440000",
                "product_name": "Samsung Galaxy A54 5G 128GB",
                "score": 92.5
            }
        }
    }


class MatchResult(BaseModel):
    """Result of matching a supplier item."""
    
    supplier_item_id: UUID
    match_status: MatchStatusEnum
    best_match: Optional[MatchCandidate] = None
    candidates: List[MatchCandidate] = Field(default_factory=list)
    match_score: Optional[float] = Field(default=None, ge=0, le=100)
    
    @field_validator('best_match', mode='before')
    @classmethod
    def validate_best_match(cls, v, info):
        """Ensure best_match is set for matched statuses."""
        # Access other fields via info.data
        status = info.data.get('match_status')
        if status in (MatchStatusEnum.AUTO_MATCHED, MatchStatusEnum.VERIFIED_MATCH):
            if v is None:
                raise ValueError('best_match required for matched status')
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "supplier_item_id": "770e8400-e29b-41d4-a716-446655440000",
                "match_status": "auto_matched",
                "best_match": {
                    "product_id": "550e8400-e29b-41d4-a716-446655440000",
                    "product_name": "Samsung Galaxy A54 5G 128GB",
                    "score": 96.5
                },
                "candidates": [],
                "match_score": 96.5
            }
        }
    }
```

### 2. Queue Message Models

```python
# src/models/queue_message.py (additions)
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from uuid import UUID
from datetime import datetime


class MatchItemsTaskMessage(BaseModel):
    """Message for matching batch of supplier items."""
    
    task_id: str = Field(..., description="Unique task identifier")
    category_id: Optional[UUID] = Field(
        default=None,
        description="Category to filter items (blocking strategy)"
    )
    batch_size: int = Field(default=100, ge=1, le=1000)
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=1, le=10)
    enqueued_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "match-2025-11-30-001",
                "category_id": "660e8400-e29b-41d4-a716-446655440000",
                "batch_size": 100,
                "retry_count": 0,
                "max_retries": 3
            }
        }
    }


class EnrichItemTaskMessage(BaseModel):
    """Message for enriching single supplier item characteristics."""
    
    task_id: str = Field(..., description="Unique task identifier")
    supplier_item_id: UUID = Field(..., description="Item to enrich")
    extractors: List[str] = Field(
        default=["electronics", "dimensions"],
        description="Extractor names to apply"
    )
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=1, le=10)
    enqueued_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "enrich-2025-11-30-001",
                "supplier_item_id": "770e8400-e29b-41d4-a716-446655440000",
                "extractors": ["electronics", "dimensions"]
            }
        }
    }


class RecalcAggregatesTaskMessage(BaseModel):
    """Message for recalculating product aggregates."""
    
    task_id: str = Field(..., description="Unique task identifier")
    product_ids: List[UUID] = Field(..., min_length=1, max_length=100)
    trigger: Literal["auto_match", "manual_link", "price_change"] = Field(
        ..., description="What triggered the recalculation"
    )
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=1, le=10)
    enqueued_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "recalc-2025-11-30-001",
                "product_ids": ["550e8400-e29b-41d4-a716-446655440000"],
                "trigger": "auto_match"
            }
        }
    }
```

### 3. Review Queue Models

```python
# src/models/review_queue.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum


class ReviewStatusEnum(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    NEEDS_CATEGORY = "needs_category"


class ReviewQueueItem(BaseModel):
    """A supplier item pending review in the match queue."""
    
    id: UUID
    supplier_item_id: UUID
    supplier_item_name: str
    supplier_name: str
    candidate_products: List[dict]  # [{product_id, score, name}]
    status: ReviewStatusEnum
    created_at: datetime
    expires_at: datetime
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "990e8400-e29b-41d4-a716-446655440000",
                "supplier_item_id": "770e8400-e29b-41d4-a716-446655440000",
                "supplier_item_name": "Samsung A54 Phone Black 128",
                "supplier_name": "TechSupplier Inc",
                "candidate_products": [
                    {
                        "product_id": "550e8400-e29b-41d4-a716-446655440000",
                        "score": 78.5,
                        "name": "Samsung Galaxy A54 5G 128GB"
                    }
                ],
                "status": "pending",
                "created_at": "2025-11-30T10:00:00Z",
                "expires_at": "2025-12-30T10:00:00Z"
            }
        }
    }


class ReviewAction(BaseModel):
    """Action to take on a review queue item."""
    
    action: Literal["approve", "reject", "create_new"]
    product_id: Optional[UUID] = Field(
        default=None,
        description="Product to link (required for 'approve')"
    )
    new_product_name: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Name for new product (required for 'create_new')"
    )
    
    @field_validator('product_id', mode='before')
    @classmethod
    def validate_product_id(cls, v, info):
        action = info.data.get('action')
        if action == 'approve' and v is None:
            raise ValueError('product_id required for approve action')
        return v
    
    @field_validator('new_product_name', mode='before')
    @classmethod
    def validate_new_product_name(cls, v, info):
        action = info.data.get('action')
        if action == 'create_new' and not v:
            raise ValueError('new_product_name required for create_new action')
        return v
```

### 4. Extraction Models

```python
# src/models/extraction.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class ExtractedFeatures(BaseModel):
    """Features extracted from supplier item text."""
    
    # Electronics
    voltage: Optional[int] = Field(default=None, ge=0, le=10000)
    power_watts: Optional[int] = Field(default=None, ge=0, le=100000)
    
    # Dimensions
    weight_kg: Optional[float] = Field(default=None, ge=0, le=10000)
    dimensions_cm: Optional[Dict[str, float]] = Field(
        default=None,
        description="{ length, width, height }"
    )
    
    # Storage (for electronics)
    storage_gb: Optional[int] = Field(default=None, ge=0, le=100000)
    
    # Memory (for electronics)
    memory_gb: Optional[int] = Field(default=None, ge=0, le=1000)
    
    def to_characteristics(self) -> Dict[str, Any]:
        """Convert to characteristics JSONB format."""
        return {k: v for k, v in self.model_dump().items() if v is not None}
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "voltage": 220,
                "power_watts": 750,
                "weight_kg": 2.5,
                "dimensions_cm": {
                    "length": 30,
                    "width": 20,
                    "height": 10
                }
            }
        }
    }
```

---

## State Transitions

### Match Status State Machine

```
                 ┌────────────────┐
                 │   unmatched    │◄──────────────────────┐
                 │   (initial)    │                       │
                 └───────┬────────┘                       │
                         │                                │
         ┌───────────────┼───────────────┐               │
         │               │               │               │
         ▼               ▼               ▼               │
 ┌───────────────┐ ┌────────────┐ ┌─────────────┐       │
 │ auto_matched  │ │ potential_ │ │ verified_   │       │ admin
 │ (score ≥95%)  │ │ match      │ │ match       │       │ reset
 └───────┬───────┘ │ (70-94%)   │ │ (manual)    │───────┘
         │         └──────┬─────┘ └─────────────┘
         │                │               ▲
         │    ┌───────────┴───────────┐   │
         │    │                       │   │
         │    ▼                       ▼   │
         │  admin                   admin │
         │  approves               rejects│
         │    │                       │   │
         │    └───────────┬───────────┘   │
         │                │               │
         ▼                ▼               │
 ┌─────────────────────────────────────┐ │
 │         verified_match               │─┘
 │  (protected from auto-matcher)       │
 └─────────────────────────────────────┘
```

**Transition Rules:**

| From | To | Trigger | Permissions |
|------|----|---------|-------------|
| `unmatched` | `auto_matched` | Score ≥95% | System |
| `unmatched` | `potential_match` | Score 70-94% | System |
| `unmatched` | `verified_match` | Manual link | Procurement, Admin |
| `auto_matched` | `verified_match` | Admin confirms | Admin |
| `auto_matched` | `unmatched` | Admin rejects | Admin |
| `potential_match` | `verified_match` | Approve review | Procurement, Admin |
| `potential_match` | `unmatched` | Reject review | Procurement, Admin |
| `verified_match` | `unmatched` | Reset for re-match | Admin only |

---

## Example Queries

### 1. Get Unmatched Items for Processing (with Locking)

```sql
SELECT si.* FROM supplier_items si
WHERE si.product_id IS NULL
  AND si.match_status = 'unmatched'
ORDER BY si.created_at
LIMIT 100
FOR UPDATE SKIP LOCKED;
```

### 2. Get Products for Matching by Category

```sql
SELECT p.id, p.name, p.category_id
FROM products p
WHERE p.category_id = $1
  AND p.status = 'active'
ORDER BY p.name;
```

### 3. Recalculate Product Aggregates

```sql
-- Availability is TRUE if ANY linked supplier item has in_stock = true
-- No price-based inference is used (KISS principle)
UPDATE products p
SET 
    min_price = (
        SELECT MIN(si.current_price)
        FROM supplier_items si
        WHERE si.product_id = p.id
          AND si.match_status IN ('auto_matched', 'verified_match')
    ),
    availability = EXISTS (
        SELECT 1 FROM supplier_items si
        WHERE si.product_id = p.id
          AND si.match_status IN ('auto_matched', 'verified_match')
          AND (
              (si.characteristics->>'in_stock')::boolean = true
              OR LOWER(si.characteristics->>'in_stock') IN ('yes', 'true', '1')
          )
    ),
    updated_at = NOW()
WHERE p.id = $1;
```

### 4. Get Review Queue with Pagination

```sql
SELECT 
    rq.*,
    si.name as supplier_item_name,
    s.name as supplier_name
FROM match_review_queue rq
JOIN supplier_items si ON rq.supplier_item_id = si.id
JOIN suppliers s ON si.supplier_id = s.id
WHERE rq.status = 'pending'
  AND rq.expires_at > NOW()
ORDER BY rq.created_at DESC
LIMIT $1 OFFSET $2;
```

### 5. Expire Old Review Queue Items

```sql
UPDATE match_review_queue
SET status = 'expired'
WHERE status = 'pending'
  AND expires_at < NOW();
```

---

## Migration Plan

### Migration: 002_add_matching_pipeline.py

```python
"""Add matching pipeline tables and columns.

Revision ID: 002
Revises: 001
Create Date: 2025-11-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE match_status AS ENUM ('unmatched', 'auto_matched', 'potential_match', 'verified_match')")
    op.execute("CREATE TYPE review_status AS ENUM ('pending', 'approved', 'rejected', 'expired', 'needs_category')")
    
    # Add columns to products table
    op.add_column('products', sa.Column('min_price', sa.Numeric(10, 2), nullable=True))
    op.add_column('products', sa.Column('availability', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('products', sa.Column('mrp', sa.Numeric(10, 2), nullable=True))
    
    # Create indexes for products
    op.create_index('idx_products_min_price', 'products', ['min_price'], postgresql_where=sa.text('min_price IS NOT NULL'))
    op.create_index('idx_products_availability', 'products', ['availability'])
    
    # Add columns to supplier_items table
    op.add_column('supplier_items', sa.Column('match_status', sa.Enum('unmatched', 'auto_matched', 'potential_match', 'verified_match', name='match_status'), nullable=False, server_default='unmatched'))
    op.add_column('supplier_items', sa.Column('match_score', sa.Numeric(5, 2), nullable=True))
    op.add_column('supplier_items', sa.Column('match_candidates', JSONB, nullable=True))
    
    # Create indexes for supplier_items
    op.create_index('idx_supplier_items_match_status', 'supplier_items', ['match_status'])
    op.create_index('idx_supplier_items_unmatched', 'supplier_items', ['product_id'], postgresql_where=sa.text("product_id IS NULL AND match_status = 'unmatched'"))
    op.create_index('idx_supplier_items_match_score', 'supplier_items', [sa.text('match_score DESC')], postgresql_where=sa.text('match_score IS NOT NULL'))
    
    # Add constraint for match_score
    op.create_check_constraint('check_match_score', 'supplier_items', 'match_score IS NULL OR (match_score >= 0 AND match_score <= 100)')
    
    # Create match_review_queue table
    op.create_table(
        'match_review_queue',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('supplier_item_id', UUID, sa.ForeignKey('supplier_items.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('candidate_products', JSONB, nullable=False, server_default='[]'),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'expired', 'needs_category', name='review_status'), nullable=False, server_default='pending'),
        sa.Column('reviewed_by', UUID, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create indexes for match_review_queue
    op.create_index('idx_review_queue_status', 'match_review_queue', ['status'])
    op.create_index('idx_review_queue_expires', 'match_review_queue', ['expires_at'], postgresql_where=sa.text("status = 'pending'"))
    op.create_index('idx_review_queue_created', 'match_review_queue', [sa.text('created_at DESC')])
    op.create_index('idx_review_queue_status_expires', 'match_review_queue', ['status', 'expires_at'], postgresql_where=sa.text("status = 'pending'"))


def downgrade() -> None:
    # Drop match_review_queue
    op.drop_table('match_review_queue')
    
    # Drop supplier_items columns and indexes
    op.drop_constraint('check_match_score', 'supplier_items', type_='check')
    op.drop_index('idx_supplier_items_match_score')
    op.drop_index('idx_supplier_items_unmatched')
    op.drop_index('idx_supplier_items_match_status')
    op.drop_column('supplier_items', 'match_candidates')
    op.drop_column('supplier_items', 'match_score')
    op.drop_column('supplier_items', 'match_status')
    
    # Drop products columns and indexes
    op.drop_index('idx_products_availability')
    op.drop_index('idx_products_min_price')
    op.drop_column('products', 'mrp')
    op.drop_column('products', 'availability')
    op.drop_column('products', 'min_price')
    
    # Drop enum types
    op.execute("DROP TYPE review_status")
    op.execute("DROP TYPE match_status")
```

---

## Validation Rules Summary

### Database-Level Constraints

1. **match_score:** 0-100 or NULL
2. **supplier_item_id in review_queue:** Unique (one review per item)
3. **Foreign keys:** CASCADE delete for orphan cleanup

### Application-Level Validation (Pydantic)

1. **MatchCandidate.score:** 0-100
2. **ReviewAction:** product_id required for 'approve', new_product_name for 'create_new'
3. **Batch sizes:** 1-1000 for matching tasks

---

**Approval:**
- [x] Data Model Complete - Ready for Contracts Phase

