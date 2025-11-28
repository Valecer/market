# Claude Agent Context

This file provides context to Claude AI when working on this project.

## Project Overview

**Name:** Marketbel - Unified Catalog System
**Type:** Multi-service application for supplier price list management and product catalog
**Stage:** Phase 1 Complete ✅ | Phase 2 Complete ✅ | Phase 3 Planning Complete ✅

Before implementation, use mcp context7 to collect up-to-date documentation.

---

## Shared Infrastructure

### Database
- **PostgreSQL 16** with JSONB support for flexible product characteristics
- Schema includes: suppliers, categories, products, supplier_items, price_history, parsing_logs
- Managed by Phase 1 (Alembic migrations for core tables) + Phase 2 (SQL migration for users table)

**Core Entities:**
- `Supplier` - External data sources with source_type (google_sheets, csv, excel)
- `Product` - Internal catalog with status enum (draft, active, archived)
- `SupplierItem` - Raw supplier data with JSONB characteristics
- `PriceHistory` - Time-series price tracking
- `ParsingLog` - Structured error logging without crashing worker
- `User` - Authentication and authorization (Phase 2)

**Key Relationships:**
- One Supplier → Many SupplierItems (CASCADE delete)
- One Product → Many SupplierItems (SET NULL on delete)
- One SupplierItem → Many PriceHistory entries (CASCADE delete)

**Indexes:**
- GIN index on `supplier_items.characteristics` for JSONB queries
- Composite unique index on `(supplier_id, supplier_sku)`
- Descending indexes on timestamps for chronological queries

### Queue/Cache
- **Redis 7 (alpine)** for task queue and caching
- Phase 1 (Python worker) consumes from queue
- Phase 2 (Bun API) publishes to queue

### Container Orchestration
- **Docker** 24+
- **Docker Compose** v2 for local development
- Services: postgres, redis, python-ingestion (worker), bun-api, frontend (Phase 3)

### Docker Operations
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f bun-api
docker-compose logs -f worker
docker-compose logs -f frontend

# Run Phase 1 migrations (Python/Alembic)
docker-compose exec worker alembic upgrade head

# Run Phase 2 migration (users table)
psql $DATABASE_URL -f services/bun-api/migrations/001_create_users.sql

# Access database
docker-compose exec postgres psql -U marketbel_user -d marketbel
```

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
│   ├── 002-api-layer/                 # Phase 2 (Bun API)
│   │   ├── spec.md
│   │   └── plan/
│   │       ├── research.md
│   │       ├── data-model.md
│   │       ├── quickstart.md
│   │       └── contracts/
│   │           ├── catalog-api.json
│   │           ├── admin-api.json
│   │           ├── auth-api.json
│   │           └── queue-messages.json
│   └── 003-frontend-app/              # Phase 3 (React Frontend)
│       ├── spec.md
│       └── plan/
│           ├── research.md
│           ├── data-model.md
│           ├── quickstart.md
│           ├── constitutional-compliance.md
│           └── contracts/
│               ├── catalog-api.json
│               ├── auth-api.json
│               └── admin-api.json
├── services/
│   ├── python-ingestion/              # Phase 1: Data Ingestion
│   │   ├── src/
│   │   │   ├── db/models/             # SQLAlchemy ORM models
│   │   │   ├── parsers/               # Data source parsers
│   │   │   ├── models/                # Pydantic validation models
│   │   │   └── worker.py              # arq worker configuration
│   │   └── migrations/                # Alembic migrations
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
│   └── frontend/                      # Phase 3: React + Vite Frontend
│       ├── src/
│       │   ├── components/
│       │   │   ├── catalog/           # Public catalog components
│       │   │   ├── admin/             # Admin components (sales, procurement)
│       │   │   ├── cart/              # Cart components
│       │   │   └── shared/            # Reusable UI components
│       │   ├── pages/                 # Route components
│       │   ├── hooks/                 # Custom React hooks
│       │   ├── lib/                   # Utilities (API client, query keys)
│       │   ├── types/                 # TypeScript types (auto-generated + manual)
│       │   ├── App.tsx
│       │   ├── main.tsx
│       │   └── index.css              # Tailwind CSS-first config
│       ├── package.json
│       ├── tsconfig.json
│       └── vite.config.ts
└── docker-compose.yml                 # Service orchestration
```

