# Data Model: ML-Based Product Analysis & Merging Service

**Date:** 2025-12-03

**Status:** Complete

**Purpose:** Define database schema, entity relationships, and data flow for the ml-analyze service.

---

## Overview

The ml-analyze service extends the existing Marketbel database schema with vector embedding support. It reads from and writes to existing tables (`supplier_items`, `products`, `match_review_queue`, `parsing_logs`) while introducing a new `product_embeddings` table for vector search.

**Key Principle:** **No modifications to existing schema** - only additions and foreign key references.

---

## Entity Relationship Diagram

```
┌─────────────────────┐
│    suppliers        │
│  (existing)         │
│  - id (PK)          │
│  - name             │
│  - source_type      │
└──────────┬──────────┘
           │ 1:N
           │
┌──────────▼──────────┐
│  supplier_items     │
│  (existing)         │
│  - id (PK)          │
│  - supplier_id (FK) │
│  - product_id (FK)  │◄───────┐
│  - name             │        │ N:1
│  - description      │        │
│  - price            │        │
│  - characteristics  │        │
└──────────┬──────────┘        │
           │ 1:1                │
           │                    │
┌──────────▼──────────┐        │
│ product_embeddings  │        │
│  (NEW)              │        │
│  - id (PK)          │        │
│  - supplier_item_id │        │
│  - embedding        │        │
│  - model_name       │        │
│  - created_at       │        │
└─────────────────────┘        │
                               │
                               │
                    ┌──────────┴──────────┐
                    │     products        │
                    │   (existing)        │
                    │   - id (PK)         │
                    │   - name            │
                    │   - status          │
                    └─────────────────────┘

┌─────────────────────┐
│ match_review_queue  │
│  (existing)         │
│  - id (PK)          │
│  - supplier_item_id │
│  - suggested_match  │
│  - confidence       │
│  - status           │
└─────────────────────┘

┌─────────────────────┐
│  parsing_logs       │
│  (existing)         │
│  - id (PK)          │
│  - supplier_id (FK) │
│  - error_type       │
│  - error_message    │
│  - created_at       │
└─────────────────────┘

┌─────────────────────┐
│   analysis_jobs     │
│  (NEW - in-memory)  │
│  - job_id (PK)      │
│  - status           │
│  - progress         │
│  - errors           │
│  (stored in Redis)  │
└─────────────────────┘
```

---

## New Tables

### 1. product_embeddings

**Purpose:** Store vector embeddings of supplier items for semantic similarity search.

**Schema:**

```sql
CREATE TABLE product_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_item_id UUID NOT NULL REFERENCES supplier_items(id) ON DELETE CASCADE,
    embedding vector(768) NOT NULL,  -- pgvector type: 768-dimensional float array
    model_name VARCHAR(100) NOT NULL DEFAULT 'nomic-embed-text',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_item_embedding UNIQUE (supplier_item_id, model_name)
);

-- Index for fast cosine similarity search
CREATE INDEX idx_embeddings_cosine_similarity
ON product_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);  -- Tune based on dataset size (sqrt(rows))

-- Index for lookups by supplier_item_id
CREATE INDEX idx_embeddings_supplier_item
ON product_embeddings(supplier_item_id);

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_product_embeddings_updated_at
BEFORE UPDATE ON product_embeddings
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
```

**Fields:**

- `id`: UUID primary key
- `supplier_item_id`: FK to supplier_items (cascade delete)
- `embedding`: 768-dimension float vector (pgvector type)
- `model_name`: Embedding model identifier (for future model upgrades)
- `created_at`: Timestamp when embedding was generated
- `updated_at`: Timestamp of last update

**Constraints:**

- Unique constraint on (supplier_item_id, model_name) - prevents duplicate embeddings
- NOT NULL on embedding - every row must have a valid vector
- Foreign key cascade delete - remove embeddings when supplier_item is deleted

**Indexes:**

1. **IVFFLAT (cosine similarity)**: Enables fast vector search using cosine distance
   - Operator class: `vector_cosine_ops`
   - Lists parameter: 100 (tune to sqrt(total_rows) as dataset grows)
   - Search operator: `embedding <=> query_vector`

