# Claude Agent Context

This file provides context to Claude AI when working on this project.

## Project Overview

**Name:** Marketbel - Unified Catalog System
**Type:** Multi-service application for supplier price list management and product catalog
**Stage:** Phase 1 Complete ✅ | Phase 2 Planning Complete ✅

Before implementation, use mcp context7 to collect up-to-date documentation.

## Technology Stack

### Backend Infrastructure

**Bun API Service (Phase 2):**
- **Runtime:** Bun (latest)
- **Framework:** ElysiaJS (high-performance, type-safe)
- **ORM:** Drizzle ORM + node-postgres
- **Validation:** TypeBox (native to Elysia)
- **Authentication:** @elysiajs/jwt + bcrypt
- **Documentation:** @elysiajs/swagger (auto-generated OpenAPI)
- **Queue Client:** ioredis (publisher-only)
- **Database Access:** READ-ONLY for Phase 1 tables, MANAGED for users table

**Python Worker Service (Phase 1):**
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

**Phase 2 (Bun API):**
1. **SOLID Architecture:** Controllers (HTTP) → Services (logic) → Repositories (data)
2. **Feature-Based Structure:** auth/, catalog/, admin/ modules with controller/service/model
3. **Type Safety:** End-to-end TypeScript with Drizzle ORM + TypeBox validation
4. **JWT Authentication:** Role-based access (sales, procurement, admin)
5. **Schema Introspection:** Drizzle reads Phase 1 schema without managing migrations
6. **Queue Publisher:** Redis LPUSH for async task delegation to Python worker

**Phase 1 (Python Worker):**
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
│   ├── 001-data-ingestion-infra/     # Phase 1 (Python Worker)
│   │   ├── spec.md
│   │   └── plan/
│   │       ├── research.md
│   │       ├── data-model.md
│   │       ├── implementation-plan.md
│   │       ├── quickstart.md
│   │       └── contracts/
│   └── 002-api-layer/                 # Phase 2 (Bun API)
│       ├── spec.md
│       └── plan/
│           ├── research.md
│           ├── data-model.md
│           ├── quickstart.md
│           └── contracts/
│               ├── catalog-api.json
│               ├── admin-api.json
│               ├── auth-api.json
│               └── queue-messages.json
├── services/
│   ├── bun-api/                       # Phase 2: API Service
│   │   ├── src/
│   │   │   ├── index.ts               # Entry point
│   │   │   ├── db/
│   │   │   │   ├── client.ts          # Drizzle connection
│   │   │   │   ├── schema/            # Auto-generated + manual schemas
│   │   │   │   └── repositories/      # Repository pattern
│   │   │   ├── controllers/           # Feature-based HTTP controllers
│   │   │   │   ├── auth/
│   │   │   │   ├── catalog/
│   │   │   │   └── admin/
│   │   │   ├── services/              # Business logic
│   │   │   ├── types/                 # TypeBox schemas & TS types
│   │   │   ├── middleware/            # JWT auth, error handling
│   │   │   └── utils/                 # Helpers
│   │   ├── migrations/                # SQL migrations for users table
│   │   └── tests/                     # Unit + integration tests
│   └── python-ingestion/              # Phase 1: Data Ingestion
│       ├── src/
│       │   ├── db/models/             # SQLAlchemy ORM models
│       │   ├── parsers/               # Data source parsers
│       │   ├── models/                # Pydantic validation models
│       │   └── worker.py              # arq worker configuration
│       └── migrations/                # Alembic migrations
└── docker-compose.yml                 # Service orchestration
```

## Current Focus

**Phase 1 (Python Worker):** Complete ✅ | Implemented and tested
**Phase 2 (Bun API):** Planning Complete ✅ | Ready for implementation

**Phase 2 Recent Work:**
- Researched ElysiaJS, Drizzle ORM, TypeBox integration
- Designed hybrid database strategy (introspect Phase 1, manage users table)
- Created API contracts (catalog, admin, auth, queue messages)
- Generated 15-minute quickstart guide
- Documented SOLID architecture pattern for controllers/services/repositories

## Development Guidelines

### Code Style

**TypeScript (Bun API):**
- Use TypeScript strict mode (no `any` without justification)
- Controllers handle HTTP only - no business logic
- Services are static classes or pure functions (stateless)
- Repositories implement interfaces for Dependency Inversion
- TypeBox schemas for all request/response validation
- Feature-based folder structure (auth/, catalog/, admin/)

**Python (Worker):**
- Use async/await for all I/O operations
- Type hints required for all functions
- Pydantic models for data validation
- structlog for structured JSON logging

**Database:**
- **Bun API:** Drizzle ORM with introspected schema, use repository pattern
- **Python:** SQLAlchemy 2.0 style (no legacy Query API)
- Always use transactions for write operations
- Prefer parameterized queries over string concatenation

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
# Start all services (Python worker + Bun API)
docker-compose up -d

# View Bun API logs
docker-compose logs -f bun-api

# View Python worker logs
docker-compose logs -f worker

# Run Phase 1 migrations (Python/Alembic)
docker-compose exec worker alembic upgrade head

# Run Phase 2 migration (users table)
psql $DATABASE_URL -f services/bun-api/migrations/001_create_users.sql

# Access database
docker-compose exec postgres psql -U marketbel_user -d marketbel
```

