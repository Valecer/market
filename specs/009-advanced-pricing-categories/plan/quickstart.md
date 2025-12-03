# Quickstart: Phase 009 - Advanced Pricing

**Time to complete:** ~15 minutes  
**Prerequisites:** Docker running, Python 3.12+, Bun installed

---

## Overview

This guide walks you through implementing the data model changes for dual pricing (retail/wholesale) with currency tracking.

---

## Step 1: Create the Migration (5 min)

### 1.1 Navigate to Python Worker Service

```bash
cd services/python-ingestion
source venv/bin/activate
```

### 1.2 Create Migration File

```bash
# Create new migration
alembic revision -m "add_pricing_fields"
```

This creates a new file in `migrations/versions/`. Rename it to match our convention:

```bash
mv migrations/versions/*_add_pricing_fields.py \
   migrations/versions/009_add_pricing_fields.py
```

### 1.3 Edit Migration Content

Replace the migration content with:

```python
"""Add retail_price, wholesale_price, and currency_code to products.

Revision ID: 009_add_pricing_fields
Revises: 008_create_product_embeddings
Create Date: 2025-12-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '009_add_pricing_fields'
down_revision: Union[str, None] = '008_create_product_embeddings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add retail_price column
    op.add_column(
        'products',
        sa.Column('retail_price', sa.Numeric(precision=10, scale=2), nullable=True)
    )
    
    # Add wholesale_price column
    op.add_column(
        'products',
        sa.Column('wholesale_price', sa.Numeric(precision=10, scale=2), nullable=True)
    )
    
    # Add currency_code column
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
    op.drop_constraint('check_wholesale_price_non_negative', 'products', type_='check')
    op.drop_constraint('check_retail_price_non_negative', 'products', type_='check')
    op.drop_column('products', 'currency_code')
    op.drop_column('products', 'wholesale_price')
    op.drop_column('products', 'retail_price')
```

---

## Step 2: Update SQLAlchemy Model (3 min)

### 2.1 Edit Product Model

Open `src/db/models/product.py` and add the new fields:

```python
# Add to imports at top
from sqlalchemy import CheckConstraint

# Add __table_args__ to Product class (after __tablename__)
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

# Add new fields after mrp field
retail_price: Mapped[Decimal | None] = mapped_column(
    Numeric(10, 2),
    nullable=True,
    doc="End-customer price (canonical product-level)"
)
wholesale_price: Mapped[Decimal | None] = mapped_column(
    Numeric(10, 2),
    nullable=True,
    doc="Bulk/dealer price (canonical product-level)"
)
currency_code: Mapped[str | None] = mapped_column(
    String(3),
    nullable=True,
    doc="ISO 4217 currency code (e.g., USD, EUR, RUB)"
)
```

---

## Step 3: Run Migration (2 min)

### 3.1 Start Database (if not running)

```bash
docker-compose up -d postgres
```

### 3.2 Apply Migration

```bash
cd services/python-ingestion
source venv/bin/activate
alembic upgrade head
```

### 3.3 Verify Migration

```bash
docker exec -it marketbel-postgres psql -U postgres -d marketbel -c "\d products"
```

Expected output should include:

```
    Column      |           Type           | ...
----------------+--------------------------+
 retail_price   | numeric(10,2)            |
 wholesale_price| numeric(10,2)            |
 currency_code  | character varying(3)     |
```

---

## Step 4: Update Drizzle Schema (3 min)

### 4.1 Introspect Schema

```bash
cd services/bun-api
bun run drizzle-kit introspect
```

### 4.2 Or Manual Update

If introspect doesn't pick up the changes, manually add to `src/db/schema/schema.ts`:

```typescript
export const products = pgTable("products", {
    // ... existing fields ...
    
    // NEW: Phase 9 - Canonical pricing
    retailPrice: numeric("retail_price", { precision: 10, scale: 2 }),
    wholesalePrice: numeric("wholesale_price", { precision: 10, scale: 2 }),
    currencyCode: varchar("currency_code", { length: 3 }),
    
    // ... timestamps ...
}, (table) => [
    // ... existing constraints ...
    check("check_retail_price_non_negative", sql`retail_price IS NULL OR retail_price >= 0`),
    check("check_wholesale_price_non_negative", sql`wholesale_price IS NULL OR wholesale_price >= 0`),
]);
```

---

## Step 5: Verify Setup (2 min)

### 5.1 Run Tests

```bash
# Python tests
cd services/python-ingestion
pytest tests/unit/test_models.py -v

# Bun API tests
cd services/bun-api
bun test
```

### 5.2 Test Database Constraint

```bash
# This should FAIL (negative price)
docker exec -it marketbel-postgres psql -U postgres -d marketbel -c \
  "UPDATE products SET retail_price = -10 WHERE id = (SELECT id FROM products LIMIT 1);"

# This should SUCCEED
docker exec -it marketbel-postgres psql -U postgres -d marketbel -c \
  "UPDATE products SET retail_price = 99.99, currency_code = 'USD' WHERE id = (SELECT id FROM products LIMIT 1);"
```

---

## Quick Reference

### New Fields Summary

| Field | Type | Nullable | Constraint |
|-------|------|----------|------------|
| `retail_price` | `DECIMAL(10,2)` | Yes | `>= 0` |
| `wholesale_price` | `DECIMAL(10,2)` | Yes | `>= 0` |
| `currency_code` | `VARCHAR(3)` | Yes | — |

### Commands Cheat Sheet

```bash
# Run migration
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Check migration history
alembic history

# Generate new migration
alembic revision -m "description"
```

### Validation Regex for Currency Code

```python
import re
pattern = r'^[A-Z]{3}$'
re.match(pattern, 'USD')  # Valid
re.match(pattern, 'usd')  # Invalid (lowercase)
re.match(pattern, 'US')   # Invalid (too short)
```

---

## Next Steps

After completing this quickstart:

1. **API Layer:** Add pricing fields to product endpoints (FR-4)
2. **Frontend:** Display dual pricing in product views (FR-5)
3. **ML-Analyze:** Update parsers to extract dual pricing from source documents
4. **i18n:** Add translation keys for "Retail Price", "Wholesale Price", currency display

---

## Troubleshooting

### Migration Fails: "relation already exists"

The migration may have partially run. Check current state:

```bash
alembic current
```

If stuck, you can manually drop and recreate:

```sql
ALTER TABLE products DROP COLUMN IF EXISTS retail_price;
ALTER TABLE products DROP COLUMN IF EXISTS wholesale_price;
ALTER TABLE products DROP COLUMN IF EXISTS currency_code;
```

Then re-run `alembic upgrade head`.

### Drizzle Type Errors

Regenerate types after schema changes:

```bash
cd services/bun-api
bun run drizzle-kit generate
```

### Category Hierarchy Questions

The Category model **already supports infinite nesting** via the `parent_id` self-reference. No changes needed for Phase 009.

