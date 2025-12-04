# Migration Checklist: Semantic ETL Pipeline

**Document Version:** 1.0.0

**Last Updated:** 2025-12-04

**Feature:** Phase 9 - Semantic ETL with LLM-Based Extraction

---

## Overview

This checklist guides the migration from legacy parsing to the Semantic ETL pipeline. Follow each step in order. Do not skip steps.

**Estimated Time:** 2-4 hours for full migration

**Rollback Time:** < 5 minutes (see [rollback.md](./rollback.md))

---

## Pre-Migration Checklist

### Infrastructure Requirements

- [ ] **PostgreSQL 16+** with pgvector extension installed
- [ ] **Redis 7+** running and accessible
- [ ] **Ollama** with `llama3` model available
- [ ] **Docker Compose** v2.0+ installed
- [ ] **Shared volume** `/shared/uploads` mounted on worker and ml-analyze

### Verify Ollama Setup

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Verify llama3 model is available
ollama list | grep llama3

# If not installed, pull the model
ollama pull llama3
```

### Database Backup

- [ ] **Create database backup before migration:**

```bash
# Backup database
docker exec marketbel-postgres pg_dump -U marketbel_user marketbel > backup_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -la backup_*.sql
```

---

## Phase 1: Database Migrations

### 1.1 Categories Table Updates

- [ ] Run category hierarchy migration:

```sql
-- Check if columns already exist
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'categories' 
AND column_name IN ('parent_id', 'needs_review', 'is_active', 'supplier_id');

-- If not, run migration
ALTER TABLE categories 
ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES categories(id),
ADD COLUMN IF NOT EXISTS needs_review BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS supplier_id UUID REFERENCES suppliers(id),
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Create index for parent lookups
CREATE INDEX IF NOT EXISTS idx_categories_parent_id ON categories(parent_id);
CREATE INDEX IF NOT EXISTS idx_categories_needs_review ON categories(needs_review) WHERE needs_review = true;
```

### 1.2 Parsing Logs Enhancement

- [ ] Run parsing logs migration:

```sql
-- Add semantic ETL columns to parsing_logs
ALTER TABLE parsing_logs
ADD COLUMN IF NOT EXISTS chunk_id INTEGER,
ADD COLUMN IF NOT EXISTS extraction_phase VARCHAR(50),
ADD COLUMN IF NOT EXISTS error_type VARCHAR(50);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_parsing_logs_chunk_id ON parsing_logs(chunk_id);
CREATE INDEX IF NOT EXISTS idx_parsing_logs_error_type ON parsing_logs(error_type);
```

### 1.3 Suppliers Table Feature Flag

- [ ] Add supplier-level feature flag:

```sql
-- Add feature flag column
ALTER TABLE suppliers 
ADD COLUMN IF NOT EXISTS use_semantic_etl BOOLEAN DEFAULT false;

-- Verify column exists
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'suppliers' AND column_name = 'use_semantic_etl';
```

---

## Phase 2: Environment Configuration

### 2.1 Update Docker Compose

- [ ] Verify `docker-compose.yml` has semantic ETL variables:

```yaml
# ml-analyze service should have:
environment:
  USE_SEMANTIC_ETL: ${USE_SEMANTIC_ETL:-false}
  FUZZY_MATCH_THRESHOLD: ${FUZZY_MATCH_THRESHOLD:-85}
  CHUNK_SIZE_ROWS: ${CHUNK_SIZE_ROWS:-250}
  CHUNK_OVERLAP_ROWS: ${CHUNK_OVERLAP_ROWS:-40}
  OLLAMA_TEMPERATURE: ${OLLAMA_TEMPERATURE:-0.2}
```

### 2.2 Create/Update .env File

- [ ] Add semantic ETL configuration:

```bash
# Add to .env file
cat >> .env << 'EOF'
# Phase 9: Semantic ETL Configuration
USE_SEMANTIC_ETL=false
FUZZY_MATCH_THRESHOLD=85
CHUNK_SIZE_ROWS=250
CHUNK_OVERLAP_ROWS=40
OLLAMA_TEMPERATURE=0.2
OLLAMA_LLM_MODEL=llama3
EOF
```

### 2.3 Verify Configuration

- [ ] Check environment variables are loaded:

```bash
# Rebuild and start services
docker-compose build ml-analyze
docker-compose up -d ml-analyze

# Check environment
docker exec marketbel-ml-analyze env | grep -E "(SEMANTIC|FUZZY|CHUNK|OLLAMA)"
```

---

## Phase 3: Service Deployment

### 3.1 Deploy Updated Services

- [ ] Build and deploy ml-analyze:

```bash
docker-compose build ml-analyze
docker-compose up -d ml-analyze
```

- [ ] Build and deploy worker:

```bash
docker-compose build worker
docker-compose up -d worker
```

- [ ] Build and deploy bun-api:

```bash
docker-compose build bun-api
docker-compose up -d bun-api
```

- [ ] Build and deploy frontend:

```bash
docker-compose build frontend
docker-compose up -d frontend
```

### 3.2 Verify Service Health

- [ ] All services healthy:

```bash
docker-compose ps