### Security Considerations

- Google service account credentials mounted as read-only volume
- Database and Redis passwords in `.env` (not committed)
- Least privilege for worker database user (INSERT/UPDATE/SELECT only)
- Pydantic validation prevents SQL injection via parameterized queries
- JWT tokens for API authentication with role-based access control

### Testing Requirements

- **Unit Tests:** ≥85% coverage for business logic
- **Integration Tests:** End-to-end with Docker services
- **Performance Tests:** >1,000 items/min throughput (Phase 1 worker)

### Testing Best Practices (Phase 1 .py)

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

---

## Phase 1: Python Worker (Data Ingestion)

**Status:** Complete ✅ (Implemented and tested)

### Technology Stack

- **Runtime:** Python 3.12 (cmd in use python3.13, and venv)
- **ORM:** SQLAlchemy 2.0+ with AsyncIO support
- **Database Driver:** asyncpg (PostgreSQL async driver)
- **Task Queue:** arq (asyncio-based Redis queue)
- **Data Processing:** pandas 2.x
- **Validation:** pydantic 2.x
- **Migrations:** alembic 1.13+
- **API Integration:** gspread 6.x (Google Sheets API)

### Design Patterns

1. **Parser Interface:** Abstract base class for pluggable data sources (Google Sheets, CSV, Excel)
2. **Async Architecture:** Full async/await pattern with SQLAlchemy AsyncIO + arq
3. **Queue-Based Processing:** Decoupled ingestion with retry logic and dead letter queue
4. **JSONB Flexibility:** Product characteristics stored as JSON for varying supplier fields
5. **Error Isolation:** Per-row error logging to `parsing_logs` table prevents cascade failures

### Code Style

**Python (Worker):**
- Use async/await for all I/O operations
- Type hints required for all functions
- Pydantic models for data validation
- structlog for structured JSON logging
- SQLAlchemy 2.0 style (no legacy Query API)
- Always use transactions for write operations
- Prefer parameterized queries over string concatenation

**Error Handling:**
- Custom exception hierarchy rooted in `DataIngestionError`
- Per-row error logging to `parsing_logs` table
- Retry logic with exponential backoff (1s, 5s, 25s)
- Dead letter queue for permanently failed tasks

### Commands

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

### Key References

- Feature Spec: `/specs/001-data-ingestion-infra/spec.md`
- Implementation Plan: `/specs/001-data-ingestion-infra/plan/implementation-plan.md`
- Data Model: `/specs/001-data-ingestion-infra/plan/data-model.md`
- Quickstart: `/specs/001-data-ingestion-infra/plan/quickstart.md`

