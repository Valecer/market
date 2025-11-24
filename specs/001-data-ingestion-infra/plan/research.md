# Research: Data Ingestion Infrastructure

**Date:** 2025-11-23  
**Feature:** 001-data-ingestion-infra  
**Status:** Completed

---

## Overview

This document consolidates research findings for technical decisions, best practices, and patterns needed to implement the Data Ingestion Infrastructure.

---

## Technical Decisions

### 1. SQLAlchemy AsyncIO vs Synchronous ORM

**Decision:** Use SQLAlchemy 2.0+ with AsyncIO support

**Rationale:**
- Modern async/await patterns enable better concurrency for I/O-bound operations
- Native asyncpg driver provides superior performance over psycopg2
- Async operations integrate seamlessly with async task queue (arq)
- Better resource utilization when handling multiple concurrent parse tasks
- SQLAlchemy 2.0 has mature async support with comprehensive documentation

**Alternatives Considered:**
- **Synchronous SQLAlchemy:** Simpler but blocks workers during database operations
- **Raw asyncpg:** More performant but lacks ORM convenience and migration tooling
- **Django ORM:** Not suitable without full Django framework

**Implementation Notes:**
```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    echo=False,
    pool_size=20,
    max_overflow=10
)
```

---

### 2. Task Queue: arq vs Celery

**Decision:** Use `arq` for Redis-based task processing

**Rationale:**
- Built natively on asyncio, matches SQLAlchemy async architecture
- Simpler configuration than Celery (no separate broker/backend)
- Redis-only approach reduces infrastructure complexity
- Excellent retry and job result tracking built-in
- Lower overhead and memory footprint
- Active maintenance and modern Python features support

**Alternatives Considered:**
- **Celery:** Industry standard but more complex, supports multiple brokers (overkill for our needs)
- **RQ:** Simpler than Celery but synchronous, doesn't match async architecture
- **Dramatiq:** Good alternative but less Redis-optimized than arq

**Implementation Pattern:**
```python
from arq import create_pool, cron
from arq.connections import RedisSettings

async def parse_task(ctx, message: dict):
    # Task implementation
    pass

class WorkerSettings:
    redis_settings = RedisSettings(host='localhost', port=6379)
    functions = [parse_task]
    max_jobs = 5
    job_timeout = 300
```

---

### 3. Google Sheets Access: gspread vs google-api-python-client

**Decision:** Use `gspread` with service account authentication

**Rationale:**
- Higher-level API specifically designed for Sheets operations
- Simpler authentication flow with service accounts
- Built-in retry logic and rate limiting
- Pandas integration available via `gspread-dataframe`
- Cleaner code for common operations (read range, get all records)
- Active community and extensive examples

**Alternatives Considered:**
- **google-api-python-client:** More generic, requires more boilerplate for Sheets operations
- **pygsheets:** Similar to gspread but less mature and smaller community

**Authentication Setup:**
```python
import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)
```

---

### 4. Data Validation: Pydantic v2

**Decision:** Use Pydantic v2 for data validation before database insertion

**Rationale:**
- Type-safe validation with Python type hints
- Automatic JSON schema generation for documentation
- Excellent error messages for debugging invalid data
- Performance improvements in v2 (rust core)
- Integrates well with SQLAlchemy models via pydantic-settings
- Standard in modern Python APIs (FastAPI uses it)

**Validation Strategy:**
```python
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal

class ParsedSupplierItem(BaseModel):
    supplier_sku: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=500)
    price: Decimal = Field(..., ge=0, decimal_places=2)
    characteristics: dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('price')
    def validate_price_precision(cls, v):
        if v.as_tuple().exponent < -2:
            raise ValueError('Price must have at most 2 decimal places')
        return v
```

---

### 5. Database Migration: Alembic

**Decision:** Use Alembic for database schema versioning

**Rationale:**
- Official SQLAlchemy migration tool
- Supports both sync and async engines
- Auto-generation of migrations from model changes
- Rollback capabilities essential for production
- Branch merging for concurrent development
- Works seamlessly with asyncpg

