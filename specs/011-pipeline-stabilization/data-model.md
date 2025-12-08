# Data Model: Data Pipeline Stabilization

**Feature:** 011-pipeline-stabilization

**Date:** 2025-12-09

**Status:** Complete

---

## Entity Relationship Diagram

```
┌─────────────────────┐         ┌─────────────────────┐
│   supplier_items    │         │     products        │
│─────────────────────│         │─────────────────────│
│ id (UUID) PK        │╲       ╱│ id (UUID) PK        │
│ supplier_id (UUID)  │ ╲     ╱ │ internal_sku (str)  │
│ product_id (UUID) FK│──●───●  │ name (str)          │
│ variant_id (UUID) FK│         │ category_id (UUID)  │
│ source_row_hash (32)│◄──NEW  │ status (enum)       │
│ name (str)          │         │ has_variants (bool) │
│ current_price (num) │         │ variant_schema (json│
│ characteristics(json│         └─────────────────────┘
│ match_status (enum) │                  │
│ last_ingested_at    │                  │
└─────────────────────┘                  │
                                         │
        ┌────────────────────────────────┤
        │                                │
        ▼                                ▼
┌─────────────────────┐         ┌─────────────────────┐
│product_variants     │         │    categories       │
│─────────────────────│         │─────────────────────│
│ id (UUID) PK        │         │ id (UUID) PK        │
│ product_id (UUID) FK│         │ name (str)          │
│ variant_key (str)   │         │ parent_id (UUID) FK │◄─┐
│ variant_attributes  │         │ category_level (int)│◄─NEW
│ display_order (int) │         │ needs_review (bool) │  │
└─────────────────────┘         │ is_active (bool)    │  │
                                 │ supplier_id (UUID)  │  │
                                 └─────────────────────┘  │
                                          │               │
                                          └───────────────┘
                                          self-reference

┌─────────────────────────────────────┐
│    potential_duplicates (NEW)       │
│─────────────────────────────────────│
│ id (UUID) PK                        │
│ product_id_1 (UUID) FK → products   │
│ product_id_2 (UUID) FK → products   │
│ similarity_score (numeric)          │
│ detection_reason (str)              │
│ status (enum: pending|merged|       │
│          dismissed)                 │
│ reviewed_by (UUID) FK → users       │
│ reviewed_at (timestamp)             │
│ created_at (timestamp)              │
│                                     │
│ CHK: product_id_1 != product_id_2   │
│ CHK: product_id_1 < product_id_2    │
└─────────────────────────────────────┘
```

---

## Entity Definitions

### 1. SupplierItem (Modified)

**Purpose:** Represents a product offering from a supplier. Extended with hash-based idempotency.

**Table:** `supplier_items`

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `supplier_id` | UUID | NOT NULL, FK → suppliers | Supplier providing this item |
| `product_id` | UUID | NULLABLE, FK → products | Linked product (null if unmatched) |
| `variant_id` | UUID | NULLABLE, FK → product_variants | Linked variant (Phase 10) |
| **`source_row_hash`** | VARCHAR(32) | **NEW**, INDEXED | MD5 hash of raw row data for idempotency |
| `supplier_sku` | VARCHAR(255) | NOT NULL | Supplier's SKU |
| `name` | VARCHAR(500) | NOT NULL | Product name from supplier |
| `current_price` | NUMERIC(10,2) | NOT NULL | Current retail price |
| `price_opt` | NUMERIC(12,2) | NULLABLE | Wholesale/optimal price |
| `price_rrc` | NUMERIC(12,2) | NULLABLE | Recommended retail price |
| `characteristics` | JSONB | NULLABLE | Flexible attributes from parsing |
| `category_id` | UUID | NULLABLE, FK → categories | Normalized category |
| `match_status` | ENUM | NOT NULL | 'unmatched', 'auto_matched', 'auto_created', 'verified_match' |
| `match_score` | NUMERIC(5,2) | NULLABLE | Confidence score (0-100) |
| `match_candidates` | JSONB | NULLABLE | Array of potential matches |
| `last_ingested_at` | TIMESTAMP | NOT NULL | Last time this item was ingested |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | First ingestion timestamp |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Indexes:**

```sql
CREATE INDEX idx_supplier_items_hash ON supplier_items(source_row_hash);
CREATE INDEX idx_supplier_items_supplier ON supplier_items(supplier_id);
CREATE INDEX idx_supplier_items_product ON supplier_items(product_id);
CREATE INDEX idx_supplier_items_category ON supplier_items(category_id);
```

**State Transitions:**

