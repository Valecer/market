# Implementation Plan: Data Ingestion Infrastructure

**Feature ID:** 001-data-ingestion-infra
**Status:** Ready for Implementation
**Branch:** 001-data-ingestion-infra

---

## Technology Stack

### Core Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Database** | PostgreSQL | 16 | JSONB support, mature async drivers |
| **Cache/Queue** | Redis | 7-alpine | Task queue and caching |
| **Runtime** | Python | 3.12 | Worker service implementation |
| **ORM** | SQLAlchemy | 2.0+ async | Database access with AsyncIO |
| **Database Driver** | asyncpg | latest | PostgreSQL async driver |
| **Task Queue** | arq | latest | Redis-based async task processing |
| **Data Processing** | pandas | 2.x | Data manipulation |
| **Validation** | pydantic | 2.x | Type-safe data validation |
| **Migrations** | alembic | 1.13+ | Database schema versioning |
| **Sheets API** | gspread | 6.x | Google Sheets integration |
| **Container** | Docker | 24+ | Service containerization |
| **Orchestration** | Docker Compose | v2 | Local development |

### Python Dependencies

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

---

## Project Structure

```
marketbel/
├── services/
│   └── python-ingestion/
│       ├── src/
│       │   ├── db/
│       │   │   ├── base.py              # Base ORM classes and mixins
│       │   │   └── models/              # SQLAlchemy models
│       │   │       ├── supplier.py
│       │   │       ├── category.py
│       │   │       ├── product.py
│       │   │       ├── supplier_item.py
│       │   │       ├── price_history.py
│       │   │       └── parsing_log.py
│       │   ├── parsers/                 # Data source parsers
│       │   │   ├── base.py              # Parser interface
│       │   │   └── google_sheets.py     # Google Sheets implementation
│       │   ├── models/                  # Pydantic validation models
│       │   │   ├── parsed_item.py
│       │   │   ├── queue_message.py
│       │   │   └── google_sheets_config.py
│       │   ├── exceptions.py            # Custom exceptions
│       │   ├── config.py                # Configuration management
│       │   └── worker.py                # arq worker configuration
│       ├── migrations/                  # Alembic migrations
│       │   └── versions/
│       ├── tests/                       # Test suite
│       ├── Dockerfile
│       ├── requirements.txt
│       └── alembic.ini
├── docker-compose.yml
└── .env.example
```

---

## Database Schema

### Core Tables

1. **suppliers** - External data sources with source_type (google_sheets, csv, excel)
2. **categories** - Product hierarchy (self-referential)
3. **products** - Internal unified catalog with status (draft/active/archived)
4. **supplier_items** - Raw supplier data with JSONB characteristics
5. **price_history** - Time-series price tracking
6. **parsing_logs** - Structured error logging

### Key Relationships

- One Supplier → Many SupplierItems (CASCADE delete)
- One Product → Many SupplierItems (SET NULL on delete)
- One SupplierItem → Many PriceHistory entries (CASCADE delete)

### Key Indexes

- GIN index on `supplier_items.characteristics` for JSONB queries
- Composite unique index on `(supplier_id, supplier_sku)`
- Descending indexes on timestamps for chronological queries

For complete schema details, see: `plan/data-model.md`

---

## Architecture Patterns

### 1. Parser Interface (FR-3)

Abstract base class for pluggable data sources:

```python
class ParserInterface(ABC):
    @abstractmethod
    async def parse(self, config: dict) -> List[ParsedItem]:
        """Parse data from source and return validated items"""
        pass

    @abstractmethod
    def validate_config(self, config: dict) -> bool:
        """Validate parser-specific configuration"""
        pass
```

**Implementations:**
- `GoogleSheetsParser` - Reads from Google Sheets API
- `CSVParser` (future) - Reads from CSV files
- `ExcelParser` (future) - Reads from Excel files

### 2. Async Architecture (FR-2)

Full async/await pattern throughout:
- SQLAlchemy AsyncIO for database operations
- arq for async task queue processing
- asyncpg for non-blocking PostgreSQL access

### 3. Queue-Based Processing (FR-4)

Decoupled ingestion with retry logic:
- Redis queue via arq
- Exponential backoff (1s, 5s, 25s)
- Dead letter queue for failed tasks
- Max 3 retries per task

### 4. JSONB Flexibility (FR-1)

Product characteristics stored as JSON for varying supplier fields:
- Dynamic column mapping with fuzzy matching
- Manual override configuration support
- GIN indexing for fast queries

### 5. Error Isolation (FR-5)

Per-row error logging prevents cascade failures:
- Errors logged to `parsing_logs` table
- Processing continues for valid rows
- Structured error tracking with context

---

## Implementation Milestones

### Milestone 1: Infrastructure Setup (Week 1)

**Deliverables:**
- Docker Compose configuration
- PostgreSQL service with health checks
- Redis service with password authentication
- Python worker Dockerfile

**Acceptance Criteria:**
- All services start successfully with `docker-compose up`
- Health checks pass for all services
- Services restart automatically on failure

---

### Milestone 2: Database Layer (Week 1-2)

**Deliverables:**
- SQLAlchemy models for all entities
- Alembic migration setup
- Initial schema migration
- Database connection pooling configuration

