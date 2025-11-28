# Quickstart Guide: Data Ingestion Infrastructure

**Feature:** 001-data-ingestion-infra  
**Last Updated:** 2025-11-23  
**Estimated Setup Time:** 30 minutes

---

## Overview

This guide walks you through setting up and running the Data Ingestion Infrastructure locally for development and testing. By the end of this guide, you'll have:

- PostgreSQL database with schema initialized
- Redis queue running
- Python worker service processing tasks
- Sample data ingestion from Google Sheets

---

## Prerequisites

### Required Software

- **Docker Desktop** 24+ ([Download](https://www.docker.com/products/docker-desktop))
- **Docker Compose** v2+ (included with Docker Desktop)
- **Python** 3.12+ (for local development)
- **Git** (for cloning repository)

### Required Credentials

- **Google Service Account** JSON credentials with Sheets API access ([Setup Guide](https://developers.google.com/sheets/api/quickstart/python))
- Place credentials file at `credentials/google-sheets.json`

### System Requirements

- 2GB RAM available
- 2 CPU cores
- 5GB disk space

---

## Quick Start (5 Minutes)

### 1. Clone and Configure

```bash
# Clone repository (replace with actual repo URL)
git clone <repository-url>
cd marketbel

# Create environment file
cp .env.example .env

# Edit .env with your configuration
nano .env
```

**Required Environment Variables:**

```bash
# Database
POSTGRES_USER=marketbel_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=marketbel
DATABASE_URL=postgresql+asyncpg://marketbel_user:your_secure_password@postgres:5432/marketbel

# Redis
REDIS_PASSWORD=your_redis_password
REDIS_URL=redis://:your_redis_password@redis:6379/0

# Queue
QUEUE_NAME=price-ingestion-queue
DLQ_NAME=price-ingestion-dlq

# Worker
WORKER_COUNT=3
LOG_LEVEL=INFO

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_PATH=/app/credentials/google-sheets.json
```

### 2. Start Services

```bash
# Start all services in background
docker-compose up -d

# Verify all services are running
docker-compose ps

# Expected output:
# NAME                 STATUS
# marketbel-postgres   Up (healthy)
# marketbel-redis      Up
# marketbel-worker     Up
```

### 3. Initialize Database

```bash
# Run database migrations
docker-compose exec worker alembic upgrade head

# Verify tables created
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "\dt"

# Expected tables:
# suppliers, categories, products, supplier_items, price_history, parsing_logs
```

### 4. Test with Sample Data

```bash
# Enqueue a test parse task
python scripts/enqueue_task.py \
  --task-id "test-001" \
  --parser-type "google_sheets" \
  --supplier-name "Test Supplier" \
  --sheet-url "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID" \
  --sheet-name "Price List"

# Monitor worker logs
docker-compose logs -f worker

# Check results in database
docker-compose exec postgres psql -U marketbel_user -d marketbel -c \
  "SELECT COUNT(*) FROM supplier_items;"
```

---

## Detailed Setup

### Directory Structure

```
marketbel/
├── docker-compose.yml          # Service orchestration
├── .env                        # Environment configuration
├── credentials/
│   └── google-sheets.json      # Google API credentials (gitignored)
├── services/
│   └── python-ingestion/
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── src/
│       │   ├── db/
│       │   │   ├── base.py
│       │   │   └── models/
│       │   │       ├── supplier.py
│       │   │       ├── category.py
│       │   │       ├── product.py
│       │   │       ├── supplier_item.py
│       │   │       ├── price_history.py
│       │   │       └── parsing_log.py
│       │   ├── parsers/
│       │   │   ├── base_parser.py
│       │   │   ├── google_sheets_parser.py
│       │   │   ├── csv_parser.py       # Future
│       │   │   └── excel_parser.py      # Future
│       │   ├── models/
│       │   │   ├── parsed_item.py
│       │   │   └── queue_message.py
│       │   ├── worker.py
│       │   └── config.py
│       └── migrations/
│           ├── alembic.ini
│           ├── env.py
│           └── versions/
│               └── 001_initial_schema.py
├── scripts/
│   ├── enqueue_task.py         # Helper to enqueue tasks
│   └── monitor_queue.py        # Queue monitoring tool
└── docs/
    └── setup.md
```

### Service Configuration

#### docker-compose.yml

```yaml
version: '3.9'

services:
  postgres:
    image: postgres:16
    container_name: marketbel-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: marketbel-redis
    command: redis-server --requirepass ${REDIS_PASSWORD}
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    restart: unless-stopped

  worker:
    build:
      context: ./services/python-ingestion
      dockerfile: Dockerfile
    container_name: marketbel-worker
    environment:
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
      QUEUE_NAME: ${QUEUE_NAME}
      DLQ_NAME: ${DLQ_NAME}
      LOG_LEVEL: ${LOG_LEVEL}
      WORKER_COUNT: ${WORKER_COUNT}
      GOOGLE_SHEETS_CREDENTIALS_PATH: ${GOOGLE_SHEETS_CREDENTIALS_PATH}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./credentials:/app/credentials:ro
      - ./services/python-ingestion/src:/app/src:ro
    restart: unless-stopped
    command: ["python", "-m", "arq", "src.worker.WorkerSettings"]

volumes:
  postgres_data:
  redis_data:
```

#### Dockerfile (services/python-ingestion/Dockerfile)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 worker && chown -R worker:worker /app
USER worker

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import redis; r=redis.from_url('${REDIS_URL}'); r.ping()"

CMD ["python", "-m", "arq", "src.worker.WorkerSettings"]
```

#### requirements.txt

```txt
# Core
sqlalchemy[asyncio]>=2.0.23
asyncpg>=0.29.0
alembic>=1.13.0
pydantic>=2.5.0
pydantic-settings>=2.1.0

# Data Processing
pandas>=2.1.3
gspread>=6.0.0
oauth2client>=4.1.3

# Queue
arq>=0.25.0
redis>=5.0.1

# Utilities
python-dotenv>=1.0.0
structlog>=24.1.0
```

---

## Usage Examples

### Example 1: Enqueue Google Sheets Parse Task

```python
# scripts/enqueue_task.py
import asyncio
import json
from arq import create_pool
from arq.connections import RedisSettings
import os

async def enqueue_google_sheets_task():
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL"))
    redis = await create_pool(redis_settings)
    
    task_message = {
        "task_id": "task-2025-11-23-001",
        "parser_type": "google_sheets",
        "supplier_name": "Acme Wholesale",
        "source_config": {
            "sheet_url": "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID",
            "sheet_name": "Price List",
            "column_mapping": {
                "sku": "Product Code",
                "name": "Description",
                "price": "Unit Price"
            },
            "characteristic_columns": ["Color", "Size", "Material"],
            "header_row": 1,
            "data_start_row": 2
        },
        "retry_count": 0,
        "max_retries": 3
    }
    
    job = await redis.enqueue_job(
        'parse_task',
        task_message
    )
    print(f"Enqueued job: {job.job_id}")
    await redis.close()

if __name__ == "__main__":
    asyncio.run(enqueue_google_sheets_task())
```

**Run:**
```bash
python scripts/enqueue_task.py
```

### Example 2: Query Ingested Data

```sql
-- Find all items from a supplier
SELECT 
    si.supplier_sku,
    si.name,
    si.current_price,
    si.characteristics,
    s.name AS supplier_name
FROM supplier_items si
JOIN suppliers s ON si.supplier_id = s.id
WHERE s.name = 'Acme Wholesale'
ORDER BY si.name;

-- Get price history for an item
SELECT 
    si.supplier_sku,
    si.name,
    ph.price,
    ph.recorded_at
FROM price_history ph
JOIN supplier_items si ON ph.supplier_item_id = si.id
WHERE si.supplier_sku = 'ABC-001'
ORDER BY ph.recorded_at DESC;

-- Find items with specific characteristics
SELECT * FROM supplier_items
WHERE characteristics @> '{"color": "red"}'::jsonb;

-- Check recent parsing errors
SELECT 
    pl.task_id,
    pl.error_type,
    pl.error_message,
    pl.row_number,
    pl.created_at
FROM parsing_logs pl
WHERE pl.created_at > NOW() - INTERVAL '1 hour'
ORDER BY pl.created_at DESC;
```

### Example 3: Monitor Queue

```python
# scripts/monitor_queue.py
import asyncio
import redis.asyncio as redis
import os

async def monitor_queue():
    r = await redis.from_url(os.getenv("REDIS_URL"))
    queue_name = os.getenv("QUEUE_NAME")
    dlq_name = os.getenv("DLQ_NAME")
    
    while True:
        queue_length = await r.llen(queue_name)
        dlq_length = await r.llen(dlq_name)
        
        print(f"Queue: {queue_length} | DLQ: {dlq_length}")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(monitor_queue())
```

**Run:**
```bash
python scripts/monitor_queue.py
```

---

## Development Workflow

### Local Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
cd services/python-ingestion
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Testing tools

# Set up pre-commit hooks (optional)
pre-commit install
```

### Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires Docker services running)
pytest tests/integration/ -v

# Coverage report
pytest --cov=src --cov-report=html

# Open coverage report
open htmlcov/index.html
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add new column"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# View migration history
alembic history
```

### Debugging

```bash
# Access PostgreSQL CLI
docker-compose exec postgres psql -U marketbel_user -d marketbel

# Access Redis CLI
docker-compose exec redis redis-cli -a your_redis_password

# View worker logs
docker-compose logs -f worker

# Restart worker after code changes
docker-compose restart worker

# Execute Python shell in worker container
docker-compose exec worker python
```

---

## Troubleshooting

### Issue: Worker fails to start

**Symptoms:**
```
ERROR: Cannot connect to Redis
```

**Solution:**
```bash
# Check Redis is running
docker-compose ps redis

# Verify Redis password in .env matches docker-compose.yml
grep REDIS_PASSWORD .env

# Test Redis connection
docker-compose exec redis redis-cli -a your_password ping
```

---

### Issue: Google Sheets authentication fails

**Symptoms:**
```
ERROR: Invalid credentials for Google Sheets API
```

**Solution:**
1. Verify `credentials/google-sheets.json` exists
2. Check service account has Sheets API enabled
3. Share target Google Sheet with service account email
4. Verify file path in `.env` matches volume mount

```bash
# Check credentials file
ls -la credentials/google-sheets.json

# View service account email
cat credentials/google-sheets.json | grep client_email
```

---

### Issue: Database migration fails

**Symptoms:**
```
ERROR: relation "suppliers" already exists
```

**Solution:**
```bash
# Check current migration version
docker-compose exec worker alembic current

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
docker-compose exec worker alembic upgrade head
```

---

### Issue: No items being ingested

**Symptoms:**
- Worker logs show "Processing task" but no database inserts

**Debugging Steps:**
```bash
# 1. Check parsing logs table for errors
docker-compose exec postgres psql -U marketbel_user -d marketbel -c \
  "SELECT * FROM parsing_logs ORDER BY created_at DESC LIMIT 10;"

# 2. Verify column mapping in task message
# 3. Check Google Sheet is accessible
# 4. Verify data format (price should be numeric)

# 5. Enable DEBUG logging
# In .env: LOG_LEVEL=DEBUG
docker-compose restart worker
docker-compose logs -f worker
```

---

## Performance Tuning

### Increase Worker Concurrency

```bash
# In .env
WORKER_COUNT=5  # Increase from default 3

# Restart worker
docker-compose restart worker
```

### Optimize Database Connections

```python
# In src/config.py
engine = create_async_engine(
    DATABASE_URL,
    pool_size=30,        # Increase from 20
    max_overflow=20,     # Increase from 10
    pool_pre_ping=True
)
```

### Batch Processing

For large sheets (>10,000 rows), consider batching inserts:

```python
# In parser implementation
BATCH_SIZE = 1000

for i in range(0, len(items), BATCH_SIZE):
    batch = items[i:i+BATCH_SIZE]
    async with session.begin():
        session.add_all(batch)
```

---

## Next Steps

### Phase 2: Add New Parser

See [Parser Implementation Guide](./docs/parser-guide.md) for:
- CSV parser implementation
- Excel parser implementation
- Custom parser development

### Phase 3: Production Deployment

See [Deployment Guide](./docs/deployment.md) for:
- Kubernetes manifests
- Monitoring setup (Prometheus/Grafana)
- Log aggregation (ELK stack)
- Backup/restore procedures

### Phase 4: API Integration

Once the Bun User API is built:
- Trigger ingestion via HTTP endpoints
- Query supplier items via REST API
- Real-time ingestion status webhooks

---

## Support Resources

### Documentation
- [Feature Specification](../spec.md)
- [Data Model](./data-model.md)
- [Research Decisions](./research.md)
- [API Contracts](./contracts/)

### External Links
- [PostgreSQL JSONB Documentation](https://www.postgresql.org/docs/current/datatype-json.html)
- [Google Sheets API v4](https://developers.google.com/sheets/api)
- [ARQ Documentation](https://arq-docs.helpmanual.io/)
- [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

### Community
- Internal Slack: `#marketbel-ingestion`
- Issue Tracker: GitHub Issues
- Code Reviews: GitHub Pull Requests

---

**Ready to start?** Run `docker-compose up -d` and follow Section 2 above! 🚀

