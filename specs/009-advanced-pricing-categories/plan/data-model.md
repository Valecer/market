# Data Model: Advanced Pricing and Categorization

**Phase:** 009  
**Date:** 2025-12-03  
**Status:** Complete

---

## Overview

This document defines the schema changes required to support dual pricing (retail/wholesale) with currency tracking on the Product entity.

---

## Entity Changes

### Product (Extended)

**Table:** `products`

#### New Columns

| Column | Type | Nullable | Default | Constraint | Description |
|--------|------|----------|---------|------------|-------------|
| `retail_price` | `DECIMAL(10,2)` | Yes | `NULL` | `>= 0` | End-customer price |
| `wholesale_price` | `DECIMAL(10,2)` | Yes | `NULL` | `>= 0` | Bulk/dealer price |
| `currency_code` | `VARCHAR(3)` | Yes | `NULL` | — | ISO 4217 currency code |

#### Existing Columns (Unchanged)

| Column | Type | Description |
|--------|------|-------------|
| `id` | `UUID` | Primary key |
| `internal_sku` | `VARCHAR(100)` | Unique SKU |
| `name` | `VARCHAR(500)` | Product name |
| `category_id` | `UUID` | FK to categories |
| `status` | `product_status` | draft/active/archived |
| `min_price` | `DECIMAL(10,2)` | Aggregate: lowest supplier price |
| `availability` | `BOOLEAN` | Aggregate: any supplier has stock |
| `mrp` | `DECIMAL(10,2)` | Manufacturer's recommended price |
| `created_at` | `TIMESTAMPTZ` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | Last update timestamp |

#### Field Relationships

```
min_price      → Aggregate from supplier_items (computed)
retail_price   → Product-level canonical price (direct)
wholesale_price → Product-level canonical price (direct)
```

---

### Category (No Changes)

The Category entity already supports infinite nesting via adjacency list pattern.

**Existing Self-Referential Structure:**

```sql
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    parent_id UUID REFERENCES categories(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(name, parent_id)
);

CREATE INDEX idx_categories_parent ON categories(parent_id);
```

**Hierarchy Query Example:**

```sql
-- Get full path to root for a category
WITH RECURSIVE category_path AS (
    SELECT id, name, parent_id, 1 as depth, ARRAY[name] as path
    FROM categories
    WHERE id = :category_id
    
    UNION ALL
    
    SELECT c.id, c.name, c.parent_id, cp.depth + 1, c.name || cp.path
    FROM categories c
    JOIN category_path cp ON c.id = cp.parent_id
)
SELECT * FROM category_path ORDER BY depth DESC;
```

---

## SQLAlchemy ORM Model

### Updated Product Model

```python
# src/db/models/product.py

from sqlalchemy import String, ForeignKey, Enum as SQLEnum, Numeric, Boolean, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin, TimestampMixin
from enum import Enum as PyEnum
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from src.db.models.category import Category
    from src.db.models.supplier_item import SupplierItem


class ProductStatus(PyEnum):
    """Product lifecycle status enum."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Product(Base, UUIDMixin, TimestampMixin):
    """Product model representing internal unified catalog."""
    
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            'retail_price IS NULL OR retail_price >= 0',
            name='check_retail_price_non_negative'
        ),
        CheckConstraint(
            'wholesale_price IS NULL OR wholesale_price >= 0',
            name='check_wholesale_price_non_negative'
        ),
    )
    
    # Existing fields
    internal_sku: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    status: Mapped[ProductStatus] = mapped_column(
        SQLEnum(ProductStatus, name="product_status", 
                values_callable=lambda x: [e.value for e in x]),
        nullable=False, server_default=ProductStatus.DRAFT.value, index=True
    )
    
    # Aggregate fields (Phase 4)
    min_price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True, index=True,
        doc="Lowest price among linked active supplier items"
    )
    availability: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default='false',
        doc="TRUE if any linked supplier has stock"
    )
    mrp: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True,
        doc="Manufacturer's recommended price (placeholder)"
    )
    
    # === NEW: Phase 9 - Canonical pricing fields ===
    retail_price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True,
        doc="End-customer price (canonical product-level)"
    )
    wholesale_price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True,
        doc="Bulk/dealer price (canonical product-level)"
    )
    currency_code: Mapped[str | None] = mapped_column(
        String(3), nullable=True,
        doc="ISO 4217 currency code (e.g., USD, EUR, RUB)"
    )
    
    # Relationships
    category: Mapped[Optional["Category"]] = relationship(back_populates="products")
    supplier_items: Mapped[List["SupplierItem"]] = relationship(back_populates="product")
    
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku='{self.internal_sku}', status='{self.status.value}')>"
```

