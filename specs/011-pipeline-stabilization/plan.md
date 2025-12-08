# Feature Plan: Data Pipeline Stabilization

**Date:** 2025-12-09

**Status:** Draft

**Owner:** Development Team

---

## Overview

This feature stabilizes the data ingestion pipeline by implementing hash-based idempotency, automatic product creation for low-confidence matches, strict 3-level category hierarchy, and integrated variant detection. The goal is to eliminate duplicate products during re-ingestion, reduce manual review workload, and provide a consistent catalog structure.

**Core Problem Solved:** Current pipeline creates duplicate products when re-importing files due to non-deterministic LLM outputs and requires extensive manual matching for new items.

---

## Constitutional Compliance Check

This feature aligns with the following constitutional principles:

- **Single Responsibility Principle (SOLID-S):**
  - `python-ingestion` handles flow control and hash computation (single responsibility: orchestration)
  - `ml-analyze` handles ML logic and product creation (single responsibility: intelligence)
  - `bun-api` handles API/user interface (single responsibility: client interface)
  - New `IdempotencyService` has single responsibility: hash-based deduplication
  - New `AutoCreationService` has single responsibility: product creation for low-confidence matches

- **Open/Closed Principle (SOLID-O):**
  - Existing `variant_detection_service.py` is reused without modification (closed for modification)
  - New post-processing hook `on_batch_complete` extends behavior (open for extension)
  - Category hierarchy validation extends existing `category_normalizer.py` through composition

- **Dependency Inversion Principle (SOLID-D):**
  - Services depend on repository abstractions, not concrete implementations
  - Hash computation depends on `IHashStrategy` interface, allowing MD5 → SHA256 migration
  - Category validation depends on `ICategoryRepository` interface

- **KISS Principle:**
  - MD5 hashing (simple, deterministic, sufficient for deduplication)
  - 3-level category tree (clear constraint, bounded complexity)
  - Threshold-based auto-creation (<90% = create, ≥90% = link)

- **DRY Principle:**
  - Reuses existing `variant_detection_service.py` instead of reimplementing grouping logic
  - Reuses existing `category_normalizer.py` for fuzzy matching
  - Single source of truth for category level: `categories.category_level` column

- **Separation of Concerns:**
  - `python-ingestion`: Computes hashes, checks cache, triggers ML
  - `ml-analyze`: Extraction, matching, auto-creation, variant detection
  - `bun-api`: Admin UI for duplicate review, REST API
  - No direct HTTP calls between services (communication via PostgreSQL shared state)

- **Strong Typing:**
  - Pydantic models for all queue messages and database models
  - TypeScript strict mode for frontend and bun-api
  - Explicit type hints for hash computation functions

**Violations/Exceptions:** None

---

## Goals

- [x] Implement hash-based idempotency to prevent duplicate products on re-ingestion
- [x] Auto-create products for <90% confidence matches using ML-cleaned names
- [x] Enforce 3-level category hierarchy (Top → Sub-category → Brand)
- [x] Integrate variant detection into ingestion pipeline
- [x] Detect and flag potential duplicates created by auto-creation logic
- [x] Reduce re-ingestion time by 60-80% for files with mostly unchanged rows

---

## Non-Goals

- Retroactive fixing of existing duplicate products (manual cleanup required)
- Real-time duplicate detection during user data entry (only batch detection after ingestion)
- Cross-supplier variant grouping (variants detected within single supplier only)
- Manual merge workflow UI for potential duplicates (Phase 12 future work)
- Semantic similarity for hash computation (MD5 is structural, not semantic)

---

## Success Metrics

- **Hash Hit Rate:** ≥70% on typical re-ingestion (indicates successful caching)
- **Re-ingestion Time Reduction:** 60-80% faster for files with 80%+ unchanged rows
- **Auto-Creation Rate:** 50-90% of new items (indicates matching service health)
- **Duplicate Detection Precision:** <10% false positive rate in potential_duplicates queue
- **Category Hierarchy Compliance:** 100% of products assigned to valid categories (Level 1-3)
- **Variant Grouping Recall:** ≥85% of true variants correctly grouped

