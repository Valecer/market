# Feature Plan: High-Performance API Layer with Bun + ElysiaJS

**Date:** 2025-11-26

**Status:** Planning Complete

**Owner:** Development Team

---

## Overview

This feature implements a high-performance REST API using Bun runtime and ElysiaJS framework to serve the product catalog to three user roles (public clients, internal sales, and procurement staff). The API provides public catalog access, authenticated admin operations, manual product matching, and async task triggering via Redis queues.

**Key Value:** Enables frontend applications and internal tools to interact with the unified product catalog through a type-safe, performant API layer while maintaining separation from the Python data ingestion service.

---

## Constitutional Compliance Check

This feature aligns with the following constitutional principles:

- **Single Responsibility:** API service exclusively handles HTTP requests, validation, and response formatting. Business logic is delegated to service layers. Database access is abstracted through repositories. No business rules exist in route handlers.

- **Separation of Concerns:** The Bun service handles API/User logic exclusively and does NOT perform data parsing or normalization. Communication with the Python worker (Phase 1) occurs asynchronously via Redis queues. No direct HTTP calls between services.

- **Strong Typing:** All API contracts use TypeScript with strict mode enabled. Request validation uses TypeBox schemas. Database models are typed via Drizzle ORM. No `any` types without explicit justification.

- **KISS:** Product matching starts with simple manual linking by staff. Margin calculations use straightforward arithmetic. Authentication uses standard JWT patterns without custom cryptography. Drizzle introspects existing schema rather than managing complex migrations.

- **DRY:** API response schemas are defined once and reused across endpoints. Database types are generated from existing PostgreSQL schema (Phase 1). Validation schemas are shared between request/response handling. TypeBox schemas auto-generate from Drizzle ORM.

**Violations/Exceptions:** None

---

## Goals

- [x] Expose public catalog API with filtering (category, price range, search) without authentication
- [x] Provide authenticated admin API for internal staff to view detailed product/supplier data
- [x] Implement JWT-based authentication with role-based access control (sales, procurement, admin)
- [x] Enable manual product-to-supplier-item matching (link/unlink operations)
- [x] Support product creation workflow with "split SKU" capability
- [x] Allow triggering of background parsing tasks via Redis queue
- [x] Auto-generate OpenAPI/Swagger documentation for all endpoints
- [x] Achieve p95 response time < 500ms for catalog, < 1000ms for admin endpoints
- [x] Maintain read-only access to Phase 1 database schema (no migration management)
- [x] Implement hybrid database strategy (introspect Phase 1, manage users table locally)

---

## Non-Goals

Explicitly list what this feature will NOT accomplish to maintain scope discipline.

- User registration/password reset endpoints (users managed by admin or external system)
- Automated product matching algorithms (future feature)
- Real-time price updates (polling via periodic sync is acceptable)
- Frontend implementation (API-only feature)
- Payment processing or order management
- Password complexity enforcement beyond basic validation (MVP)
- Multi-factor authentication (MFA)
- Database migrations for Phase 1 tables (owned by Python/Alembic)
- Response caching layer (future optimization)
- Hierarchical category filtering (flat filtering only)

---

## Success Metrics

How will we measure success?

- **API Response Time (p95):** Catalog < 500ms, Admin endpoints < 1000ms for up to 10,000 products
- **Test Coverage:** ≥80% for business logic (services, validation, repositories)
- **Concurrent Users:** Support 1,000 concurrent users without degradation
- **Uptime:** Maintain 99.9% availability during business hours
- **Type Safety:** 90% of integration errors caught at compile time
- **Documentation Completeness:** All endpoints documented in Swagger with examples
- **Database Pool Utilization:** Does not exceed 80% under normal load
- **Error Rate:** < 1% for all endpoints under normal conditions

---

## User Stories

### Story 1: Public Catalog Browsing

**As a** public client (unauthenticated user)
**I want** to browse active products with filters (category, price range, search)
**So that** I can find relevant products without needing to authenticate

**Acceptance Criteria:**

- [x] Access `/api/v1/catalog` without authentication
- [x] Filter by category_id, min_price, max_price, search query
- [x] Results include product name, internal SKU, price range, supplier count
- [x] Only products with `status = 'active'` are visible
- [x] Results are paginated (default 50, max 200 per page)
- [x] Response time p95 < 500ms for typical queries

### Story 2: Sales Staff View Product Margins