2. **B-tree (supplier_item_id)**: Fast lookups for checking if embedding exists

**Storage Estimates:**

- Vector size: 768 floats × 4 bytes = 3,072 bytes per embedding
- Row overhead: ~100 bytes (UUID, timestamps, indexes)
- Total per row: ~3.2 KB
- 100,000 products: ~320 MB
- 1,000,000 products: ~3.2 GB

---

## Existing Tables (Extended Usage)

### 2. supplier_items (Existing - No Modifications)

**Extended Usage:** ml-analyze service reads from this table for matching and writes `product_id` when matches are found.

**Relevant Fields:**

- `id`: Primary key
- `supplier_id`: FK to suppliers
- `product_id`: FK to products (NULL when unmatched, populated by ml-analyze)
- `name`: Product name (used for embedding)
- `description`: Product description (used for embedding)
- `price`: Current price
- `characteristics`: JSONB with additional attributes
- `status`: Enum ('pending_match', 'matched', 'rejected')

**ML-Analyze Operations:**

1. **Read**: Fetch items with `status = 'pending_match'` and `product_id IS NULL`
2. **Write**: Update `product_id` when high-confidence match found (>90%)
3. **Write**: Update `status = 'matched'` after linking

**Example Query:**

```sql
-- Find unmatched items for analysis
SELECT id, name, description, price, characteristics
FROM supplier_items
WHERE product_id IS NULL
  AND status = 'pending_match'
  AND supplier_id = $1
ORDER BY created_at DESC;
```

---

### 3. products (Existing - No Modifications)

**Extended Usage:** ml-analyze service searches this table via embeddings to find match candidates.

**Relevant Fields:**

- `id`: Primary key
- `name`: Product name
- `status`: Enum ('draft', 'active', 'archived')

**ML-Analyze Operations:**

1. **Read**: Search for similar products via embedding similarity
2. **Join**: Link supplier_items to products via product_id

**Example Query:**

```sql
-- Find products similar to a supplier item
SELECT
    p.id,
    p.name,
    p.status,
    pe.embedding <=> $1 AS similarity_score
FROM products p
JOIN supplier_items si ON si.product_id = p.id
JOIN product_embeddings pe ON pe.supplier_item_id = si.id
WHERE p.status = 'active'
  AND pe.model_name = 'nomic-embed-text'
ORDER BY similarity_score ASC
LIMIT 5;
```

---

### 4. match_review_queue (Existing - No Modifications)

**Extended Usage:** ml-analyze service inserts uncertain matches (70-90% confidence) for manual admin review.

**Relevant Fields:**

- `id`: Primary key
- `supplier_item_id`: FK to supplier_items
- `suggested_product_id`: FK to products
- `confidence_score`: Float (0.0 - 1.0)
- `matching_algorithm`: String (e.g., 'llm-llama3')
- `status`: Enum ('pending', 'approved', 'rejected')
- `created_at`: Timestamp

**ML-Analyze Operations:**

1. **Write**: Insert matches with 0.7 ≤ confidence < 0.9

**Example Insert:**

```sql
INSERT INTO match_review_queue (
    supplier_item_id,
    suggested_product_id,
    confidence_score,
    matching_algorithm,
    reasoning,
    status
) VALUES (
    $1,  -- supplier_item_id
    $2,  -- suggested_product_id
    $3,  -- confidence_score (0.7-0.9)
    'llm-llama3-rag',
    $4,  -- LLM reasoning text
    'pending'
);
```

---

### 5. parsing_logs (Existing - No Modifications)

**Extended Usage:** ml-analyze service logs all errors during file parsing, embedding generation, and matching.

**Relevant Fields:**

- `id`: Primary key
- `supplier_id`: FK to suppliers
- `error_type`: String (e.g., 'pdf_parse_error', 'embedding_failed', 'llm_timeout')
- `error_message`: Text description
- `error_details`: JSONB with stack trace, file info, etc.
- `created_at`: Timestamp

**ML-Analyze Error Types:**

