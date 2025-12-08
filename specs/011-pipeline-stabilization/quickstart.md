# Quickstart: Data Pipeline Stabilization

**Feature:** 011-pipeline-stabilization

**Date:** 2025-12-09

**Estimated Setup Time:** 30 minutes

---

## Overview

This feature adds hash-based idempotency, automatic product creation, 3-level category hierarchy enforcement, and integrated variant detection to the data ingestion pipeline.

**Benefits:**
- ⚡ 60-80% faster re-ingestion for files with mostly unchanged rows
- 🎯 Zero manual matching for initial ingestion (auto-create + duplicate detection)
- 📊 Consistent catalog structure (3-level hierarchy)
- 🔗 Unified product presentation (variants grouped automatically)

---

## Prerequisites

- PostgreSQL 14+ running
- Python 3.12+ environment (ml-analyze, python-ingestion)
- Bun 1.0+ environment (bun-api)
- Docker Compose (for local development)

---

## Setup Instructions

### 1. Database Migration

Run the database migration to add new schema:

```bash
cd services/python-ingestion

# Activate virtual environment
source venv/bin/activate

# Run migration
alembic upgrade head
```

**Expected Output:**

```
INFO  [alembic.runtime.migration] Running upgrade 010 -> 011
INFO  [alembic.runtime.migration] Adding source_row_hash to supplier_items
INFO  [alembic.runtime.migration] Adding category_level to categories
INFO  [alembic.runtime.migration] Backfilling category levels
INFO  [alembic.runtime.migration] Creating potential_duplicates table
```

**Verification:**

```sql
-- Verify source_row_hash column exists
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'supplier_items' AND column_name = 'source_row_hash';

-- Verify category_level exists and is backfilled
SELECT category_level, COUNT(*)
FROM categories
GROUP BY category_level
ORDER BY category_level;

-- Expected output: Level 1, 2, 3 with counts

-- Verify potential_duplicates table exists
SELECT table_name
FROM information_schema.tables
WHERE table_name = 'potential_duplicates';
```

---

### 2. Environment Variables

Add new environment variables to your `.env` files:

**services/python-ingestion/.env:**

```bash
# Idempotency settings
HASH_CACHE_ENABLED=true          # Enable hash-based deduplication
HASH_ALGORITHM=md5                # Hashing algorithm (md5 | sha256)
```

**services/ml-analyze/.env:**

```bash
# Auto-creation settings
AUTO_CREATE_THRESHOLD=90          # Confidence threshold for auto-creation (0-100)
VARIANT_DETECTION_ENABLED=true    # Enable variant detection
DUPLICATE_DETECTION_ENABLED=true  # Enable duplicate detection

# Duplicate detection tuning
DUPLICATE_SIMILARITY_THRESHOLD=85 # Min similarity for duplicate flagging (0-100)
DUPLICATE_PRICE_DIFF_THRESHOLD=20 # Max price diff % for duplicates (0-100)
```

**services/bun-api/.env:**

```bash
# No new environment variables required
```

---

### 3. Install Dependencies

**Python Services (ml-analyze, python-ingestion):**

No new dependencies required (uses stdlib `hashlib`, existing `rapidfuzz` and `sqlalchemy`).

**TypeScript Services (bun-api, frontend):**

No new dependencies required (uses existing `@tanstack/react-query`, `zod`).

---

### 4. Start Services

**Docker Compose (Recommended):**

```bash
# From project root
docker-compose up -d

# Verify all services running
docker-compose ps

# Check logs
docker-compose logs -f ml-analyze python-ingestion bun-api
```

**Manual Start (Development):**

```bash
# Terminal 1: ml-analyze
cd services/ml-analyze
source venv/bin/activate
uvicorn src.api.main:app --reload --port 8001

# Terminal 2: python-ingestion worker
cd services/python-ingestion
source venv/bin/activate
arq src.tasks.worker.WorkerSettings

# Terminal 3: bun-api
cd services/bun-api
bun --watch src/index.ts

# Terminal 4: frontend
cd services/frontend
bun run dev
```

