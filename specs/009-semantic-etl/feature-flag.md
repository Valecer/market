# Feature Flag Guide: Semantic ETL Pipeline

**Document Version:** 1.0.0

**Last Updated:** 2025-12-04

**Feature:** Phase 9 - Semantic ETL with LLM-Based Extraction

---

## Overview

The Semantic ETL pipeline uses a two-level feature flag system:

1. **Global Flag** (`USE_SEMANTIC_ETL`): Environment variable enabling/disabling the feature system-wide
2. **Supplier Flag** (`use_semantic_etl`): Database column enabling/disabling per supplier

This design allows gradual rollout and instant rollback.

---

## Feature Flag Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Feature Flag Decision Flow                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Job Request                                                        │
│       │                                                              │
│       ▼                                                              │
│   ┌──────────────────────────────┐                                  │
│   │ Global Flag: USE_SEMANTIC_ETL │                                  │
│   │      (Environment Var)        │                                  │
│   └──────────────┬───────────────┘                                  │
│                  │                                                   │
│        ┌─────────┴─────────┐                                        │
│        │                   │                                        │
│    false                 true                                       │
│        │                   │                                        │
│        ▼                   ▼                                        │
│   [Legacy Parser]    ┌──────────────────────────────┐              │
│                      │ Supplier Flag: use_semantic_etl│              │
│                      │      (Database Column)        │              │
│                      └──────────────┬───────────────┘              │
│                                     │                               │
│                           ┌─────────┴─────────┐                     │
│                           │                   │                     │
│                       false                 true                    │
│                           │                   │                     │
│                           ▼                   ▼                     │
│                    [Legacy Parser]    [Semantic ETL]                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Global Feature Flag

### Environment Variable: `USE_SEMANTIC_ETL`

| Value | Effect |
|-------|--------|
| `false` (default) | All suppliers use legacy parser |
| `true` | Supplier-level flag controls behavior |

### Configuration Methods

#### Method 1: Docker Compose Override (Development)

```bash
# Create or edit docker-compose.override.yml
cat > docker-compose.override.yml << 'EOF'
services:
  ml-analyze:
    environment:
      USE_SEMANTIC_ETL: "true"
EOF

# Apply changes
docker-compose up -d ml-analyze
```

#### Method 2: Environment File (Recommended)

```bash
# Add to .env file
echo "USE_SEMANTIC_ETL=true" >> .env

# Restart services to pick up changes
docker-compose restart ml-analyze worker
```

#### Method 3: Inline Override (Testing)

```bash
# One-time override
USE_SEMANTIC_ETL=true docker-compose up -d ml-analyze
```

### Verification

```bash
# Check current setting
docker exec marketbel-ml-analyze env | grep USE_SEMANTIC_ETL

# Check via API (if endpoint exists)
curl -s http://localhost:8001/health | jq '.config.use_semantic_etl'
```

---

## Supplier-Level Feature Flag

### Database Column: `suppliers.use_semantic_etl`

| Value | Effect (when global flag is `true`) |
|-------|-------------------------------------|
| `false` (default) | Supplier uses legacy parser |
| `true` | Supplier uses Semantic ETL |

### Enable for Specific Suppliers

```sql
-- Enable for a single supplier by ID
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE id = 'YOUR_SUPPLIER_UUID';

-- Enable for a supplier by name
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE name = 'Test Supplier';

-- Enable for multiple suppliers
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE id IN ('uuid1', 'uuid2', 'uuid3');
```

### Enable for All Suppliers

```sql
-- Enable globally (when ready for full rollout)
UPDATE suppliers SET use_semantic_etl = true;

-- Verify
SELECT COUNT(*) as enabled_count 
FROM suppliers 
WHERE use_semantic_etl = true;
```

### Disable for Specific Suppliers

```sql
-- Disable for problematic supplier
UPDATE suppliers 
SET use_semantic_etl = false 
WHERE id = 'PROBLEMATIC_SUPPLIER_UUID';

-- Disable for all (emergency rollback)
UPDATE suppliers SET use_semantic_etl = false;
```

### Query Current Status

```sql
-- Check all suppliers' status
SELECT 
    id,
    name,
    use_semantic_etl,
    created_at
FROM suppliers
ORDER BY name;

-- Count enabled vs disabled
SELECT 
    use_semantic_etl,
    COUNT(*) as count
FROM suppliers
GROUP BY use_semantic_etl;
```

---

## Gradual Rollout Strategy

### Phase 1: Testing (Day 1-2)

```sql
-- Enable for 1 test supplier
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE name = 'Test Supplier';
```

- Monitor extraction accuracy
- Check job completion times
- Review category creation

### Phase 2: Pilot (Day 3-7)

```sql
-- Enable for 10% of suppliers (small/reliable ones)
WITH pilot_suppliers AS (
    SELECT id 
    FROM suppliers 
    WHERE is_active = true
    ORDER BY (SELECT COUNT(*) FROM supplier_items WHERE supplier_id = suppliers.id) ASC
    LIMIT (SELECT COUNT(*) / 10 FROM suppliers)
)
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE id IN (SELECT id FROM pilot_suppliers);
```