- `pdf_parse_error`: Failed to extract tables from PDF
- `excel_parse_error`: Failed to parse Excel file (corrupt, missing headers)
- `embedding_failed`: Ollama API error during embedding generation
- `llm_timeout`: LLM inference exceeded 30s timeout
- `llm_invalid_json`: LLM returned malformed JSON response
- `vector_search_error`: pgvector query failed

**Example Insert:**

```python
await conn.execute('''
    INSERT INTO parsing_logs (
        supplier_id,
        error_type,
        error_message,
        error_details
    ) VALUES ($1, $2, $3, $4)
''',
    supplier_id,
    'pdf_parse_error',
    f'Failed to extract tables from {file_path}',
    json.dumps({
        'file_path': file_path,
        'exception': str(exc),
        'traceback': traceback.format_exc()
    })
)
```

---

## In-Memory Data Structures (Redis)

### 6. analysis_jobs (In-Memory via arq)

**Purpose:** Track status and progress of background file analysis jobs.

**Storage:** Redis (via arq queue system)

**Schema (JSON structure):**

```json
{
  "job_id": "uuid-here",
  "status": "pending|processing|completed|failed",
  "file_url": "https://example.com/file.pdf",
  "supplier_id": "uuid-here",
  "file_type": "pdf|excel|csv",
  "progress_percentage": 45,
  "items_processed": 45,
  "items_total": 100,
  "errors": ["Error 1", "Error 2"],
  "created_at": "2025-12-03T10:00:00Z",
  "started_at": "2025-12-03T10:00:05Z",
  "completed_at": "2025-12-03T10:02:30Z"
}
```

**Operations:**

1. **Create**: On POST /analyze/file
2. **Update**: During processing (update progress, errors)
3. **Read**: On GET /analyze/status/:job_id
4. **Expire**: Auto-delete after 24 hours (Redis TTL)

**Redis Key Pattern:**

```
ml-analyze:job:{job_id}
```

**Example:**

```python
import json
import redis

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Create job
job_data = {
    "job_id": str(job_id),
    "status": "pending",
    "file_url": file_url,
    "supplier_id": str(supplier_id),
    "progress_percentage": 0,
    "items_processed": 0,
    "items_total": 0,
    "errors": [],
    "created_at": datetime.utcnow().isoformat()
}

redis_client.setex(
    f"ml-analyze:job:{job_id}",
    86400,  # 24 hour TTL
    json.dumps(job_data)
)

# Update job status
job_data['status'] = 'processing'
job_data['progress_percentage'] = 50
redis_client.setex(
    f"ml-analyze:job:{job_id}",
    86400,
    json.dumps(job_data)
)

# Retrieve job status
job_json = redis_client.get(f"ml-analyze:job:{job_id}")
if job_json:
    job = json.loads(job_json)
```

---

## Data Flow

### 1. File Ingestion → Embedding Generation

```
POST /analyze/file
  ↓
Create job in Redis (status: pending)
  ↓
Enqueue arq task: process_file_job
  ↓
Parse file → Normalize rows (ExcelStrategy or PdfStrategy)
  ↓
For each row:
  ├─ Generate embedding (Ollama nomic-embed-text)
  ├─ INSERT INTO product_embeddings (supplier_item_id, embedding)
  └─ Update job progress in Redis
  ↓
Job complete (status: completed)
```

### 2. Embedding → Product Matching

```
For each supplier_item with new embedding:
  ↓
Vector search for Top-5 similar products
  ↓
SELECT products WHERE embedding <=> query_embedding
  ↓
Construct LLM prompt with item + Top-5 candidates
  ↓
Call Ollama llama3 (JSON output)
  ↓
Parse match results (confidence scores)
  ↓
If confidence > 0.9:
  └─ UPDATE supplier_items SET product_id = matched_id
If 0.7 ≤ confidence < 0.9:
  └─ INSERT INTO match_review_queue
If confidence < 0.7:
  └─ Log to parsing_logs (no_match)
```

---

## Validation Rules

### product_embeddings

- `embedding` must have exactly 768 dimensions
- `embedding` values must be floats in range [-1.0, 1.0] (unit normalized)
- `model_name` must match pattern `^[a-z0-9-]+$`
- `supplier_item_id` must exist in supplier_items table

### supplier_items (Matching Logic)