**Migration Setup:**
```bash
alembic init migrations
# Configure alembic.ini with async database URL
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

---

### 6. Dynamic Column Mapping Strategy

**Decision:** Implement header analysis with fuzzy matching and configuration overrides

**Rationale:**
- Google Sheets headers vary between suppliers
- Manual configuration for each supplier is unmaintainable
- Fuzzy matching (e.g., "Product Name" → "name") improves flexibility
- Configuration overrides allow manual fixes when fuzzy matching fails

**Implementation Approach:**
```python
from difflib import get_close_matches

STANDARD_FIELDS = {
    'sku': ['sku', 'code', 'item_code', 'product_code'],
    'name': ['name', 'product_name', 'description', 'title'],
    'price': ['price', 'cost', 'unit_price', 'amount'],
}

def detect_column_mapping(headers: list[str], config_override: dict = None) -> dict:
    """
    Match sheet headers to standard fields using fuzzy matching
    config_override allows manual specification: {'sku': 'A', 'price': 'C'}
    """
    mapping = {}
    if config_override:
        mapping.update(config_override)
    
    for field, synonyms in STANDARD_FIELDS.items():
        if field in mapping:
            continue
        matches = get_close_matches(headers, synonyms, n=1, cutoff=0.6)
        if matches:
            mapping[field] = headers.index(matches[0])
    
    return mapping
```

---

### 7. Error Logging Strategy

**Decision:** Create `ParsingLogs` table for structured error tracking

**Rationale:**
- Errors must not crash the container (requirement)
- Database storage enables querying and analytics on failures
- Structured logging allows filtering by error type, supplier, timestamp
- Facilitates debugging and data quality monitoring

**Schema:**
```sql
CREATE TABLE parsing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id VARCHAR(255) NOT NULL,
    supplier_id UUID REFERENCES suppliers(id),
    error_type VARCHAR(100) NOT NULL, -- 'ValidationError', 'ParserError', etc.
    error_message TEXT NOT NULL,
    row_number INTEGER,
    row_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_parsing_logs_supplier ON parsing_logs(supplier_id);
CREATE INDEX idx_parsing_logs_task ON parsing_logs(task_id);
CREATE INDEX idx_parsing_logs_created ON parsing_logs(created_at DESC);
```

---

### 8. Docker Base Image

**Decision:** Use `python:3.12-slim` as base image

**Rationale:**
- Python 3.12 has performance improvements (up to 25% faster than 3.10)
- `slim` variant reduces image size (~150MB vs ~900MB for full image)
- Includes essential build tools for compiled dependencies
- Official Python image with security updates
- Balances size and functionality

**Dockerfile Pattern:**
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "arq", "worker.WorkerSettings"]
```

---

### 9. Draft vs Active Products Architecture

**Decision:** Add `status` enum field to `products` table

**Rationale:**
- Simple implementation without table duplication
- Enables easy transitions between states
- Supports querying by status for workflows
- Future-proof for additional states (e.g., 'archived', 'discontinued')

**Schema Addition:**
```sql
CREATE TYPE product_status AS ENUM ('draft', 'active', 'archived');

ALTER TABLE products ADD COLUMN status product_status NOT NULL DEFAULT 'draft';
CREATE INDEX idx_products_status ON products(status);
```

---

### 10. Connection Pooling Configuration

**Decision:** Configure SQLAlchemy pool_size=20, max_overflow=10

**Rationale:**
- Supports up to 20 concurrent database connections
- max_overflow allows bursts up to 30 connections
- Matches NFR-2 requirement: "support up to 20 concurrent workers"
- PostgreSQL default max_connections=100 provides headroom
- Pool recycling prevents stale connections