---

## User Stories

### Story 1: Idempotent Re-Ingestion

**As a** Procurement Manager
**I want** to re-import supplier price lists multiple times per day
**So that** I can keep prices up-to-date without creating duplicate products

**Acceptance Criteria:**

- [x] Re-importing a file with 80% unchanged rows completes in <40% of initial ingestion time
- [x] Unchanged rows preserve their product_id linkages
- [x] Only price fields (current_price, price_opt, price_rrc) are updated for cached rows
- [x] Changed rows (e.g., name updated) trigger full re-extraction

### Story 2: Automatic Product Creation

**As a** Sales Manager
**I want** new supplier items to be automatically added to the catalog
**So that** I don't have to manually review 200+ unmatched items

**Acceptance Criteria:**

- [x] Items with <90% match confidence automatically create new Products
- [x] New Products use ML-cleaned names (not raw supplier names)
- [x] "Unmatched Items" queue remains empty after ingestion
- [x] Potential duplicates are flagged in a separate review queue

### Story 3: Consistent Category Structure

**As a** Product Catalog Administrator
**I want** all products to follow a 3-level category hierarchy
**So that** the catalog is organized consistently for clients

**Acceptance Criteria:**

- [x] All products are assigned to Level 1, 2, or 3 categories
- [x] Excess category levels (4+) are logged but don't block ingestion
- [x] Incomplete hierarchies (<3 levels) are flagged for admin review
- [x] Brand becomes a category node under Sub-category

### Story 4: Automatic Variant Grouping

**As a** Client
**I want** similar products (e.g., "48V 20Ah" vs "48V 30Ah") to be presented as variants
**So that** I can easily compare options and select the right one

**Acceptance Criteria:**

- [x] Products with >85% name similarity and differing attributes are grouped
- [x] Variant schema shows which attributes vary (voltage, capacity, storage, size)
- [x] Grouped variants share the same base product
- [x] Price ratio validation prevents grouping unrelated products (>2.0x ratio)

---

## Technical Approach

### Architecture

**Service Responsibilities:**

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ python-ingestion│         │   ml-analyze    │         │    bun-api      │
│                 │         │                 │         │                 │
│ • Hash compute  │◄────────│ • ML extraction │◄────────│ • Admin UI      │
│ • Cache check   │         │ • Auto-create   │         │ • Duplicate API │
│ • Price update  │         │ • Variant detect│         │ • Category API  │
│ • ML trigger    │         │ • Duplicate flag│         │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
        │                           │                           │
        └───────────────────────────┴───────────────────────────┘
                                    │
                            ┌───────▼────────┐
                            │   PostgreSQL   │
                            │ • supplier_items│
                            │ • products      │
                            │ • categories    │
                            │ • pot_duplicates│
                            └────────────────┘
```

---

### Phase 0: Research & Design Decisions

**Research Areas:**

1. **Hash Algorithm Selection**
   - Decision: MD5 (sufficient for deduplication, collision probability <10^-15)
   - Rationale: Fast, deterministic, widely supported
   - Alternatives: SHA256 (slower, overkill for non-cryptographic use)

2. **Row Normalization Strategy**
   - Decision: Sort columns by name, trim whitespace, lowercase keys
   - Rationale: Prevents false cache misses from column reordering
   - Alternatives: Canonical JSON (more complex, unnecessary)

3. **Category Level Backfill Strategy**
   - Decision: Recursive parent traversal with memoization
   - Rationale: O(depth) per category, depth bounded to 3
   - Alternatives: LTREE extension (PostgreSQL-specific, adds dependency)

4. **Duplicate Detection Scope**
   - Decision: Within-category only (category_id filter)
   - Rationale: Reduces O(n^2) to O(k^2) where k = products per category (~100-500)
   - Alternatives: Cross-category (too expensive, low signal)

---

### Database Schema Changes

**Migration: 011_pipeline_stabilization_schema.py**

```sql
-- Add source_row_hash to supplier_items
ALTER TABLE supplier_items
ADD COLUMN source_row_hash VARCHAR(32);

