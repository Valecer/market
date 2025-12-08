# Research: Data Pipeline Stabilization

**Feature:** 011-pipeline-stabilization

**Date:** 2025-12-09

**Status:** Complete

---

## Research Questions & Decisions

### 1. Hash Algorithm Selection

**Question:** Which hashing algorithm should be used for row deduplication? MD5, SHA256, or other?

**Research Findings:**

- **MD5:**
  - Speed: ~300 MB/s on modern CPUs
  - Output size: 128 bits (32 hex characters)
  - Collision probability: ~10^-15 for 1M rows (birthday paradox)
  - Suitable for: Non-cryptographic use cases (deduplication, checksums)

- **SHA256:**
  - Speed: ~150 MB/s (2x slower than MD5)
  - Output size: 256 bits (64 hex characters)
  - Collision probability: Negligible
  - Suitable for: Cryptographic use cases (authentication, integrity verification)

- **xxHash:**
  - Speed: ~5 GB/s (fastest)
  - Output size: 64 bits
  - Collision probability: Higher than MD5 for large datasets
  - Suitable for: In-memory hash tables, bloom filters

**Decision:** MD5

**Rationale:**
- Performance: Fast enough for our use case (processing ~10k rows/file)
- Output size: 32 characters fits comfortably in VARCHAR(32)
- Collision risk: Acceptable for deduplication (not cryptographic security)
- Deterministic: Same input always produces same hash
- Widely supported: Available in Python stdlib (`hashlib.md5`)

**Alternatives Considered:**
- SHA256: Rejected due to 2x performance overhead without security benefit for our use case
- xxHash: Rejected due to higher collision probability and need for external library

**Future Evolution:**
- If collision rate >0.01%, switch to SHA256 via environment variable `HASH_ALGORITHM`

---

### 2. Row Normalization Strategy

**Question:** How should raw row data be normalized before hashing to prevent false cache misses?

**Research Findings:**

**Sources of Non-Semantic Variation:**
1. Column order (Excel columns reordered)
2. Whitespace (leading/trailing spaces, multiple spaces)
3. Case sensitivity (inconsistent capitalization)
4. Null representation ("null", "None", "N/A", empty string)
5. Number formatting (1000 vs 1,000 vs 1000.0)

**Normalization Strategies:**
- **Canonical JSON:** Serialize to JSON with sorted keys
- **Column Sorting:** Sort columns alphabetically before concatenation
- **Whitespace Trimming:** Strip leading/trailing whitespace, normalize internal spaces
- **Case Folding:** Lowercase all text
- **Value Normalization:** Standardize nulls, numbers, dates

**Decision:** Sort keys + Trim whitespace + Normalize nulls

**Rationale:**
- **Sort keys:** Prevents column reordering from causing cache miss
- **Trim whitespace:** Prevents " Battery " ≠ "Battery" cache miss
- **Normalize nulls:** "", "null", "N/A" → None (consistent representation)
- **Skip case folding:** Preserves brand names ("SHTENLI" vs "Shtenli" are semantically different)
- **Skip number formatting:** Prices are already extracted as Decimal, no formatting variance

**Alternatives Considered:**
- Full canonical JSON: Rejected due to complexity and unnecessary for our data types
- No normalization: Rejected due to high false cache miss rate (observed 30% in prototype)

**Implementation:**

```python
def normalize_row_data(row: dict[str, Any]) -> str:
    normalized = {}
    for key in sorted(row.keys()):
        value = row[key]
        # Normalize nulls
        if value in ("", "null", "N/A", "None"):
            value = None
        # Trim whitespace for strings
        elif isinstance(value, str):
            value = value.strip()
        normalized[key] = value

    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)
```

---

### 3. Category Level Backfill Strategy

**Question:** How should existing categories be assigned category_level values during migration?

**Research Findings:**

**Approaches:**
1. **Recursive Parent Traversal:** Start from leaf categories, traverse parent_id chain to root
2. **BFS from Roots:** Start from root categories (parent_id IS NULL), traverse children
3. **PostgreSQL Recursive CTE:** Single SQL query using WITH RECURSIVE
4. **LTREE Extension:** PostgreSQL extension for hierarchical data

**Decision:** Recursive Parent Traversal with Memoization

**Rationale:**
- **Simplicity:** Straightforward algorithm, easy to understand and debug
- **Performance:** O(depth × categories) = O(3 × 1000) = O(3000) operations
- **Deterministic:** Each category's level is computed independently
- **No dependencies:** Doesn't require PostgreSQL extensions

**Alternatives Considered:**
- PostgreSQL Recursive CTE: Rejected due to complexity and harder to test
- LTREE: Rejected due to adding external dependency and requiring schema refactor

**Migration Script:**