**External Documentation:**
- [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [arq Documentation](https://arq-docs.helpmanual.io/)
- [Pydantic v2](https://docs.pydantic.dev/)
- [gspread API](https://docs.gspread.org/)

### Notes for Claude

- **Parser extensibility is critical:** New data sources should be easy to add
- **Error handling must not crash worker:** Use `parsing_logs` table
- **Performance target:** >1,000 items/min throughput
- **Dynamic column mapping:** Google Sheets headers vary between suppliers
- **JSONB characteristics:** Flexible schema for varying product attributes

---

## Phase 2: Bun API (REST API Layer)

**Status:** Complete ✅ (Implemented and tested)

### Technology Stack

- **Runtime:** Bun (latest)
- **Framework:** ElysiaJS (high-performance, type-safe)
- **ORM:** Drizzle ORM + node-postgres
- **Validation:** TypeBox (native to Elysia)
- **Authentication:** @elysiajs/jwt + bcrypt
- **Documentation:** @elysiajs/swagger (auto-generated OpenAPI)
- **Queue Client:** ioredis (publisher-only)
- **Database Access:** READ-ONLY for Phase 1 tables, MANAGED for users table

### Design Patterns

1. **SOLID Architecture:** Controllers (HTTP) → Services (logic) → Repositories (data)
2. **Feature-Based Structure:** auth/, catalog/, admin/ modules with controller/service/model
3. **Type Safety:** End-to-end TypeScript with Drizzle ORM + TypeBox validation
4. **JWT Authentication:** Role-based access (sales, procurement, admin)
5. **Schema Introspection:** Drizzle reads Phase 1 schema without managing migrations
6. **Queue Publisher:** Redis LPUSH for async task delegation to Python worker

### Code Style

**TypeScript (Bun API):**
- Use TypeScript strict mode (no `any` without justification)
- Controllers handle HTTP only - no business logic
- Services are static classes or pure functions (stateless)
- Repositories implement interfaces for Dependency Inversion
- TypeBox schemas for all request/response validation
- Feature-based folder structure (auth/, catalog/, admin/)
- Drizzle ORM with introspected schema, use repository pattern
- Always use transactions for write operations
- Prefer parameterized queries over string concatenation

### Commands

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

### Key References

- Feature Spec: `/specs/002-api-layer/spec.md`
- Research: `/specs/002-api-layer/plan/research.md`
- Data Model: `/specs/002-api-layer/plan/data-model.md`
- Quickstart: `/specs/002-api-layer/plan/quickstart.md`
- API Contracts: `/specs/002-api-layer/plan/contracts/`

**External Documentation:**
- [ElysiaJS](https://elysiajs.com/)
- [Drizzle ORM](https://orm.drizzle.team/)
- [Bun](https://bun.sh/docs)

### Notes for Claude

- **SOLID principles are mandatory:** Controllers → Services → Repositories
- **No business logic in controllers:** Only HTTP handling, validation, serialization
- **Schema introspection is read-only:** Do NOT manage Phase 1 table migrations
- **Users table is managed locally:** SQL migration required before deployment
- **Type safety is critical:** TypeScript strict mode, TypeBox validation, Drizzle types
- **Performance targets:** p95 < 500ms for catalog, < 1000ms for admin endpoints
- **JWT authentication:** Role-based (sales, procurement, admin)
- **Queue communication:** Publish-only to Redis, Python worker consumes

**When implementing Phase 2:**
1. Start with `quickstart.md` for 15-minute setup
2. Reference `research.md` for technology stack decisions and best practices
3. Reference `data-model.md` for Drizzle schemas and TypeBox validation
4. Use `contracts/` JSON schemas for API request/response validation
5. Follow SOLID architecture: feature-based modules with controller/service/model
6. Test with Swagger UI at `/docs` endpoint

---

## Phase 3: React Frontend (Unified Application)

**Status:** Planning Complete ✅ (Ready for implementation)

### Technology Stack

- **Runtime:** Bun (latest)
- **Framework:** React 18+ with TypeScript (strict mode)
- **Build Tool:** Vite 5+ with @vitejs/plugin-react
- **Routing:** React Router v6 (client-side routing)
- **Data Fetching:** TanStack Query v5 (server state management)
- **Tables:** TanStack Table v8 (headless table library)
- **UI Components:** Radix UI Themes (accessible, TypeScript-first)
- **Styling:** Tailwind CSS v4.1 (CSS-first configuration, NO tailwind.config.js)
- **API Client:** openapi-fetch + openapi-typescript (auto-generated types)
- **State Management:** React Context (cart, auth), TanStack Query (server state)
- **Testing:** Vitest + React Testing Library
- **Linting:** ESLint + @typescript-eslint

### Design Patterns

1. **Component Architecture:** Feature-sliced design (catalog/, admin/, cart/, shared/)
2. **SOLID Principles:** Components → Hooks → API Client (dependency inversion)
3. **Type Safety:** TypeScript strict mode, auto-generated API types from OpenAPI
4. **Tailwind v4.1 CSS-First:** `@import "tailwindcss"` + `@theme` blocks (NO tailwind.config.js)
5. **Server State:** TanStack Query with optimistic updates and cache invalidation
6. **Accessibility:** Radix UI components (WCAG 2.1 Level AA compliant)
7. **KISS Principle:** No Redux, simple patterns, minimal abstraction

### Code Style

**React (Frontend):**
- Use TypeScript strict mode (no `any` without justification)
- Components handle UI only - no business logic
- Custom hooks for data fetching (useCatalog, useProduct, useAuth)
- API types auto-generated from OpenAPI spec (run `bun run generate-api-types`)
- **Tailwind CSS v4.1 CSS-first:** NO `tailwind.config.js`, use `@theme` blocks in CSS
- Feature-based folder structure (catalog/, admin/, cart/, shared/)
- TanStack Query for server state, React Context for app state
- Radix UI components for accessibility
- Always use transactions for write operations (API calls)
- Prefer parameterized queries over string concatenation

### Commands

```bash
# Navigate to Frontend service
cd services/frontend

# Install dependencies
bun install

# Run with hot reload
bun run dev  # Starts on http://localhost:5173

# Run tests
bun test

# Type check
bun run type-check

# Lint
bun run lint

# Build for production
bun run build

# Preview production build
bun run preview

# Generate API types from Bun API OpenAPI spec
bun run generate-api-types  # Requires Bun API running on port 3000
```

### Key References

- Feature Spec: `/specs/003-frontend-app/spec.md`
- Implementation Plan: `/specs/003-frontend-app/plan.md`
- Research: `/specs/003-frontend-app/plan/research.md`
- Data Model: `/specs/003-frontend-app/plan/data-model.md`
- Quickstart: `/specs/003-frontend-app/plan/quickstart.md`
- API Contracts: `/specs/003-frontend-app/plan/contracts/`
- Constitutional Compliance: `/specs/003-frontend-app/plan/constitutional-compliance.md`

**External Documentation:**
- [React](https://react.dev/)
- [Vite](https://vitejs.dev/)
- [TanStack Query](https://tanstack.com/query/v5)
- [TanStack Table](https://tanstack.com/table/v8)
- [Radix UI](https://www.radix-ui.com/)
- [Tailwind CSS v4](https://tailwindcss.com/docs)
- [React Router](https://reactrouter.com/)
- [openapi-typescript](https://github.com/drwpow/openapi-typescript)

### Notes for Claude

**Recent Work:**
- Researched React ecosystem: Radix UI, TanStack Query v5, TanStack Table v8, Tailwind v4.1
- Decided on openapi-typescript for API type generation (broader compatibility vs elysia/eden)
- Designed component architecture: feature-sliced (catalog/, admin/, cart/, shared/)
- Created API contracts for frontend-backend communication
- Generated 15-minute quickstart guide for Vite + React + Tailwind v4.1 setup
- Verified constitutional compliance (all 10 principles ✅)

**Implementation Guidelines:**
- **Components → Hooks → API Client:** Strict dependency inversion
- **NO business logic in components:** Only UI rendering and user interaction handling
- **Auto-generated types are source of truth:** Regenerate from OpenAPI after API changes
- **Tailwind v4.1 CSS-first is mandatory:** NO `tailwind.config.js` file allowed
- **Type safety is critical:** TypeScript strict mode, no `any` types
- **KISS decisions:**
  - Authentication: Redirect to login (no silent token refresh)
  - Cart: localStorage only (no backend sync in Phase 3)
  - Error Reporting: Console logging (no Sentry/LogRocket yet)
  - State Management: No Redux, use TanStack Query + React Context

**When implementing Phase 3:**
1. Start with `quickstart.md` for 15-minute Vite + React + Tailwind v4.1 setup
2. Reference `research.md` for technology stack decisions (Radix UI vs Headless UI, etc.)
3. Reference `data-model.md` for TypeScript types and component prop interfaces
4. Use `contracts/` JSON schemas for understanding API request/response structures
5. Follow feature-sliced architecture: catalog/, admin/, cart/, shared/
6. Generate API types: `bun run generate-api-types` before starting
7. Consult `mcp 21st-dev/magic` for design system elements (per constitution)
8. Verify Tailwind v4.1 setup: `@import "tailwindcss"` + `@theme` blocks, plugin BEFORE react()

---

## Workflow State

**Current Branch:** 003-frontend-app
**Phase 1 Status:** Complete ✅ (Implemented and tested)
**Phase 2 Status:** Complete ✅ (Implemented and tested)
**Phase 3 Status:** Planning Complete ✅ (Ready for implementation)

**Next Step:** Generate tasks for Phase 3 implementation (`/speckit.tasks`) or start implementation (`/speckit.implement`)