**As a** sales staff member (authenticated)
**I want** to view products with all supplier prices and calculated margins
**So that** I can identify low-margin products and adjust pricing strategies

**Acceptance Criteria:**

- [x] Authenticate with JWT token
- [x] Access `/api/v1/admin/products` endpoint
- [x] View all products (draft, active, archived) with supplier details
- [x] See calculated margin percentage for each product
- [x] Filter by margin threshold, supplier, status
- [x] Paginated results for efficient data handling

### Story 3: Procurement Staff Link Supplier Items

**As a** procurement staff member (authenticated)
**I want** to manually link supplier items to internal products or create new products
**So that** I can maintain accurate product-to-supplier mappings

**Acceptance Criteria:**

- [x] Link supplier item to existing product via PATCH `/admin/products/:id/match`
- [x] Unlink supplier item (set product_id to NULL)
- [x] Create new product with initial supplier item link (split SKU workflow)
- [x] Validation prevents linking to archived products
- [x] Validation ensures unique internal_sku when creating products
- [x] Transaction ensures atomicity (rollback on error)

### Story 4: Admin Trigger Data Sync

**As a** system administrator (authenticated)
**I want** to trigger background data ingestion for a specific supplier
**So that** I can refresh product data on-demand without manual intervention

**Acceptance Criteria:**

- [x] Trigger sync via POST `/admin/sync` with supplier_id
- [x] System enqueues task to Redis (consumed by Python worker)
- [x] Returns task ID immediately (non-blocking)
- [x] Rate limiting: max 10 requests per minute per user
- [x] Graceful error handling if Redis unavailable (503 response)

---

## Technical Approach

### Architecture

High-level architecture decisions and service interactions.

**System Architecture:**

```
┌─────────────────┐
│  Public Clients │ (Unauthenticated)
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────────────────────────┐
│      Bun API Service (Phase 2)      │
│  ┌─────────────────────────────┐   │
│  │  Controllers (HTTP Layer)   │   │
│  │  - auth/  - catalog/        │   │
│  │  - admin/ (matching, sync)  │   │
│  └──────────┬──────────────────┘   │
│             │                       │
│  ┌──────────▼──────────────────┐   │
│  │   Services (Business Logic) │   │
│  │  - Filtering  - Margins     │   │
│  │  - Validation - SKU Gen     │   │
│  └──────────┬──────────────────┘   │
│             │                       │
│  ┌──────────▼──────────────────┐   │
│  │  Repositories (Data Access) │   │
│  │  - ProductRepo              │   │
│  │  - SupplierItemRepo         │   │
│  │  - UserRepo                 │   │
│  └──────────┬──────────────────┘   │
│             │                       │
└─────────────┼───────────────────────┘
              │ Drizzle ORM
              ▼
┌─────────────────────────────────────┐
│       PostgreSQL Database           │
│  ┌─────────────┬──────────────────┐ │
│  │ Phase 1     │ Phase 2          │ │
│  │ (Alembic)   │ (SQL Migration)  │ │
│  ├─────────────┼──────────────────┤ │
│  │ products    │ users            │ │
│  │ suppliers   │                  │ │
│  │ categories  │                  │ │
│  │ supplier_   │                  │ │
│  │   items     │                  │ │
│  └─────────────┴──────────────────┘ │
└─────────────────────────────────────┘
              ▲
              │ arq consumer
┌─────────────┴───────────────────────┐
│   Python Worker (Phase 1)           │
│   - Parses supplier data            │
│   - Updates products/supplier_items │
└─────────────┬───────────────────────┘
              │ LPOP
              ▼
┌─────────────────────────────────────┐
│         Redis Queue                 │
│   Queue: parse-tasks                │
└─────────────▲───────────────────────┘
              │ LPUSH
         Sync Endpoint
```

**Bun Service (API/User Logic):**

- **Responsibilities:**
  - Handle HTTP requests/responses
  - Validate input via TypeBox schemas
  - Authenticate users via JWT
  - Serve public catalog data
  - Provide admin operations (matching, sync triggering)

- **Endpoints:**
  - Public: `GET /api/v1/catalog`
  - Auth: `POST /api/v1/auth/login`
  - Admin: `GET /api/v1/admin/products`
  - Admin: `PATCH /api/v1/admin/products/:id/match`
  - Admin: `POST /api/v1/admin/products`
  - Admin: `POST /api/v1/admin/sync`

