# Marketbel Data Ingestion Worker

Async Python worker for parsing supplier price lists and managing product data ingestion pipeline.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Environment Variables](#environment-variables)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- **Python 3.12+** installed
- **PostgreSQL 16+** running (or via Docker)
- **Redis 7+** running (or via Docker)
- Google service account credentials for Sheets API

### Setup Steps

```bash
# 1. Create virtual environment
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment (copy and edit)
cp .env.example .env

# 4. Run database migrations
alembic upgrade head

# 5. Start the worker
arq src.worker.WorkerSettings
```

### Verify Installation

```bash
# Check worker starts without errors
arq src.worker.WorkerSettings --check

# Enqueue a test task
python scripts/enqueue_task.py
```

---

## Architecture

### Layer Architecture

```
┌─────────────────────────────────────────────────┐
│                 Task Queue (arq)                │
│  - trigger_master_sync_task                     │
│  - parse_task                                   │
│  - match_items_task                             │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│               Services (Business Logic)          │
│  - MasterSheetIngestor                          │
│  - Parsers (GoogleSheets, CSV, Excel)           │
│  - Matcher                                      │
│  - Aggregation                                  │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│          Repositories (Data Access)              │
│  - SQLAlchemy ORM models                        │
│  - Async database operations                    │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│              Database (PostgreSQL)               │
│  - suppliers, products, supplier_items          │
│  - parsing_logs, price_history                  │
│  - categories, match_review_queue               │
└─────────────────────────────────────────────────┘
```

### Project Structure

```
src/
├── worker.py             # arq worker configuration
├── config.py             # Settings (pydantic-settings)
├── db/
│   ├── base.py           # Database connection
│   ├── operations.py     # Common DB operations
│   └── models/           # SQLAlchemy ORM models
├── models/               # Pydantic validation models
├── parsers/              # Data source parsers
│   ├── base_parser.py    # Abstract base class
│   ├── google_sheets_parser.py
│   └── parser_registry.py
├── services/             # Business logic
│   ├── matching/         # Product matching
│   ├── extraction/       # Feature extraction
│   └── aggregation/      # Price aggregation
├── tasks/                # arq task definitions
│   └── matching_tasks.py
└── errors/               # Custom exceptions
```

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg) | `postgresql+asyncpg://user:pass@localhost:5432/marketbel` |
| `REDIS_PASSWORD` | Redis password | `your_redis_password` |

### Redis Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_URL` | Auto-built | Full Redis URL (optional, built from above if not set) |

### Queue Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `QUEUE_NAME` | `price-ingestion-queue` | Main task queue name |
| `DLQ_NAME` | `price-ingestion-dlq` | Dead letter queue name |

### Worker Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_WORKERS` | `5` | Maximum concurrent workers |
| `JOB_TIMEOUT` | `300` | Task timeout in seconds |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `LOG_FORMAT` | `json` | Log format (json/console) |
| `ENVIRONMENT` | `development` | Environment name |

### Google Sheets Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_CREDENTIALS_PATH` | `/app/credentials/google-credentials.json` | Path to service account JSON |

### Master Sync Scheduler (Phase 6)

| Variable | Default | Description |
|----------|---------|-------------|
| `MASTER_SHEET_URL` | ⚠️ Required for sync | URL to Master Google Sheet with supplier configs |
| `SYNC_INTERVAL_HOURS` | `8` | Hours between automatic sync runs |

### Matching Pipeline (Phase 4)

| Variable | Default | Description |
|----------|---------|-------------|
| `MATCH_AUTO_THRESHOLD` | `95.0` | Score >= this triggers automatic linking |
| `MATCH_POTENTIAL_THRESHOLD` | `70.0` | Score >= this triggers review queue |
| `MATCH_BATCH_SIZE` | `100` | Items to process per batch (1-1000) |
| `MATCH_MAX_CANDIDATES` | `5` | Max candidates for review queue |
| `MATCH_REVIEW_EXPIRATION_DAYS` | `30` | Days until reviews expire |

### Example `.env` File

```bash
# Database
DATABASE_URL=postgresql+asyncpg://marketbel_user:dev_password@localhost:5432/marketbel

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=dev_redis_password

# Worker
MAX_WORKERS=5
JOB_TIMEOUT=300
LOG_LEVEL=INFO

# Google Sheets
GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json

# Master Sync (Phase 6)
MASTER_SHEET_URL=https://docs.google.com/spreadsheets/d/your-master-sheet-id
SYNC_INTERVAL_HOURS=8

# Matching (Phase 4)
MATCH_AUTO_THRESHOLD=95.0
MATCH_POTENTIAL_THRESHOLD=70.0
MATCH_BATCH_SIZE=100
```

---

## Development

### Running the Worker

```bash
# Activate virtual environment
source venv/bin/activate

# Development mode (auto-reload not supported by arq)
arq src.worker.WorkerSettings

# Watch logs
docker-compose logs -f worker
```

