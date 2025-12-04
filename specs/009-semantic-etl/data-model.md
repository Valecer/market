# Data Model: Semantic ETL Pipeline

**Date:** 2025-12-04

**Status:** Complete

---

## Overview

This document defines all data structures, database schema changes, and entity relationships for the Semantic ETL pipeline refactoring.

---

## Database Schema Changes

### 1. Categories Table Update

**Purpose:** Support hierarchical categories with fuzzy matching and admin review workflow.

```sql
-- Migration: 009_add_category_hierarchy.sql

ALTER TABLE categories
ADD COLUMN parent_id INT REFERENCES categories(id) ON DELETE CASCADE,
ADD COLUMN needs_review BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true,
ADD COLUMN supplier_id INT REFERENCES suppliers(id) ON DELETE SET NULL,
ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();

-- Indexes for performance
CREATE INDEX idx_categories_parent_id ON categories(parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX idx_categories_needs_review ON categories(needs_review) WHERE needs_review = true;
CREATE INDEX idx_categories_supplier_id ON categories(supplier_id) WHERE supplier_id IS NOT NULL;

-- Constraint: Prevent circular references
ALTER TABLE categories
ADD CONSTRAINT chk_no_self_reference CHECK (id != parent_id);

-- Function: Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_categories_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_categories_updated_at
BEFORE UPDATE ON categories
FOR EACH ROW
EXECUTE FUNCTION update_categories_updated_at();

-- Sample root categories
INSERT INTO categories (name, parent_id, needs_review, is_active)
VALUES
    ('Root', NULL, false, true),
    ('Uncategorized', NULL, false, true)
ON CONFLICT DO NOTHING;
```

**Fields:**

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INT | No | Primary key |
| `name` | VARCHAR(255) | No | Category name |
| `parent_id` | INT | Yes | FK to parent category (NULL for root) |
| `needs_review` | BOOLEAN | No | Flag for admin review queue |
| `is_active` | BOOLEAN | No | Soft delete flag |
| `supplier_id` | INT | Yes | Original supplier (for tracking) |
| `created_at` | TIMESTAMPTZ | No | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | No | Last update timestamp |

**Relationships:**

- Self-referencing: `parent_id → categories.id`
- Many-to-One: `supplier_id → suppliers.id`

---

### 2. Supplier Items Table Validation

**Purpose:** Ensure `price_opt` and `price_rrc` columns exist with correct types.

```sql
-- Migration: 009_validate_supplier_items.sql

-- Check if columns exist, add if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'supplier_items' AND column_name = 'price_opt'
    ) THEN
        ALTER TABLE supplier_items ADD COLUMN price_opt DECIMAL(12, 2);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'supplier_items' AND column_name = 'price_rrc'
    ) THEN
        ALTER TABLE supplier_items ADD COLUMN price_rrc DECIMAL(12, 2);
    END IF;
END $$;

-- Add constraints
ALTER TABLE supplier_items
ADD CONSTRAINT chk_price_opt_positive CHECK (price_opt IS NULL OR price_opt >= 0),
ADD CONSTRAINT chk_price_rrc_positive CHECK (price_rrc IS NULL OR price_rrc >= 0);

-- Rename columns if old naming exists (Phase 7 compatibility)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'supplier_items' AND column_name = 'wholesale_price'
    ) THEN
        ALTER TABLE supplier_items RENAME COLUMN wholesale_price TO price_opt;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'supplier_items' AND column_name = 'retail_price'
    ) THEN
        ALTER TABLE supplier_items RENAME COLUMN retail_price TO price_rrc;
    END IF;
END $$;
```

**Fields (Validation):**

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `price_opt` | DECIMAL(12,2) | Yes | Wholesale/optimal price in BYN |
| `price_rrc` | DECIMAL(12,2) | Yes | Retail/recommended price in BYN |

---

### 3. Parsing Logs Enhancement

**Purpose:** Add semantic ETL-specific error tracking.

```sql
-- Migration: 009_enhance_parsing_logs.sql

ALTER TABLE parsing_logs
ADD COLUMN chunk_id INT,
ADD COLUMN row_number INT,
ADD COLUMN error_type VARCHAR(50),  -- 'validation', 'timeout', 'parsing', 'llm_error'
ADD COLUMN extraction_phase VARCHAR(50);  -- 'sheet_selection', 'markdown_conversion', 'llm_extraction', 'category_matching'

-- Index for querying errors by phase
CREATE INDEX idx_parsing_logs_error_type ON parsing_logs(error_type);
CREATE INDEX idx_parsing_logs_phase ON parsing_logs(extraction_phase);
```

