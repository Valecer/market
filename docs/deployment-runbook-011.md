# Deployment Runbook: Phase 11 - Pipeline Stabilization

**Feature:** 011-pipeline-stabilization  
**Date:** 2025-12-10  
**Version:** 1.0

## Overview

This runbook covers the deployment of Phase 11 (Data Pipeline Stabilization) features:
- Hash-based idempotent re-ingestion
- Auto-creation of products (<90% confidence)
- 3-level category hierarchy enforcement
- Variant detection integration
- Duplicate detection with admin review

## Pre-Deployment Checklist

### 1. Database Readiness

- [ ] Backup production database
- [ ] Verify migration file exists: `services/python-ingestion/migrations/versions/011_pipeline_stabilization_schema.py`
- [ ] Dry-run migration on staging: `alembic upgrade head --sql`
- [ ] Verify indexes created:
  - `idx_supplier_items_hash`
  - `idx_potential_duplicates_status`
  - `idx_potential_duplicates_product_id_1`
  - `idx_potential_duplicates_product_id_2`

### 2. Environment Variables

**Python Ingestion Service:**
```bash
# Add to .env
HASH_CACHE_ENABLED=false      # Start disabled
HASH_ALGORITHM=md5

# Database connection pooling (tune for production concurrency)
DB_POOL_SIZE=20                    # Base pool connections
DB_POOL_MAX_OVERFLOW=10            # Extra connections under load
DB_POOL_RECYCLE_SECONDS=3600       # Recycle connections hourly

# Error monitoring (optional, recommended for production)
SENTRY_DSN=https://your-dsn@sentry.io/project
SENTRY_TRACES_SAMPLE_RATE=0.1
```

**ML-Analyze Service:**
```bash
# Add to .env
AUTO_CREATE_THRESHOLD=90
VARIANT_DETECTION_ENABLED=false     # Start disabled
DUPLICATE_DETECTION_ENABLED=false   # Start disabled
DUPLICATE_SIMILARITY_THRESHOLD=85
DUPLICATE_PRICE_DIFF_THRESHOLD=20

# Error monitoring (optional, recommended for production)
SENTRY_DSN=https://your-dsn@sentry.io/project
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1
```

### 3. Service Dependencies

- [ ] Redis available and healthy
- [ ] PostgreSQL available with sufficient disk space
- [ ] Ollama service running (for ML operations)

## Deployment Steps

### Phase 1: Database Migration (Day 1)

1. **Enter maintenance mode** (if applicable)
   ```bash
   # Disable ingestion jobs
   docker-compose stop worker
   ```

2. **Run database migration**
   ```bash
   cd services/python-ingestion
   alembic upgrade head
   ```

3. **Verify migration**
   ```sql
   -- Check new columns
   SELECT column_name, data_type 
   FROM information_schema.columns 
   WHERE table_name IN ('supplier_items', 'categories', 'potential_duplicates');
   
   -- Verify category_level backfill
   SELECT category_level, COUNT(*) 
   FROM categories 
   GROUP BY category_level;
   ```

4. **Deploy services with features OFF**
   ```bash
   docker-compose up -d --build
   ```

### Phase 2: Enable Hash-Based Idempotency (Day 2)

1. **Enable feature flag**
   ```bash
   # python-ingestion .env
   HASH_CACHE_ENABLED=true
   ```

2. **Restart worker**
   ```bash
   docker-compose restart worker
   ```

3. **Monitor for 24 hours**
   - `hash_hit_rate` should be low initially (no cached hashes)
   - On re-ingestion: `hash_hit_rate` should climb to ≥70%

### Phase 3: Enable Auto-Creation (Day 3)

1. **Enable feature flag**
   ```bash
   # ml-analyze .env
   AUTO_CREATE_THRESHOLD=90
   ```

2. **Restart ml-analyze**
   ```bash
   docker-compose restart ml-analyze
   ```

3. **Monitor metrics**
   - `auto_creation_rate`: Expected 50-90%
   - Alert if >95% (matching degradation)

### Phase 4: Enable Duplicate Detection (Day 4)

1. **Enable feature flag**
   ```bash
   # ml-analyze .env
   DUPLICATE_DETECTION_ENABLED=true
   ```

2. **Restart ml-analyze**
   ```bash
   docker-compose restart ml-analyze
   ```

3. **Monitor duplicate queue**
   - `duplicate_queue_size`: Should be <500 pending
   - Review first 10-20 detections manually for quality

### Phase 5: Enable Variant Detection (Day 5)

1. **Enable feature flag**
   ```bash
   # ml-analyze .env
   VARIANT_DETECTION_ENABLED=true
   ```

2. **Restart ml-analyze**
   ```bash
   docker-compose restart ml-analyze
   ```

3. **Verify variant groups**
   ```sql
   SELECT COUNT(*) FROM products WHERE has_variants = true;
   SELECT COUNT(*) FROM product_variants;
   ```