---

## Drizzle Schema (Bun API)

```typescript
// services/bun-api/src/db/schema/schema.ts (partial update)

export const products = pgTable("products", {
    id: uuid().defaultRandom().primaryKey().notNull(),
    internalSku: varchar("internal_sku", { length: 100 }).notNull(),
    name: varchar({ length: 500 }).notNull(),
    categoryId: uuid("category_id"),
    status: productStatus().default('draft').notNull(),
    
    // Aggregate fields
    minPrice: numeric("min_price", { precision: 10, scale: 2 }),
    availability: boolean().default(false).notNull(),
    mrp: numeric({ precision: 10, scale: 2 }),
    
    // NEW: Phase 9 - Canonical pricing
    retailPrice: numeric("retail_price", { precision: 10, scale: 2 }),
    wholesalePrice: numeric("wholesale_price", { precision: 10, scale: 2 }),
    currencyCode: varchar("currency_code", { length: 3 }),
    
    createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
    // Existing indexes...
    index("idx_products_category").using("btree", table.categoryId),
    index("idx_products_name").using("btree", table.name),
    index("idx_products_sku").using("btree", table.internalSku),
    index("idx_products_status").using("btree", table.status),
    // Existing constraints...
    foreignKey({
        columns: [table.categoryId],
        foreignColumns: [categories.id],
        name: "products_category_id_fkey"
    }).onDelete("set null"),
    unique("products_internal_sku_key").on(table.internalSku),
    // NEW: Price constraints
    check("check_retail_price_non_negative", sql`retail_price IS NULL OR retail_price >= 0`),
    check("check_wholesale_price_non_negative", sql`wholesale_price IS NULL OR wholesale_price >= 0`),
]);
```

---

## Pydantic Models

### Request/Response Schemas

```python
# src/models/product_pricing.py

from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
import re
from typing import Optional


class ProductPricingUpdate(BaseModel):
    """Schema for updating product pricing fields."""
    retail_price: Decimal | None = Field(None, ge=0, decimal_places=2)
    wholesale_price: Decimal | None = Field(None, ge=0, decimal_places=2)
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    
    @field_validator('currency_code')
    @classmethod
    def validate_currency_code(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r'^[A-Z]{3}$', v):
            raise ValueError('Currency code must be 3 uppercase letters (ISO 4217 format)')
        return v


class ProductPricingResponse(BaseModel):
    """Schema for product pricing in API responses."""
    id: str
    internal_sku: str
    name: str
    category_id: str | None
    status: str
    
    # Aggregate fields
    min_price: Decimal | None
    availability: bool
    mrp: Decimal | None
    
    # Canonical pricing
    retail_price: Decimal | None
    wholesale_price: Decimal | None
    currency_code: str | None
    
    class Config:
        from_attributes = True
```

---

## Migration Script

### File: `009_add_pricing_fields.py`