CREATE INDEX idx_supplier_items_hash
ON supplier_items(source_row_hash);

-- Add category_level to categories
ALTER TABLE categories
ADD COLUMN category_level INTEGER;

-- Backfill existing categories (migration script)
-- Level = 1 if parent_id IS NULL
-- Level = 2 if parent.parent_id IS NULL
-- Level = 3 otherwise

ALTER TABLE categories
ADD CONSTRAINT chk_category_level
CHECK (category_level IN (1, 2, 3));

-- Create potential_duplicates table
CREATE TABLE potential_duplicates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id_1 UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    product_id_2 UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    similarity_score NUMERIC(5, 2) NOT NULL,
    detection_reason VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_different_products CHECK (product_id_1 != product_id_2),
    CONSTRAINT chk_ordered_ids CHECK (product_id_1 < product_id_2)
);

CREATE INDEX idx_potential_duplicates_status
ON potential_duplicates(status);
```

---

### Service Implementation Details

#### 1. Idempotency Service (python-ingestion)

**Location:** `services/python-ingestion/src/services/idempotency_service.py`

**Responsibilities:**
- Compute MD5 hash of raw row data
- Query database for existing hash
- Return cached data or trigger ML extraction

**Key Methods:**

```python
class IdempotencyService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def compute_row_hash(
        self,
        supplier_id: str,
        row_data: dict[str, Any]
    ) -> str:
        """
        Compute MD5 hash of normalized row data.
        Normalization: sort keys, trim whitespace, lowercase.
        """
        normalized = self._normalize_row_data(row_data)
        content = f"{supplier_id}|{normalized}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    async def get_cached_item(
        self,
        source_row_hash: str
    ) -> Optional[SupplierItem]:
        """
        Query supplier_items by hash.
        Returns None if not found.
        """
        result = await self.db.execute(
            select(SupplierItem)
            .where(SupplierItem.source_row_hash == source_row_hash)
        )
        return result.scalar_one_or_none()

    async def update_price_only(
        self,
        item_id: UUID,
        prices: dict[str, Decimal]
    ) -> None:
        """
        Update only time-variant fields for cached items.
        Fields: current_price, price_opt, price_rrc, last_ingested_at.
        """
        await self.db.execute(
            update(SupplierItem)
            .where(SupplierItem.id == item_id)
            .values(
                current_price=prices.get('current_price'),
                price_opt=prices.get('price_opt'),
                price_rrc=prices.get('price_rrc'),
                last_ingested_at=func.now()
            )
        )
        await self.db.commit()
```

**Integration Point:**

```python
# In services/python-ingestion/src/tasks/download_tasks.py

async def process_supplier_file(file_path: str, supplier_id: str):
    rows = parse_excel(file_path)
    idempotency_svc = IdempotencyService(db_session)

    for row in rows:
        row_hash = await idempotency_svc.compute_row_hash(supplier_id, row)
        cached_item = await idempotency_svc.get_cached_item(row_hash)

        if cached_item:
            # Cache hit: update prices only
            prices = extract_prices(row)
            await idempotency_svc.update_price_only(cached_item.id, prices)
            metrics.hash_hits += 1
        else:
            # Cache miss: trigger ML extraction
            ml_result = await ml_client.extract_item(file_path, row, supplier_id)
            await store_supplier_item(ml_result, row_hash)
            metrics.hash_misses += 1
```

---

#### 2. Auto-Creation Service (ml-analyze)

**Location:** `services/ml-analyze/src/services/auto_creation_service.py`

**Responsibilities:**
- Create products automatically for <90% confidence matches
- Use ML-cleaned names from extraction phase
- Link supplier_item to newly created product

**Key Methods:**

```python
class AutoCreationService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_product_from_extraction(
        self,
        extraction: ExtractedProduct,
        supplier_item_id: UUID
    ) -> Product:
        """
        Create a new Product using ML-cleaned data.
        Returns the created Product.
        """
        product = Product(
            id=uuid4(),
            name=extraction.cleaned_name,
            category_id=extraction.category_id,
            status='active',
            internal_sku=f"AUTO-{uuid4().hex[:8].upper()}",
            created_at=func.now()
        )

        self.db.add(product)
        await self.db.flush()

        # Link supplier_item to new product
        await self.db.execute(
            update(SupplierItem)
            .where(SupplierItem.id == supplier_item_id)
            .values(
                product_id=product.id,
                match_status='auto_created',
                match_score=None
            )
        )

        await self.db.commit()

        logger.info(
            f"Auto-created product {product.id} "
            f"for supplier_item {supplier_item_id}"
        )

        return product