# Expected output: all services "healthy"
```

- [ ] Check ml-analyze health endpoint:

```bash
curl -s http://localhost:8001/health | jq .
# Expected: {"status": "healthy", ...}
```

- [ ] Check bun-api health:

```bash
curl -s http://localhost:3000/health | jq .
```

---

## Phase 4: Validation Testing

### 4.1 Test with Legacy Processing (Feature Flag Off)

- [ ] Upload test file with legacy processing:

```bash
# Ensure USE_SEMANTIC_ETL=false
curl -X POST http://localhost:3000/admin/suppliers/1/sync \
  -H "Authorization: Bearer YOUR_TOKEN"
```

- [ ] Verify job completes successfully with legacy parser

### 4.2 Test with Semantic ETL (Single Supplier)

- [ ] Enable for one test supplier:

```sql
UPDATE suppliers SET use_semantic_etl = true WHERE id = 1;
```

- [ ] Upload test file:

```bash
curl -X POST http://localhost:3000/admin/suppliers/1/sync \
  -H "Authorization: Bearer YOUR_TOKEN"
```

- [ ] Monitor job phases:

```bash
watch -n 5 'curl -s http://localhost:3000/admin/sync/status | jq ".jobs[0]"'
```

- [ ] Verify expected phases appear: `downloading` → `analyzing` → `extracting` → `normalizing` → `complete`

### 4.3 Validate Extraction Results

- [ ] Check extracted products:

```sql
SELECT COUNT(*) as products_extracted
FROM supplier_items
WHERE supplier_id = (SELECT id FROM suppliers WHERE id = 1)
AND created_at > NOW() - INTERVAL '1 hour';
```

- [ ] Check categories created:

```sql
SELECT COUNT(*) as categories_created, 
       SUM(CASE WHEN needs_review THEN 1 ELSE 0 END) as needs_review_count
FROM categories
WHERE created_at > NOW() - INTERVAL '1 hour';
```

- [ ] Verify extraction accuracy (manual spot check):
  - [ ] Product names are correct
  - [ ] Prices are correct
  - [ ] Categories are reasonable

---

## Phase 5: Parallel Run (1 Week)

### 5.1 Enable for Subset of Suppliers

- [ ] Enable for 10-20% of suppliers:

```sql
-- Enable for specific suppliers
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE id IN (1, 2, 3, 4, 5);
```

### 5.2 Monitor Metrics Daily

- [ ] **Day 1:** Check extraction success rate > 95%
- [ ] **Day 2:** Check category match rate > 80%
- [ ] **Day 3:** Check processing time < 3 min for 500 rows
- [ ] **Day 4:** Check job failure rate < 5%
- [ ] **Day 5:** Check category review queue manageable
- [ ] **Day 6:** Review any error logs
- [ ] **Day 7:** Final validation before full rollout

### 5.3 Monitoring Queries

```sql
-- Extraction success rate
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_jobs,
    SUM(CASE WHEN phase = 'complete' THEN 1 ELSE 0 END) as successful,
    ROUND(100.0 * SUM(CASE WHEN phase = 'complete' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM sync_jobs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Category match rate (check parsing_logs)
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_categories,
    SUM(CASE WHEN error_type IS NULL THEN 1 ELSE 0 END) as matched,
    ROUND(100.0 * SUM(CASE WHEN error_type IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as match_rate
FROM parsing_logs
WHERE extraction_phase = 'normalizing'
AND created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

---

## Phase 6: Full Rollout

### 6.1 Enable Globally

- [ ] Enable for all suppliers:

```sql
UPDATE suppliers SET use_semantic_etl = true;
```

- [ ] Or enable via environment variable:

```bash
# Update .env
sed -i 's/USE_SEMANTIC_ETL=false/USE_SEMANTIC_ETL=true/' .env

# Restart services
docker-compose restart ml-analyze worker
```

### 6.2 Post-Rollout Monitoring

- [ ] Set up alerting for:
  - [ ] Extraction success rate < 90%
  - [ ] Job failure rate > 10%
  - [ ] Processing time > 5 min
  - [ ] Category review queue > 100 items

### 6.3 Remove Legacy Code (Optional)

After 2 weeks of stable operation:

- [ ] Archive legacy parser code
- [ ] Update documentation
- [ ] Remove legacy-specific feature flags

---

## Troubleshooting

### Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| LLM Timeout | Jobs stuck in `extracting` | Reduce `CHUNK_SIZE_ROWS` to 150 |
| Low Match Rate | Many `needs_review` categories | Lower `FUZZY_MATCH_THRESHOLD` to 80 |
| Memory Issues | ml-analyze OOM kills | Increase Docker memory limit |
| Slow Processing | > 5 min for 500 rows | Check Ollama GPU availability |

### Emergency Rollback

If critical issues arise:

```bash
# Quick disable
docker exec marketbel-postgres psql -U marketbel_user -d marketbel \
  -c "UPDATE suppliers SET use_semantic_etl = false;"

docker-compose restart ml-analyze worker
```

See [rollback.md](./rollback.md) for detailed procedure.

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Development Lead | | | |
| QA Engineer | | | |
| DevOps Engineer | | | |
| Product Owner | | | |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-04 | AI Assistant | Initial document |