---

## Usage Guide

### 1. Hash-Based Idempotent Re-Ingestion

**Scenario:** Re-import a supplier file with mostly unchanged rows.

```bash
# First import (full extraction)
curl -X POST http://localhost:3000/api/v1/admin/sync \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "supplierId": "a3f2b91c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
    "sourceUrl": "https://docs.google.com/spreadsheets/d/SHEET_ID"
  }'

# Response:
{
  "jobId": "job-123",
  "status": "queued"
}

# Check job status
curl http://localhost:3000/api/v1/jobs/job-123

# Wait for completion (phase: complete)
# Metrics: total_rows: 100, hash_hits: 0, hash_misses: 100
```

**Re-import same file (most rows unchanged, 10 price updates):**

```bash
curl -X POST http://localhost:3000/api/v1/admin/sync \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "supplierId": "a3f2b91c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
    "sourceUrl": "https://docs.google.com/spreadsheets/d/SHEET_ID"
  }'

# Metrics: total_rows: 100, hash_hits: 90, hash_misses: 10
# Time: ~30 seconds (vs. ~5 minutes for full extraction)
```

**Verification:**

```sql
-- Check hash hit rate
SELECT
  COUNT(*) FILTER (WHERE source_row_hash IS NOT NULL) AS hashed_rows,
  COUNT(*) AS total_rows,
  ROUND(100.0 * COUNT(*) FILTER (WHERE source_row_hash IS NOT NULL) / COUNT(*), 2) AS hash_coverage_pct
FROM supplier_items
WHERE supplier_id = 'a3f2b91c-4d5e-6f7a-8b9c-0d1e2f3a4b5c';

-- Expected: hash_coverage_pct: 100.00
```

---

### 2. Automatic Product Creation

**Scenario:** Import new supplier catalog (200 items, none match existing products above 90%).

```bash
curl -X POST http://localhost:3000/api/v1/admin/sync \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "supplierId": "new-supplier-id",
    "sourceUrl": "https://docs.google.com/spreadsheets/d/NEW_SHEET_ID"
  }'

# Poll job status until complete
# Metrics:
#   extracted: 200,
#   auto_created: 195,
#   auto_matched: 0,
#   duplicates_flagged: 5
```

**Verification:**

```sql
-- Check auto-created products
SELECT
  COUNT(*) AS auto_created_count,
  COUNT(*) FILTER (WHERE internal_sku LIKE 'AUTO-%') AS auto_sku_count
FROM products
WHERE id IN (
  SELECT product_id
  FROM supplier_items
  WHERE match_status = 'auto_created'
  AND supplier_id = 'new-supplier-id'
);

-- Expected: Both counts should match (all auto-created products have AUTO-* SKUs)
```

---

### 3. 3-Level Category Hierarchy

**Scenario:** View category tree structure.

```sql
-- Query category hierarchy
WITH RECURSIVE category_tree AS (
  -- Root categories (Level 1)
  SELECT id, name, parent_id, category_level, name::TEXT AS path
  FROM categories
  WHERE parent_id IS NULL

  UNION ALL

  -- Children categories
  SELECT c.id, c.name, c.parent_id, c.category_level,
         ct.path || ' > ' || c.name
  FROM categories c
  INNER JOIN category_tree ct ON c.parent_id = ct.id
)
SELECT category_level, path, id
FROM category_tree
ORDER BY path;

-- Example output:
-- level | path                                        | id
-- ------|---------------------------------------------|------
-- 1     | Electric Transport                          | xxx
-- 2     | Electric Transport > Motorcycles            | yyy
-- 3     | Electric Transport > Motorcycles > Shtenli  | zzz
```

**Check for incomplete hierarchies:**

```sql
SELECT
  category_level,
  COUNT(*) AS count,
  COUNT(*) FILTER (WHERE needs_review = true) AS needs_review_count
FROM categories
GROUP BY category_level
ORDER BY category_level;

-- Expected: needs_review_count > 0 only for Level 1 or 2 (incomplete hierarchies)
```

