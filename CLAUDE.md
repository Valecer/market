# Claude Agent Context

This file provides context to Claude AI when working on this project.

## Project Overview

**Name:** Marketbel - Unified Catalog System  
**Type:** Data ingestion infrastructure for supplier price list management  
**Stage:** Planning Complete, Implementation Pending

Before implmentation, use mcp context7 to collect up-to-date documentation.

## Technology Stack

### Backend Infrastructure

**Python Worker Service:**
- **Runtime:** Python 3.12 (cmd in use python3.13, and venv)
- **ORM:** SQLAlchemy 2.0+ with AsyncIO support
- **Database Driver:** asyncpg (PostgreSQL async driver)
- **Task Queue:** arq (asyncio-based Redis queue)
- **Data Processing:** pandas 2.x
- **Validation:** pydantic 2.x
- **Migrations:** alembic 1.13+
- **API Integration:** gspread 6.x (Google Sheets API)

**Database:**
- **PostgreSQL 16** with JSONB support for flexible product characteristics
- Schema includes: suppliers, categories, products, supplier_items, price_history, parsing_logs

**Queue/Cache:**
- **Redis 7 (alpine)** for task queue and caching

**Container Orchestration:**
- **Docker** 24+
- **Docker Compose** v2 for local development

### Key Design Patterns

1. **Parser Interface:** Abstract base class for pluggable data sources (Google Sheets, CSV, Excel)
2. **Async Architecture:** Full async/await pattern with SQLAlchemy AsyncIO + arq
3. **Queue-Based Processing:** Decoupled ingestion with retry logic and dead letter queue
4. **JSONB Flexibility:** Product characteristics stored as JSON for varying supplier fields
5. **Error Isolation:** Per-row error logging to `parsing_logs` table prevents cascade failures

### Data Model Highlights

**Core Entities:**
- `Supplier` - External data sources with source_type (google_sheets, csv, excel)
- `Product` - Internal catalog with status enum (draft, active, archived)
- `SupplierItem` - Raw supplier data with JSONB characteristics
- `PriceHistory` - Time-series price tracking
- `ParsingLog` - Structured error logging without crashing worker

**Key Relationships:**
- One Supplier → Many SupplierItems (CASCADE delete)
- One Product → Many SupplierItems (SET NULL on delete)
- One SupplierItem → Many PriceHistory entries (CASCADE delete)

**Indexes:**
- GIN index on `supplier_items.characteristics` for JSONB queries
- Composite unique index on `(supplier_id, supplier_sku)`
- Descending indexes on timestamps for chronological queries

### Project Structure

```
marketbel/
├── specs/
│   └── 001-data-ingestion-infra/
│       ├── spec.md                    # Feature specification
│       ├── checklists/requirements.md # Requirements tracking
│       └── plan/                      # Implementation planning
│           ├── research.md            # Technical decisions
│           ├── data-model.md          # Database schema & ORM
│           ├── implementation-plan.md # 9-milestone roadmap
│           ├── quickstart.md          # Setup guide
│           ├── contracts/             # JSON Schema contracts
│           └── SUMMARY.md             # Planning summary
├── services/
│   └── python-ingestion/
│       ├── src/
│       │   ├── db/models/             # SQLAlchemy ORM models
│       │   ├── parsers/               # Data source parsers
│       │   ├── models/                # Pydantic validation models
│       │   └── worker.py              # arq worker configuration
│       └── migrations/                # Alembic migrations
└── docker-compose.yml                 # Service orchestration
```

## Current Focus

**Feature:** 001-data-ingestion-infra  
**Phase:** Planning Complete ✅  
**Next Step:** Begin Implementation (Milestone 1: Infrastructure Setup)

**Recent Work:**
- Completed research on technology stack decisions
- Designed complete database schema with 6 tables
- Created JSON Schema contracts for queue messages
- Generated quickstart guide for 30-minute setup
- Built 9-milestone implementation roadmap (5 weeks)

## Development Guidelines

### Code Style

**Python:**
- Use async/await for all I/O operations
- Type hints required for all functions
- Pydantic models for data validation
- structlog for structured JSON logging

