# Python Worker Service Context

## Overview
Data ingestion worker for Marketbel. Acts as **data courier** (Phase 8) - downloads files and delegates parsing to `ml-analyze` service.

**Queue:** Redis (arq)  
**Phases:** 1 (Ingestion), 4 (Matching), 6 (Sync Scheduler), 8 (ML Integration)

---

## Stack
- **Runtime:** Python 3.12+ (venv)
- **ORM:** SQLAlchemy 2.0 AsyncIO
- **Queue:** arq (Redis-based)
- **Validation:** Pydantic 2.x
- **Matching:** RapidFuzz
- **HTTP Client:** httpx (async) - for ML service communication

---

## Structure

```
src/
├── db/
│   ├── models/         # SQLAlchemy ORM models
│   └── operations.py   # DB operations
├── parsers/            # Data source parsers (legacy)
│   ├── base_parser.py  # Abstract interface
│   ├── google_sheets_parser.py  # + export_to_xlsx() for ML
│   ├── csv_parser.py
│   ├── excel_parser.py
│   └── parser_registry.py
├── services/
│   ├── matching/       # RapidFuzz matcher
│   ├── extraction/     # Feature extractors
│   ├── aggregation/    # Price aggregation
│   ├── ml_client.py    # Phase 8: HTTP client for ml-analyze
│   └── job_state.py    # Phase 8: Redis job state management
├── tasks/              # arq task handlers
│   ├── matching_tasks.py
│   ├── sync_tasks.py
│   ├── download_tasks.py    # Phase 8: File download + ML trigger
│   ├── ml_polling_tasks.py  # Phase 8: Poll ML job status
│   ├── cleanup_tasks.py     # Phase 8: Shared file cleanup
│   └── retry_tasks.py       # Phase 8: Retry failed jobs
├── models/             # Pydantic models
│   └── ml_models.py    # Phase 8: ML request/response models
├── errors/             # Custom exceptions
├── config.py           # Environment config (includes ML settings)
└── worker.py           # arq worker entry point
```

---

## Commands

```bash
cd services/python-ingestion
source venv/bin/activate

# Run worker
python -m src.worker

# Tests
pytest tests/ -v --cov=src

# Migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

---

## Critical Rules

### 1. Async/Await for All I/O

```python
# ❌ Wrong
def get_product(id: str):
    return session.query(Product).get(id)

# ✅ Correct
async def get_product(id: str) -> Product | None:
    async with get_session() as session:
        return await session.get(Product, id)
```

### 2. Type Hints Required

```python
# ❌ Wrong
def parse_row(row, mapping):
    return ParsedItem(...)

# ✅ Correct
def parse_row(row: dict[str, Any], mapping: ColumnMapping) -> ParsedItem:
    return ParsedItem(...)
```

### 3. Pydantic for Validation

```python
from pydantic import BaseModel, Field

class ParsedItem(BaseModel):
    name: str = Field(..., min_length=1)
    price: Decimal = Field(..., gt=0)
    sku: str | None = None
```

### 4. Error Isolation - Never Crash Worker

```python
# ❌ Wrong - one bad row crashes entire parse
for row in rows:
    item = parse_row(row)  # Exception kills worker

# ✅ Correct - log error, continue with next row
for row in rows:
    try:
        item = parse_row(row)
        items.append(item)
    except ValidationError as e:
        await log_parsing_error(supplier_id, row, str(e))
        continue
```

### 5. Use `patch.object()` for Mocking

```python
# ❌ Wrong - leaks between tests
parser._client.open_by_url = Mock(return_value=mock_sheet)

# ✅ Correct - auto-restores after test
with patch.object(parser._client, 'open_by_url', return_value=mock_sheet):
    result = await parser.parse(config)
```

---

## Key Models

### SQLAlchemy (db/models/)

```python
class Supplier(Base):
    __tablename__ = 'suppliers'
    id: Mapped[UUID]
    name: Mapped[str]
    source_type: Mapped[str]  # google_sheets, csv, excel
    source_url: Mapped[str]
    is_active: Mapped[bool]

class SupplierItem(Base):
    __tablename__ = 'supplier_items'
    id: Mapped[UUID]
    supplier_id: Mapped[UUID]
    product_id: Mapped[UUID | None]
    name: Mapped[str]
    price: Mapped[Decimal]
    characteristics: Mapped[dict]  # JSONB
    match_status: Mapped[str]
```

### Pydantic (models/)

```python
class GoogleSheetsConfig(BaseModel):
    spreadsheet_url: str
    sheet_name: str | None = None
    column_mapping: ColumnMapping

class ParsedItem(BaseModel):
    name: str
    price: Decimal
    sku: str | None
    characteristics: dict[str, Any]