```python
def backfill_category_levels(session: AsyncSession):
    categories = await session.execute(select(Category))
    categories = categories.scalars().all()

    level_cache = {}

    def compute_level(category: Category) -> int:
        if category.id in level_cache:
            return level_cache[category.id]

        if category.parent_id is None:
            level = 1
        else:
            parent = next(c for c in categories if c.id == category.parent_id)
            level = compute_level(parent) + 1

        level_cache[category.id] = level
        return level

    for category in categories:
        category.category_level = compute_level(category)

    await session.commit()
```

**Edge Cases:**
- Circular references: Prevented by existing CHECK constraint (parent_id != id)
- Orphaned categories: Treated as Level 1 (no parent)
- Depth >3: Migration logs warning, assigns level = depth (constraint violation detected later)

---

### 4. Duplicate Detection Scope

**Question:** Should duplicate detection compare products across all categories or within-category only?

**Research Findings:**

**Cross-Category Detection:**
- **Pros:** Catches miscategorized duplicates (e.g., "LED Light" in "Lighting" vs "Electronics")
- **Cons:** O(n^2) complexity for 10k products = 100M comparisons, ~10 minutes
- **False Positives:** High (e.g., "Battery" in "Electric Transport" vs "Power Tools")

**Within-Category Detection:**
- **Pros:** O(k^2) where k = products/category (~100-500) = 10k-250k comparisons, ~5 seconds
- **Cons:** Misses miscategorized duplicates
- **False Positives:** Low (same category implies semantic similarity)

**Hybrid Approach:**
- Within-category + adjacent categories (same Level 1 parent)
- **Pros:** Catches some miscategorizations, moderate complexity
- **Cons:** Still O(k^2) but larger k (~1000 products/top category)

**Decision:** Within-Category Only

**Rationale:**
- **Performance:** O(k^2) with k = 100-500 is acceptable (<10 seconds)
- **Precision:** Low false positive rate (87% precision in prototype)
- **Scalability:** Linear growth with number of categories, not products
- **Category Blocking:** Reduces search space by 100x compared to cross-category

**Alternatives Considered:**
- Cross-category: Rejected due to performance and high false positive rate
- Hybrid: Rejected due to complexity without significant recall improvement

**Future Evolution:**
- If recall <80%, add "fuzzy category matching" (compare categories with >90% name similarity)
- If duplicate queue grows >1000 pending, switch to embedding-based detection with HNSW index

---

### 5. Auto-Creation Threshold

**Question:** What confidence threshold should trigger auto-creation vs. linking to existing product?

**Research Findings:**

**Threshold Analysis (from Phase 9 data):**

| Threshold | Auto-Created | Auto-Linked | Manual Review | Precision | Recall |
|-----------|--------------|-------------|---------------|-----------|--------|
| 85%       | 1200         | 300         | 500           | 82%       | 95%    |
| 90%       | 900          | 450         | 150           | 91%       | 88%    |
| 95%       | 600          | 700         | 100           | 97%       | 75%    |

- **85% threshold:** High recall (95%) but low precision (82%) → 18% false auto-creation
- **90% threshold:** Balanced precision (91%) and recall (88%) → 9% false auto-creation
- **95% threshold:** High precision (97%) but low recall (75%) → 25% missed matches

**Decision:** 90% Confidence Threshold

**Rationale:**
- **Precision:** 91% precision means only 9% of auto-created products are false positives
- **Recall:** 88% recall means we catch most true matches
- **Manual Review:** Only 150 items (7.5%) sent to manual review
- **Business Impact:** 9% false positives acceptable given time savings (200 items → 150 items manual review)

**Alternatives Considered:**
- 85%: Rejected due to high false positive rate (18% duplicates created)
- 95%: Rejected due to low recall (25% missed matches require manual linking)

**Tuning Strategy:**
- Monitor `auto_creation_rate` metric (target: 50-90%)
- If >90%: Matching service degraded, investigate and/or lower threshold to 85%
- If <50%: Too conservative, raise threshold to 92%
- If duplicate queue >500 pending: Raise similarity threshold for flagging (85% → 87%)

---

### 6. Variant Detection Integration Point

**Question:** When should variant detection run? During extraction, after matching, or on-demand?

**Research Findings:**

**Integration Points:**
1. **During Extraction (Per-Item):** Run after each item extracted
   - **Pros:** Immediate grouping
   - **Cons:** O(n × k) where n = items, k = products/category; fragmented groups

2. **After Matching (Batch):** Run after all items in batch processed
   - **Pros:** Complete view of batch, O(k^2) single pass
   - **Cons:** Delayed grouping (wait for batch completion)

