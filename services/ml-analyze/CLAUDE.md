> **Refer to: [[../../CLAUDE.md]] and [[../../docs/PROJECT_SUMMARY.md]]**

# ML-Analyze Service

**Role:** AI-powered parsing and product matching
**Phase:** 7 (RAG Pipeline)

## Stack

Python 3.12+, FastAPI, LangChain + LangChain-Ollama, Ollama (nomic-embed-text, llama3), pgvector, asyncpg, pymupdf4llm, openpyxl

## Commands

```bash
cd services/ml-analyze
source venv/bin/activate

uvicorn src.api.main:app --reload --port 8001  # Dev server
pytest tests/ -v --cov=src                     # Tests
mypy src/ --strict                             # Type check
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (DB, Redis, Ollama) |
| POST | `/analyze/file` | Trigger file analysis |
| GET | `/analyze/status/:job_id` | Poll job status |
| POST | `/analyze/merge` | Batch product matching |

## Matching Pipeline

```
Supplier Item → Vector Search (Top-5) → LLM Reasoning → Confidence Score
     │
     ├─ ≥90% → Auto-match (supplier_items.product_id = match)
     ├─ 70-90% → Review queue (match_review_queue)
     └─ <70% → Log (parsing_logs, no action)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | (required) | PostgreSQL connection |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PASSWORD` | (required) | Redis password |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model (768-dim) |
| `OLLAMA_LLM_MODEL` | `llama3` | LLM model |
| `MATCH_CONFIDENCE_AUTO_THRESHOLD` | `0.9` | Auto-match threshold |
| `MATCH_CONFIDENCE_REVIEW_THRESHOLD` | `0.7` | Review queue threshold |

## Key Conventions

- Async/await for all I/O (required)
- Type hints required (strict mode)
- Use `patch.object()` for mocking
- Error isolation: per-row try/catch

## Database (Phase 7)

### New Table: product_embeddings

```sql
CREATE TABLE product_embeddings (
    id UUID PRIMARY KEY,
    supplier_item_id UUID REFERENCES supplier_items(id),
    embedding vector(768),
    model_name VARCHAR(100),
    created_at TIMESTAMP
);
```

### Used Tables
- `supplier_items` - Updated with product_id when matched
- `match_review_queue` - Medium-confidence matches
- `parsing_logs` - Errors and low-confidence
- `products` - Referenced for matching

## Common Issues

1. **"Cannot connect to Ollama"** → Ensure `ollama serve` is running
2. **"pgvector extension not found"** → Run migration: `007_enable_pgvector.py`
3. **"Connection pool exhausted"** → Increase DB_POOL_MAX
4. **"Embedding dimension mismatch"** → Ensure EMBEDDING_DIMENSIONS=768 for nomic-embed-text