```
┌─────────────┐    Matching       ┌──────────────┐
│  unmatched  │────(conf≥90%)────→│ auto_matched │
└─────────────┘                   └──────────────┘
      │
      │ Auto-Creation (conf<90%)
      ▼
┌──────────────┐    Admin Review   ┌────────────────┐
│ auto_created │────────────────→ │verified_match │
└──────────────┘                   └────────────────┘
```

**Validation Rules:**

- `source_row_hash` must be exactly 32 characters (MD5 hex digest)
- `match_status = 'auto_matched'` requires `product_id IS NOT NULL` and `match_score ≥ 90`
- `match_status = 'auto_created'` requires `product_id IS NOT NULL` and `match_score IS NULL`
- `current_price > 0`

---

### 2. Product (Unchanged Schema, Modified Behavior)

**Purpose:** Internal product entity. May be auto-created by matching service.

**Table:** `products`

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `internal_sku` | VARCHAR(100) | UNIQUE, NOT NULL | Internal SKU (format: AUTO-{hex} for auto-created) |
| `name` | VARCHAR(500) | NOT NULL | Product name (ML-cleaned for auto-created) |
| `category_id` | UUID | NOT NULL, FK → categories | Product category |
| `status` | ENUM | NOT NULL, DEFAULT 'active' | 'draft', 'active', 'archived' |
| `has_variants` | BOOLEAN | NOT NULL, DEFAULT false | True if product has variants |
| `variant_schema` | JSONB | NULLABLE | Array of variant attribute keys (e.g., [{key: "voltage"}]) |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Indexes:**

```sql
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_status ON products(status);
CREATE UNIQUE INDEX idx_products_sku ON products(internal_sku);
```

**Auto-Creation Behavior:**

- When `match_status < 90%`, matching service creates new Product:
  - `internal_sku = AUTO-{uuid4().hex[:8].upper()}` (e.g., "AUTO-A3F2B91C")
  - `name = extraction.cleaned_name` (ML-cleaned, not raw supplier name)
  - `category_id = extraction.category_id` (normalized category)
  - `status = 'active'` (immediately visible in catalog)

---

### 3. Category (Modified)

**Purpose:** Hierarchical product categories. Extended with level enforcement.

**Table:** `categories`

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `name` | VARCHAR(255) | NOT NULL | Category name |
| `parent_id` | UUID | NULLABLE, FK → categories | Parent category (null for root) |
| **`category_level`** | INTEGER | **NEW**, NOT NULL, CHK(1-3) | Hierarchy level (1=Top, 2=Sub, 3=Brand) |
| `needs_review` | BOOLEAN | NOT NULL, DEFAULT false | Flag for admin review |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true | Soft delete flag |
| `supplier_id` | UUID | NULLABLE, FK → suppliers | Originating supplier (for review) |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Constraints:**

```sql
ALTER TABLE categories
ADD CONSTRAINT chk_category_level CHECK (category_level IN (1, 2, 3));

ALTER TABLE categories
ADD CONSTRAINT chk_no_self_reference CHECK (id != parent_id);
```

**Indexes:**

```sql
CREATE INDEX idx_categories_parent ON categories(parent_id);
CREATE INDEX idx_categories_level ON categories(category_level);
CREATE INDEX idx_categories_needs_review ON categories(needs_review) WHERE needs_review = true;
```

**Hierarchy Rules:**

| Level | Description | parent_id | Example |
|-------|-------------|-----------|---------|
| 1     | Top Category | NULL      | "Electric Transport" |
| 2     | Sub-category | Level 1 category | "Motorcycles" |
| 3     | Brand        | Level 2 category | "Shtenli" |

**State Transitions:**

```
┌─────────────────┐    Admin Review     ┌──────────────┐
│ needs_review=T  │────────────────────→│ is_active=T  │
│ category_level<3│                     │ needs_review=F│
└─────────────────┘                     └──────────────┘
```

**Incomplete Hierarchy Handling:**

- If extraction provides only 1 level (e.g., "Tools"):
  - Create Level 1 category: "Tools" (parent_id = NULL, category_level = 1)
  - Flag: `needs_review = true`
  - Product assigned to Level 1 category temporarily
- If extraction provides only 2 levels (e.g., ["Home", "Kitchen"]):
  - Create Level 1: "Home", Level 2: "Kitchen"
  - Flag Level 2: `needs_review = true`
  - Product assigned to Level 2 category temporarily

---

### 4. PotentialDuplicate (New Entity)

**Purpose:** Tracks suspected duplicate products created by auto-creation logic.