```

**Integration Point:**

```python
# In services/ml-analyze/src/services/matching_service.py

async def match_batch(self, supplier_item_ids: list[UUID]) -> MatchStats:
    stats = MatchStats()
    auto_creation_svc = AutoCreationService(self.db)

    for item_id in supplier_item_ids:
        item = await self.get_supplier_item(item_id)
        match_result = await self.find_best_match(item)

        if match_result.confidence >= 0.90:
            # High confidence: link to existing product
            await self.link_to_product(item_id, match_result.product_id)
            stats.auto_matched += 1
        else:
            # Low confidence: auto-create new product
            extraction = await self.get_extraction_data(item_id)
            new_product = await auto_creation_svc.create_product_from_extraction(
                extraction, item_id
            )
            stats.auto_created += 1

    return stats
```

---

#### 3. Category Hierarchy Enforcement (ml-analyze)

**Location:** `services/ml-analyze/src/services/category_hierarchy_service.py`

**Responsibilities:**
- Validate category paths conform to 3-level constraint
- Create Brand categories under Sub-categories
- Flag incomplete hierarchies for admin review

**Key Methods:**

```python
class CategoryHierarchyService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def ensure_3_level_hierarchy(
        self,
        category_path: list[str]
    ) -> UUID:
        """
        Ensure category path conforms to 3-level hierarchy.
        Returns the Level 3 category ID to assign to the product.

        If path has <3 levels: create partial, flag needs_review
        If path has >3 levels: take first 3, log warning
        """
        if len(category_path) > 3:
            logger.warning(
                f"Excess category levels: {category_path}. "
                f"Using first 3 levels."
            )
            category_path = category_path[:3]

        # Create/find Level 1 (Top Category)
        level_1 = await self.find_or_create_category(
            name=category_path[0],
            parent_id=None,
            level=1
        )

        if len(category_path) == 1:
            # Incomplete hierarchy: flag for review
            await self.flag_incomplete_hierarchy(level_1.id)
            return level_1.id

        # Create/find Level 2 (Sub-category)
        level_2 = await self.find_or_create_category(
            name=category_path[1],
            parent_id=level_1.id,
            level=2
        )

        if len(category_path) == 2:
            # Incomplete hierarchy: flag for review
            await self.flag_incomplete_hierarchy(level_2.id)
            return level_2.id

        # Create/find Level 3 (Brand)
        level_3 = await self.find_or_create_category(
            name=category_path[2],
            parent_id=level_2.id,
            level=3
        )

        return level_3.id

    async def find_or_create_category(
        self,
        name: str,
        parent_id: Optional[UUID],
        level: int
    ) -> Category:
        """
        Find existing category by (name, parent_id) or create new.
        Validates level constraint.
        """
        if level > 3:
            raise CategoryHierarchyError(
                f"Cannot create level {level} category"
            )

        result = await self.db.execute(
            select(Category)
            .where(
                Category.name == name,
                Category.parent_id == parent_id
            )
        )
        category = result.scalar_one_or_none()

        if not category:
            category = Category(
                id=uuid4(),
                name=name,
                parent_id=parent_id,
                category_level=level,
                created_at=func.now()
            )
            self.db.add(category)
            await self.db.flush()

        return category

    async def flag_incomplete_hierarchy(self, category_id: UUID) -> None:
        """
        Log incomplete hierarchy to parsing_logs for admin review.
        """
        await self.db.execute(
            insert(ParsingLog).values(
                task_id=None,
                supplier_id=None,
                error_type='incomplete_category_hierarchy',
                error_message=f'Category {category_id} has <3 levels',
                row_data={'category_id': str(category_id)},
                created_at=func.now()
            )
        )