### Database Operations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Check current revision
alembic current
```

### Code Quality

```bash
# Type checking
mypy src/ --strict

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Format code
black src/ tests/
isort src/ tests/

# Lint
ruff check src/ tests/
```

### Enqueue Tasks Manually

```bash
# Parse a specific supplier
python scripts/enqueue_task.py

# Monitor queue
python scripts/monitor_queue.py
```

---

## Testing

### Test Structure

```
tests/
├── conftest.py           # Shared fixtures
├── unit/                 # Unit tests
│   ├── test_models.py
│   ├── test_parsers.py
│   ├── test_matcher.py
│   └── test_extractors.py
└── integration/          # Integration tests
    ├── test_end_to_end.py
    ├── test_matching_pipeline.py
    └── test_performance.py
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_parsers.py -v

# Run tests matching pattern
pytest tests/ -k "test_google" -v
```

### Coverage Targets

- **Business logic (services):** ≥85%
- **Parsers:** ≥80%
- **Models:** ≥90%

---

## Deployment

### Docker Deployment

#### Using Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# View worker logs
docker-compose logs -f worker

# Rebuild after changes
docker-compose build worker
docker-compose up -d worker
```

#### Standalone Docker

```bash
# Build the image
docker build -t marketbel-worker ./services/python-ingestion

# Run container
docker run \
  -e DATABASE_URL="postgresql+asyncpg://..." \
  -e REDIS_PASSWORD="..." \
  -v /path/to/credentials:/app/credentials:ro \
  marketbel-worker
```

### Pre-Deployment Checklist

1. **Database Migrations:**
   ```bash
   alembic upgrade head
   ```

2. **Google Credentials:**
   - Mount credentials file as read-only volume
   - Set `GOOGLE_CREDENTIALS_PATH` appropriately

3. **Environment Variables:**
   - Set `LOG_LEVEL=INFO` or `WARNING` for production
   - Configure `MASTER_SHEET_URL` for sync feature
   - Review matching thresholds

4. **Health Check:**
   ```bash
   # Worker provides health endpoint on port 8080
   curl http://localhost:8080/health
   ```

### Production Considerations

#### Security

- **Credentials:** Mount as read-only, never log
- **Database:** Use least-privilege user (INSERT/UPDATE/SELECT only)
- **Redis:** Use password authentication

#### Performance

- **Worker Count:** Tune `MAX_WORKERS` based on CPU cores
- **Job Timeout:** Increase `JOB_TIMEOUT` for large suppliers
- **Targets:**
  - Parse throughput: >1,000 items/min
  - Matching batch: <30 seconds for 100 items

#### Monitoring

- **Structured Logging:** JSON format for log aggregation
- **Metrics:** Queue depth, processing time, error rates
- **Alerts:** Dead letter queue size, worker crashes

---

## Troubleshooting

### Common Issues

#### Database Connection Failed

```
Error: Connection refused to localhost:5432
```

**Solution:**
- Check PostgreSQL is running: `docker-compose ps postgres`
- Verify `DATABASE_URL` format includes `+asyncpg`
- Check network access

#### Redis Connection Failed

```
Error: Redis connection refused
```

**Solution:**
- Check Redis is running: `docker-compose ps redis`
- Verify `REDIS_PASSWORD` is correct
- Check `REDIS_HOST` and `REDIS_PORT`

#### Google Sheets Authentication Failed

```
Error: Could not refresh access token
```

**Solution:**
- Verify service account JSON exists at `GOOGLE_CREDENTIALS_PATH`
- Check service account has Sheets API access
- Ensure sheet is shared with service account email

#### Task Timeout

```
Error: Job exceeded timeout
```

**Solution:**
- Increase `JOB_TIMEOUT` in environment
- Check supplier data size
- Monitor for network issues

### Debug Mode

Enable verbose logging:

```bash
LOG_LEVEL=DEBUG arq src.worker.WorkerSettings
```

### Support

- **Parser Guide:** `docs/parser-guide.md`
- **Mocking Guide:** `docs/mocking-guide.md`
- **Quickstart:** `specs/001-data-ingestion-infra/plan/quickstart.md`
- **Data Model:** `specs/001-data-ingestion-infra/plan/data-model.md`

---

## References

- [arq Documentation](https://arq-docs.helpmanual.io/)
- [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Pydantic v2](https://docs.pydantic.dev/)
- [gspread API](https://docs.gspread.org/)
- Phase 1 Spec: `specs/001-data-ingestion-infra/spec.md`
- Phase 4 Spec: `specs/004-product-matching-pipeline/spec.md`
- Phase 6 Spec: `specs/006-admin-sync-scheduler/spec.md`

---

**Version:** 1.0.0 | **Last Updated:** 2025-12-01