**Fields (New):**

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `chunk_id` | INT | Yes | Chunk identifier for sliding window |
| `row_number` | INT | Yes | Row number in source file |
| `error_type` | VARCHAR(50) | Yes | Error classification |
| `extraction_phase` | VARCHAR(50) | Yes | Phase where error occurred |

---

## Python Data Models (Pydantic)

### 1. ExtractedProduct

**File:** `services/ml-analyze/src/schemas/extraction.py`

**Purpose:** Represents a single product extracted from supplier file via LLM.

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from decimal import Decimal

class ExtractedProduct(BaseModel):
    """Product extracted from supplier file via LLM."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Product name (required)"
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Product specifications or description"
    )
    price_opt: Optional[Decimal] = Field(
        None,
        ge=0,
        decimal_places=2,
        description="Wholesale/optimal price in BYN"
    )
    price_rrc: Decimal = Field(
        ...,
        ge=0,
        decimal_places=2,
        description="Retail/recommended price in BYN (required)"
    )
    category_path: list[str] = Field(
        default_factory=list,
        description="Category hierarchy, e.g., ['Electronics', 'Laptops']"
    )
    raw_data: dict = Field(
        default_factory=dict,
        description="Original row data for debugging"
    )

    @field_validator('name')
    @classmethod
    def normalize_name(cls, v: str) -> str:
        """Normalize product name: strip whitespace, remove extra spaces."""
        return ' '.join(v.strip().split())

    @field_validator('category_path')
    @classmethod
    def normalize_categories(cls, v: list[str]) -> list[str]:
        """Normalize category names: strip whitespace, filter empty."""
        return [c.strip() for c in v if c.strip()]

    @field_validator('description')
    @classmethod
    def normalize_description(cls, v: Optional[str]) -> Optional[str]:
        """Normalize description: strip whitespace, return None if empty."""
        if v:
            v = v.strip()
            return v if v else None
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "name": self.name,
            "description": self.description,
            "price_opt": float(self.price_opt) if self.price_opt else None,
            "price_rrc": float(self.price_rrc),
            "category_path": self.category_path,
            "raw_data": self.raw_data,
        }
```

**Validation Rules:**

- `name`: Required, 1-500 chars, normalized (strip, collapse spaces)
- `price_rrc`: Required, non-negative, 2 decimal places
- `price_opt`: Optional, non-negative if present
- `category_path`: Array of strings, normalized (strip, filter empty)
- `description`: Optional, normalized (strip, None if empty)

---

### 2. ExtractionResult

**File:** `services/ml-analyze/src/schemas/extraction.py`

**Purpose:** Aggregated result of processing one sheet/file.

```python
from pydantic import BaseModel, Field

class ExtractionResult(BaseModel):
    """Result of file/sheet extraction process."""

    products: list[ExtractedProduct] = Field(
        default_factory=list,
        description="Successfully extracted products"
    )
    sheet_name: str = Field(
        ...,
        description="Name of the processed sheet"
    )
    total_rows: int = Field(
        ...,
        ge=0,
        description="Total rows processed (excluding header)"
    )
    successful_extractions: int = Field(
        ...,
        ge=0,
        description="Number of products extracted successfully"
    )
    failed_extractions: int = Field(
        ...,
        ge=0,
        description="Number of rows that failed extraction"
    )
    duplicates_removed: int = Field(
        default=0,
        ge=0,
        description="Number of duplicate products removed"
    )
    extraction_errors: list[dict] = Field(
        default_factory=list,
        description="List of errors with row numbers and messages"
    )

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_rows == 0:
            return 0.0
        return (self.successful_extractions / self.total_rows) * 100

    @property
    def status(self) -> str:
        """Determine job status based on success rate."""
        if self.success_rate == 100:
            return "success"
        elif self.success_rate >= 80:
            return "completed_with_errors"
        else:
            return "failed"
```

**Computed Properties:**

- `success_rate`: Percentage of successful extractions
- `status`: Derived from success rate (success | completed_with_errors | failed)

---

### 3. CategoryMatchResult

**File:** `services/ml-analyze/src/schemas/category.py`

**Purpose:** Result of fuzzy matching a category name against existing categories.

```python
from pydantic import BaseModel, Field
from typing import Optional

class CategoryMatchResult(BaseModel):
    """Result of category fuzzy matching."""

    extracted_name: str = Field(
        ...,
        description="Original category name from LLM extraction"
    )
    matched_id: Optional[int] = Field(
        None,
        description="ID of matched existing category (if found)"
    )
    matched_name: Optional[str] = Field(
        None,
        description="Name of matched existing category (if found)"
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Fuzzy match similarity score (0-100)"
    )
    action: str = Field(
        ...,
        description="Action taken: 'matched' | 'created' | 'skipped'"
    )
    needs_review: bool = Field(
        default=False,
        description="Flag indicating if category needs admin review"
    )
    parent_id: Optional[int] = Field(
        None,
        description="Parent category ID in hierarchy"
    )

    @property
    def is_new_category(self) -> bool:
        """Check if a new category was created."""
        return self.action == "created"

    @property
    def is_confident_match(self) -> bool:
        """Check if match confidence is high (>90%)."""
        return self.similarity_score > 90.0
```

---

### 4. MLAnalyzeRequest / Response

**File:** `services/python-ingestion/src/schemas/ml_client.py`

**Purpose:** HTTP contract between python-ingestion and ml-analyze.

```python
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional

class MLAnalyzeRequest(BaseModel):
    """Request to ml-analyze service for file analysis."""

    file_path: str = Field(
        ...,
        description="Absolute path to file in shared volume"
    )
    supplier_id: int = Field(
        ...,
        gt=0,
        description="Supplier ID from database"
    )
    job_id: str = Field(
        ...,
        min_length=1,
        description="Unique job identifier for tracking"
    )

class MLAnalyzeResponse(BaseModel):
    """Response from ml-analyze service."""

    job_id: str = Field(..., description="Job identifier")
    status: str = Field(
        ...,
        description="Job status: 'queued' | 'processing' | 'complete' | 'failed'"
    )
    progress_percent: int = Field(
        ...,
        ge=0,
        le=100,
        description="Progress percentage (0-100)"
    )
    total_rows: Optional[int] = Field(None, description="Total rows processed")
    successful_extractions: Optional[int] = Field(None, description="Successful products")
    failed_extractions: Optional[int] = Field(None, description="Failed products")
    duplicates_removed: Optional[int] = Field(None, description="Duplicates removed")
    message: Optional[str] = Field(None, description="Status message or error")
    current_phase: Optional[str] = Field(
        None,
        description="Current processing phase: 'sheet_selection' | 'markdown_conversion' | 'llm_extraction' | 'category_matching'"
    )
```

---

## TypeScript Data Models

### 1. JobPhase Type

**File:** `services/bun-api/src/types/job.types.ts`

**Purpose:** Extended job phases for semantic ETL.

```typescript
export type JobPhase =
  | 'pending'
  | 'downloading'
  | 'analyzing'          // New: ml-analyze is processing file
  | 'extracting'          // New: LLM extraction phase
  | 'normalizing'         // New: Category matching phase
  | 'complete'
  | 'failed'
  | 'completed_with_errors';  // New: Partial success

export interface JobStatus {
  job_id: string;
  supplier_id: number;
  phase: JobPhase;
  progress_percent: number;
  total_rows?: number;
  processed_rows?: number;
  successful_extractions?: number;
  failed_extractions?: number;
  duplicates_removed?: number;
  error_message?: string;
  created_at: Date;
  updated_at: Date;
}

export interface JobPhaseMetadata {
  phase: JobPhase;
  display_name: string;
  color: 'blue' | 'yellow' | 'green' | 'red' | 'gray';
  icon: string;  // Icon name from Radix UI
  description: string;
}

export const JOB_PHASE_CONFIG: Record<JobPhase, JobPhaseMetadata> = {
  pending: {
    phase: 'pending',
    display_name: 'Pending',
    color: 'gray',
    icon: 'clock',
    description: 'Job is queued for processing'
  },
  downloading: {
    phase: 'downloading',
    display_name: 'Downloading',
    color: 'blue',
    icon: 'download',
    description: 'Downloading file from source'
  },
  analyzing: {
    phase: 'analyzing',
    display_name: 'Analyzing Structure',
    color: 'blue',
    icon: 'magnifying-glass',
    description: 'Identifying sheets and data structure'
  },
  extracting: {
    phase: 'extracting',
    display_name: 'Extracting Products',
    color: 'blue',
    icon: 'archive',
    description: 'Extracting product data with LLM'
  },
  normalizing: {
    phase: 'normalizing',
    display_name: 'Matching Categories',
    color: 'blue',
    icon: 'component-1',
    description: 'Normalizing categories and deduplicating'
  },
  complete: {
    phase: 'complete',
    display_name: 'Complete',
    color: 'green',
    icon: 'check-circle',
    description: 'Job completed successfully'
  },
  completed_with_errors: {
    phase: 'completed_with_errors',
    display_name: 'Completed with Errors',
    color: 'yellow',
    icon: 'exclamation-triangle',
    description: 'Job completed with some failures'
  },
  failed: {
    phase: 'failed',
    display_name: 'Failed',
    color: 'red',
    icon: 'cross-circle',
    description: 'Job failed to complete'
  }
};
```

---

### 2. CategoryReviewItem

**File:** `services/bun-api/src/types/category.types.ts`

**Purpose:** Category entity for admin review workflow.

```typescript
export interface CategoryReviewItem {
  id: number;
  name: string;
  parent_id: number | null;
  parent_name?: string;  // Joined from parent category
  needs_review: boolean;
  is_active: boolean;
  supplier_id: number | null;
  supplier_name?: string;  // Joined from suppliers table
  product_count: number;  // Count of products in this category
  created_at: Date;
  updated_at: Date;
}

export interface CategoryApprovalRequest {
  category_id: number;
  action: 'approve' | 'merge';
  merge_with_id?: number;  // Required if action = 'merge'
}

export interface CategoryApprovalResponse {
  success: boolean;
  message: string;
  affected_products?: number;  // Number of products updated
}

export interface CategoryHierarchyNode {
  id: number;
  name: string;
  parent_id: number | null;
  children: CategoryHierarchyNode[];
  needs_review: boolean;
  product_count: number;
}
```

---

### 3. ExtractedProductDTO

**File:** `services/frontend/src/types/product.types.ts`

**Purpose:** Frontend representation of extracted product.

```typescript
export interface ExtractedProductDTO {
  name: string;
  description?: string;
  price_opt?: number;
  price_rrc: number;
  category_path: string[];
  supplier_id: number;
  created_at: string;  // ISO 8601 timestamp
}

export interface ExtractionSummary {
  total_rows: number;
  successful_extractions: number;
  failed_extractions: number;
  duplicates_removed: number;
  success_rate: number;  // Percentage (0-100)
  status: 'success' | 'completed_with_errors' | 'failed';
}
```

---

## Entity Relationships

### Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          suppliers                              │
│  id, name, source_type, config, use_semantic_etl               │
└───────┬─────────────────────────────────────────────────────────┘
        │ 1:N
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                       supplier_items                            │
│  id, supplier_id, name, price_opt, price_rrc, characteristics  │
└───────┬─────────────────────────────────────────────────────────┘
        │ N:1
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                         categories                              │
│  id, name, parent_id (FK self), needs_review, is_active        │
│  supplier_id (FK suppliers), created_at, updated_at            │
└───────┬─────────────────────────────────────────────────────────┘
        │ self-reference
        │ parent_id → categories.id
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Category Hierarchy                          │
│  Root                                                           │
│    ├─ Electronics                                               │
│    │    ├─ Laptops                                              │
│    │    └─ Accessories                                          │
│    └─ Furniture                                                 │
│         └─ Office                                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        parsing_logs                             │
│  id, supplier_id, job_id, chunk_id, row_number, error_type,    │
│  error_message, extraction_phase, raw_data, created_at         │
└─────────────────────────────────────────────────────────────────┘
```

### Relationships

1. **suppliers → supplier_items:** One-to-Many
   - One supplier provides many products
   - FK: `supplier_items.supplier_id → suppliers.id`

2. **categories (self-reference):** Tree Structure
   - One category can have one parent and many children
   - FK: `categories.parent_id → categories.id`
   - Root categories: `parent_id = NULL`

3. **categories → suppliers:** Many-to-One (tracking)
   - Categories track which supplier introduced them
   - FK: `categories.supplier_id → suppliers.id`

4. **supplier_items → categories:** Many-to-One
   - Products belong to one category
   - FK: `supplier_items.category_id → categories.id` (existing)

5. **suppliers → parsing_logs:** One-to-Many
   - Logs track errors per supplier
   - FK: `parsing_logs.supplier_id → suppliers.id`

---

## Data Flow

### Ingestion Pipeline

```
[Excel File] → [MarkdownConverter] → [Markdown String]
                                            ↓
                                [SmartParserService]
                                            ↓
                      [LLM Extraction] → [ExtractedProduct[]]
                                            ↓
                        [CategoryNormalizer] → [CategoryMatchResult[]]
                                            ↓
                          [DeduplicationService] → [Unique Products]
                                            ↓
                            [Database Insert] → [supplier_items]
                                            ↓
                              [Job Status Update] → [Redis]
```

### Category Matching Flow

```
[LLM returns category_path: ["Electronics", "Laptops"]]
                ↓
      [CategoryNormalizer.process_hierarchy()]
                ↓
┌─────────────────────────────────────────────────────────┐
│ Level 1: "Electronics"                                  │
│   - Fuzzy match against categories WHERE parent_id IS NULL│
│   - Match found: "Electronics" (95% similarity)         │
│   - Use existing category (id=5)                        │
└─────────────────────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────────────────────┐
│ Level 2: "Laptops"                                      │
│   - Fuzzy match against categories WHERE parent_id = 5 │
│   - No match found (best: "Notebooks" 70%)              │
│   - Create new category:                                │
│       INSERT INTO categories (name, parent_id,          │
│                               needs_review, supplier_id)│
│       VALUES ('Laptops', 5, true, 123)                  │
│   - Return new category (id=42)                         │
└─────────────────────────────────────────────────────────┘
                ↓
          [Link product to category_id=42]
```

---

## Migration Checklist

### Phase 1: Database

- [ ] Create migration `009_add_category_hierarchy.sql`
- [ ] Create migration `009_validate_supplier_items.sql`
- [ ] Create migration `009_enhance_parsing_logs.sql`
- [ ] Run migrations in dev environment
- [ ] Verify indexes created correctly
- [ ] Test category self-reference constraint

### Phase 2: Python Models

- [ ] Create `services/ml-analyze/src/schemas/extraction.py`
- [ ] Create `services/ml-analyze/src/schemas/category.py`
- [ ] Update `services/python-ingestion/src/schemas/ml_client.py`
- [ ] Write unit tests for Pydantic validators
- [ ] Generate JSON schemas for API documentation

### Phase 3: TypeScript Models

- [ ] Create `services/bun-api/src/types/job.types.ts`
- [ ] Create `services/bun-api/src/types/category.types.ts`
- [ ] Update `services/frontend/src/types/product.types.ts`
- [ ] Generate OpenAPI spec from types
- [ ] Verify TypeScript strict mode compliance

### Phase 4: Validation

- [ ] Test category hierarchy creation (3 levels deep)
- [ ] Test circular reference prevention
- [ ] Test fuzzy matching with known examples
- [ ] Test extraction with missing fields
- [ ] Test partial extraction handling (80% threshold)

---

## Testing Data

### Sample Categories (Seed Data)

```sql
-- Insert test category hierarchy
INSERT INTO categories (name, parent_id, needs_review, is_active) VALUES
('Electronics', NULL, false, true),
('Laptops', 1, false, true),
('Gaming Laptops', 2, false, true),
('Business Laptops', 2, false, true),
('Accessories', 1, false, true),
('Furniture', NULL, false, true),
('Office Furniture', 6, false, true);
```

### Sample Extracted Products (Test Data)

```python
test_products = [
    ExtractedProduct(
        name="Dell XPS 15",
        description="15.6\" laptop, Intel i7, 16GB RAM",
        price_opt=1200.00,
        price_rrc=1500.00,
        category_path=["Electronics", "Laptops", "Business Laptops"],
        raw_data={"row": 5, "sheet": "Products"}
    ),
    ExtractedProduct(
        name="Razer Blade 17",
        description="Gaming laptop, RTX 4080, 32GB RAM",
        price_opt=2500.00,
        price_rrc=3000.00,
        category_path=["Electronics", "Laptops", "Gaming Laptops"],
        raw_data={"row": 12, "sheet": "Products"}
    ),
]
```

---

## API Contract Reference

See `/contracts/ml-analyze-api.json` for full OpenAPI specification.

---

**Next Steps:**

Proceed to generate API contracts and quickstart guide.
