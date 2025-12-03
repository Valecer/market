# ML-Analyze Service Rollback Procedures

## Overview

This document provides rollback procedures for the ML-Analyze service when deployments fail or issues are detected in production.

## Quick Reference

| Scenario | Action | Time |
|----------|--------|------|
| Bad deployment | [Container Rollback](#1-container-rollback) | ~1 min |
| Database migration issue | [Migration Rollback](#2-database-migration-rollback) | ~5 min |
| Data corruption | [Data Recovery](#3-data-recovery) | ~15 min |
| Complete service failure | [Full Rollback](#4-full-rollback) | ~30 min |

## Rollback Procedures

### 1. Container Rollback

**When:** API returns 5xx errors, health check failing, application crash

#### Docker Compose

```bash
# Stop current container
docker-compose stop ml-analyze

# Pull previous image version
docker-compose pull ml-analyze:previous-tag

# Or use specific version
docker-compose up -d ml-analyze --no-build

# Verify health
curl http://localhost:8001/health
```

#### Kubernetes

```bash
# View deployment history
kubectl rollout history deployment/ml-analyze

# Rollback to previous revision
kubectl rollout undo deployment/ml-analyze

# Or rollback to specific revision
kubectl rollout undo deployment/ml-analyze --to-revision=2

# Verify status
kubectl rollout status deployment/ml-analyze
```

### 2. Database Migration Rollback

**When:** Migration failed, data schema issues, performance regression

#### Check Current Migration

```bash
cd services/python-ingestion
source venv/bin/activate

# View current revision
alembic current

# View migration history
alembic history --verbose
```

#### Rollback Migrations

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade abc123def

# Rollback all Phase 7 migrations
alembic downgrade 006  # Pre-Phase 7 revision
```

#### Phase 7 Specific Migrations

| Migration | Action | Impact |
|-----------|--------|--------|
| `008_create_product_embeddings.py` | `alembic downgrade -1` | Drops embeddings table |
| `007_enable_pgvector.py` | `alembic downgrade -1` | Removes pgvector extension |

**Warning:** Downgrading `007_enable_pgvector.py` will fail if embeddings exist. Drop the table first:

```sql
DROP TABLE IF EXISTS product_embeddings CASCADE;
```

### 3. Data Recovery

**When:** Embeddings corrupted, incorrect matching results

#### Clear Embeddings (Regenerate)

```sql
-- Clear all embeddings (can regenerate)
TRUNCATE TABLE product_embeddings;

-- Clear embeddings for specific supplier
DELETE FROM product_embeddings 
WHERE supplier_item_id IN (
  SELECT id FROM supplier_items 
  WHERE supplier_id = 'supplier-uuid'
);
```

#### Revert Automatic Matches

```sql
-- Find items matched by ml-analyze within time window
SELECT si.id, si.product_id, si.name
FROM supplier_items si
WHERE si.product_id IS NOT NULL
  AND si.updated_at > '2024-01-15 10:00:00'
  AND EXISTS (
    SELECT 1 FROM parsing_logs pl 
    WHERE pl.supplier_id = si.supplier_id
    AND pl.details->>'source' = 'ml-analyze'
  );

-- Revert matches (set back to pending)
UPDATE supplier_items
SET product_id = NULL, 
    status = 'pending_match',
    updated_at = NOW()
WHERE product_id IS NOT NULL
  AND updated_at > '2024-01-15 10:00:00';
```

#### Clear Review Queue

```sql
-- Remove entries added by ml-analyze
DELETE FROM match_review_queue
WHERE created_at > '2024-01-15 10:00:00'
  AND metadata->>'source' = 'ml-analyze';
```

### 4. Full Rollback

**When:** Complete service failure, need to restore previous state

#### Step 1: Stop ML-Analyze

```bash
docker-compose stop ml-analyze
```

#### Step 2: Rollback Database

```bash
cd services/python-ingestion
source venv/bin/activate

# Rollback all Phase 7 migrations
alembic downgrade pre_phase7_revision
```

#### Step 3: Clear Related Data

```sql
-- Clear all ML-Analyze artifacts
DROP TABLE IF EXISTS product_embeddings CASCADE;
DROP EXTENSION IF EXISTS vector CASCADE;

-- Clear parsing logs from ml-analyze
DELETE FROM parsing_logs 
WHERE details->>'source' = 'ml-analyze';

-- Clear review queue entries
DELETE FROM match_review_queue
WHERE metadata->>'source' = 'ml-analyze';
```

#### Step 4: Clear Redis Jobs

```bash
# Connect to Redis
redis-cli -h redis-host -p 6379 -a password

# Clear ml-analyze job keys
KEYS ml-analyze:job:*
DEL ml-analyze:job:*

# Clear arq queue
KEYS arq:queue:ml-analyze
DEL arq:queue:ml-analyze
```

#### Step 5: Verify System State

```bash
# Check other services still healthy
curl http://localhost:3000/health  # bun-api
curl http://localhost:5173/health  # frontend

# Verify database connectivity
psql $DATABASE_URL -c "SELECT 1;"
```

## Recovery Procedures

### Regenerate Embeddings

After rollback, embeddings can be regenerated:

```bash
# Via API
curl -X POST http://localhost:8001/analyze/merge \
  -H "Content-Type: application/json" \
  -d '{"limit": 1000}'

# Monitor job progress
curl http://localhost:8001/analyze/status/{job_id}
```

### Restore from Backup

If backups are available:

```bash
# Restore PostgreSQL
pg_restore -U user -d marketbel backup.dump

# Restore specific table
pg_restore -U user -d marketbel -t product_embeddings backup.dump
```

## Health Verification Checklist

After any rollback:

- [ ] API returns 200 on `/health`
- [ ] Database connections working
- [ ] Redis connectivity verified
- [ ] Other services unaffected (bun-api, worker)
- [ ] No 5xx errors in logs
- [ ] Job queue processing (if applicable)

## Incident Response

### Severity Levels

| Level | Definition | Response Time |
|-------|------------|---------------|
| P1 | Complete service outage | 15 minutes |
| P2 | Degraded performance | 1 hour |
| P3 | Non-critical feature broken | 4 hours |
| P4 | Minor issue | Next business day |

### Communication Template

```
INCIDENT: ML-Analyze Service [P1/P2/P3/P4]
STATUS: [Investigating/Identified/Resolved]
IMPACT: [Description of user impact]
START: [Timestamp]
ETA: [Resolution estimate]
ACTIONS: [Steps being taken]
```

## Prevention

### Pre-Deployment Checklist

- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Check type errors: `mypy src/ --strict`
- [ ] Review migration: `alembic upgrade --sql head`
- [ ] Test in staging environment
- [ ] Prepare rollback commands

### Monitoring Alerts

Set up alerts for:
- Health check failures (2+ consecutive)
- Error rate > 5%
- Response time p95 > 2s
- Memory usage > 85%
- Database connection pool exhaustion

## Contact

For escalation:
1. Check #ml-analyze Slack channel
2. Review recent deployments in CI/CD
3. Consult [DEPLOYMENT.md](./DEPLOYMENT.md) for configuration details