```

**Integration Point:**

```python
# In services/ml-analyze/src/services/category_normalizer.py

async def normalize_category_with_hierarchy(
    self,
    extracted_categories: list[str],
    extracted_brand: Optional[str]
) -> UUID:
    """
    Normalize category path and enforce 3-level hierarchy.
    Brand becomes the Level 3 category.
    """
    hierarchy_svc = CategoryHierarchyService(self.db)

    # Build path: Top → Sub → Brand
    category_path = extracted_categories.copy()
    if extracted_brand:
        category_path.append(extracted_brand)

    category_id = await hierarchy_svc.ensure_3_level_hierarchy(category_path)
    return category_id
```

---

#### 4. Variant Detection Integration (ml-analyze)

**Location:** `services/ml-analyze/src/services/ingestion_orchestrator.py`

**Responsibilities:**
- Run variant detection after all items in a batch are processed
- Scope detection to newly created products + existing products in same categories

**Key Methods:**

```python
class IngestionOrchestrator:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.variant_detection_svc = VariantDetectionService()

    async def on_batch_complete(
        self,
        batch_id: str,
        created_product_ids: list[UUID]
    ) -> VariantDetectionStats:
        """
        Post-processing hook after ingestion batch completes.
        Runs variant detection on newly created products.
        """
        logger.info(f"Running variant detection for batch {batch_id}")

        # Get categories of newly created products
        result = await self.db.execute(
            select(Product.category_id)
            .where(Product.id.in_(created_product_ids))
            .distinct()
        )
        category_ids = [row[0] for row in result.fetchall()]

        # Get all products in these categories (for cross-batch variants)
        result = await self.db.execute(
            select(Product)
            .where(Product.category_id.in_(category_ids))
        )
        all_products_in_categories = result.scalars().all()

        # Run variant detection
        variant_groups = self.variant_detection_svc.group_variants(
            all_products_in_categories
        )

        # Store variant records
        stats = VariantDetectionStats()
        for group in variant_groups:
            await self.store_variant_group(group)
            stats.groups_created += 1
            stats.products_grouped += len(group.variants)

        logger.info(
            f"Variant detection complete: "
            f"{stats.groups_created} groups, "
            f"{stats.products_grouped} products"
        )

        return stats

    async def store_variant_group(self, group: VariantGroup) -> None:
        """
        Store variant group in product_variants table.
        Update parent product with has_variants=true.
        """
        parent_product_id = group.variants[0].product_id

        # Update parent product
        await self.db.execute(
            update(Product)
            .where(Product.id == parent_product_id)
            .values(
                has_variants=True,
                variant_schema=group.variant_schema
            )
        )

        # Create variant records
        for variant in group.variants:
            variant_record = ProductVariant(
                id=uuid4(),
                product_id=parent_product_id,
                variant_key=variant.variant_key,
                variant_attributes=variant.attributes,
                display_order=variant.display_order,
                created_at=func.now()
            )
            self.db.add(variant_record)

        await self.db.commit()
