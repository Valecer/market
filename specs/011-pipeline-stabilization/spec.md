# Feature Specification: Data Pipeline Stabilization

**Version:** 1.0.0

**Last Updated:** 2025-12-09

**Status:** Draft

---

## Constitutional Alignment

**Relevant Principles:**

- **Single Responsibility:** Each service maintains its core responsibility: python-ingestion for orchestration, ml-analyze for intelligence, bun-api for client interface. Idempotency logic is contained within the ingestion service.
- **Separation of Concerns:** Hashing and deduplication logic remains separate from ML extraction. Category hierarchy validation is decoupled from category creation.
- **Strong Typing:** All new fields (source_row_hash, category_level) use explicit type definitions in Pydantic schemas and SQLAlchemy models.
- **KISS:** MD5 hashing for row identification (simple, deterministic). Three-level category tree (clear, bounded). Threshold-based matching (explicit decision points).
- **DRY:** Reuses existing variant_detection_service.py and category_normalizer.py instead of reimplementing grouping logic.

**Compliance Statement:**

This specification adheres to all constitutional principles. Any deviations are documented in the Exceptions section below.

---

## Overview

### Purpose

Eliminate duplicate product creation when re-importing supplier files, enforce a consistent 3-level category structure (Top → Sub-category → Brand), and automatically organize similar products into variant groups during ingestion.

### Scope

**In Scope:**

- Hash-based deduplication of supplier items using raw row content fingerprints
- Reuse of previously extracted data when source rows are unchanged
- Automatic product creation for low-confidence matches (<90%) using ML-cleaned names
- Elimination of the "Unmatched Items" queue for initial ingestion
- Strict 3-level category hierarchy enforcement (Top Category → Sub-category → Brand as Category)
- Integration of variant detection into the ingestion pipeline immediately after product creation
- Detection and flagging of potential duplicate products created by the new auto-creation logic

**Out of Scope:**