**Table:** `potential_duplicates`

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `product_id_1` | UUID | NOT NULL, FK → products | First product in pair |
| `product_id_2` | UUID | NOT NULL, FK → products | Second product in pair |
| `similarity_score` | NUMERIC(5,2) | NOT NULL, CHK(0-100) | Name similarity (0-100) |
| `detection_reason` | VARCHAR(100) | NOT NULL | 'auto_creation_similarity', 'manual_report' |
| `status` | ENUM | NOT NULL, DEFAULT 'pending' | 'pending', 'merged', 'dismissed' |
| `reviewed_by` | UUID | NULLABLE, FK → users | Admin who reviewed |
| `reviewed_at` | TIMESTAMP | NULLABLE | Review timestamp |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Detection timestamp |

**Constraints:**

```sql
ALTER TABLE potential_duplicates
ADD CONSTRAINT chk_different_products CHECK (product_id_1 != product_id_2);

ALTER TABLE potential_duplicates
ADD CONSTRAINT chk_ordered_ids CHECK (product_id_1 < product_id_2);

ALTER TABLE potential_duplicates
ADD CONSTRAINT chk_similarity_range CHECK (similarity_score BETWEEN 0 AND 100);
```

**Indexes:**

```sql
CREATE INDEX idx_potential_duplicates_status ON potential_duplicates(status);
CREATE INDEX idx_potential_duplicates_product1 ON potential_duplicates(product_id_1);
CREATE INDEX idx_potential_duplicates_product2 ON potential_duplicates(product_id_2);
```

**State Transitions:**

```
┌──────────┐    Admin: Merge     ┌──────────┐
│ pending  │────────────────────→│  merged  │
└──────────┘                     └──────────┘
     │
     │ Admin: Dismiss
     ▼
┌──────────┐
│dismissed │
└──────────┘
```

**Detection Criteria:**

Products are flagged as potential duplicates if ALL conditions met:
1. Name similarity ≥85% AND <90% (RapidFuzz WRatio)
2. Same `category_id`
3. NOT already grouped as variants (`has_variants` false OR different `variant_schema`)
4. Price difference <20%

**Merge Behavior:**

When admin merges duplicates (keeps product A, archives product B):
1. `UPDATE supplier_items SET product_id = A WHERE product_id = B`
2. `UPDATE products SET status = 'archived' WHERE id = B`
3. `UPDATE potential_duplicates SET status = 'merged', reviewed_by = ?, reviewed_at = NOW() WHERE id = ?`

---

### 5. ProductVariant (Unchanged, Referenced)

**Purpose:** Represents a variant of a product (e.g., different voltage, capacity).

**Table:** `product_variants`

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier |
| `product_id` | UUID | NOT NULL, FK → products | Parent product |
| `variant_key` | VARCHAR(255) | NOT NULL | Variant key (e.g., "48V/20Ah") |
| `variant_attributes` | JSONB | NOT NULL | Attributes (e.g., {voltage: "48V", capacity: "20Ah"}) |
| `display_order` | INTEGER | NOT NULL, DEFAULT 0 | Display order in UI |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Constraints:**

```sql
ALTER TABLE product_variants
ADD CONSTRAINT uq_product_variant_key UNIQUE (product_id, variant_key);
```

**Integration with Pipeline:**

- Variant detection runs after auto-creation phase
- Compares newly created products in same category
- Groups products with >85% name similarity and differing variant attributes
- Updates parent product: `has_variants = true`, `variant_schema = [{key: "voltage"}, ...]`
- Creates variant records for each product in group

---

## Data Flow Diagrams

### 1. Idempotent Re-Ingestion Flow

```
┌──────────────┐
│ Excel Row    │
│ {"SKU": 123, │
│  "Name": "X",│
│  "Price": 10}│
└──────┬───────┘
       │
       ▼
┌──────────────────────────────┐
│ Compute Hash                 │
│ hash = md5("supplier_123|    │
│    {name:X,price:10,sku:123}")│
└──────┬───────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│ Query: SELECT * FROM         │
│ supplier_items WHERE         │
│ source_row_hash = 'abc123'   │
└──────┬───────────────────────┘
       │
   ┌───┴───┐
   │Found? │
   └───┬───┘
       │
   ┌───▼───┐No      ┌──────────────────┐
   │ Yes   ├───────→│ ML Extraction    │
   └───┬───┘        │ (cache miss)     │
       │            └──────────────────┘
       │ Cache Hit
       ▼
┌──────────────────────────────┐
│ UPDATE supplier_items        │
│ SET current_price = 10,      │
│     last_ingested_at = NOW() │
│ WHERE source_row_hash='abc123│
└──────────────────────────────┘
```

### 2. Auto-Creation Flow