---

### 4. Variant Detection

**Scenario:** Check variant grouping for auto-created products.

```sql
-- Find products with variants
SELECT
  p.id,
  p.name,
  p.has_variants,
  p.variant_schema,
  (SELECT COUNT(*) FROM product_variants WHERE product_id = p.id) AS variant_count
FROM products p
WHERE p.has_variants = true
ORDER BY p.created_at DESC
LIMIT 10;

-- Example output:
-- id  | name                | has_variants | variant_schema          | variant_count
-- ----|---------------------|--------------|-------------------------|---------------
-- xxx | Battery 48V Shtenli | true         | [{"key":"capacity"}]    | 2

-- View variants for a product
SELECT
  variant_key,
  variant_attributes
FROM product_variants
WHERE product_id = 'xxx'
ORDER BY display_order;

-- Example output:
-- variant_key | variant_attributes
-- ------------|--------------------
-- 20Ah        | {"capacity":"20Ah"}
-- 30Ah        | {"capacity":"30Ah"}
```

---

### 5. Potential Duplicate Management

**Scenario:** Review and merge potential duplicates via Admin UI.

**Web UI:**

1. Navigate to `http://localhost:5173/admin/duplicates`
2. View pending duplicates (side-by-side comparison)
3. Click "Merge" on a duplicate pair
4. Select which product to keep
5. Confirm merge

**API (Manual Testing):**

```bash
# List pending duplicates
curl http://localhost:3000/api/v1/admin/duplicates?status=pending \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Response:
{
  "duplicates": [
    {
      "id": "dup-1",
      "product1": {
        "id": "prod-a",
        "name": "LED Light 50W",
        "category": "Lighting > LED > Generic",
        "price": 1500,
        "supplierCount": 2
      },
      "product2": {
        "id": "prod-b",
        "name": "LED Lamp 50W",
        "category": "Lighting > LED > Generic",
        "price": 1550,
        "supplierCount": 1
      },
      "similarityScore": 87.5,
      "detectionReason": "auto_creation_similarity",
      "status": "pending",
      "createdAt": "2025-12-09T10:30:00Z"
    }
  ],
  "total": 5
}

# Merge duplicates (keep prod-a, archive prod-b)
curl -X PATCH http://localhost:3000/api/v1/admin/duplicates/dup-1/merge \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "keepProductId": "prod-a",
    "archiveProductId": "prod-b"
  }'

# Response:
{
  "success": true,
  "mergedProduct": {
    "id": "prod-a",
    "name": "LED Light 50W",
    "supplierItemCount": 3
  }
}
```

---

## Testing

### Unit Tests

```bash
# Python (python-ingestion)
cd services/python-ingestion
pytest tests/services/test_idempotency_service.py -v

# Python (ml-analyze)
cd services/ml-analyze
pytest tests/services/test_auto_creation_service.py -v
pytest tests/services/test_category_hierarchy_service.py -v
pytest tests/services/test_duplicate_detection_service.py -v

# TypeScript (bun-api)
cd services/bun-api
bun test src/controllers/admin/duplicates.controller.test.ts
```

### Integration Tests

```bash
# Full pipeline test
cd services/python-ingestion
pytest tests/integration/test_idempotent_reingestion.py -v
```

---

## Monitoring & Metrics

**Key Metrics to Monitor:**

