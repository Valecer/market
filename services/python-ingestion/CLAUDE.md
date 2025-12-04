> **Refer to: [[../../CLAUDE.md]] and [[../../docs/PROJECT_SUMMARY.md]]**

# Python Worker Service

**Role:** Data courier (downloads files) + legacy parsing
**Phases:** 1, 4, 6, 8 (ML Integration)

## Stack

Python 3.12+, SQLAlchemy 2.0 AsyncIO, arq (Redis queue), Pydantic 2.x, RapidFuzz, httpx

## Commands

```bash
cd services/python-ingestion
source venv/bin/activate

python -m src.worker                    # Run worker
pytest tests/ -v --cov=src              # Tests
alembic upgrade head                    # Migrations
alembic revision --autogenerate -m "x"  # New migration
```

## Key Conventions

- Async/await for all I/O (required)
- Type hints required
- Use `patch.object()` for mocking (never direct assignment)
- Error isolation: per-row try/catch + log to `parsing_logs`

## Courier Pattern (Phase 8)

```
[API] → [download_and_trigger_ml] → 1. Download to /shared/uploads/
                                    2. Write .meta.json
                                    3. POST → ml-analyze/analyze/file
                                    4. Poll status → update Redis
```

### ML Client

```python
from src.services.ml_client import ml_client

# Check health
is_healthy = await ml_client.check_health()

# Trigger analysis
job_id = await ml_client.trigger_analysis(
    file_path="/shared/uploads/supplier_123_file.xlsx",
    supplier_id="123e4567-...",
    file_type="excel",  # "pdf", "excel", "csv"
)

# Get status
status = await ml_client.get_job_status(job_id)
```

### Job State

```python
from src.services.job_state import create_job, update_job, get_job

await create_job(redis, job_id, supplier_id, supplier_name)
await update_job(redis, job_id, phase="analyzing", ml_job_id="...")
job = await get_job(redis, job_id)
```

**Job Phases:** `downloading` → `analyzing` → `matching` → `complete`/`failed`

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ML_ANALYZE_URL` | `http://ml-analyze:8001` | ML service URL |
| `USE_ML_PROCESSING` | `true` | Global ML toggle |
| `ML_POLL_INTERVAL_SECONDS` | `5` | Polling interval |
| `MAX_FILE_SIZE_MB` | `50` | Upload limit |
| `FILE_CLEANUP_TTL_HOURS` | `24` | File retention |

### Feature Flags

```python
from src.config import settings

# Global toggle
if settings.use_ml_processing:
    await redis.enqueue_job('download_and_trigger_ml', ...)
else:
    await redis.enqueue_job('parse_task', ...)

# Per-supplier toggle
supplier_uses_ml = supplier.meta.get("use_ml_processing", True)
```

## Tasks (arq)

| Task | Description | Phase |
|------|-------------|-------|
| `parse_task` | Legacy parsing | 1 |
| `match_items_task` | RapidFuzz matching | 4 |
| `master_sync_task` | Sync Master Sheet | 6 |
| **`download_and_trigger_ml`** | **Download + trigger ML** | **8** |
| **`poll_ml_job_status_task`** | **Poll ML status (10s cron)** | **8** |
| **`cleanup_shared_files_task`** | **Cleanup (6h cron)** | **8** |
| **`retry_job_task`** | **Retry failed jobs** | **8** |

## Common Issues

1. **"greenlet" error** → Use `async with get_session()`
2. **Test pollution** → Use `patch.object()`, not direct assignment
3. **ML service unavailable** → Check `docker-compose logs ml-analyze`, verify Ollama running
4. **Job stuck in "downloading"** → Check shared volume permissions
5. **Job stuck in "analyzing"** → Check ML health: `http://ml-analyze:8001/health`
6. **Files not cleaned up** → Verify `cleanup_shared_files_task` registered in worker