- **Data flow:**
  1. Request → Controller (HTTP validation)
  2. Controller → Service (business logic)
  3. Service → Repository (data access)
  4. Repository → Database (Drizzle ORM)
  5. Response ← Controller (serialization)

**Python Service (Data Processing):**

- **Responsibilities:**
  - Consume tasks from Redis queue
  - Parse supplier data (Google Sheets, CSV, Excel)
  - Update products and supplier_items tables
  - Log errors to parsing_logs table

- **Processing logic:**
  - Already implemented in Phase 1
  - No changes required for Phase 2

- **Data flow:**
  - Redis queue → arq worker → Parser → Database

**Redis Queue Communication:**

- **Queue names:**
  - `parse-tasks` (configurable via `REDIS_QUEUE_NAME` env var)

- **Message formats (Pydantic models):**
  ```json
  {
    "task_id": "uuid",
    "parser_type": "google_sheets|csv|excel",
    "supplier_name": "string",
    "source_config": {
      "spreadsheet_url": "string (for google_sheets)",
      "sheet_name": "string"
    },
    "retry_count": 0,
    "max_retries": 3,
    "enqueued_at": "ISO-8601 timestamp"
  }
  ```

- **Error handling:**
  - 503 Service Unavailable if Redis connection fails
  - Rate limiting prevents queue flooding
  - Python worker handles retry logic

**PostgreSQL Schema:**

- **Tables affected:**
  - Read-only: `products`, `supplier_items`, `suppliers`, `categories`, `price_history`, `parsing_logs`
  - Managed locally: `users`

- **Migration plan:**
  - Phase 1 tables: No migrations (introspect only)
  - Phase 2 users table: SQL migration script (`migrations/001_create_users.sql`)
  - Run before deployment: `psql $DATABASE_URL -f migrations/001_create_users.sql`

**Frontend (React + Vite + Tailwind v4.1):**

- Out of scope for this feature (API-only)
- Future implementation will consume these endpoints
- Swagger UI provides testing interface during development

### Design System

- [x] Consulted `mcp context7` for ElysiaJS, Drizzle ORM, Bun documentation
- [x] Reviewed ElysiaJS best practices for SOLID architecture
- [x] Confirmed TypeBox native integration with Elysia
- [x] Verified Drizzle introspection workflow

### Algorithm Choice

Following KISS principle, start with simplest solution:

- **JWT Authentication:** Standard HS256 signing with bcrypt password hashing
- **Product Filtering:** SQL WHERE clauses with indexed columns (no search engine)
- **Margin Calculation:** Simple arithmetic: `(target - min_supplier_price) / target * 100`
- **SKU Generation:** Format `PROD-{timestamp}-{random}` for auto-generated SKUs
- **Rate Limiting:** In-memory counter for MVP (Redis-backed for production)

**Scalability Path:**
- Future: Full-text search engine (e.g., Meilisearch) for catalog search
- Future: Redis-backed rate limiting for multi-instance deployment
- Future: Response caching layer for catalog endpoint

### Data Flow

```
[User] → [Bun API] → [Redis Queue] → [Python Worker] → [PostgreSQL]
           ↓                                               ↓
    [API Response]                                  [Result Storage]
                                                           ↑
                                                           │
    [Bun API] ← [Drizzle ORM] ← [Database Connection Pool]
```

**Example: Sync Flow**
1. Admin sends POST `/admin/sync` with `supplier_id`
2. Bun API validates JWT token and supplier existence
3. Bun API enqueues message to Redis via LPUSH
4. Bun API returns task_id immediately (non-blocking)
5. Python worker (Phase 1) consumes message via arq
6. Python worker parses data and updates database
7. Future admin queries see updated data

---

## Type Safety

### TypeScript Types