```bash
# Hash hit rate (target: ≥70%)
SELECT
  supplier_id,
  COUNT(*) FILTER (WHERE last_ingested_at > NOW() - INTERVAL '1 day') AS recent_ingestions,
  ROUND(100.0 * COUNT(*) FILTER (WHERE source_row_hash IS NOT NULL) / COUNT(*), 2) AS hash_coverage_pct
FROM supplier_items
GROUP BY supplier_id
ORDER BY recent_ingestions DESC;

# Auto-creation rate (target: 50-90%)
SELECT
  supplier_id,
  COUNT(*) AS total_items,
  COUNT(*) FILTER (WHERE match_status = 'auto_created') AS auto_created,
  ROUND(100.0 * COUNT(*) FILTER (WHERE match_status = 'auto_created') / COUNT(*), 2) AS auto_creation_pct
FROM supplier_items
WHERE created_at > NOW() - INTERVAL '1 day'
GROUP BY supplier_id;

# Duplicate queue size (alert if >500)
SELECT
  status,
  COUNT(*) AS count
FROM potential_duplicates
GROUP BY status;

# Category hierarchy compliance (target: 100%)
SELECT
  category_level,
  COUNT(*) AS count,
  COUNT(*) FILTER (WHERE needs_review = false) AS compliant_count,
  ROUND(100.0 * COUNT(*) FILTER (WHERE needs_review = false) / COUNT(*), 2) AS compliance_pct
FROM categories
GROUP BY category_level
ORDER BY category_level;
```

---

## Troubleshooting

### Issue 1: Hash Hit Rate <50%

**Symptom:** Re-ingestion is not significantly faster than initial ingestion.

**Diagnosis:**

```sql
-- Check if hashes are being computed
SELECT COUNT(*) FILTER (WHERE source_row_hash IS NULL) AS unhashed_rows
FROM supplier_items
WHERE created_at > NOW() - INTERVAL '1 day';

-- If unhashed_rows > 0, check environment variable
```

**Solution:**

1. Verify `HASH_CACHE_ENABLED=true` in python-ingestion `.env`
2. Restart python-ingestion worker
3. Check logs for hash computation errors

---

### Issue 2: Auto-Creation Rate >95%

**Symptom:** Almost all new items create new products (matching service degraded).

**Diagnosis:**

```sql
-- Check match confidence distribution
SELECT
  FLOOR(match_score / 10) * 10 AS confidence_bucket,
  COUNT(*) AS count
FROM supplier_items
WHERE match_score IS NOT NULL
GROUP BY confidence_bucket
ORDER BY confidence_bucket DESC;
```

**Solution:**

1. Check if matching service (ml-analyze) is running
2. Verify product embeddings are up-to-date
3. Consider lowering `AUTO_CREATE_THRESHOLD` to 85 temporarily
4. Investigate matching logic for degradation

---

### Issue 3: Duplicate Queue Overwhelmed (>500 Pending)

**Symptom:** Too many potential duplicates flagged, false positive rate high.

**Diagnosis:**

```sql
-- Check similarity score distribution
SELECT
  FLOOR(similarity_score / 5) * 5 AS similarity_bucket,
  COUNT(*) AS count
FROM potential_duplicates
WHERE status = 'pending'
GROUP BY similarity_bucket
ORDER BY similarity_bucket DESC;
```

**Solution:**

1. Increase `DUPLICATE_SIMILARITY_THRESHOLD` from 85 to 87
2. Decrease `DUPLICATE_PRICE_DIFF_THRESHOLD` from 20 to 15
3. Batch review: Dismiss all duplicates with similarity <86% and price diff >18%

```sql
-- Batch dismiss low-confidence duplicates
UPDATE potential_duplicates
SET status = 'dismissed', reviewed_at = NOW()
WHERE status = 'pending'
AND (similarity_score < 86 OR ABS(price_diff) > 18);
```

---

## Next Steps

After successful setup:

1. **Run a test ingestion** with a small file (10-20 rows) to verify all features work
2. **Monitor metrics** for the first week to tune thresholds
3. **Review duplicate queue** daily for the first week to assess false positive rate
4. **Complete category hierarchy** for any items flagged with `needs_review=true`
5. **Train team** on duplicate management UI and workflows

---

## Support

- **Documentation:** [Feature Specification](./spec.md), [Implementation Plan](./plan.md)
- **API Reference:** [OpenAPI Spec](./contracts/duplicates-api.yaml)
- **Troubleshooting:** See above or check logs in Docker containers
- **Contact:** Dev team via Slack #marketbel-dev

---

**Happy Pipelining! 🚀**