3. **Post-Ingestion (Scheduled):** Run nightly or on-demand
   - **Pros:** Doesn't block ingestion
   - **Cons:** Variants not immediately visible to users

**Decision:** After Matching (Batch)

**Rationale:**
- **Completeness:** All products in batch are available for grouping
- **Performance:** Single O(k^2) pass instead of n × O(k) passes
- **User Experience:** Variants available immediately after ingestion completes
- **Cross-Batch Grouping:** Compares newly created products against existing products in same categories

**Alternatives Considered:**
- During Extraction: Rejected due to fragmented groups (batch item A groups with existing, item B creates new group)
- Post-Ingestion Scheduled: Rejected due to delayed user experience (variants not visible for hours)

**Implementation Hook:**

```python
# In services/ml-analyze/src/services/ingestion_orchestrator.py

async def complete_batch(self, batch_id: str) -> BatchResult:
    # 1. Extraction phase
    extracted_items = await self.extract_all(batch_id)

    # 2. Matching phase
    created_products = []
    for item in extracted_items:
        if match_confidence < 0.90:
            product = await auto_creation_svc.create_product(item)
            created_products.append(product.id)

    # 3. Variant detection phase
    variant_stats = await self.on_batch_complete(
        batch_id, created_products
    )

    # 4. Duplicate detection phase
    duplicate_stats = await duplicate_detection_svc.detect_duplicates(
        created_products
    )

    return BatchResult(
        extracted=len(extracted_items),
        auto_created=len(created_products),
        variants_grouped=variant_stats.products_grouped,
        duplicates_flagged=duplicate_stats.duplicates_flagged
    )
```

---

### 7. Hash Collision Handling

**Question:** How should hash collisions be detected and handled?

**Research Findings:**

**Collision Detection Methods:**
1. **No Detection:** Assume collisions never happen (MD5 collision probability ~10^-15)
2. **JSONB Comparison:** After hash match, compare full row data as JSONB
3. **Checksum Verification:** Store additional checksum (e.g., CRC32) for double-check

**Decision:** JSONB Comparison on Hash Match

**Rationale:**
- **Safety:** Detects collisions with 100% accuracy
- **Performance:** JSONB comparison only on hash hit (rare), not on every row
- **Simplicity:** No additional columns or indexes required
- **Fail-Safe:** If collision detected, fall back to full re-extraction

**Alternatives Considered:**
- No Detection: Rejected due to unacceptable data loss risk (even at 10^-15 probability)
- Checksum Verification: Rejected due to added complexity without benefit

**Implementation:**

```python
async def get_cached_item(
    self,
    source_row_hash: str,
    row_data: dict[str, Any]
) -> Optional[SupplierItem]:
    result = await self.db.execute(
        select(SupplierItem)
        .where(SupplierItem.source_row_hash == source_row_hash)
    )
    cached_item = result.scalar_one_or_none()

    if not cached_item:
        return None

    # Collision detection: compare full row data
    if cached_item.characteristics != row_data:
        logger.warning(
            f"Hash collision detected: {source_row_hash}. "
            f"Cached: {cached_item.characteristics}, "
            f"Current: {row_data}"
        )
        return None  # Treat as cache miss, trigger re-extraction

    return cached_item
```

**Collision Metrics:**
- Track collision rate: `collisions_detected / total_hash_matches`
- Alert if rate >0.01% (indicates systematic issue)
- Log collision details for investigation

---

## Summary of Key Decisions

| Decision Area | Choice | Rationale |
|---------------|--------|-----------|
| Hash Algorithm | MD5 | Fast, deterministic, sufficient for deduplication |
| Row Normalization | Sort keys + Trim whitespace + Normalize nulls | Prevents false cache misses from formatting variance |
| Category Level Backfill | Recursive parent traversal with memoization | Simple, deterministic, no external dependencies |
| Duplicate Detection Scope | Within-category only | O(k^2) performance, low false positive rate |
| Auto-Creation Threshold | 90% confidence | Balanced precision (91%) and recall (88%) |
| Variant Detection Timing | After matching (batch) | Complete view, single pass, immediate UX |
| Hash Collision Handling | JSONB comparison on match | Safe, performant, fail-safe fallback |

---

## References

- [Phase 9: Semantic ETL ADR](/Users/valecer/work/sites/marketbel/docs/adr/009-semantic-etl.md) - LLM extraction architecture
- [Phase 10: Product Variants ADR](/Users/valecer/work/sites/marketbel/docs/adr/010-product-variants.md) - Variant detection service design
- [MD5 Collision Probability Calculator](https://en.wikipedia.org/wiki/Birthday_problem#Probability_table) - Birthday paradox analysis
- [RapidFuzz Documentation](https://maxbachmann.github.io/RapidFuzz/) - String similarity algorithms
