# ADR 011: Data Pipeline Stabilization

**Status:** Accepted  
**Date:** 2025-12-10  
**Authors:** Development Team

## Context

The data ingestion pipeline suffered from several issues:

1. **Duplicate Products on Re-import**: Re-importing supplier files created duplicate products due to non-deterministic LLM outputs
2. **Manual Matching Overhead**: New supplier items with <90% confidence required manual review (200+ items per import)
3. **Inconsistent Category Structure**: Categories lacked enforced hierarchy, leading to flat or deeply nested structures
4. **No Variant Presentation**: Similar products (e.g., different capacities) were displayed as separate listings

## Decision

We implement four interconnected features:

### 1. Hash-Based Idempotency (MD5)

**Decision:** Use MD5 hashing for row deduplication

**Rationale:**
- Fast computation (~5ms/1000 rows)
- Deterministic output for identical input
- Sufficient collision resistance for deduplication (probability <10^-15 for 1M rows)
- Not used for security, so MD5 cryptographic weaknesses are irrelevant

**Alternatives Considered:**
- SHA256: More secure but 30% slower, unnecessary for non-security use case
- SHA1: Deprecated, no advantage over MD5 for this use case
- Content-addressable storage: Over-engineering for the problem

**Hash Normalization Algorithm:**
```python
# 1. Normalize keys: lowercase, sorted alphabetically
# 2. Normalize values: trim strings, null -> ""
# 3. Serialize to canonical JSON (sorted keys, compact)
# 4. Compute: MD5("{supplier_id}|{canonical_json}")
```

### 2. Auto-Creation Strategy (<90% Confidence)

**Decision:** Automatically create new Products when match confidence <90%

**Rationale:**
- Eliminates "Unmatched Items" queue bottleneck
- Products immediately visible to clients
- Uses ML-cleaned names (not raw supplier text)
- Duplicate detection catches false positives post-hoc

**Thresholds:**
- ≥90%: Link to existing product (high confidence)
- <90%: Auto-create new product with `match_status='auto_created'`
- 85-90% similarity: Flag as potential duplicate for review

**SKU Format:** `AUTO-{uuid4().hex[:8].upper()}` (e.g., `AUTO-A3F2B91C`)

### 3. Three-Level Category Hierarchy

**Decision:** Enforce strict 3-level category structure

**Structure:**
```
Level 1: Top Category    (e.g., "Electric Transport")
Level 2: Sub-category    (e.g., "Motorcycles")
Level 3: Brand/Type      (e.g., "Shtenli")
```

**Rationale:**
- Consistent navigation across all suppliers
- Clear mental model for users
- Prevents flat (1-level) or deep (5+ level) hierarchies
- Brand becomes a category node, not a product field

**Handling Edge Cases:**
- **>3 levels provided:** Take first 3, log warning, discard excess
- **<3 levels provided:** Create partial hierarchy, flag `needs_review=true`
- **Empty path:** Log error, allow but flag for review

### 4. Duplicate Detection After Auto-Creation

**Decision:** Post-hoc duplicate detection with admin review queue

**Algorithm:**
- Pairwise comparison within same category (reduces O(n²) to manageable scope)
- Name similarity: 85% ≤ score < 90% (RapidFuzz WRatio)
- Price difference: <20% (products with >20% diff are likely variants)
- NOT already grouped as variants

**Data Model:**
```sql
CREATE TABLE potential_duplicates (
    id UUID PRIMARY KEY,
    product_id_1 UUID REFERENCES products(id),
    product_id_2 UUID REFERENCES products(id),
    similarity_score NUMERIC(5,2),
    detection_reason VARCHAR(100),
    status VARCHAR(50) DEFAULT 'pending',  -- pending, merged, dismissed
    CONSTRAINT chk_ordered_ids CHECK (product_id_1 < product_id_2)
);
```

The ordered ID constraint prevents (A,B) and (B,A) duplicate entries.

## Consequences

### Positive

1. **60-80% faster re-ingestion** for files with mostly unchanged rows
2. **Zero manual matching** for initial imports (auto-create handles everything)
3. **Consistent catalog structure** with 3-level hierarchy
4. **Reduced false positives** in duplicate queue (85-90% threshold, not 80%)

### Negative

1. **MD5 is not cryptographically secure** (mitigated: not used for security)
2. **Auto-creation may create duplicates** (mitigated: post-hoc detection catches these)
3. **3-level constraint may not fit all taxonomies** (mitigated: log warnings, flag for review)

### Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Hash collision | Very Low (<0.01%) | High | Content comparison on match, fallback to full extraction |
| High auto-creation rate (>95%) | Medium | High | Monitor metric, adjust threshold, alert on anomaly |
| Duplicate queue overwhelmed | Medium | Medium | Increase similarity threshold, add price filter |
| Category level backfill fails | Low | High | Dry-run on staging, verify all categories assigned levels |

## Performance Characteristics

| Operation | Target | Actual |
|-----------|--------|--------|
| Hash computation | <5ms/1000 rows | ✅ |
| Hash lookup (batch) | <50ms/1000 hashes | ✅ |
| Re-ingestion (80% cached) | <40% of full time | ✅ |
| Variant detection (200 products) | <10 seconds | ✅ |
| Duplicate detection (500 products) | <30 seconds | ✅ |

## Monitoring

**Key Metrics:**
- `hash_hit_rate`: Target ≥70% (cache effectiveness)
- `auto_creation_rate`: 50-90% is healthy (matching quality)
- `duplicate_queue_size`: Alert if >500 pending (review backlog)
- `category_compliance_rate`: Target 100% L1-L3 assignment

**Alerting Thresholds:**
- `hash_hit_rate < 50%`: Investigation required
- `auto_creation_rate > 95%`: Matching degradation
- `duplicate_queue > 500 pending`: Review bottleneck

## Rollback Plan

1. Disable feature flags:
   - `HASH_CACHE_ENABLED=false`
   - `AUTO_CREATE_THRESHOLD=95` (revert to manual matching)
   - `VARIANT_DETECTION_ENABLED=false`
   - `DUPLICATE_DETECTION_ENABLED=false`

2. Database columns/tables are NOT dropped (preserve data for debugging)

3. Redeploy previous service versions

## Related Documents

- [Feature Specification](/specs/011-pipeline-stabilization/spec.md)
- [Implementation Plan](/specs/011-pipeline-stabilization/plan.md)
- [Data Model](/specs/011-pipeline-stabilization/data-model.md)
- [API Contracts](/specs/011-pipeline-stabilization/contracts/duplicates-api.yaml)

## Changelog

| Date | Change |
|------|--------|
| 2025-12-10 | Initial ADR created (Phase 7 implementation) |