```python
"""Add retail_price, wholesale_price, and currency_code to products.

This migration adds canonical pricing fields to support dual pricing
(retail/wholesale) with currency tracking.

Revision ID: 009_add_pricing_fields
Revises: 008_create_product_embeddings
Create Date: 2025-12-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '009_add_pricing_fields'
down_revision: Union[str, None] = '008_create_product_embeddings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add retail_price column (nullable, no default)
    op.add_column(
        'products',
        sa.Column('retail_price', sa.Numeric(precision=10, scale=2), nullable=True)
    )
    
    # Add wholesale_price column (nullable, no default)
    op.add_column(
        'products',
        sa.Column('wholesale_price', sa.Numeric(precision=10, scale=2), nullable=True)
    )
    
    # Add currency_code column (nullable, no default)
    op.add_column(
        'products',
        sa.Column('currency_code', sa.String(length=3), nullable=True)
    )
    
    # Add check constraint for retail_price >= 0
    op.create_check_constraint(
        'check_retail_price_non_negative',
        'products',
        'retail_price IS NULL OR retail_price >= 0'
    )
    
    # Add check constraint for wholesale_price >= 0
    op.create_check_constraint(
        'check_wholesale_price_non_negative',
        'products',
        'wholesale_price IS NULL OR wholesale_price >= 0'
    )


def downgrade() -> None:
    # Drop check constraints first
    op.drop_constraint('check_wholesale_price_non_negative', 'products', type_='check')
    op.drop_constraint('check_retail_price_non_negative', 'products', type_='check')
    
    # Drop columns
    op.drop_column('products', 'currency_code')
    op.drop_column('products', 'wholesale_price')
    op.drop_column('products', 'retail_price')
```

---

## Database State Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         products                                 │
├─────────────────────────────────────────────────────────────────┤
│ id                 UUID PK                                       │
│ internal_sku       VARCHAR(100) UNIQUE NOT NULL                  │
│ name               VARCHAR(500) NOT NULL                         │
│ category_id        UUID FK → categories(id) ON DELETE SET NULL   │
│ status             product_status NOT NULL DEFAULT 'draft'       │
│─────────────────────────────────────────────────────────────────│
│ min_price          DECIMAL(10,2)       -- aggregate              │
│ availability       BOOLEAN NOT NULL     -- aggregate              │
│ mrp                DECIMAL(10,2)       -- placeholder            │
│─────────────────────────────────────────────────────────────────│
│ retail_price       DECIMAL(10,2)       -- NEW: canonical         │
│ wholesale_price    DECIMAL(10,2)       -- NEW: canonical         │
│ currency_code      VARCHAR(3)          -- NEW: ISO 4217          │
│─────────────────────────────────────────────────────────────────│
│ created_at         TIMESTAMPTZ NOT NULL                          │
│ updated_at         TIMESTAMPTZ NOT NULL                          │
├─────────────────────────────────────────────────────────────────┤
│ CONSTRAINTS:                                                     │
│   check_retail_price_non_negative                                │
│   check_wholesale_price_non_negative                             │
└─────────────────────────────────────────────────────────────────┘
           │
           │ category_id
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        categories                                │
├─────────────────────────────────────────────────────────────────┤
│ id           UUID PK                                             │
│ name         VARCHAR(255) NOT NULL                               │
│ parent_id    UUID FK → categories(id) ON DELETE CASCADE          │
│ created_at   TIMESTAMPTZ NOT NULL                                │
├─────────────────────────────────────────────────────────────────┤
│ CONSTRAINTS:                                                     │
│   UNIQUE(name, parent_id)                                        │
│ INDEXES:                                                         │
│   idx_categories_parent (parent_id)                              │
│                                                                  │
│ *** SUPPORTS INFINITE NESTING VIA SELF-REFERENCE ***             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Validation Rules

| Field | Validation | Layer |
|-------|------------|-------|
| `retail_price` | `>= 0` or `NULL` | Database (CHECK), Pydantic |
| `wholesale_price` | `>= 0` or `NULL` | Database (CHECK), Pydantic |
| `currency_code` | `^[A-Z]{3}$` or `NULL` | Pydantic |

---

## State Transitions

No state machine changes. The new fields are simple data attributes.

---

## Backward Compatibility

| Scenario | Behavior |
|----------|----------|
| Existing products | All new fields default to `NULL` |
| Existing API consumers | New fields returned but nullable |
| Legacy integrations | Can ignore new fields |
| New ingestion | Should populate fields when available |