```typescript
// src/types/catalog.types.ts
import { Type, Static } from '@sinclair/typebox'

export const CatalogQuerySchema = Type.Object({
  category_id: Type.Optional(Type.String({ format: 'uuid' })),
  min_price: Type.Optional(Type.Number({ minimum: 0 })),
  max_price: Type.Optional(Type.Number({ minimum: 0 })),
  search: Type.Optional(Type.String({ minLength: 1 })),
  page: Type.Optional(Type.Integer({ minimum: 1, default: 1 })),
  limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 200, default: 50 }))
})

export type CatalogQuery = Static<typeof CatalogQuerySchema>

export const CatalogProductSchema = Type.Object({
  id: Type.String({ format: 'uuid' }),
  internal_sku: Type.String(),
  name: Type.String(),
  category_id: Type.Union([Type.String({ format: 'uuid' }), Type.Null()]),
  min_price: Type.String(), // Decimal as string
  max_price: Type.String(),
  supplier_count: Type.Integer({ minimum: 0 })
})

export type CatalogProduct = Static<typeof CatalogProductSchema>

export const CatalogResponseSchema = Type.Object({
  total_count: Type.Integer({ minimum: 0 }),
  page: Type.Integer({ minimum: 1 }),
  limit: Type.Integer({ minimum: 1 }),
  data: Type.Array(CatalogProductSchema)
})

export type CatalogResponse = Static<typeof CatalogResponseSchema>
```

```typescript
// src/types/auth.types.ts
import { Type, Static } from '@sinclair/typebox'

export const LoginRequestSchema = Type.Object({
  username: Type.String({ minLength: 3 }),
  password: Type.String({ minLength: 8 })
})

export type LoginRequest = Static<typeof LoginRequestSchema>

export const JWTPayloadSchema = Type.Object({
  sub: Type.String({ format: 'uuid' }), // User ID
  role: Type.Union([
    Type.Literal('sales'),
    Type.Literal('procurement'),
    Type.Literal('admin')
  ]),
  exp: Type.Number(), // Expiration timestamp
  iss: Type.String()  // Issuer
})

export type JWTPayload = Static<typeof JWTPayloadSchema>
```

### Python Types

```python
# Python worker (Phase 1) - already implemented
from pydantic import BaseModel

class QueueMessage(BaseModel):
    task_id: str
    parser_type: str  # "google_sheets" | "csv" | "excel"
    supplier_name: str
    source_config: dict
    retry_count: int
    max_retries: int
    enqueued_at: str  # ISO-8601 timestamp

class ProcessedResult(BaseModel):
    task_id: str
    status: str  # "success" | "failed"
    items_processed: int
    errors: list[str]
    completed_at: str
```

---

## Testing Strategy

- **Unit Tests:**
  - Validation schemas (TypeBox) - all request/response types
  - Service functions - margin calculation, filtering logic, SKU generation
  - JWT utilities - token generation, validation, expiration
  - Repository query builders - WHERE clause construction

- **Integration Tests:**
  - Database queries - catalog filtering, product matching, user authentication
  - Redis operations - message enqueuing, connection failover
  - Authentication flow - login, token validation, role-based access
  - End-to-end API - request → response with test database

- **E2E Tests:**
  - Public catalog flow (unauthenticated)
  - Admin matching flow (authenticated)
  - Sync trigger flow (with Redis verification)
  - Error scenarios (invalid tokens, missing resources, Redis down)

- **Coverage Target:** ≥80% for business logic (services, repositories, validation)

**Testing Tools:**
- Bun Test (native test runner)
- Elysia Eden Treaty (type-safe API client for testing)
- Docker Compose (test database and Redis)

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Drizzle introspection fails if Phase 1 schema changes | High | Medium | Pin to specific schema version, add CI check to detect schema drift |
| Redis unavailable blocks sync endpoint | Medium | Low | Return 503 gracefully, other endpoints unaffected, add health check monitoring |
| JWT secret leaked | Critical | Low | Store in environment variable, rotate on compromise, never commit to git |
| Database connection pool exhaustion | High | Medium | Monitor pool usage, alert at 80% utilization, implement connection limits |
| Phase 1 and Phase 2 write conflicts on supplier_items | High | Low | Use database transactions, implement row-level locking for matching operations |
| Rate limiting ineffective in multi-instance deployment | Medium | High | Document limitation, migrate to Redis-backed rate limiting for production |
| Performance degradation with large datasets | Medium | Medium | Add database indexes, implement pagination, monitor query performance |

---

## Dependencies

- **Bun Packages:**
  - `elysia` - Web framework
  - `@elysiajs/jwt` - JWT authentication
  - `@elysiajs/swagger` - API documentation
  - `@elysiajs/cors` - CORS middleware
  - `drizzle-orm` - Type-safe ORM
  - `drizzle-typebox` - TypeBox schema generation
  - `pg` - PostgreSQL driver
  - `ioredis` - Redis client
  - `@types/pg` (dev) - TypeScript types
  - `drizzle-kit` (dev) - Schema introspection tool