- Retroactive fixing of duplicate products created before this feature (manual cleanup required)
- Multi-brand category nodes (Brand remains a single category under Sub-category)
- Cross-supplier variant grouping (variants are detected within a single supplier's catalog)
- Manual merge workflows for flagged duplicates (to be addressed in a future feature)

---

## User Scenarios & Testing

### Scenario 1: Re-importing Unchanged Supplier File

**Actor:** Procurement Manager

**Context:** A supplier sends weekly price updates via the same Excel file structure. Most rows are unchanged, only prices vary for some products.

**Flow:**

1. Manager triggers a sync for Supplier A (Google Sheets URL)
2. System downloads the file and computes row hashes for all data rows
3. For rows with matching hashes (existing source_row_hash in database):
   - System reuses the existing supplier_item record (SKU, name, category)
   - Updates only time-variant fields (current_price, last_ingested_at)
   - Skips ML extraction entirely for these rows
4. For rows with new/changed hashes:
   - System calls ML service for extraction
   - Stores new supplier_item with new hash
5. Manager sees ingestion complete in ~30 seconds instead of ~5 minutes
6. No duplicate products are created

**Acceptance Criteria:**

- Re-importing a file with 80% unchanged rows processes in <40% of the time compared to full re-extraction
- Unchanged rows preserve their original product_id linkages
- Changed rows (e.g., "Battery 48V" renamed to "Battery 48V Pro") trigger re-extraction and new matching

---

### Scenario 2: Auto-Creating Products for New Items

**Actor:** Sales Manager

**Context:** A new supplier provides a catalog with 200 unique items. None match existing products above 90% confidence.

**Flow:**

1. Sales manager imports the new supplier's Excel file
2. ML service extracts and cleans product names (e.g., "Btry 48v 20ah shtenli" → "Battery 48V 20Ah Shtenli")
3. Matching service evaluates each item:
   - Match confidence: 65% against "Battery 48V 15Ah Yamaha" (similar but different brand/capacity)
   - Since <90%, system automatically creates a new Product using the cleaned name "Battery 48V 20Ah Shtenli"
   - Links supplier_item to newly created product_id
   - Sets match_status = 'auto_created'
4. After all 200 items are processed, duplicate detection runs:
   - Finds 5 pairs of likely duplicates based on high name similarity (e.g., "LED Light 50W" vs. "LED Lamp 50W")
   - Flags these for manual review in a "Potential Duplicates" queue
5. Sales manager reviews only 5 potential duplicates instead of 200 unmatched items
6. 195 items are immediately available in the catalog for clients

**Acceptance Criteria:**

- Items with match confidence <90% result in new Product creation within the same ingestion job
- Newly created Products use ML-cleaned names (not raw supplier names)
- The "Unmatched Items" queue remains empty after ingestion
- Duplicate detection identifies products created in the same batch with >85% name similarity
- Flagged duplicates are sent to a separate "Potential Duplicates" review queue

---

### Scenario 3: Enforcing 3-Level Category Hierarchy

**Actor:** Product Catalog Administrator

**Context:** Supplier extracts include messy category data. Some items have "Electric Transport > Motorcycles > Shtenli > 48V Models" (4 levels), others have "Tools" (1 level).

**Flow:**

1. ML extraction identifies categories from supplier data
2. Category normalizer receives: ["Electric Transport", "Motorcycles", "Shtenli", "48V Models"]
3. System applies hierarchy rules:
   - Top Category: "Electric Transport" (create/find)
   - Sub-category: "Motorcycles" (create/find as child of Top)
   - Brand: "Shtenli" (create/find as child of Sub-category)
   - Excess level "48V Models" is ignored (logged as a warning)
4. Product is assigned to category_id = "Shtenli"
5. For flat categories like "Tools" (only 1 level):
   - System allows temporary Level 1 assignment: Product.category_id = "Tools" (level 1)
   - Item is flagged in parsing_logs with warning_type = 'incomplete_category_hierarchy'
   - Admin review queue shows these items for category completion
6. Admin reviews category tree and sees consistent 3-level structure for completed items, pending items in review queue
7. Client-facing catalog displays: Electric Transport → Motorcycles → Shtenli

**Acceptance Criteria:**

- All products are assigned to a category at exactly level 3 (has parent at level 2, grandparent at level 1)
- Excess category levels beyond 3 are logged but do not block ingestion
- Category tree queries return a maximum depth of 3
- Frontend category breadcrumbs always show exactly 3 levels (or padding for incomplete hierarchies)

---

### Scenario 4: Automatic Variant Grouping

**Actor:** Client (Catalog Viewer)

**Context:** A supplier lists "Battery 48V 20Ah" and "Battery 48V 30Ah" as separate items. These should be presented as a single product with selectable variants.

**Flow:**

1. During ingestion, both items have <90% match confidence against existing products
2. System auto-creates two Products:
   - Product A: "Battery 48V 20Ah"
   - Product B: "Battery 48V 30Ah"
3. Variant detection runs immediately after creation:
   - Detects 95% name similarity (base name: "Battery")
   - Extracts variant attributes: {capacity: "20Ah"} vs. {capacity: "30Ah"}
   - Validates price ratio: 30Ah is 1.4x price of 20Ah (within 2.0x threshold)
4. System groups into a variant set:
   - Updates Product A: has_variants=true, variant_schema=[{key: "capacity"}]
   - Creates product_variants records:
     - Variant 1: variant_key="20Ah", variant_attributes={capacity: "20Ah"}
     - Variant 2: variant_key="30Ah", variant_attributes={capacity: "30Ah"}
5. Client views catalog and sees a single product "Battery 48V" with a dropdown: [20Ah | 30Ah]
6. Selecting "30Ah" updates price and supplier availability

**Acceptance Criteria:**

- Products created in the same batch with >85% name similarity and differing variant attributes are grouped within 10 seconds of creation
- Variant schema includes all detected attribute types (voltage, capacity, storage, size)
- Products with price ratios >2.0x are NOT grouped (flagged as potential errors)
- Grouped variants share the same base category_id

---

## Functional Requirements

### FR-1: Source Row Hash Storage and Lookup

**Priority:** Critical

**Description:** For every row extracted from a supplier file (Excel/CSV/PDF/Google Sheets), compute a unique fingerprint based on the raw row content and supplier ID. Store this hash with the supplier_item record. On subsequent ingestions, check if a hash already exists before calling the ML service.

**Acceptance Criteria:**

- [ ] AC-1: A source_row_hash field exists in the supplier_items table (VARCHAR(32) for MD5 hex digest)
- [ ] AC-2: Hash is computed from concatenated string: `{supplier_id}|{raw_row_data}` where raw_row_data is a normalized representation of all cell values
- [ ] AC-3: Before calling ml-analyze, the ingestion service queries: `SELECT id, product_id, name, category_id FROM supplier_items WHERE source_row_hash = ?`
- [ ] AC-4: If a matching hash is found AND the row content is identical (double-check via JSONB comparison), reuse the existing record by updating only: current_price, price_opt, price_rrc, last_ingested_at
- [ ] AC-5: If hash matches but content differs (hash collision, <0.01% probability), proceed with full re-extraction and update the record
- [ ] AC-6: Metrics are logged: total_rows, hash_hits, hash_misses, ml_extractions_saved

**Dependencies:** None (extends existing supplier_items schema)

---

### FR-2: Auto-Creation of Products for Low-Confidence Matches

**Priority:** Critical

**Description:** When a supplier item is matched against existing products and the highest confidence score is below 90%, the system must automatically create a new Product using the ML-cleaned name from the extraction phase. The new Product is immediately linked to the supplier_item, eliminating the need for manual matching.

**Acceptance Criteria:**

- [ ] AC-1: Matching service evaluates all supplier items after extraction
- [ ] AC-2: For items where max(match_scores) < 90%, a new Product is created with:
  - name = ML-cleaned name from extraction
  - category_id = normalized category from extraction
  - status = 'active'
  - internal_sku = auto-generated unique identifier (e.g., `AUTO-{UUID}`)
- [ ] AC-3: The supplier_item is updated: product_id = new_product.id, match_status = 'auto_created', match_score = NULL
- [ ] AC-4: The "Unmatched Items" queue (match_review_queue table) receives ZERO entries from initial ingestion jobs
- [ ] AC-5: Audit log records the auto-creation event with: supplier_item_id, new_product_id, ml_cleaned_name, timestamp

**Dependencies:**
- FR-1 (to avoid creating duplicates from re-imported rows)
- FR-6 (to detect duplicates created by this auto-creation logic)

---

### FR-3: 3-Level Category Hierarchy Enforcement

**Priority:** High

**Description:** Enforce a strict 3-level category tree structure across all products: Level 1 (Top Category, e.g., "Electric Transport"), Level 2 (Sub-category, e.g., "Motorcycles"), Level 3 (Brand, e.g., "Shtenli"). All products must be assigned to a Level 3 category. The "Brand" extracted from supplier data becomes a Category node rather than a separate product field.

**Acceptance Criteria:**

- [ ] AC-1: A category_level field is added to the categories table (INTEGER, values: 1, 2, or 3)
- [ ] AC-2: Category creation logic computes level based on parent_id chain: root categories (parent_id = NULL) are level 1, their children are level 2, their grandchildren are level 3
- [ ] AC-3: Database constraint prevents creation of level 4+ categories (CHECK constraint or application-level validation)
- [ ] AC-4: When ML extraction returns category path ["Top", "Sub", "Brand"], system creates/finds categories in order:
  - Level 1: "Top" (parent_id = NULL, category_level = 1)
  - Level 2: "Sub" (parent_id = Top.id, category_level = 2)
  - Level 3: "Brand" (parent_id = Sub.id, category_level = 3)
- [ ] AC-5: Product.category_id points to a Level 3 category when available; temporarily allows Level 1 or Level 2 categories when supplier data is incomplete
- [ ] AC-6: Products with incomplete category hierarchy (Level 1 or Level 2 assignments) are flagged in parsing_logs with warning_type = 'incomplete_category_hierarchy'
- [ ] AC-7: Admin review queue includes items with incomplete category hierarchies for manual completion
- [ ] AC-8: Frontend breadcrumb navigation displays available levels (1, 2, or 3) and pads with "Uncategorized" placeholders as needed
- [ ] AC-9: Excess category levels beyond 3 (from supplier data) are logged to parsing_logs with error_type = 'excess_category_levels' and do not block ingestion

**Dependencies:** FR-2 (auto-created products must be assigned to valid categories; 3-level constraint is aspirational, not blocking)

---

### FR-4: Integrated Variant Detection in Ingestion Pipeline

**Priority:** High

**Description:** After auto-creating new Products (FR-2), immediately invoke the existing variant_detection_service.py to group products with similar base names and differing variant attributes (voltage, capacity, storage, size) into variant sets. This ensures clients see a unified product presentation with selectable options rather than duplicate-looking listings.

**Acceptance Criteria:**

- [ ] AC-1: Variant detection runs as the final phase of each ingestion job, after all supplier items are processed
- [ ] AC-2: Detection scope is limited to: (a) Products auto-created in the current job, AND (b) Products already existing in the same category_id (to catch variants across batches)
- [ ] AC-3: Grouping logic matches the existing variant_detection_service.py algorithm:
  - Name similarity ≥85% (RapidFuzz WRatio)
  - At least one differing variant attribute (voltage, capacity, storage, size)
  - Price ratio ≤2.0x (sanity check to avoid grouping unrelated products)
- [ ] AC-4: For each detected variant group:
  - Select one Product as the "parent" (lowest price or first created)
  - Update parent: has_variants = true, variant_schema = [{key: "voltage"}, ...] (list of varying attributes)
  - Create product_variants records for each variant (including the parent itself)
- [ ] AC-5: Metrics are logged: total_products_scanned, variant_groups_created, products_grouped, ungrouped_singletons

**Dependencies:** FR-2 (requires auto-created products to exist)

---

### FR-5: Potential Duplicate Detection After Auto-Creation

**Priority:** Medium

**Description:** Since FR-2 automatically creates new Products for low-confidence matches, there is a risk of creating duplicates (e.g., "LED Light 50W" and "LED Lamp 50W" are semantically identical but match at 88% confidence). The system must detect such potential duplicates and flag them for manual review AFTER creation, replacing the old "Unmatched Items" queue with a "Potential Duplicates" queue.

**Acceptance Criteria:**

- [ ] AC-1: A new table `potential_duplicates` exists with columns: id, product_id_1, product_id_2, similarity_score, detection_reason, status (pending|merged|dismissed), created_at
- [ ] AC-2: After variant detection (FR-4), the system scans all auto-created Products from the current job
- [ ] AC-3: For each product, perform pairwise comparison against:
  - Other products in the same category_id
  - Products created in the current job
- [ ] AC-4: If two products meet ALL conditions:
  - Name similarity ≥85% AND <90% (below auto-match threshold but suspiciously similar)
  - Same category_id
  - NOT already grouped as variants (different has_variants or variant_schema values)
  - Price difference <20% (suggesting they are the same product, not variants)
- [ ] AC-5: Then insert a record into potential_duplicates with: product_id_1, product_id_2, similarity_score, detection_reason = 'auto_creation_similarity'
- [ ] AC-6: Admin UI displays the "Potential Duplicates" queue with side-by-side product comparison (name, category, price, linked supplier items)
- [ ] AC-7: Admin actions: Merge (merge supplier_items into one product, archive the other) or Dismiss (mark as not duplicates)

**Dependencies:** FR-2, FR-4

---

### FR-6: Idempotent Re-Ingestion with Price Updates

**Priority:** High

**Description:** When a supplier file is re-imported and a row's hash matches an existing record (FR-1), the system must intelligently update only time-variant fields (prices) while preserving structural fields (name, category, product linkage). This ensures price feeds can be refreshed multiple times per day without data churn.

**Acceptance Criteria:**

- [ ] AC-1: For hash-matched rows, the system performs a partial update: `UPDATE supplier_items SET current_price = ?, price_opt = ?, price_rrc = ?, last_ingested_at = NOW() WHERE source_row_hash = ?`
- [ ] AC-2: The following fields are NEVER updated on hash match: name, category_id, product_id, match_status, characteristics (these require re-extraction if changed)
- [ ] AC-3: If a hash-matched row has changed content (detected via JSONB comparison of characteristics), the hash match is ignored and full re-extraction occurs
- [ ] AC-4: Metrics distinguish between: pure_hash_hits (price-only updates), hash_collisions (content changed), full_reextractions
- [ ] AC-5: Ingestion logs include: `rows_processed: 500, hash_hits: 420, ml_extractions: 80, products_created: 12`

**Dependencies:** FR-1

---

## Technical Requirements

### TR-1: Service Architecture

**Bun Service Responsibilities:**

- API endpoint(s):
  - `POST /api/v1/admin/sync` (existing, no changes)
  - `GET /api/v1/admin/duplicates` (new endpoint for potential duplicates queue)
  - `PATCH /api/v1/admin/duplicates/:id/merge` (merge duplicate products)
  - `PATCH /api/v1/admin/duplicates/:id/dismiss` (dismiss false positive)
- Request validation using TypeBox
- Enqueue jobs to Redis
- Return response to client

**Python Service Responsibilities (python-ingestion):**

- Consume Redis queue: `supplier_sync_queue`
- Compute source row hashes before calling ml-analyze
- Query database for existing hashes
- Trigger ML service for non-cached rows
- Update price-only fields for cached rows
- Coordinate with ml-analyze via HTTP polling (existing pattern)

**Python Service Responsibilities (ml-analyze):**

- Process extraction requests (existing)
- Perform matching with new <90% auto-creation logic
- Create Products automatically for low-confidence matches
- Invoke variant_detection_service.py after batch creation
- Detect potential duplicates and populate potential_duplicates table
- Write results to PostgreSQL

**Communication Contract:**

```typescript
// Existing contract, no changes
interface SyncJobMessage {
  jobId: string;
  supplierId: string;
  sourceUrl: string;
  useSemanticETL: boolean;
}
```

```python
# Existing contract, no changes
class SyncJobMessage(BaseModel):
    job_id: str
    supplier_id: str
    source_url: str
    use_semantic_etl: bool
```

---

### TR-2: Database Schema

**Tables:**

**Modified Table: supplier_items**

```sql
ALTER TABLE supplier_items
ADD COLUMN source_row_hash VARCHAR(32);  -- MD5 hex digest

CREATE INDEX idx_supplier_items_hash ON supplier_items(source_row_hash);
```

**Modified Table: categories**

```sql
ALTER TABLE categories
ADD COLUMN category_level INTEGER;

-- Populate existing records via migration script:
-- Level = 1 if parent_id IS NULL
-- Level = 2 if parent.parent_id IS NULL
-- Level = 3 otherwise

ALTER TABLE categories
ADD CONSTRAINT chk_category_level CHECK (category_level IN (1, 2, 3));
```

**New Table: potential_duplicates**

```sql
CREATE TABLE potential_duplicates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id_1 UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    product_id_2 UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    similarity_score NUMERIC(5, 2) NOT NULL,  -- 0-100
    detection_reason VARCHAR(100) NOT NULL,  -- 'auto_creation_similarity', 'manual_report'
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- 'pending', 'merged', 'dismissed'
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_different_products CHECK (product_id_1 != product_id_2),
    CONSTRAINT chk_ordered_ids CHECK (product_id_1 < product_id_2)  -- Prevent (A,B) and (B,A) duplicates
);

CREATE INDEX idx_potential_duplicates_status ON potential_duplicates(status);
```

**Indexes:**

- `idx_supplier_items_hash` - Fast hash lookup for idempotency checks
- `idx_potential_duplicates_status` - Admin queue filtering

**Migrations:**

- Migration file: `011_pipeline_stabilization_schema.py`
- Rollback strategy: Drop added columns and table, restore original constraints

---

### TR-3: API Specification

**Endpoint:** `GET /api/v1/admin/duplicates`

**Request:**

```typescript
interface GetDuplicatesRequest {
  status?: 'pending' | 'merged' | 'dismissed';  // Filter, default: 'pending'
  limit?: number;  // Pagination, default: 50
  offset?: number;
}
```

**Response:**

```typescript
interface GetDuplicatesResponse {
  duplicates: Array<{
    id: string;
    product1: {
      id: string;
      name: string;
      category: string;
      price: number;
      supplierCount: number;  // How many supplier_items linked
    };
    product2: { /* same structure */ };
    similarityScore: number;
    detectionReason: string;
    createdAt: string;
  }>;
  total: number;
}
```

**Status Codes:**

- `200 OK`: Success
- `401 Unauthorized`: Missing/invalid JWT
- `500 Internal Server Error`: Server error

**Authentication:** Required (JWT, internal role)

---

**Endpoint:** `PATCH /api/v1/admin/duplicates/:id/merge`

**Request:**

```typescript
interface MergeDuplicatesRequest {
  keepProductId: string;  // Which product to keep (product_id_1 or product_id_2)
  archiveProductId: string;  // Which product to archive
}
```

**Response:**

```typescript
interface MergeDuplicatesResponse {
  success: boolean;
  mergedProduct: {
    id: string;
    name: string;
    supplierItemCount: number;  // Total after merge
  };
}
```

**Status Codes:**

- `200 OK`: Merge successful
- `400 Bad Request`: Invalid product IDs or constraint violation
- `500 Internal Server Error`: Server error

**Authentication:** Required (JWT, internal role)

---

### TR-4: Frontend Components

**Components:**

- `PotentialDuplicatesTable.tsx`: Admin table showing side-by-side product comparison with Merge/Dismiss actions
- `ProductMergeModal.tsx`: Confirmation dialog for merge action, showing supplier item counts and preview of kept product

**State Management:**

- TanStack Query for duplicate queue fetching and mutations
- Optimistic updates on Merge/Dismiss actions

**Styling:**

- Tailwind CSS v4.1 with CSS-first configuration
- Use `@theme` blocks for customization
- Responsive table with sticky header for long lists

---

### TR-5: Type Safety

**TypeScript Configuration:**

- Strict mode enabled
- No `any` types without explicit `@ts-expect-error` justification

**Python Configuration:**

- Type hints on all functions
- Mypy strict mode compliance
- Pydantic models for all API contracts and database models

---

## Non-Functional Requirements

### NFR-1: Performance

- Hash computation and lookup: <5ms per row (batch queries for 1000 rows: <50ms total)
- Re-ingestion of 80% cached rows: completes in <40% of full extraction time
- Variant detection for 200 products: <10 seconds
- Duplicate detection for 500 products: <30 seconds

### NFR-2: Scalability

- Hash index supports 10M+ supplier_items without degradation
- Duplicate detection uses batch queries with category_id filtering to reduce search space
- Variant detection processes products in batches of 100 to avoid memory bloat

### NFR-3: Security

- Hash algorithm (MD5) is used only for deduplication, NOT for cryptographic security
- Admin duplicate management endpoints require JWT authentication with internal role
- Product merge operations are logged to audit_logs table for accountability

### NFR-4: Observability

- Structured logging (JSON format) for all hash hits/misses, auto-creations, variant groupings
- Metrics exposed: hash_hit_rate, auto_creation_count, variant_groups_created, duplicates_detected
- Error tracking for hash collisions, category hierarchy violations, variant detection failures

### NFR-5: Reliability

- Hash collision handling: if hash matches but content differs, proceed with full extraction (fail-safe)
- Category hierarchy violations: log to parsing_logs with error_type = 'invalid_category_level', do not block ingestion
- Variant detection failures: log error, continue with remaining products (per-product error isolation)
- Duplicate detection failures: log error, ingestion completes successfully (duplicate detection is non-blocking)

---

## Algorithm Specification

Following the KISS principle, we implement the simplest solution first:

**Hash Algorithm: MD5**

- **Complexity:** O(n) where n = row length in bytes
- **Justification:** Fast, deterministic, sufficient for deduplication (collision probability <10^-15 for 1M rows). Not used for security, so MD5 weakness is irrelevant.
- **Normalization:** Row data is sorted by column name and whitespace-trimmed before hashing to avoid false misses from column reordering or trailing spaces.
- **Limitations:** Hash does not detect semantic changes (e.g., "Battery 48V" → "Батарея 48В" would hash differently even if semantically identical).

**Future Evolution: Content-Addressable Hashing with Semantic Normalization**

- **Trigger:** When hash miss rate >20% due to superficial formatting changes
- **Migration Path:** Use LLM to normalize row content before hashing (e.g., translate Cyrillic to Latin, expand abbreviations)

---

**Category Hierarchy Algorithm: Level Computation via Parent Chain Traversal**

- **Complexity:** O(d) where d = depth (max 3)
- **Justification:** Simple recursive/iterative traversal. Depth is bounded, so performance is constant.
- **Validation:** On category creation, check parent.category_level and assign child.category_level = parent.category_level + 1. Reject if result >3.
- **Limitations:** Requires existing categories to have correct category_level values (migration script must backfill).

**Future Evolution: Graph-Based Category System**

- **Trigger:** When business requirements expand beyond 3 levels (e.g., product lines, sub-brands)
- **Migration Path:** Replace category_level with a flexible path materialization (LTREE or JSONB path array)

---

**Duplicate Detection Algorithm: Pairwise Similarity with Category Blocking**

- **Complexity:** O(n^2) within each category, but category blocking reduces n to ~100-500 products per category
- **Justification:** RapidFuzz is highly optimized for string similarity. Category blocking prevents cross-category comparisons.
- **Thresholds:** 85% ≤ similarity <90%, price difference <20%
- **Limitations:** Does not detect duplicates across different categories (e.g., miscategorized products). Does not detect semantic duplicates with <85% string similarity.

**Future Evolution: Embedding-Based Duplicate Detection**

- **Trigger:** When duplicate queue has >100 pending items with high false positive rate
- **Migration Path:** Use product embeddings (already stored for matching) to compute cosine similarity, apply HNSW index for fast approximate nearest neighbor search

---

## Data Models

### Bun Service (TypeScript)

```typescript
// src/types/duplicate.types.ts
export interface PotentialDuplicate {
  id: string;
  product1: ProductSummary;
  product2: ProductSummary;
  similarityScore: number;
  detectionReason: string;
  status: 'pending' | 'merged' | 'dismissed';
  createdAt: Date;
}

export interface ProductSummary {
  id: string;
  name: string;
  category: string;
  price: number;
  supplierCount: number;
}
```

### Python Service (Pydantic)

```python
# services/ml-analyze/src/schemas/duplicate.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class PotentialDuplicateCreate(BaseModel):
    product_id_1: str
    product_id_2: str
    similarity_score: float = Field(..., ge=0, le=100)
    detection_reason: str

class PotentialDuplicateResponse(BaseModel):
    id: str
    product_id_1: str
    product_id_2: str
    similarity_score: float
    status: Literal['pending', 'merged', 'dismissed']
    created_at: datetime
```

### Database (PostgreSQL)

*See TR-2 for schema definitions*

---

## Error Handling

### Bun Service

```typescript
// Standard error response
interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}
```

**Error Codes:**

- `VALIDATION_ERROR`: Invalid request data (e.g., keepProductId not in duplicate pair)
- `DUPLICATE_NOT_FOUND`: Duplicate ID does not exist
- `MERGE_FAILED`: Product merge operation failed (e.g., constraint violation)
- `INTERNAL_ERROR`: Unexpected server error

---

### Python Service

```python
# Hash collision handling
try:
    existing_item = get_item_by_hash(source_row_hash)
    if existing_item and existing_item.row_data != current_row_data:
        logger.warning(f"Hash collision detected: {source_row_hash}")
        # Proceed with full extraction despite hash match
        extraction_result = call_ml_service(current_row_data)
except Exception as e:
    # Log and continue to next row (per-row error isolation)
    logger.error(f"Hash lookup failed for row {row_num}: {e}")
```

```python
# Category level validation
def create_category(name: str, parent_id: str | None) -> Category:
    if parent_id:
        parent = get_category(parent_id)
        level = parent.category_level + 1
        if level > 3:
            raise CategoryHierarchyError(f"Cannot create level {level} category")
    else:
        level = 1
    return Category(name=name, parent_id=parent_id, category_level=level)
```

```python
# Variant detection error isolation
for product in batch:
    try:
        variant_groups = detect_variants([product] + related_products)
        create_variant_records(variant_groups)
    except Exception as e:
        logger.error(f"Variant detection failed for product {product.id}: {e}")
        # Continue with next product
```

---

## Testing Requirements

### Unit Tests

- **Python (python-ingestion):**
  - `test_source_row_hash_computation()` - Verify MD5 hash, normalization (whitespace, column order)
  - `test_hash_match_price_update()` - Ensure only price fields are updated on hash match
  - `test_hash_collision_handling()` - Simulate hash match with different content, verify full re-extraction

- **Python (ml-analyze):**
  - `test_auto_create_product_below_90_confidence()` - Verify product creation with ML-cleaned name
  - `test_category_level_assignment()` - Verify level 1/2/3 computation from parent chain
  - `test_category_level_validation_rejects_level_4()` - Attempt to create level 4 category, expect error
  - `test_variant_detection_integration()` - Mock product batch, verify variant grouping
  - `test_duplicate_detection_within_category()` - Mock products with 88% similarity, verify potential_duplicates insert

- **TypeScript (bun-api):**
  - Test duplicate queue endpoint schema validation
  - Test merge logic: supplier_items reassignment, product archival

### Integration Tests

- **Hash-Based Idempotency Flow:**
  1. Ingest file with 100 rows
  2. Re-ingest same file with 90 unchanged rows, 10 price changes
  3. Verify: 90 hash hits (price updates), 10 hash misses (re-extraction)
  4. Verify: No duplicate products created

- **Auto-Creation & Duplicate Detection Flow:**
  1. Ingest new supplier catalog (200 items, all <90% match confidence)
  2. Verify: 200 new products created, match_status = 'auto_created'
  3. Verify: potential_duplicates table contains flagged pairs (e.g., "LED Light" vs. "LED Lamp")
  4. Admin merges one duplicate pair
  5. Verify: supplier_items from both products now linked to kept product

- **Category Hierarchy Enforcement:**
  1. Create categories: "Electronics" (L1) → "Laptops" (L2) → "Dell" (L3)
  2. Attempt to create "Gaming Series" (L4) under "Dell"
  3. Verify: Error logged, L4 category not created
  4. Ingest product with category path ["Electronics", "Laptops", "Dell"]
  5. Verify: Product.category_id = Dell.id (L3 category)

### E2E Tests

- Full user flow: Upload Excel file → Hash-based dedup → Auto-create products → Variant grouping → Duplicate flagging → Admin review and merge
- Error scenarios: Hash collision handling, category hierarchy violation, variant detection failure (price ratio >2.0x)

**Coverage Target:** ≥80% for all business logic

---

## Deployment

### Environment Variables

```bash
# Python Service (ml-analyze)
USE_SEMANTIC_ETL=true  # Existing
AUTO_CREATE_THRESHOLD=90  # NEW: Confidence threshold for auto-creation (0-100)
VARIANT_DETECTION_ENABLED=true  # NEW: Toggle variant detection
DUPLICATE_DETECTION_ENABLED=true  # NEW: Toggle duplicate detection
DUPLICATE_SIMILARITY_THRESHOLD=85  # NEW: Min similarity for duplicate flagging (0-100)
DUPLICATE_PRICE_DIFF_THRESHOLD=20  # NEW: Max price difference % for duplicates (0-100)

# Python Service (python-ingestion)
HASH_ALGORITHM=md5  # NEW: Algorithm for row hashing (md5, sha256)
HASH_CACHE_ENABLED=true  # NEW: Toggle hash-based deduplication
```

### Docker Configuration

- Services defined in `docker-compose.yml` (no changes)
- Health checks for all services
- Volume mounts for development
- Network isolation for security

### Migration Strategy

1. Run database migrations (add source_row_hash, category_level, potential_duplicates table)
2. Backfill category_level for existing categories (migration script)
3. Deploy ml-analyze with new auto-creation and duplicate detection logic (feature flags OFF)
4. Deploy python-ingestion with hash computation logic (HASH_CACHE_ENABLED=false initially)
5. Test on staging environment with sample supplier files
6. Enable feature flags gradually: HASH_CACHE_ENABLED=true, then AUTO_CREATE_THRESHOLD=90, then VARIANT_DETECTION_ENABLED=true, then DUPLICATE_DETECTION_ENABLED=true
7. Deploy bun-api with new duplicate management endpoints
8. Deploy frontend with duplicate review UI
9. Monitor metrics: hash_hit_rate, auto_creation_count, duplicate_detection_count

---

## Documentation

- [ ] API documentation (OpenAPI/Swagger) - Add new duplicate management endpoints
- [ ] README update with feature overview - Document new AUTO_CREATE_THRESHOLD environment variable
- [ ] Architecture Decision Record (ADR) - Document decision to use MD5 hashing, 3-level category constraint, and auto-creation strategy
- [ ] Inline code documentation for hash normalization logic, category level computation, and duplicate detection algorithm

---

## Rollback Plan

**Trigger Conditions:**

- Hash hit rate <50% (indicates hash computation bug or normalization issue)
- Auto-creation rate >95% (indicates matching service degradation)
- Duplicate queue accumulates >500 pending items in 24 hours (indicates high false positive rate)
- Category hierarchy violations blocking >10% of ingestions

**Rollback Steps:**

1. Disable feature flags: AUTO_CREATE_THRESHOLD=95 (revert to old threshold), HASH_CACHE_ENABLED=false, VARIANT_DETECTION_ENABLED=false, DUPLICATE_DETECTION_ENABLED=false
2. Revert ml-analyze deployment to previous version
3. Revert python-ingestion deployment to previous version
4. Revert bun-api deployment (remove duplicate endpoints)
5. Database rollback: Do NOT drop new columns (source_row_hash, category_level) or potential_duplicates table, as they may contain valuable data. Instead, disable constraints and triggers.
6. Investigate root cause: analyze parsing_logs, hash collision logs, duplicate detection metrics
7. Fix issues and redeploy with feature flags gradually re-enabled

---

## Exceptions & Deviations

**None**

---

## Appendix

### References

- [Phase 9: Semantic ETL Specification](/Users/valecer/work/sites/marketbel/docs/adr/009-semantic-etl.md) - LLM extraction architecture
- [Phase 10: Product Variants ADR](/Users/valecer/work/sites/marketbel/docs/adr/010-product-variants.md) - Variant detection service design
- [Variant Detection Service](/Users/valecer/work/sites/marketbel/services/ml-analyze/src/services/variant_detection_service.py) - Existing implementation to be integrated

### Glossary

- **Source Row Hash:** MD5 fingerprint of raw Excel/CSV row data, used for idempotency
- **Auto-Creation:** Automatic creation of a new Product when match confidence <90%, using ML-cleaned name
- **Potential Duplicate:** A flagged pair of products with high name similarity (≥85%, <90%) and low price difference (<20%), suspected to be the same product
- **Category Level:** Integer value (1, 2, or 3) indicating the depth of a category in the hierarchy tree
- **Variant Schema:** JSONB array defining which attributes vary across a product's variants (e.g., [{key: "voltage"}, {key: "capacity"}])
- **Hash Hit:** A row whose source_row_hash matches an existing database record, allowing ML extraction to be skipped
- **Hash Miss:** A row whose source_row_hash does not match any existing record, requiring full ML extraction

---

**Approval:**

- [ ] Tech Lead: [Name] - [Date]
- [ ] Product: [Name] - [Date]
- [ ] QA: [Name] - [Date]