**Acceptance Criteria:**
- Migration runs successfully: `alembic upgrade head`
- All tables created with correct constraints
- Indexes verified
- Foreign key relationships validated

---

### Milestone 3: Parser Interface (Week 2)

**Deliverables:**
- Abstract `ParserInterface` base class
- `ParsedItem` Pydantic model
- Parser registration mechanism
- Configuration validation method

**Acceptance Criteria:**
- Parser interface defines `parse()` and `validate_config()` methods
- New parsers can inherit from base class
- Validation rejects invalid configurations

---

### Milestone 4: Google Sheets Parser (Week 2-3)

**Deliverables:**
- `GoogleSheetsParser` class
- gspread authentication setup
- Dynamic column mapping with fuzzy matching
- Characteristics JSONB builder
- Row-level error handling

**Acceptance Criteria:**
- Authenticates with Google service account
- Reads all rows from specified sheet
- Maps columns to standard fields (sku, name, price)
- Extracts characteristics from additional columns
- Handles missing data gracefully

---

### Milestone 5: Queue System (Week 3)

**Deliverables:**
- arq worker configuration
- `ParseTaskMessage` message handler
- Retry logic with exponential backoff
- Dead letter queue for failed tasks
- Queue monitoring script

**Acceptance Criteria:**
- Worker consumes messages from Redis queue
- Failed tasks retry up to 3 times with delays (1s, 5s, 25s)
- Tasks exceeding max retries move to DLQ
- Worker logs queue depth periodically

---

### Milestone 6: Data Ingestion Pipeline (Week 3-4)

**Deliverables:**
- End-to-end task processing
- Supplier get-or-create logic
- SupplierItem upsert with conflict resolution
- PriceHistory entry creation on price changes
- Transaction rollback on validation failures
- ParsingLogs insertion for errors

**Acceptance Criteria:**
- Task received → supplier created if not exists
- Valid items inserted into supplier_items
- Price changes recorded in price_history
- Invalid rows logged without crashing
- Database transaction rolls back on critical errors

---

### Milestone 7: Error Handling & Logging (Week 4)

**Deliverables:**
- Custom exception hierarchy
- Structured logging with structlog
- Error categorization
- ParsingLogs table insertion on errors
- Graceful degradation

**Acceptance Criteria:**
- Errors logged with context (task_id, supplier_id, row_number)
- Worker continues processing after non-critical errors
- Critical errors trigger task retry
- Parsing errors queryable via SQL

---

### Milestone 8: Testing & Validation (Week 4-5)

**Deliverables:**
- Unit tests for parsers (mock gspread)
- Integration tests (Docker services)
- Performance test: 10,000 items in <10 minutes
- Error scenario tests
- Test coverage ≥85%

**Acceptance Criteria:**
- All unit tests pass
- Integration tests pass with real Postgres/Redis
- Performance meets NFR: >1,000 items/min
- Error handling validated

---

### Milestone 9: Documentation & Deployment (Week 5)

**Deliverables:**
- Quickstart guide (already created)
- Parser implementation guide
- Deployment runbook
- Monitoring setup (optional)

**Acceptance Criteria:**
- New developer can set up locally in <30 minutes
- Documentation covers troubleshooting scenarios
- Deployment guide includes rollback procedures

---

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://marketbel_user:password@postgres:5432/marketbel

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# Google Sheets
GOOGLE_CREDENTIALS_PATH=/app/secrets/google-credentials.json

# Worker
MAX_WORKERS=5
JOB_TIMEOUT=300

# Logging
LOG_LEVEL=INFO
```

### Docker Compose Services

- **postgres**: PostgreSQL 16 with JSONB support
- **redis**: Redis 7-alpine for queue
- **worker**: Python worker service with arq

---

## Error Handling Strategy

### Error Categories

| Error Type | Retriable? | Action |
|-----------|-----------|--------|
| **ValidationError** | No | Log to parsing_logs, continue processing |
| **ParserError** | Yes | Retry task with backoff |
| **DatabaseError** | Yes | Rollback transaction, retry task |
| **AuthenticationError** | No | Move to DLQ, alert admin |
| **NetworkError** | Yes | Retry task with backoff |

### Retry Configuration

```python
MAX_RETRIES = 3
BACKOFF_DELAYS = [1, 5, 25]  # seconds
```

---

## Performance Requirements

| Requirement | Target | Validation |
|------------|--------|------------|
| **Throughput** | >1,000 items/min | Load test with 10,000 items |
| **Latency** | <100ms queue → processing | Measure with timestamps |
| **Memory** | <512MB per worker | Monitor Docker stats |

---

## Security Considerations

- Google service account credentials mounted as read-only volume
- Database and Redis passwords in `.env` (not committed)
- Least privilege for worker database user
- Pydantic validation prevents SQL injection

---

## Related Documents

- [Feature Specification](./spec.md) - Requirements and user scenarios
- [Research Document](./plan/research.md) - Technical decision rationale
- [Data Model](./plan/data-model.md) - Complete database schema
- [Quickstart Guide](./plan/quickstart.md) - Development setup
- [API Contracts](./plan/contracts/) - Queue message schemas

---

**Status:** ✅ READY FOR IMPLEMENTATION

**Last Updated:** 2025-11-24