- Run for 5-7 days
- Monitor metrics daily
- Gather feedback

### Phase 3: Expansion (Week 2)

```sql
-- Enable for 50% of suppliers
WITH half_suppliers AS (
    SELECT id 
    FROM suppliers 
    WHERE use_semantic_etl = false
    ORDER BY RANDOM()
    LIMIT (SELECT COUNT(*) / 2 FROM suppliers WHERE use_semantic_etl = false)
)
UPDATE suppliers 
SET use_semantic_etl = true 
WHERE id IN (SELECT id FROM half_suppliers);
```

### Phase 4: Full Rollout (Week 3+)

```sql
-- Enable for all remaining suppliers
UPDATE suppliers SET use_semantic_etl = true WHERE use_semantic_etl = false;
```

---

## Configuration Parameters

Additional parameters that work alongside the feature flag:

### ML-Analyze Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FUZZY_MATCH_THRESHOLD` | `85` | Category fuzzy match threshold (0-100) |
| `CHUNK_SIZE_ROWS` | `250` | Rows per LLM chunk |
| `CHUNK_OVERLAP_ROWS` | `40` | Overlap between chunks (~16%) |
| `OLLAMA_TEMPERATURE` | `0.2` | LLM temperature (lower = deterministic) |
| `OLLAMA_LLM_MODEL` | `llama3` | LLM model name |

### Tuning for Specific Scenarios

**For better accuracy (slower):**

```bash
FUZZY_MATCH_THRESHOLD=90
CHUNK_SIZE_ROWS=150
OLLAMA_TEMPERATURE=0.1
```

**For faster processing (less accurate):**

```bash
FUZZY_MATCH_THRESHOLD=80
CHUNK_SIZE_ROWS=350
OLLAMA_TEMPERATURE=0.3
```

**For very large files:**

```bash
CHUNK_SIZE_ROWS=500
CHUNK_OVERLAP_ROWS=60
```

---

## Monitoring Feature Flag Status

### Check Effective Flag Status

```sql
-- Which processing mode each supplier will use
SELECT 
    s.id,
    s.name,
    CASE 
        WHEN s.use_semantic_etl = true THEN 'Semantic ETL'
        ELSE 'Legacy Parser'
    END as processing_mode,
    s.use_semantic_etl as flag_value
FROM suppliers s
ORDER BY s.name;
```

### Recent Jobs by Processing Mode

```sql
-- Check which mode recent jobs used
SELECT 
    sj.id as job_id,
    s.name as supplier_name,
    sj.phase,
    CASE 
        WHEN sj.phase IN ('extracting', 'normalizing') THEN 'Semantic ETL'
        WHEN sj.phase = 'processing' THEN 'Legacy Parser'
        ELSE 'Unknown'
    END as likely_mode,
    sj.created_at
FROM sync_jobs sj
JOIN suppliers s ON sj.supplier_id = s.id
WHERE sj.created_at > NOW() - INTERVAL '24 hours'
ORDER BY sj.created_at DESC
LIMIT 20;
```

---

## Troubleshooting

### Flag Not Taking Effect

1. **Check global flag is enabled:**

   ```bash
   docker exec marketbel-ml-analyze env | grep USE_SEMANTIC_ETL
   ```

2. **Check supplier flag:**

   ```sql
   SELECT use_semantic_etl FROM suppliers WHERE id = 'YOUR_SUPPLIER_ID';
   ```

3. **Restart services:**

   ```bash
   docker-compose restart ml-analyze worker
   ```

### Rollback Commands

**Quick disable (all suppliers):**

```bash
docker exec marketbel-postgres psql -U marketbel_user -d marketbel \
  -c "UPDATE suppliers SET use_semantic_etl = false;"
docker-compose restart ml-analyze worker
```

**Disable specific supplier:**

```bash
docker exec marketbel-postgres psql -U marketbel_user -d marketbel \
  -c "UPDATE suppliers SET use_semantic_etl = false WHERE id = 'SUPPLIER_ID';"
```

**Global disable via environment:**

```bash
sed -i 's/USE_SEMANTIC_ETL=true/USE_SEMANTIC_ETL=false/' .env
docker-compose restart ml-analyze worker
```

---

## API Integration

### Check Supplier Flag via API

```typescript
// GET /admin/suppliers/:id
{
  "id": "uuid",
  "name": "Supplier Name",
  "use_semantic_etl": true,
  // ... other fields
}
```

### Update Supplier Flag via API

```bash
# Enable semantic ETL for a supplier
curl -X PATCH http://localhost:3000/admin/suppliers/SUPPLIER_ID \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"use_semantic_etl": true}'
```

---

## Best Practices

1. **Always start with global flag OFF** in new deployments
2. **Test with a single supplier** before enabling more
3. **Monitor metrics** during rollout
4. **Keep rollback commands handy** during initial rollout
5. **Document which suppliers** are enabled and when
6. **Review category creation** regularly during rollout

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-04 | AI Assistant | Initial document |