```

---

## Tasks (arq)

| Task | Description | Trigger |
|------|-------------|---------|
| `parse_task` | Parse supplier price list (legacy) | API, sync (when ML disabled) |
| `match_items_task` | Fuzzy match items to products | After parse |
| `enrich_item_task` | Extract features from text | After match |
| `recalc_aggregates_task` | Update product min_price | After match/price change |
| `master_sync_task` | Sync from Master Google Sheet | Scheduled (8h) |
| **`download_and_trigger_ml`** | **Download file + trigger ML (Phase 8)** | **API, sync (default)** |
| **`poll_ml_job_status_task`** | **Poll ML service for status (Phase 8)** | **Cron (every 10s)** |
| **`cleanup_shared_files_task`** | **Remove old files (Phase 8)** | **Cron (every 6h)** |
| **`retry_job_task`** | **Retry failed jobs (Phase 8)** | **API trigger** |

### Enqueue Task

```python
from arq import create_pool

async def trigger_parse(supplier_id: str):
    redis = await create_pool(RedisSettings())
    await redis.enqueue_job('parse_task', supplier_id=supplier_id)
```

### Enqueue ML Download Task (Phase 8)

```python
from arq import create_pool
from uuid import uuid4

async def trigger_ml_processing(supplier_id: str, source_url: str):
    redis = await create_pool(RedisSettings())
    job_id = str(uuid4())
    await redis.enqueue_job(
        'download_and_trigger_ml',
        task_id=f"download-{job_id}",
        job_id=job_id,
        supplier_id=supplier_id,
        source_url=source_url,
        source_type="google_sheets",  # or "csv", "excel"
    )
    return job_id
```

---

## Matching Pipeline (Phase 4)

```
Unmatched Item → Find Candidates (same category) → RapidFuzz
  │
  ├─ Score ≥95% → Auto-link to product
  ├─ Score 70-94% → Add to review queue
  └─ Score <70% → Create new product (draft)
```

---

## Sync Pipeline (Phase 6)

```
Master Sheet → Parse suppliers → Sync to DB → Enqueue parse tasks
```

- Default interval: 8 hours (`SYNC_INTERVAL_HOURS`)
- Only one sync at a time (skip if running)

---

## ML Integration Pipeline (Phase 8)

### Architecture: Courier Pattern

This service acts as a **data courier** - it fetches files but does NOT parse them.
Parsing is delegated to `ml-analyze` service via HTTP.

```
[Admin Upload] → [Bun API] → [Redis] → [download_and_trigger_ml]
                                              │
                                              ├── 1. Download file to /shared/uploads/
                                              ├── 2. Write metadata (.meta.json)
                                              ├── 3. HTTP POST → ml-analyze/analyze/file
                                              └── 4. Poll status → update Redis job state
```

### ML Client Usage

```python
from src.services.ml_client import ml_client

# Check service health
is_healthy = await ml_client.check_health()

# Trigger file analysis
job_id = await ml_client.trigger_analysis(
    file_path="/shared/uploads/supplier_123_file.xlsx",
    supplier_id="123e4567-e89b-...",
    file_type="excel",  # "pdf", "excel", "csv"
)

# Get job status
status = await ml_client.get_job_status(job_id)
# Returns: MLJobStatus(job_id=..., status="processing", progress_percentage=45, ...)
```

### Job State Management

```python
from src.services.job_state import create_job, update_job, get_job

# Create new job (phase: downloading)
await create_job(redis, job_id, supplier_id, supplier_name)

# Update job phase
await update_job(redis, job_id, phase="analyzing", ml_job_id="...")

# Get job state
job = await get_job(redis, job_id)
# Returns: {"phase": "analyzing", "progress": 45, ...}
```

### Job Phases

| Phase | Description | Actor |
|-------|-------------|-------|
| `downloading` | File being downloaded | python-ingestion |
| `analyzing` | ML service parsing file | ml-analyze |
| `matching` | Products being matched | ml-analyze |
| `complete` | Successfully finished | ml-analyze |
| `failed` | Error occurred | Either |

### Environment Variables (Phase 8)

| Variable | Default | Description |
|----------|---------|-------------|
| `ML_ANALYZE_URL` | `http://ml-analyze:8001` | ML service URL |
| `USE_ML_PROCESSING` | `true` | Global toggle for ML pipeline |
| `ML_POLL_INTERVAL_SECONDS` | `5` | Status polling interval |
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload file size |
| `FILE_CLEANUP_TTL_HOURS` | `24` | File retention before cleanup |

### Feature Flag

```python
from src.config import settings

# Global flag (environment variable)
if settings.use_ml_processing:
    # Use ML pipeline
    await redis.enqueue_job('download_and_trigger_ml', ...)
else:
    # Use legacy pipeline
    await redis.enqueue_job('parse_task', ...)

# Per-supplier flag (in supplier.meta)
supplier_uses_ml = supplier.meta.get("use_ml_processing", True)
```

---

## Common Issues

1. **"greenlet" error** → Use `async with get_session()`, not sync session
2. **Test pollution** → Use `patch.object()` instead of direct assignment
3. **Missing characteristics** → Check column mapping in parser config
4. **Slow parsing** → Check batch_size, use `executemany` for inserts
5. **ML service unavailable** → Check `docker-compose logs ml-analyze`, verify Ollama is running
6. **Job stuck in "downloading"** → Check shared volume permissions, verify file write succeeded
7. **Job stuck in "analyzing"** → Check ML service health at `http://ml-analyze:8001/health`
8. **Files not cleaned up** → Verify `cleanup_shared_files_task` cron is registered in worker

