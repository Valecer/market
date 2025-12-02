# ML-Analyze Service Context

## Overview
AI-powered product analysis and matching service for Marketbel. Uses RAG (Retrieval-Augmented Generation) pipeline for intelligent parsing and product matching.

**Phase:** 7 (ML-Analyze Service)
**Status:** In Development

---

## Stack
- **Runtime:** Python 3.12+ (venv)
- **Framework:** FastAPI + uvicorn
- **LLM Orchestration:** LangChain + LangChain-Ollama
- **LLM:** Ollama (nomic-embed-text for embeddings, llama3 for matching)
- **Vector DB:** pgvector (PostgreSQL extension)
- **Database:** asyncpg (async PostgreSQL driver)
- **File Parsing:** pymupdf4llm (PDF), openpyxl (Excel)
- **Queue:** arq (Redis-based, same as python-ingestion)
- **Validation:** Pydantic 2.x

---

## Structure

```
src/
├── api/
│   ├── main.py             # FastAPI app entry point
│   └── routes/             # API route modules
│       ├── analyze.py      # POST /analyze/file
│       ├── status.py       # GET /analyze/status/:job_id
│       └── health.py       # GET /health
├── config/
│   └── settings.py         # pydantic-settings configuration
├── db/
│   ├── connection.py       # asyncpg connection pool
│   ├── models.py           # SQLAlchemy models
│   └── repositories/       # Data access layer
│       ├── embeddings_repo.py
│       ├── supplier_items_repo.py
│       └── parsing_logs_repo.py
├── ingest/
│   ├── table_normalizer.py # Abstract base class
│   ├── excel_strategy.py   # ExcelStrategy (openpyxl + pandas)
│   ├── pdf_strategy.py     # PdfStrategy (pymupdf4llm)
│   ├── chunker.py          # Row-to-chunk converter
│   └── parser_factory.py   # Strategy factory
├── rag/
│   ├── vector_service.py   # Embedding + similarity search
│   ├── merger_agent.py     # LLM-based matching
│   └── prompt_templates.py # LangChain prompt templates
├── schemas/
│   ├── requests.py         # API request models
│   ├── responses.py        # API response models
│   └── domain.py           # Domain models
├── services/
│   ├── ingestion_service.py   # Parsing orchestration
│   ├── matching_service.py    # Matching orchestration
│   └── job_service.py         # Redis job status
├── tasks/
│   └── file_analysis_task.py  # arq background worker
└── utils/
    ├── logger.py           # Structured logging
    └── errors.py           # Custom exceptions
```

---

## Commands

```bash
cd services/ml-analyze

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run server (development)
uvicorn src.api.main:app --reload --port 8001

# Run tests
pytest tests/ -v --cov=src

# Type checking
mypy src/ --strict

# Linting
ruff check src/
```

---

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Service health check |
| POST | /analyze/file | Trigger file analysis |
| GET | /analyze/status/:job_id | Check job status |
| POST | /analyze/merge | Trigger batch matching |
| POST | /analyze/vision | Stub (501 Not Implemented) |

---

## Critical Rules

### 1. Async/Await for All I/O

```python
# ❌ Wrong
def get_embedding(text: str):
    return ollama.embed(text)

# ✅ Correct
async def get_embedding(text: str) -> list[float]:
    async with httpx.AsyncClient() as client:
        response = await client.post(...)
    return response.json()["embedding"]
```

### 2. Type Hints Required (Strict Mode)

```python
# ❌ Wrong
def process_file(file_url, supplier_id):
    return parse(file_url)

# ✅ Correct
async def process_file(
    file_url: str,
    supplier_id: UUID
) -> list[NormalizedRow]:
    return await parse(file_url)
```

### 3. Pydantic for All Data Validation

```python
from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID

class FileAnalysisRequest(BaseModel):
    file_url: HttpUrl | str
    supplier_id: UUID
    file_type: Literal["pdf", "excel", "csv"]
```

### 4. Error Isolation - Never Crash Service

```python
# ❌ Wrong - one bad row crashes entire parse
for row in rows:
    embedding = await embed(row)  # Exception kills service

# ✅ Correct - log error, continue
for row in rows:
    try:
        embedding = await embed(row)
        results.append(embedding)
    except EmbeddingError as e:
        await log_error(supplier_id, row, str(e))
        continue
```

### 5. Use patch.object() for Mocking

```python
# ❌ Wrong - leaks between tests
service._ollama_client.embed = Mock(return_value=[0.1, 0.2])

# ✅ Correct - auto-restores after test
with patch.object(service._ollama_client, 'embed', return_value=[0.1, 0.2]):
    result = await service.get_embedding("test")
```

---

## Matching Pipeline

```
Supplier Item → Vector Search (Top-5) → LLM Matching → Database Update
     │
     ├─ Score ≥90% → Auto-link: supplier_items.product_id = match
     ├─ Score 70-90% → Review: INSERT INTO match_review_queue
     └─ Score <70% → Log: INSERT INTO parsing_logs (no action)
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | (required) | PostgreSQL connection string |
| REDIS_HOST | localhost | Redis host |
| REDIS_PASSWORD | (required) | Redis password |
| OLLAMA_BASE_URL | http://localhost:11434 | Ollama API URL |
| OLLAMA_EMBEDDING_MODEL | nomic-embed-text | Embedding model |
| OLLAMA_LLM_MODEL | llama3 | LLM model |
| MATCH_CONFIDENCE_AUTO_THRESHOLD | 0.9 | Auto-match threshold |
| MATCH_CONFIDENCE_REVIEW_THRESHOLD | 0.7 | Review queue threshold |

---

## Database Tables (Phase 7)

### product_embeddings (NEW)
```sql
CREATE TABLE product_embeddings (
    id UUID PRIMARY KEY,
    supplier_item_id UUID REFERENCES supplier_items(id),
    embedding vector(768),
    model_name VARCHAR(100),
    created_at TIMESTAMP
);
```

### Existing Tables Used
- `supplier_items` - Updated with product_id when matched
- `match_review_queue` - Medium-confidence matches
- `parsing_logs` - Errors and low-confidence matches
- `products` - Referenced for matching

---

## Common Issues

1. **"Cannot connect to Ollama"** → Ensure Ollama is running: `ollama serve`
2. **"pgvector extension not found"** → Run migration: `007_enable_pgvector.py`
3. **"Connection pool exhausted"** → Increase DB_POOL_MAX or reduce concurrency
4. **"Embedding dimension mismatch"** → Ensure EMBEDDING_DIMENSIONS=768 for nomic-embed-text