## Rollback Procedures

### Scenario 1: Hash Hit Rate <50%

**Symptoms:** Re-ingestion not faster, high ML extraction volume

**Actions:**
```bash
# 1. Disable hash caching
HASH_CACHE_ENABLED=false

# 2. Restart worker
docker-compose restart worker

# 3. Investigate
# Check hash normalization logs
docker-compose logs worker | grep "hash_collision"
```

### Scenario 2: Auto-Creation Rate >95%

**Symptoms:** Almost all items creating new products, poor matching

**Actions:**
```bash
# 1. Raise threshold (revert to manual matching)
AUTO_CREATE_THRESHOLD=95

# 2. Restart ml-analyze
docker-compose restart ml-analyze

# 3. Investigate matching service
docker-compose logs ml-analyze | grep "match_score"
```

### Scenario 3: Duplicate Queue Overwhelmed (>500 pending)

**Symptoms:** Too many false positives, admin cannot keep up

**Actions:**
```bash
# 1. Temporarily disable detection
DUPLICATE_DETECTION_ENABLED=false

# 2. Restart ml-analyze
docker-compose restart ml-analyze

# 3. Optionally, raise threshold to 87%
DUPLICATE_SIMILARITY_THRESHOLD=87
```

### Scenario 4: Category Hierarchy Violations

**Symptoms:** Products not assigned to Level 3 categories

**Actions:**
```sql
-- Find incomplete hierarchies
SELECT id, name, category_level, needs_review
FROM categories
WHERE needs_review = true;

-- Manual fix: backfill category_level
UPDATE categories c
SET category_level = (
    SELECT COUNT(*)
    FROM categories AS parent
    WHERE parent.id = c.parent_id
) + 1
WHERE category_level IS NULL;
```

### Complete Rollback (Emergency)

If all features need to be disabled:

```bash
# 1. Disable all Phase 11 features
cat >> services/python-ingestion/.env << EOF
HASH_CACHE_ENABLED=false
EOF

cat >> services/ml-analyze/.env << EOF
AUTO_CREATE_THRESHOLD=95
VARIANT_DETECTION_ENABLED=false
DUPLICATE_DETECTION_ENABLED=false
EOF

# 2. Restart all services
docker-compose restart worker ml-analyze bun-api

# 3. DO NOT drop database columns/tables
# Data is preserved for debugging
```

## Monitoring Dashboard Setup

### Key Metrics to Track

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| `hash_hit_rate` | python-ingestion logs | <50% |
| `hash_miss_rate` | python-ingestion logs | >50% on re-ingestion |
| `auto_creation_rate` | ml-analyze logs | >95% |
| `duplicate_queue_size` | PostgreSQL query | >500 |
| `variant_groups_created` | ml-analyze logs | N/A (informational) |
| `category_compliance_rate` | PostgreSQL query | <100% |

### SQL Queries for Monitoring

```sql
-- Hash hit rate (last 24h)
-- Note: Requires adding metrics to a metrics table or parsing logs

-- Auto-creation rate
SELECT 
    DATE(created_at) as date,
    COUNT(*) FILTER (WHERE match_status = 'auto_created') as auto_created,
    COUNT(*) as total,
    ROUND(COUNT(*) FILTER (WHERE match_status = 'auto_created')::numeric / COUNT(*) * 100, 2) as rate
FROM supplier_items
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Duplicate queue status
SELECT status, COUNT(*) 
FROM potential_duplicates 
GROUP BY status;

-- Category compliance
SELECT 
    COALESCE(category_level::text, 'NULL') as level,
    COUNT(*) as count,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) as percentage
FROM categories
GROUP BY category_level
ORDER BY level;

-- Variant detection stats
SELECT 
    DATE(created_at) as date,
    COUNT(*) FILTER (WHERE has_variants = true) as products_with_variants,
    COUNT(*) as total_products
FROM products
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

## Post-Deployment Verification

### Day 1 Checklist
- [ ] All services healthy (`docker-compose ps`)
- [ ] No errors in logs (`docker-compose logs --tail=100`)
- [ ] Database migration applied successfully
- [ ] Admin can access /admin/duplicates page

### Week 1 Checklist
- [ ] `hash_hit_rate` ≥70% on re-ingestion
- [ ] `auto_creation_rate` between 50-90%
- [ ] `duplicate_queue_size` <500 pending
- [ ] No category hierarchy violations
- [ ] Variant groups being created correctly

### Week 2+ Checklist
- [ ] Review false positive rate in duplicate queue
- [ ] Tune thresholds if needed
- [ ] Monitor performance under production load
- [ ] Update documentation if behavior differs from expectations

## Support Contacts

- **On-call:** TBD
- **Database Admin:** TBD
- **ML/AI Issues:** TBD

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-12-10 | Initial runbook created | Development Team |