```

---

#### 5. Duplicate Detection Service (ml-analyze)

**Location:** `services/ml-analyze/src/services/duplicate_detection_service.py`

**Responsibilities:**
- Detect potential duplicates after auto-creation
- Flag products with 85-90% similarity, <20% price difference, same category

**Key Methods:**

```python
class DuplicateDetectionService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def detect_duplicates(
        self,
        created_product_ids: list[UUID]
    ) -> DuplicateDetectionStats:
        """
        Detect potential duplicates among newly created products.
        Compare against products in same category.
        """
        stats = DuplicateDetectionStats()

        for product_id in created_product_ids:
            product = await self.get_product(product_id)

            # Get candidate duplicates in same category
            candidates = await self.db.execute(
                select(Product)
                .where(
                    Product.category_id == product.category_id,
                    Product.id != product_id
                )
            )
            candidates = candidates.scalars().all()

            for candidate in candidates:
                similarity = self.compute_similarity(product.name, candidate.name)
                price_diff = self.compute_price_diff(product, candidate)

                # Thresholds: 85-90% similarity, <20% price difference
                if (0.85 <= similarity < 0.90 and
                    price_diff < 0.20 and
                    not await self.are_variants(product.id, candidate.id)):

                    await self.flag_duplicate(
                        product.id,
                        candidate.id,
                        similarity * 100
                    )
                    stats.duplicates_flagged += 1

        return stats

    async def flag_duplicate(
        self,
        product_id_1: UUID,
        product_id_2: UUID,
        similarity_score: float
    ) -> None:
        """
        Insert record into potential_duplicates table.
        Ensure product_id_1 < product_id_2 to avoid (A,B) and (B,A) duplicates.
        """
        if product_id_1 > product_id_2:
            product_id_1, product_id_2 = product_id_2, product_id_1

        # Check if already flagged
        result = await self.db.execute(
            select(PotentialDuplicate)
            .where(
                PotentialDuplicate.product_id_1 == product_id_1,
                PotentialDuplicate.product_id_2 == product_id_2
            )
        )
        if result.scalar_one_or_none():
            return  # Already flagged

        duplicate = PotentialDuplicate(
            id=uuid4(),
            product_id_1=product_id_1,
            product_id_2=product_id_2,
            similarity_score=similarity_score,
            detection_reason='auto_creation_similarity',
            status='pending',
            created_at=func.now()
        )
        self.db.add(duplicate)
        await self.db.commit()
```

---

### Bun API Endpoints

**Location:** `services/bun-api/src/controllers/admin/duplicates.controller.ts`

**Endpoints:**

```typescript
// GET /api/v1/admin/duplicates
export const getDuplicates = async (c: Context) => {
  const { status = 'pending', limit = 50, offset = 0 } = c.query;

  const duplicates = await duplicateService.list({
    status,
    limit: parseInt(limit),
    offset: parseInt(offset)
  });

  return c.json({ duplicates, total: duplicates.length });
};

// PATCH /api/v1/admin/duplicates/:id/merge
export const mergeDuplicates = async (c: Context) => {
  const { id } = c.params;
  const { keepProductId, archiveProductId } = await c.body();

  const result = await duplicateService.merge(
    id,
    keepProductId,
    archiveProductId
  );

  return c.json({ success: true, mergedProduct: result });
};

// PATCH /api/v1/admin/duplicates/:id/dismiss
export const dismissDuplicate = async (c: Context) => {
  const { id } = c.params;

  await duplicateService.dismiss(id);

  return c.json({ success: true });
};
```

---

### Frontend Components

**Location:** `services/frontend/src/pages/admin/DuplicatesReviewPage.tsx`

```tsx
export const DuplicatesReviewPage: React.FC = () => {
  const { data: duplicates, isLoading } = useQuery({
    queryKey: ['duplicates', 'pending'],
    queryFn: () => apiClient.get('/admin/duplicates', { status: 'pending' })
  });

  const mergeMutation = useMutation({
    mutationFn: (params: MergeDuplicateParams) =>
      apiClient.patch(`/admin/duplicates/${params.id}/merge`, {
        keepProductId: params.keepProductId,
        archiveProductId: params.archiveProductId
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['duplicates'] });
      toast.success(t('admin.duplicates.mergeSuccess'));
    }
  });

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">
        {t('admin.duplicates.title')}
      </h1>

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <PotentialDuplicatesTable
          duplicates={duplicates}
          onMerge={mergeMutation.mutate}
          onDismiss={dismissMutation.mutate}
        />
      )}
    </div>
  );
};
```

---

## Type Safety

### TypeScript Types

```typescript
// services/bun-api/src/types/duplicate.types.ts

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

export interface MergeDuplicateRequest {
  keepProductId: string;
  archiveProductId: string;
}

export interface DuplicateStats {
  total: number;
  pending: number;
  merged: number;
  dismissed: number;
}
```

### Python Types

```python
# services/ml-analyze/src/schemas/duplicate.py

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal
from uuid import UUID