**Database:**
- Use SQLAlchemy 2.0 style (no legacy Query API)
- Always use `async with session.begin()` for transactions
- Prefer `session.execute(select())` over `session.query()`

**Error Handling:**
- Custom exception hierarchy rooted in `DataIngestionError`
- Per-row error logging to `parsing_logs` table
- Retry logic with exponential backoff (1s, 5s, 25s)
- Dead letter queue for permanently failed tasks

### Testing Requirements

- **Unit Tests:** ≥85% coverage for business logic
- **Integration Tests:** End-to-end with Docker services
- **Performance Tests:** >1,000 items/min throughput

### Testing Best Practices

**Mocking with `patch.object()`:**
- ✅ **Always use `patch.object()` for mocking object attributes** - automatically restores original state after tests
- ❌ **Never use direct assignment** - `obj.attribute = Mock()` leaks between tests
- Use context managers (`with patch.object(...)`) for scope-limited mocks
- Use decorators (`@patch.object`) when mocking throughout entire test method
- For module-level patching, use `@patch('module.path')` instead

**Example - Correct Approach:**
```python
async def test_parse_with_mocked_client(self, parser, mock_spreadsheet):
    """Using patch.object() - recommended."""
    with patch.object(parser._client, 'open_by_url', return_value=mock_spreadsheet):
        result = await parser.parse(config)
        # Mock automatically restored after 'with' block
```

**Example - Incorrect Approach:**
```python
async def test_parse_with_mocked_client(self, parser, mock_spreadsheet):
    """Direct assignment - AVOID."""
    parser._client.open_by_url = Mock(return_value=mock_spreadsheet)
    result = await parser.parse(config)
    # Attribute remains changed - can affect other tests!
```

**When to use `patch.object()` vs `patch()`:**
- Use `patch.object()` when: patching attributes of existing object instances
- Use `patch()` when: patching imports/module-level functions/classes
- See `/docs/mocking-guide.md` for detailed examples and rationale

### Security Considerations

- Google service account credentials mounted as read-only volume
- Database and Redis passwords in `.env` (not committed)
- Least privilege for worker database user (INSERT/UPDATE/SELECT only)
- Pydantic validation prevents SQL injection via parameterized queries

## Commands

### Docker Operations
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f worker

# Run migrations
docker-compose exec worker alembic upgrade head

# Access database
docker-compose exec postgres psql -U marketbel_user -d marketbel
```

### Development
```bash
# Create virtual environment
python -m venv venv && source venv/bin/activate

# Install dependencies
pip install -r services/python-ingestion/requirements.txt

# Run tests
pytest tests/ -v --cov=src

# Create migration
alembic revision --autogenerate -m "Description"
```

## Key References

**Internal Documentation:**
- Feature Spec: `/specs/001-data-ingestion-infra/spec.md`
- Implementation Plan: `/specs/001-data-ingestion-infra/plan/implementation-plan.md`
- Data Model: `/specs/001-data-ingestion-infra/plan/data-model.md`
- Quickstart: `/specs/001-data-ingestion-infra/plan/quickstart.md`

**External Documentation:**
- [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [arq Documentation](https://arq-docs.helpmanual.io/)
- [Pydantic v2](https://docs.pydantic.dev/)
- [gspread API](https://docs.gspread.org/)

## Notes for Claude

- **Parser extensibility is critical:** New data sources should be easy to add
- **Error handling must not crash worker:** Use `parsing_logs` table
- **Performance target:** >1,000 items/min throughput
- **Dynamic column mapping:** Google Sheets headers vary between suppliers
- **JSONB characteristics:** Flexible schema for varying product attributes
- **Product lifecycle:** Draft → Active → Archived status transitions

When implementing:
1. Start with `quickstart.md` for environment setup
2. Reference `data-model.md` for SQLAlchemy models
3. Use `contracts/` JSON schemas for validation
4. Follow milestones in `implementation-plan.md`
5. Consult `research.md` for technical decision rationale

## Workflow State

**Current Branch:** 001-data-ingestion-infra (worktree)  
**Planning Status:** Complete ✅  
**Implementation Status:** Not started  
**Next Milestone:** M1 - Infrastructure Setup (Week 1)