**Configuration:**
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True  # Verify connection health before use
)
```

---

## Best Practices Applied

### Pandas Data Processing
- Use `read_excel()` with `dtype` parameter to prevent type inference issues
- Employ `fillna()` to handle missing values before validation
- Use `to_dict('records')` for row-by-row processing
- Leverage `pd.to_numeric()` with `errors='coerce'` for robust price parsing

### Redis Queue Patterns
- Use Redis Lists (LPUSH/BRPOP) for FIFO queue behavior
- Implement visibility timeout with separate "processing" list
- Store job results with TTL for garbage collection
- Use Redis transactions for atomic message operations

### SQLAlchemy Async Patterns
- Always use `async with session.begin()` for transactions
- Prefer `session.execute(select())` over `session.query()` (2.0 style)
- Use `selectinload()` for eager loading to avoid N+1 queries
- Batch inserts with `session.add_all()` for performance

### Error Handling
- Use custom exception hierarchy rooted in `DataIngestionError`
- Log errors with structured context (task_id, supplier_id, row_number)
- Implement exponential backoff for transient failures
- Separate retriable vs non-retriable errors

---

## Integration Patterns

### Google Sheets → Pandas → Pydantic → SQLAlchemy Flow

```python
async def process_google_sheet(sheet_url: str, supplier_id: UUID):
    # 1. Fetch data from Google Sheets
    client = gspread.authorize(credentials)
    sheet = client.open_by_url(sheet_url).sheet1
    data = sheet.get_all_records()
    
    # 2. Convert to DataFrame
    df = pd.DataFrame(data)
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df = df.fillna({'characteristics': {}})
    
    # 3. Validate with Pydantic
    validated_items = []
    for idx, row in df.iterrows():
        try:
            item = ParsedSupplierItem(**row.to_dict())
            validated_items.append(item)
        except ValidationError as e:
            await log_parsing_error(task_id, supplier_id, idx, str(e))
    
    # 4. Persist to database
    async with AsyncSession(engine) as session:
        async with session.begin():
            for item in validated_items:
                db_item = SupplierItem(
                    supplier_id=supplier_id,
                    **item.model_dump()
                )
                session.add(db_item)
```

---

## Remaining Considerations

### 1. Google Sheets API Rate Limits
- **Limit:** 100 requests per 100 seconds per user
- **Mitigation:** Batch read entire sheet in single request, use exponential backoff on 429 errors
- **Monitoring:** Log API call timestamps to track rate limit proximity

### 2. JSONB Indexing Performance
- GIN index on `characteristics` supports queries like `WHERE characteristics @> '{"color": "red"}'`
- Trade-off: Increases write time, essential for future filtering features
- Monitor index size growth over time

### 3. Time Zone Handling
- Store all timestamps in UTC (database default)
- Convert to local time only in presentation layer
- Use `TIMESTAMP WITH TIME ZONE` if multiple geographic regions

### 4. Duplicate Detection Strategy
- UNIQUE constraint on `(supplier_id, supplier_sku)` prevents duplicates
- On conflict: Update `current_price` and `updated_at`, insert new price_history entry
- Use `INSERT ... ON CONFLICT DO UPDATE` for upsert behavior

---

## Technology Stack Summary

| Component | Technology | Version |
|-----------|-----------|---------|
| **Database** | PostgreSQL | 16 |
| **Cache/Queue** | Redis | 7-alpine |
| **Python Runtime** | Python | 3.12 |
| **ORM** | SQLAlchemy | 2.0+ (async) |
| **Database Driver** | asyncpg | latest |
| **Task Queue** | arq | latest |
| **Data Processing** | pandas | 2.x |
| **Sheets API** | gspread | 6.x |
| **Validation** | pydantic | 2.x |
| **Migrations** | alembic | 1.13+ |
| **Container** | Docker | 24+ |
| **Orchestration** | Docker Compose | v2 |

---

## External Dependencies

### Python Packages
```txt
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
alembic>=1.13.0
pandas>=2.1.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
gspread>=6.0.0
oauth2client>=4.1.3
arq>=0.25.0
redis>=5.0.0
python-dotenv>=1.0.0
structlog>=24.1.0
```

### System Dependencies
- PostgreSQL 16 client libraries
- gcc (for compiling Python extensions)
- libpq-dev (PostgreSQL development headers)

### External Services
- Google Sheets API (requires OAuth2 service account)
- Google Drive API (for sheet access via service account)

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Google Sheets API quota exceeded | High | Medium | Implement rate limiting, batch operations, cache results |
| Database connection pool exhaustion | High | Low | Monitor pool metrics, configure appropriate pool size, implement circuit breaker |
| Memory leak from pandas DataFrames | Medium | Low | Clear DataFrames after processing, monitor memory usage |
| JSONB query performance degradation | Medium | Medium | Implement GIN indexes, query optimization, consider normalization if needed |
| Parser failures cascade | High | Low | Isolate parser errors, implement per-row error handling |

---

## Next Steps

- Proceed to Phase 1: Data Model Design
- Define SQLAlchemy model classes based on schema
- Create API contracts for future endpoints
- Generate quickstart documentation

---

**Approval:**
- [x] Research Complete - Ready for Phase 1