- `product_id` can only be set if confidence > 0.9
- `status` must transition: `pending_match` → `matched` OR `rejected`
- Cannot link to archived products (`products.status != 'archived'`)

### match_review_queue

- `confidence_score` must be in range [0.0, 1.0]
- `confidence_score` for ml-analyze entries must be in [0.7, 0.9)
- `matching_algorithm` for ml-analyze must be 'llm-llama3-rag'

---

## Performance Considerations

### Vector Search Optimization

**IVFFLAT Index Tuning:**

```sql
-- Adjust 'lists' parameter based on dataset size
-- Rule of thumb: lists = sqrt(total_rows)

-- 10,000 products:
DROP INDEX idx_embeddings_cosine_similarity;
CREATE INDEX idx_embeddings_cosine_similarity
ON product_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 100,000 products:
WITH (lists = 316);

-- 1,000,000 products:
WITH (lists = 1000);

-- Set runtime probes for recall/speed trade-off
SET ivfflat.probes = 10;  -- Higher = better recall, slower
```

**Query Performance:**

```sql
-- EXPLAIN ANALYZE for vector search
EXPLAIN (ANALYZE, BUFFERS) SELECT
    si.id,
    si.name,
    pe.embedding <=> $1 AS distance
FROM product_embeddings pe
JOIN supplier_items si ON pe.supplier_item_id = si.id
WHERE si.product_id IS NOT NULL  -- Only search existing products
ORDER BY distance
LIMIT 5;

-- Expected performance:
-- < 100ms for 10K products
-- < 500ms for 100K products
-- < 2s for 1M products (with ivfflat.probes=10)
```

### Embedding Storage Optimization

**Half-Precision Vectors** (Future optimization):

```sql
-- Use halfvec for 50% storage reduction
-- Trade-off: Slightly lower precision, faster search

ALTER TABLE product_embeddings
ADD COLUMN embedding_half halfvec(768);

-- Convert existing embeddings
UPDATE product_embeddings
SET embedding_half = embedding::halfvec;

-- Create index on half-precision
CREATE INDEX idx_embeddings_half_cosine
ON product_embeddings
USING ivfflat (embedding_half halfvec_cosine_ops)
WITH (lists = 100);
```

---

## Migration Plan

### Migration 007: Enable pgvector

```sql
-- File: migrations/007_enable_pgvector.sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Migration 008: Create product_embeddings Table

```sql
-- File: migrations/008_create_product_embeddings.sql

CREATE TABLE product_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_item_id UUID NOT NULL REFERENCES supplier_items(id) ON DELETE CASCADE,
    embedding vector(768) NOT NULL,
    model_name VARCHAR(100) NOT NULL DEFAULT 'nomic-embed-text',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_item_embedding UNIQUE (supplier_item_id, model_name)
);

CREATE INDEX idx_embeddings_cosine_similarity
ON product_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX idx_embeddings_supplier_item
ON product_embeddings(supplier_item_id);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_product_embeddings_updated_at
BEFORE UPDATE ON product_embeddings
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE product_embeddings IS 'Vector embeddings of supplier items for semantic similarity search';
COMMENT ON COLUMN product_embeddings.embedding IS '768-dimensional vector from nomic-embed-text model';
COMMENT ON COLUMN product_embeddings.model_name IS 'Embedding model identifier for future model upgrades';
```

### Rollback Plan

```sql
-- Rollback Migration 008
DROP TABLE IF EXISTS product_embeddings CASCADE;
DROP FUNCTION IF EXISTS update_updated_at_column CASCADE;

-- Rollback Migration 007
DROP EXTENSION IF EXISTS vector CASCADE;
```

---

## Summary

**New Tables:** 1 (`product_embeddings`)

**Modified Tables:** 0 (all existing tables used as-is)

**Indexes:** 2 (IVFFLAT vector index + B-tree on supplier_item_id)

**Storage Impact:** ~3.2 KB per product embedding

**Performance:** <500ms vector search for 100K products with proper indexing

**Next Steps:**
1. ✅ Data model complete
2. → Generate API contracts (OpenAPI schemas)
3. → Create quickstart.md (setup guide)