- **Python Packages:**
  - No changes required (Phase 1 already implemented)

- **External Services:**
  - PostgreSQL 16+ (from Phase 1)
  - Redis 7+ (from Phase 1)
  - Google Sheets API (used by Python worker, not directly by API)

- **Infrastructure:**
  - Docker & Docker Compose for local development
  - Environment variables: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, etc.
  - SQL migration script for users table

---

## Timeline

| Phase | Tasks | Duration | Target Date |
|-------|-------|----------|-------------|
| **Phase 1: Setup & Foundation** | - Install Bun runtime<br>- Create project structure<br>- Configure environment variables<br>- Run users table migration<br>- Introspect database schema<br>- Set up Drizzle ORM client | 1 day | Day 1 |
| **Phase 2: Core Infrastructure** | - Create database client with connection pooling<br>- Implement repository interfaces<br>- Set up TypeBox validation schemas<br>- Configure JWT middleware<br>- Add health check endpoint | 2 days | Day 2-3 |
| **Phase 3: Authentication** | - Implement login controller<br>- Create user repository<br>- Add JWT token generation<br>- Implement auth middleware<br>- Write auth unit tests | 2 days | Day 4-5 |
| **Phase 4: Public Catalog** | - Implement catalog controller<br>- Create catalog service<br>- Build product repository with filtering<br>- Add pagination logic<br>- Write catalog integration tests | 2 days | Day 6-7 |
| **Phase 5: Admin Operations** | - Implement admin products controller<br>- Create admin service (margin calc)<br>- Build supplier item repository<br>- Add product matching endpoint<br>- Add product creation endpoint<br>- Write admin integration tests | 3 days | Day 8-10 |
| **Phase 6: Redis Queue Integration** | - Implement sync controller<br>- Create queue service<br>- Add rate limiting middleware<br>- Test Redis failover handling<br>- Write sync integration tests | 2 days | Day 11-12 |
| **Phase 7: Documentation & Testing** | - Configure Swagger UI<br>- Add API examples to docs<br>- Write E2E tests<br>- Achieve 80% test coverage<br>- Performance testing | 2 days | Day 13-14 |
| **Phase 8: Docker & Deployment** | - Create Dockerfile<br>- Update docker-compose.yml<br>- Test containerized deployment<br>- Write deployment README<br>- Final integration testing | 1 day | Day 15 |

**Total Estimated Duration:** 15 days

---

## Open Questions

- [x] ~~How to handle database migrations for users table?~~ **Resolved:** Create SQL migration script, run manually before deployment
- [x] ~~Should we use Redis for rate limiting?~~ **Resolved:** Yes for production, in-memory for MVP (single instance)
- [x] ~~How to generate internal_sku?~~ **Resolved:** Format: `PROD-{timestamp}-{random}`
- [x] ~~Password complexity requirements?~~ **Resolved:** Out of scope for MVP, document as future enhancement
- [x] ~~Should catalog endpoint cache responses?~~ **Resolved:** Not for MVP, add as future optimization
- [x] ~~How to handle concurrent product matching operations?~~ **Resolved:** Use database transactions with row-level locking

---

## References

- [ElysiaJS Documentation](https://elysiajs.com/)
- [ElysiaJS Best Practices](https://elysiajs.com/essential/best-practice.html)
- [Drizzle ORM Documentation](https://orm.drizzle.team/)
- [Drizzle Introspection Guide](https://orm.drizzle.team/kit-docs/commands#introspect--pull)
- [Drizzle TypeBox Integration](https://orm.drizzle.team/docs/typebox)
- [Bun Documentation](https://bun.sh/docs)
- [ioredis Documentation](https://github.com/redis/ioredis)
- [TypeBox Documentation](https://github.com/sinclairzx81/typebox)
- Phase 1 Specification: `/specs/001-data-ingestion-infra/spec.md`
- Phase 1 Data Model: `/specs/001-data-ingestion-infra/plan/data-model.md`
- Phase 2 Research: `/specs/002-api-layer/plan/research.md`
- Phase 2 Data Model: `/specs/002-api-layer/plan/data-model.md`
- Phase 2 Quickstart: `/specs/002-api-layer/plan/quickstart.md`

---

**Approval Signatures:**

- [x] Technical Lead: Ready for implementation
- [x] Product Owner: Approved
- [x] Architecture Review: Approved (constitutional compliance verified)
