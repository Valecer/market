# Rollback Procedure: Semantic ETL Pipeline

**Document Version:** 1.0.0

**Last Updated:** 2025-12-04

**Feature:** Phase 9 - Semantic ETL with LLM-Based Extraction

---

## Overview

This document describes the rollback procedure for the Semantic ETL pipeline. The system is designed with instant rollback capability through feature flags, with no data migration required.

**Key Design Decision:** Both legacy and semantic ETL systems write to the same database tables (`supplier_items`, `categories`), enabling instant rollback without data migration.

---

## Trigger Conditions

Initiate rollback when ANY of the following conditions are met:

| Condition | Threshold | Monitoring |
|-----------|-----------|------------|
| Extraction accuracy | < 90% | `extraction_success_rate` metric |
| Job failure rate | > 10% | `job_failure_rate` metric |
| LLM service unavailable | > 1 hour | Ollama health check |
| Category match rate | < 70% | `category_match_rate` metric |
| Processing time | > 5 minutes for 500 rows | `processing_time_seconds` metric |
| Critical errors | Any unrecoverable error | Error logs |

---

## Pre-Rollback Assessment

Before initiating rollback, assess the situation:

### 1. Check Service Health

```bash
# Check all service statuses
docker-compose ps

# Check ml-analyze health
curl -s http://localhost:8001/health | jq .

# Check Ollama availability
curl -s http://localhost:11434/api/tags | jq .
```

### 2. Review Recent Logs

```bash
# Check ml-analyze logs for errors
docker-compose logs --tail=100 ml-analyze | grep -E "(ERROR|CRITICAL|Exception)"

# Check worker logs
docker-compose logs --tail=100 worker | grep -E "(ERROR|CRITICAL)"

# Check extraction success rate
docker-compose logs ml-analyze | grep "extraction_success_rate" | tail -10
```

### 3. Verify Database State

```sql
-- Check recent job failures
SELECT 
    id,
    phase,
    error,
    created_at
FROM sync_jobs
WHERE phase = 'failed'
AND created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC
LIMIT 10;

-- Check category review queue
SELECT COUNT(*) as pending_review
FROM categories
WHERE needs_review = true;
```

---

## Rollback Steps

### Step 1: Disable Semantic ETL Feature Flag

**Option A: Environment Variable (Recommended for Development)**

```bash
# Update .env file
echo "USE_SEMANTIC_ETL=false" >> .env

# Or edit docker-compose override
cat >> docker-compose.override.yml << 'EOF'
services:
  ml-analyze:
    environment:
      USE_SEMANTIC_ETL: "false"
EOF
```

**Option B: Database Flag (Recommended for Production)**

```sql
-- Disable for ALL suppliers
UPDATE suppliers
SET use_semantic_etl = false
WHERE use_semantic_etl = true;

-- Verify
SELECT COUNT(*) as still_enabled
FROM suppliers
WHERE use_semantic_etl = true;
-- Expected: 0
```

### Step 2: Restart Affected Services

```bash
# Restart ml-analyze and worker services
docker-compose restart ml-analyze worker

# Verify services are healthy
docker-compose ps
```

### Step 3: Cancel In-Progress Semantic ETL Jobs

```sql
-- Mark in-progress semantic ETL jobs as cancelled
UPDATE sync_jobs
SET 
    phase = 'cancelled',
    error = 'Rollback: Semantic ETL disabled',
    completed_at = NOW()
WHERE phase IN ('analyzing', 'extracting', 'normalizing')
AND created_at > NOW() - INTERVAL '24 hours';

-- Count affected jobs
SELECT COUNT(*) as cancelled_jobs
FROM sync_jobs
WHERE phase = 'cancelled'
AND error LIKE 'Rollback:%';
```

### Step 4: Clear Redis Job State (Optional)

Only if there are stuck jobs:

```bash
# Connect to Redis
docker exec -it marketbel-redis redis-cli -a dev_redis_password

# List semantic ETL job keys
KEYS job:*

# Delete specific job state
DEL job:YOUR_JOB_ID

# Or clear all job states (CAUTION: affects all jobs)
# FLUSHDB
```

### Step 5: Verify Rollback

```bash
# Test file upload with legacy processing
curl -X POST http://localhost:3000/admin/suppliers \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test_file.xlsx"

# Check job uses legacy processing
curl http://localhost:3000/admin/sync/status/YOUR_JOB_ID | jq .
# Should NOT show semantic ETL phases
```

---

## Post-Rollback Validation

### 1. Verify Legacy Processing Works

```bash
# Upload a test file
curl -X POST http://localhost:3000/admin/suppliers/1/sync \
  -H "Authorization: Bearer YOUR_TOKEN"

# Monitor job progress
watch -n 5 'curl -s http://localhost:3000/admin/sync/status | jq .'
```

### 2. Check System Metrics

```bash
# Check worker is processing jobs
docker-compose logs --tail=50 worker

# Verify no semantic ETL logs appear
docker-compose logs ml-analyze | grep -c "semantic_etl"
# Expected: 0 (or only historical entries)
```

### 3. Verify Database Integrity

```sql
-- Check recent supplier_items insertions
SELECT 
    COUNT(*) as recent_items,
    MIN(created_at) as earliest,
    MAX(created_at) as latest
FROM supplier_items
WHERE created_at > NOW() - INTERVAL '1 hour';

-- Verify no orphaned categories
SELECT COUNT(*) as orphaned
FROM categories c
WHERE c.parent_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM categories p WHERE p.id = c.parent_id
);
-- Expected: 0
```

---

## Recovery After Rollback

### Investigating Root Cause

1. **Check extraction logs:**

   ```bash
   docker-compose logs ml-analyze 2>&1 | grep -A 5 "extraction_error"
   ```

2. **Review failed jobs:**

   ```sql
   SELECT 
       id,
       supplier_id,
       error,
       error_details,
       created_at
   FROM sync_jobs
   WHERE phase = 'failed'
   ORDER BY created_at DESC
   LIMIT 20;
   ```

3. **Check LLM performance:**

   ```bash
   # Test Ollama directly
   curl http://localhost:11434/api/generate \
     -d '{"model": "llama3", "prompt": "Hello", "stream": false}'
   ```

### Re-enabling Semantic ETL

After fixing the root cause:

1. **Enable for a single test supplier first:**

   ```sql
   UPDATE suppliers
   SET use_semantic_etl = true
   WHERE id = YOUR_TEST_SUPPLIER_ID;
   ```

2. **Monitor the test:**

   ```bash
   # Watch job progress
   curl -s http://localhost:3000/admin/sync/status | jq '.jobs[] | select(.supplier_id == YOUR_TEST_SUPPLIER_ID)'
   ```

3. **If successful, enable globally:**

   ```sql
   UPDATE suppliers
   SET use_semantic_etl = true;
   ```

---

## Emergency Contacts

| Role | Contact | When to Escalate |
|------|---------|------------------|
| On-Call Engineer | [TBD] | Service down > 15 min |
| Database Admin | [TBD] | Data integrity issues |
| ML/AI Lead | [TBD] | LLM extraction issues |

---

## Appendix: Quick Reference Commands

```bash
# === QUICK ROLLBACK ===
# 1. Disable feature flag
docker exec marketbel-postgres psql -U marketbel_user -d marketbel \
  -c "UPDATE suppliers SET use_semantic_etl = false;"

# 2. Restart services
docker-compose restart ml-analyze worker

# 3. Verify
docker-compose logs --tail=20 ml-analyze

# === QUICK RECOVERY ===
# 1. Re-enable feature flag
docker exec marketbel-postgres psql -U marketbel_user -d marketbel \
  -c "UPDATE suppliers SET use_semantic_etl = true WHERE id = 1;"

# 2. Restart services
docker-compose restart ml-analyze worker
```

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-04 | AI Assistant | Initial document |