```
┌──────────────────┐
│ ML Extraction    │
│ ExtractedProduct:│
│ • cleaned_name   │
│ • category_id    │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────┐
│ Matching Service             │
│ find_best_match(item)        │
└────────┬─────────────────────┘
         │
   ┌─────▼─────┐
   │Confidence?│
   └─────┬─────┘
         │
    ┌────┴────┐
    │  ≥90%   │  <90%
    ▼         ▼
┌────────┐  ┌──────────────────┐
│ Link   │  │ Auto-Create      │
│ to     │  │ Product:         │
│existing│  │ • internal_sku   │
└────────┘  │   = AUTO-{hex}   │
            │ • name = cleaned │
            │ • status=active  │
            └─────┬────────────┘
                  │
                  ▼
            ┌──────────────────┐
            │ Link supplier_   │
            │ item.product_id  │
            │ = new_product.id │
            └──────────────────┘
```

### 3. Category Hierarchy Enforcement Flow

```
┌──────────────────────────────┐
│ Extracted Categories:        │
│ ["Electric Transport",       │
│  "Motorcycles", "Shtenli"]   │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│ Level 1: Find/Create         │
│ "Electric Transport"         │
│ (parent_id=NULL, level=1)    │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│ Level 2: Find/Create         │
│ "Motorcycles"                │
│ (parent_id=L1.id, level=2)   │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│ Level 3: Find/Create         │
│ "Shtenli"                    │
│ (parent_id=L2.id, level=3)   │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│ Product.category_id = L3.id  │
└──────────────────────────────┘

┌──────────────────────────────┐
│ IF path has <3 levels:       │
│ • Flag needs_review=true     │
│ • Log to parsing_logs        │
│ • Assign to partial category │
└──────────────────────────────┘
```

---

## Migration Script

**File:** `services/python-ingestion/migrations/versions/011_pipeline_stabilization_schema.py`

```python
"""Add pipeline stabilization schema

Revision ID: 011_pipeline_stabilization
Create Date: 2025-12-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

def upgrade():
    # Add source_row_hash to supplier_items
    op.add_column(
        'supplier_items',
        sa.Column('source_row_hash', sa.VARCHAR(32), nullable=True)
    )
    op.create_index(
        'idx_supplier_items_hash',
        'supplier_items',
        ['source_row_hash']
    )

    # Add category_level to categories
    op.add_column(
        'categories',
        sa.Column('category_level', sa.INTEGER, nullable=True)
    )

    # Backfill category_level for existing categories
    # (see backfill script in research.md)
    from services.python_ingestion.scripts import backfill_category_levels
    backfill_category_levels()

    # Add NOT NULL constraint after backfill
    op.alter_column('categories', 'category_level', nullable=False)

    # Add CHECK constraint for category_level
    op.create_check_constraint(
        'chk_category_level',
        'categories',
        'category_level IN (1, 2, 3)'
    )

    # Create potential_duplicates table
    op.create_table(
        'potential_duplicates',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('product_id_1', UUID, nullable=False),
        sa.Column('product_id_2', UUID, nullable=False),
        sa.Column('similarity_score', sa.NUMERIC(5, 2), nullable=False),
        sa.Column('detection_reason', sa.VARCHAR(100), nullable=False),
        sa.Column('status', sa.VARCHAR(50), nullable=False, server_default='pending'),
        sa.Column('reviewed_by', UUID, nullable=True),
        sa.Column('reviewed_at', sa.TIMESTAMP, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['product_id_1'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id_2'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.CheckConstraint('product_id_1 != product_id_2', name='chk_different_products'),
        sa.CheckConstraint('product_id_1 < product_id_2', name='chk_ordered_ids'),
        sa.CheckConstraint('similarity_score BETWEEN 0 AND 100', name='chk_similarity_range')
    )

    # Create indexes for potential_duplicates
    op.create_index('idx_potential_duplicates_status', 'potential_duplicates', ['status'])
    op.create_index('idx_potential_duplicates_product1', 'potential_duplicates', ['product_id_1'])
    op.create_index('idx_potential_duplicates_product2', 'potential_duplicates', ['product_id_2'])

def downgrade():
    # Drop potential_duplicates table
    op.drop_table('potential_duplicates')

    # Remove category_level from categories
    op.drop_constraint('chk_category_level', 'categories')
    op.drop_column('categories', 'category_level')

    # Remove source_row_hash from supplier_items
    op.drop_index('idx_supplier_items_hash', 'supplier_items')
    op.drop_column('supplier_items', 'source_row_hash')
```

---

## References

- [Feature Specification](./spec.md)
- [Implementation Plan](./plan.md)
- [Research Decisions](./research.md)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [PostgreSQL CHECK Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