class PotentialDuplicateCreate(BaseModel):
    product_id_1: UUID
    product_id_2: UUID
    similarity_score: float = Field(..., ge=0, le=100)
    detection_reason: str

class PotentialDuplicateResponse(BaseModel):
    id: UUID
    product_id_1: UUID
    product_id_2: UUID
    similarity_score: float
    status: Literal['pending', 'merged', 'dismissed']
    created_at: datetime

class DuplicateDetectionStats(BaseModel):
    duplicates_flagged: int
    false_positives_estimated: int
```

---

## Testing Strategy

### Unit Tests

**Python (python-ingestion):**
- `test_idempotency_service.py`:
  - `test_compute_row_hash_deterministic()` - Same input → same hash
  - `test_compute_row_hash_column_order_invariant()` - Column reordering → same hash
  - `test_get_cached_item_exists()` - Hash match returns item
  - `test_get_cached_item_not_found()` - No hash match returns None
  - `test_update_price_only()` - Only prices updated, name/category unchanged

**Python (ml-analyze):**
- `test_auto_creation_service.py`:
  - `test_create_product_from_extraction()` - Product created with ML-cleaned name
  - `test_auto_creation_sets_status_active()` - New product status is 'active'
  - `test_auto_creation_generates_internal_sku()` - SKU format: AUTO-{hex}

- `test_category_hierarchy_service.py`:
  - `test_ensure_3_level_hierarchy_full_path()` - 3 levels → Level 3 category returned
  - `test_ensure_3_level_hierarchy_partial_path()` - 1 level → Level 1 + flagged
  - `test_ensure_3_level_hierarchy_excess_path()` - 4 levels → first 3 used, warning logged
  - `test_find_or_create_category_existing()` - Existing category found
  - `test_find_or_create_category_new()` - New category created with correct level

- `test_duplicate_detection_service.py`:
  - `test_detect_duplicates_within_threshold()` - 88% similarity → flagged
  - `test_detect_duplicates_below_threshold()` - 82% similarity → not flagged
  - `test_detect_duplicates_high_price_diff()` - 25% price diff → not flagged
  - `test_detect_duplicates_already_variants()` - Products in variant group → not flagged

**TypeScript (bun-api):**
- `test_duplicate_controller.ts`:
  - `test_get_duplicates_filters_by_status()` - Query param filters correctly
  - `test_merge_duplicates_updates_supplier_items()` - Supplier items reassigned
  - `test_merge_duplicates_archives_product()` - Archived product status updated

### Integration Tests

**Hash-Based Idempotency Flow:**
1. Ingest file with 100 rows
2. Verify: 100 supplier_items created, all have source_row_hash
3. Re-ingest same file with 10 rows changed (prices)
4. Verify: 90 hash hits (UPDATE), 10 hash misses (INSERT)
5. Verify: No duplicate products created
6. Assert: Re-ingestion time <50% of initial ingestion

**Auto-Creation & Duplicate Detection Flow:**
1. Ingest new supplier catalog (200 items, all <90% confidence)
2. Verify: 200 new products created, match_status = 'auto_created'
3. Verify: potential_duplicates table has 5-10 flagged pairs
4. Admin merges 1 duplicate pair (keep product A, archive product B)
5. Verify: All supplier_items from B now linked to A, B status = 'archived'

**Category Hierarchy Enforcement:**
1. Ingest product with category path: ["Electronics", "Laptops", "Dell"]
2. Verify: 3 categories created (L1: Electronics, L2: Laptops, L3: Dell)
3. Verify: Product.category_id = Dell.id
4. Ingest product with path: ["Tools"]
5. Verify: 1 category created (L1: Tools)
6. Verify: parsing_logs entry: error_type = 'incomplete_category_hierarchy'

### E2E Tests

**Complete Ingestion Flow:**
1. Upload Excel file via Bun API (`POST /api/v1/admin/sync`)
2. Verify: Job status polling returns phases: downloading → analyzing → extracting → normalizing → complete
3. Verify: supplier_items created with source_row_hash
4. Verify: Products auto-created for <90% matches
5. Verify: Variants grouped (e.g., "48V 20Ah" + "48V 30Ah" → 1 product, 2 variants)
6. Verify: Potential duplicates flagged in admin UI
7. Admin merges 1 duplicate
8. Verify: Merged product shows combined supplier_items count

**Coverage Target:** ≥80% for all business logic

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Hash collision causing data loss | High | Very Low (<0.01%) | Detect collisions via JSONB comparison, fall back to re-extraction |
| Auto-creation rate >95% (matching degraded) | High | Medium | Monitor auto_creation_rate metric, alert if >90%, rollback feature flag |
| Duplicate queue overwhelmed (>500 pending) | Medium | Medium | Increase similarity threshold to 87%, add price diff filter to 15% |
| Category level backfill migration fails | High | Low | Dry-run migration on copy of production DB, verify all categories assigned levels 1-3 |
| Variant detection groups unrelated products | Medium | Low | Price ratio validation (≤2.0x), manual review of first 100 variant groups |
| Performance degradation on large files (>10k rows) | Medium | Medium | Batch hash lookups (1000 rows/query), parallel processing for non-cached rows |

---

## Dependencies

**Python Packages:**
- `hashlib` (stdlib, MD5 computation)
- `sqlalchemy` (existing, ORM)
- `rapidfuzz` (existing, name similarity)
- No new dependencies required

**TypeScript Packages:**
- `@tanstack/react-query` (existing, data fetching)
- `zod` (existing, validation)
- No new dependencies required

**Infrastructure:**
- PostgreSQL indexes: `idx_supplier_items_hash`, `idx_potential_duplicates_status`
- Database migration: `011_pipeline_stabilization_schema.py`
- Environment variables:
  - `HASH_CACHE_ENABLED` (default: true)
  - `AUTO_CREATE_THRESHOLD` (default: 90)
  - `VARIANT_DETECTION_ENABLED` (default: true)
  - `DUPLICATE_DETECTION_ENABLED` (default: true)
  - `DUPLICATE_SIMILARITY_THRESHOLD` (default: 85)

---

## Timeline

| Phase | Tasks | Duration | Target Date |
|-------|-------|----------|-------------|
| Phase 0 | Research, schema design, migration script | 1 day | 2025-12-10 |
| Phase 1 | Idempotency service, hash computation | 1 day | 2025-12-11 |
| Phase 2 | Auto-creation service, matching refactor | 1 day | 2025-12-12 |
| Phase 3 | Category hierarchy enforcement | 1 day | 2025-12-13 |
| Phase 4 | Variant detection integration | 1 day | 2025-12-14 |
| Phase 5 | Duplicate detection service | 1 day | 2025-12-15 |
| Phase 6 | Bun API endpoints, frontend UI | 1 day | 2025-12-16 |
| Phase 7 | Testing (unit, integration, E2E) | 2 days | 2025-12-18 |
| Phase 8 | Staging deployment, feature flag rollout | 1 day | 2025-12-19 |

**Total:** 9 days

---

## Open Questions

- [x] How to handle category paths with <3 levels? **RESOLVED:** Allow temporary L1/L2 assignments, flag for review
- [ ] Should hash algorithm be configurable (MD5 vs SHA256)? **DECISION NEEDED:** Start with MD5, add env var for future flexibility
- [ ] Should duplicate detection run on every batch or scheduled (e.g., daily)? **RECOMMENDATION:** Run on every batch (simpler, immediate feedback)

---

## References

- [Feature Specification](./spec.md)
- [Phase 9: Semantic ETL ADR](/Users/valecer/work/sites/marketbel/docs/adr/009-semantic-etl.md)
- [Phase 10: Product Variants ADR](/Users/valecer/work/sites/marketbel/docs/adr/010-product-variants.md)
- [Existing Variant Detection Service](/Users/valecer/work/sites/marketbel/services/ml-analyze/src/services/variant_detection_service.py)
- [Project Constitution](/.specify/memory/constitution.md)

---

**Approval Signatures:**

- [ ] Technical Lead
- [ ] Product Owner
- [ ] Architecture Review