### Bun API Development
```bash
# Navigate to Bun service
cd services/bun-api

# Install dependencies
bun install

# Run with hot reload
bun --watch src/index.ts

# Run tests
bun test

# Introspect database schema
bun run drizzle-kit introspect:pg

# Type check
bun run tsc --noEmit

# Access Swagger docs
open http://localhost:3000/docs
```

### Python Worker Development
```bash
# Navigate to Python service
cd services/python-ingestion

# Create virtual environment
python -m venv venv && source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v --cov=src

# Create migration
alembic revision --autogenerate -m "Description"
```

## Key References

**Phase 2 (Bun API) Documentation:**
- Feature Spec: `/specs/002-api-layer/spec.md`
- Research: `/specs/002-api-layer/plan/research.md`
- Data Model: `/specs/002-api-layer/plan/data-model.md`
- Quickstart: `/specs/002-api-layer/plan/quickstart.md`
- API Contracts: `/specs/002-api-layer/plan/contracts/`

**Phase 1 (Python Worker) Documentation:**
- Feature Spec: `/specs/001-data-ingestion-infra/spec.md`
- Implementation Plan: `/specs/001-data-ingestion-infra/plan/implementation-plan.md`
- Data Model: `/specs/001-data-ingestion-infra/plan/data-model.md`
- Quickstart: `/specs/001-data-ingestion-infra/plan/quickstart.md`

**External Documentation:**
- [ElysiaJS](https://elysiajs.com/)
- [Drizzle ORM](https://orm.drizzle.team/)
- [Bun](https://bun.sh/docs)
- [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [arq Documentation](https://arq-docs.helpmanual.io/)
- [Pydantic v2](https://docs.pydantic.dev/)
- [gspread API](https://docs.gspread.org/)

## Notes for Claude

**Phase 2 (Bun API) Implementation:**
- **SOLID principles are mandatory:** Controllers → Services → Repositories
- **No business logic in controllers:** Only HTTP handling, validation, serialization
- **Schema introspection is read-only:** Do NOT manage Phase 1 table migrations
- **Users table is managed locally:** SQL migration required before deployment
- **Type safety is critical:** TypeScript strict mode, TypeBox validation, Drizzle types
- **Performance targets:** p95 < 500ms for catalog, < 1000ms for admin endpoints
- **JWT authentication:** Role-based (sales, procurement, admin)
- **Queue communication:** Publish-only to Redis, Python worker consumes

**Phase 1 (Python Worker) Notes:**
- **Parser extensibility is critical:** New data sources should be easy to add
- **Error handling must not crash worker:** Use `parsing_logs` table
- **Performance target:** >1,000 items/min throughput
- **Dynamic column mapping:** Google Sheets headers vary between suppliers
- **JSONB characteristics:** Flexible schema for varying product attributes

**When implementing Phase 2:**
1. Start with `quickstart.md` for 15-minute setup
2. Reference `research.md` for technology stack decisions and best practices
3. Reference `data-model.md` for Drizzle schemas and TypeBox validation
4. Use `contracts/` JSON schemas for API request/response validation
5. Follow SOLID architecture: feature-based modules with controller/service/model
6. Test with Swagger UI at `/docs` endpoint

## Workflow State

**Current Branch:** 002-api-layer
**Phase 1 Status:** Complete ✅ (Implemented and tested)
**Phase 2 Status:** Planning Complete ✅ (Ready for implementation)
**Next Step:** Implement Phase 2 - Bun API Service

