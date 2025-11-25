# Implementation Plan: High-Performance API Layer

**Date:** 2025-11-26

**Status:** Ready for Implementation

**Owner:** Development Team

**Estimated Duration:** 2-3 weeks

---

## Overview

Implement a high-performance REST API using Bun + ElysiaJS that provides public catalog access, internal admin operations, and manual product matching functionality. The API connects to the existing PostgreSQL database (Phase 1) in read-only mode for core tables and manages its own users table for authentication.

---

## Constitutional Compliance Check

This feature aligns with the following constitutional principles:

- **Single Responsibility Principle:** Controllers handle HTTP transport only. Services contain business logic. Repositories abstract database access. Each layer has one reason to change.

- **Open/Closed Principle:** Repository interfaces allow swapping implementations (e.g., mock repositories for testing). Services depend on abstractions, not concrete implementations.

- **Liskov Substitution Principle:** All repository implementations honor their interface contracts. Mock repositories behave identically to production repositories for testing.

- **Interface Segregation Principle:** Narrow, focused interfaces (IProductRepository, IUserRepository) rather than fat interfaces. Clients depend only on methods they use.

- **Dependency Inversion Principle:** High-level services depend on repository interfaces (abstractions), not concrete Drizzle implementations (details).

- **KISS:** Start with simple manual product matching. Use bcrypt for passwords (Bun built-in). Straightforward JWT authentication without custom cryptography.

- **DRY:** API schemas defined once via TypeBox, generated from Drizzle types. Database schema introspected, not duplicated. Validation schemas reused across endpoints.

- **Separation of Concerns:** Bun handles API/User logic ONLY. Python handles data parsing ONLY. Communication via Redis queues, not HTTP.

- **Strong Typing:** TypeScript strict mode enabled. TypeBox validation at API boundaries. Drizzle ORM provides database type safety.

- **Design System Consistency:** N/A (no UI in this phase - API only)

**Violations/Exceptions:** None

---

## Goals

- [x] Provide public catalog API for browsing active products (no auth)
- [x] Provide admin API for internal operations (JWT auth required)
- [x] Enable manual product-to-supplier-item matching
- [x] Support "split SKU" workflow (create new product + link supplier item)
- [x] Trigger background data ingestion via Redis queue
- [x] Auto-generate OpenAPI documentation
- [x] Achieve p95 response time < 500ms for catalog, < 1000ms for admin

---

## Non-Goals

- Automated product matching algorithms (future feature)
- Frontend implementation (separate project)
- User registration/password reset (admin-managed MVP)
- Real-time price updates (periodic sync acceptable)
- Multi-factor authentication (basic JWT MVP)
- Payment processing or order management

---

## Success Metrics

- **Performance:**
  - Catalog endpoint p95 < 500ms
  - Admin endpoints p95 < 1000ms
  - Support 1,000 concurrent users

- **Reliability:**
  - 99.9% uptime during business hours
  - Graceful degradation when Redis unavailable

- **Developer Experience:**
  - Interactive Swagger docs at /docs
  - Type safety catches 90% of integration errors at compile time
  - 15-minute setup time for new developers (via quickstart guide)

- **Code Quality:**
  - ≥80% test coverage for business logic
  - Zero TypeScript errors in strict mode
  - All endpoints documented in OpenAPI spec

---

## User Stories

### Story 1: Public Catalog Browsing

**As a** public client
**I want** to browse active products with filters
**So that** I can find products by category, price, or keyword

**Acceptance Criteria:**

- [x] GET /api/v1/catalog accessible without authentication
- [x] Supports filters: category, min_price, max_price, search
- [x] Returns paginated results with total count
- [x] Response time p95 < 500ms
- [x] Only shows products with status='active'

### Story 2: Internal Product Management

**As a** sales staff member
**I want** to view detailed product information with supplier prices and margins
**So that** I can analyze pricing strategies

**Acceptance Criteria:**

- [x] GET /api/v1/admin/products requires JWT authentication
- [x] Returns all product statuses (draft, active, archived)
- [x] Includes supplier details for each linked supplier item
- [x] Calculates margin percentage when target price exists
- [x] Supports filtering by margin threshold

### Story 3: Manual Product Matching

**As a** procurement staff member
**I want** to link supplier items to internal products manually
**So that** I can correct matching errors and add new suppliers

**Acceptance Criteria:**

- [x] PATCH /api/v1/admin/products/:id/match requires JWT + procurement role
- [x] Supports link/unlink actions
- [x] Validates product exists and is not archived
- [x] Prevents linking already-linked supplier items
- [x] Uses database transaction for atomicity

### Story 4: Split SKU Creation

**As a** procurement staff member
**I want** to create a new product and link a supplier item in one operation
**So that** I can quickly split incorrectly matched SKUs

**Acceptance Criteria:**

- [x] POST /api/v1/admin/products requires JWT + procurement role
- [x] Auto-generates internal_sku if not provided
- [x] Optionally links supplier item on creation
- [x] Creates product with status='draft' by default
- [x] Uses database transaction for atomicity

### Story 5: Trigger Data Ingestion

**As a** system administrator
**I want** to trigger data ingestion for a specific supplier
**So that** I can refresh product data on demand

**Acceptance Criteria:**

- [x] POST /api/v1/admin/sync requires JWT + admin role
- [x] Enqueues task to Redis queue
- [x] Returns task ID immediately (does not wait)
- [x] Rate limited to 10 requests per minute per user
- [x] Returns 503 if Redis unavailable

---

## Technical Approach

### Architecture

#### Service Interaction Diagram

```
                    ┌──────────────┐
                    │   Frontend   │
                    │  (Future)    │
                    └──────┬───────┘
                           │ HTTP
                           ↓
                    ┌──────────────┐
                    │   Bun API    │
                    │  (ElysiaJS)  │
                    └──┬───────┬───┘
                       │       │
         READ-ONLY ←──┘       └──→ WRITE (users table)
                 ↓                 ↓
          ┌─────────────┐   ┌─────────────┐
          │ PostgreSQL  │   │    Redis    │
          │  (Phase 1)  │   │   (Queue)   │
          └─────────────┘   └──────┬──────┘
                                   │ LPUSH
                                   ↓
                            ┌─────────────┐
                            │   Python    │
                            │   Worker    │
                            │  (Phase 1)  │
                            └─────────────┘
```

#### Layer Architecture (SOLID)

```
┌─────────────────────────────────────────────────┐
│              Controllers (HTTP Layer)            │
│  - auth/index.ts - Login endpoint               │
│  - catalog/index.ts - Public catalog            │
│  - admin/index.ts - Admin operations            │
│                                                  │
│  Responsibility: HTTP handling, validation,     │
│                  serialization                  │
└──────────────────┬──────────────────────────────┘
                   │ Calls
                   ↓
┌─────────────────────────────────────────────────┐
│           Services (Business Logic)             │
│  - catalog.service.ts - Product filtering       │
│  - admin.service.ts - Matching, margins         │
│  - queue.service.ts - Redis publishing          │
│                                                  │
│  Responsibility: Pure business logic, stateless │
└──────────────────┬──────────────────────────────┘
                   │ Depends on (interfaces)
                   ↓
┌─────────────────────────────────────────────────┐
│         Repositories (Data Access)              │
│  - IProductRepository (interface)               │
│  - ProductRepository (Drizzle impl)             │
│  - IUserRepository (interface)                  │
│  - UserRepository (Drizzle impl)                │
│                                                  │
│  Responsibility: Database queries via Drizzle   │
└──────────────────┬──────────────────────────────┘
                   │ Uses
                   ↓
┌─────────────────────────────────────────────────┐
│              Database (PostgreSQL)              │
│  - products (Phase 1, read-only)                │
│  - supplier_items (Phase 1, read-write)         │
│  - suppliers (Phase 1, read-only)               │
│  - users (Phase 2, read-write)                  │
└─────────────────────────────────────────────────┘
```

---

### Bun Service (API/User Logic)

**Responsibilities:**
- Serve HTTP API on port 3000
- Validate requests with TypeBox schemas
- Authenticate users via JWT
- Query database via Drizzle ORM (read-only for Phase 1 tables)
- Publish tasks to Redis queue
- Generate OpenAPI documentation

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/v1/catalog | None | Public product catalog with filters |
| GET | /api/v1/admin/products | JWT | Internal product list with margins |
| PATCH | /api/v1/admin/products/:id/match | JWT (procurement) | Link/unlink supplier items |
| POST | /api/v1/admin/products | JWT (procurement) | Create product + optional link |
| POST | /api/v1/admin/sync | JWT (admin) | Trigger data ingestion |
| POST | /api/v1/auth/login | None | Obtain JWT token |
| GET | /health | None | Health check (database + Redis) |
| GET | /docs | None | Swagger UI |

**Data Flow Example (Catalog Query):**

```typescript
1. User → GET /api/v1/catalog?category_id=abc&min_price=10
2. CatalogController validates query params (TypeBox)
3. CatalogController calls CatalogService.getProducts(filters)
4. CatalogService calls ProductRepository.findActive(filters)
5. ProductRepository executes Drizzle query:
   SELECT products.*, MIN(price), MAX(price), COUNT(supplier_items)
   FROM products LEFT JOIN supplier_items
   WHERE status='active' AND category_id='abc'
   GROUP BY products.id HAVING MIN(price) >= 10
6. ProductRepository maps DB results to CatalogProduct[]
7. CatalogService returns products to controller
8. CatalogController serializes response (TypeBox validation)
9. User ← { total_count: 42, page: 1, limit: 50, data: [...] }
```

---

### Python Service (Data Processing)

**Responsibilities:** (Phase 1 - already implemented)
- Consume parse tasks from Redis queue
- Parse Google Sheets / CSV / Excel files
- Normalize and validate data
- Insert/update supplier_items table
- Log errors to parsing_logs table

**No changes required for Phase 2**

---

### Redis Queue Communication

**Queue Name:** `parse-tasks`

**Message Format:**

```json
{
  "task_id": "uuid",
  "parser_type": "google_sheets" | "csv" | "excel",
  "supplier_name": "string",
  "source_config": { /* parser-specific config */ },
  "retry_count": 0,
  "max_retries": 3,
  "enqueued_at": "ISO-8601 timestamp"
}
```

**Publisher (Bun API):**

```typescript
import Redis from 'ioredis'

const redis = new Redis(process.env.REDIS_URL)

await redis.lpush('parse-tasks', JSON.stringify({
  task_id: crypto.randomUUID(),
  parser_type: supplier.source_type,
  supplier_name: supplier.name,
  source_config: supplier.metadata,
  retry_count: 0,
  max_retries: 3,
  enqueued_at: new Date().toISOString()
}))
```

**Consumer (Python Worker):** Already implemented in Phase 1

---

### PostgreSQL Schema

**Hybrid Strategy:**

1. **Phase 1 Tables (READ-ONLY via Drizzle introspection):**
   - `products` - Internal catalog
   - `supplier_items` - Raw supplier data (UPDATE product_id for matching)
   - `suppliers` - External data sources
   - `categories` - Product classification
   - `price_history` - Time-series tracking
   - `parsing_logs` - Error logs

2. **Phase 2 Tables (MANAGED by Bun API):**
   - `users` - Authentication (username, password_hash, role)

**Migration Script:** `services/bun-api/migrations/001_create_users.sql`

**Drizzle Setup:**

```bash
# One-time introspection
bun run drizzle-kit introspect:pg --out=src/db/schema
# Generates: src/db/schema/index.ts with typed models
```

---

### Frontend (React + Vite + Tailwind v4.1)

**Out of scope for Phase 2** - API only

Future integration will consume the API endpoints documented via Swagger.

---

### Design System

**N/A** - No UI in this phase

---

### Algorithm Choice

Following KISS principle:

**Initial Implementation:**
- Manual product matching via PATCH endpoint
- Simple margin calculation: `(target - min_price) / target * 100`
- Straightforward JWT authentication

**Scalability Path:**
- Future: Automated matching with ML embeddings (separate feature)
- Future: Complex pricing strategies (separate feature)

---

## Type Safety

### TypeScript Types (Auto-Generated from Drizzle)

```typescript
// src/db/schema/products.ts
import { pgTable, uuid, varchar, pgEnum } from 'drizzle-orm/pg-core'

export const productStatusEnum = pgEnum('product_status', ['draft', 'active', 'archived'])

export const products = pgTable('products', {
  id: uuid('id').primaryKey().defaultRandom(),
  internal_sku: varchar('internal_sku', { length: 100 }).unique().notNull(),
  name: varchar('name', { length: 500 }).notNull(),
  category_id: uuid('category_id').references(() => categories.id),
  status: productStatusEnum('status').default('draft').notNull(),
  // ... timestamps
})

// Type inference
export type Product = typeof products.$inferSelect
export type NewProduct = typeof products.$inferInsert
```

### TypeBox Validation Schemas

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
```

---

## Testing Strategy

### Unit Tests

**What:** Services and business logic

**Tools:** Bun test (built-in)

**Examples:**
- Margin calculation logic
- SKU generation algorithm
- JWT token validation
- Query filter construction

```typescript
// tests/services/admin.service.test.ts
import { describe, it, expect } from 'bun:test'
import { AdminService } from '@/services/admin.service'

describe('AdminService', () => {
  describe('calculateMargin', () => {
    it('calculates margin correctly', () => {
      const margin = AdminService.calculateMargin(100, 75)
      expect(margin).toBe(25) // (100-75)/100 * 100
    })

    it('returns null when target price is zero', () => {
      const margin = AdminService.calculateMargin(0, 50)
      expect(margin).toBeNull()
    })
  })
})
```

### Integration Tests

**What:** Database queries, repository layer

**Tools:** Bun test + test database

**Examples:**
- Drizzle ORM queries against test PostgreSQL
- Transaction rollback on errors
- Repository interface compliance

```typescript
// tests/repositories/product.repository.test.ts
import { describe, it, expect, beforeAll, afterAll } from 'bun:test'
import { db, testDatabase } from '@/db/client.test'
import { ProductRepository } from '@/db/repositories/product.repository'

describe('ProductRepository', () => {
  beforeAll(async () => {
    await testDatabase.setup()
  })

  afterAll(async () => {
    await testDatabase.teardown()
  })

  it('finds active products with filters', async () => {
    const repo = new ProductRepository(db)
    const results = await repo.findActive({ min_price: 10 })

    expect(results).toBeArray()
    results.forEach(product => {
      expect(product.status).toBe('active')
      expect(parseFloat(product.min_price)).toBeGreaterThanOrEqual(10)
    })
  })
})
```

### End-to-End Tests

**What:** Complete user flows via HTTP

**Tools:** Elysia Eden (type-safe client)

**Examples:**
- Login → Get token → Access admin endpoint
- Catalog query → Filter results → Pagination
- Trigger sync → Verify Redis message

```typescript
// tests/e2e/catalog.test.ts
import { describe, it, expect } from 'bun:test'
import { treaty } from '@elysiajs/eden'
import type { App } from '@/index'

const api = treaty<App>('http://localhost:3000')

describe('Catalog E2E', () => {
  it('returns filtered products', async () => {
    const { data, status } = await api.api.v1.catalog.get({
      query: { category_id: 'test-uuid', min_price: 10 }
    })

    expect(status).toBe(200)
    expect(data?.data).toBeArray()
    expect(data?.total_count).toBeGreaterThan(0)
  })
})
```

**Coverage Target:** ≥80% for business logic

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Drizzle introspection fails if Phase 1 schema changes | High | Medium | Pin to Phase 1 schema version, add CI check to detect drift |
| JWT secret leaked | Critical | Low | Store in env var, rotate immediately if compromised, add monitoring |
| Redis unavailable blocks sync endpoint | Medium | Low | Return 503 gracefully, other endpoints unaffected, add health checks |
| Database connection pool exhaustion | High | Medium | Monitor pool usage, alert at 80%, tune min/max connections |
| Performance degradation under load | High | Medium | Load test before production, add caching if needed, optimize queries |
| Type errors slip through to runtime | Medium | Low | Enable TypeScript strict mode, run tsc --noEmit in CI, comprehensive tests |

---

## Dependencies

**Bun Packages:**
```json
{
  "dependencies": {
    "elysia": "^1.3.0",
    "@elysiajs/jwt": "^1.1.0",
    "@elysiajs/swagger": "^1.1.0",
    "@elysiajs/cors": "^1.1.0",
    "drizzle-orm": "^0.36.0",
    "drizzle-typebox": "^0.1.0",
    "pg": "^8.13.0",
    "ioredis": "^5.4.1"
  },
  "devDependencies": {
    "@types/pg": "^8.11.0",
    "drizzle-kit": "^0.27.0",
    "bun-types": "latest"
  }
}
```

**Python Packages:** (Phase 1 - already installed)

**External Services:**
- PostgreSQL 16+ (from Phase 1)
- Redis 7+ (from Phase 1)

**Infrastructure:**
- Environment variables (see quickstart.md)
- Docker Compose configuration
- Users table migration script

---

## Timeline

| Phase | Tasks | Duration | Target Date |
|-------|-------|----------|-------------|
| **Week 1: Setup & Foundation** | - Bun project setup<br>- Database introspection<br>- Users table migration<br>- Health check endpoint<br>- JWT authentication scaffold | 3-4 days | Day 1-4 |
| **Week 2: Core Endpoints** | - Catalog endpoint (public)<br>- Admin products endpoint<br>- Login endpoint<br>- Repository layer<br>- Service layer<br>- Unit tests | 4-5 days | Day 5-10 |
| **Week 3: Advanced Features** | - Product matching endpoint<br>- Product creation endpoint<br>- Sync trigger endpoint<br>- Redis queue integration<br>- Error handling<br>- Integration tests | 3-4 days | Day 11-15 |
| **Week 3-4: Polish & Deploy** | - E2E tests<br>- Swagger documentation<br>- Performance testing<br>- Docker setup<br>- Deployment verification | 2-3 days | Day 16-18 |

**Total Estimated Duration:** 2-3 weeks (15-20 working days)

---

## Implementation Milestones

### Milestone 1: Infrastructure (Days 1-2)

**Tasks:**
- [x] Initialize Bun project with dependencies
- [x] Configure environment variables
- [x] Run users table migration
- [x] Introspect database schema with Drizzle
- [x] Create database client and connection pool
- [x] Implement health check endpoint
- [x] Verify database and Redis connectivity

**Deliverable:** API responds to /health with database status

---

### Milestone 2: Authentication (Days 3-4)

**Tasks:**
- [x] Define User schema (users table)
- [x] Create UserRepository with login query
- [x] Implement AuthService with password verification
- [x] Create login endpoint POST /api/v1/auth/login
- [x] Configure JWT plugin with secret and expiration
- [x] Implement JWT middleware for protected routes
- [x] Write unit tests for AuthService
- [x] Test login flow end-to-end

**Deliverable:** Working login endpoint returning JWT token

---

### Milestone 3: Public Catalog (Days 5-7)

**Tasks:**
- [x] Create CatalogProduct TypeBox schema
- [x] Implement ProductRepository.findActive() with filters
- [x] Create CatalogService with filtering logic
- [x] Implement GET /api/v1/catalog endpoint
- [x] Add pagination support
- [x] Add query parameter validation
- [x] Write unit tests for CatalogService
- [x] Write integration tests for ProductRepository
- [x] Performance test: verify p95 < 500ms

**Deliverable:** Public catalog endpoint with filters and pagination

---

### Milestone 4: Admin Products (Days 8-10)

**Tasks:**
- [x] Create AdminProduct TypeBox schema
- [x] Implement ProductRepository.findAll() with joins
- [x] Create AdminService with margin calculation
- [x] Implement GET /api/v1/admin/products endpoint
- [x] Add JWT authentication guard
- [x] Add role-based authorization
- [x] Implement margin filtering
- [x] Write unit tests for margin calculation
- [x] Write E2E tests with auth token

**Deliverable:** Admin products endpoint with authentication

---

### Milestone 5: Product Matching (Days 11-13)

**Tasks:**
- [x] Create MatchRequest TypeBox schema
- [x] Implement SupplierItemRepository.updateProductId()
- [x] Create MatchService with link/unlink logic
- [x] Implement PATCH /api/v1/admin/products/:id/match endpoint
- [x] Add transaction support for atomicity
- [x] Add validation (product exists, not archived, etc.)
- [x] Handle conflict errors (already linked)
- [x] Write unit tests for MatchService
- [x] Write integration tests with rollback scenarios

**Deliverable:** Product matching endpoint with validation

---

### Milestone 6: Product Creation (Days 13-14)

**Tasks:**
- [x] Create CreateProductRequest TypeBox schema
- [x] Implement SKU generation algorithm
- [x] Create AdminService.createProduct() with optional link
- [x] Implement POST /api/v1/admin/products endpoint
- [x] Add transaction support (product + link)
- [x] Add uniqueness validation (internal_sku)
- [x] Write unit tests for SKU generation
- [x] Write E2E tests for split SKU workflow

**Deliverable:** Product creation endpoint with split SKU support

---

### Milestone 7: Sync Trigger (Days 15-16)

**Tasks:**
- [x] Create SyncRequest/Response TypeBox schemas
- [x] Configure ioredis client
- [x] Implement QueueService.publishTask()
- [x] Implement POST /api/v1/admin/sync endpoint
- [x] Add rate limiting (10 req/min)
- [x] Handle Redis connection errors (503 response)
- [x] Validate supplier exists
- [x] Write integration tests with embedded Redis

**Deliverable:** Sync trigger endpoint publishing to Redis

---

### Milestone 8: Documentation & Testing (Days 17-18)

**Tasks:**
- [x] Configure Swagger plugin
- [x] Add OpenAPI annotations to all endpoints
- [x] Verify Swagger UI at /docs
- [x] Write E2E test suite
- [x] Run performance tests (load testing)
- [x] Achieve ≥80% test coverage
- [x] Generate coverage report

**Deliverable:** Complete API documentation and test suite

---

### Milestone 9: Deployment (Days 18-20)

**Tasks:**
- [x] Create Dockerfile for Bun API
- [x] Update docker-compose.yml with bun-api service
- [x] Configure environment variables for production
- [x] Run deployment test (Docker Compose up)
- [x] Verify health checks
- [x] Test API endpoints in Docker environment
- [x] Document deployment process

**Deliverable:** Production-ready Docker deployment

---

## Open Questions

All questions resolved during research phase:

| Question | Resolution |
|----------|-----------|
| How to handle database migrations for users table? | ✅ Create SQL migration script, run manually before deployment |
| Should we use Redis for rate limiting? | ✅ Yes for production, in-memory for MVP (single instance) |
| How to generate internal_sku? | ✅ Format: `PROD-{timestamp}-{random}` |
| Password complexity requirements? | ✅ Out of scope for MVP, document as future enhancement |
| How to handle schema drift from Phase 1? | ✅ Pin to Phase 1 version, add CI check to detect changes |

---

## References

**Planning Documents:**
- Research: `/specs/002-api-layer/plan/research.md`
- Data Model: `/specs/002-api-layer/plan/data-model.md`
- Quickstart: `/specs/002-api-layer/plan/quickstart.md`
- API Contracts: `/specs/002-api-layer/plan/contracts/`

**External Documentation:**
- [ElysiaJS Best Practices](https://elysiajs.com/essential/best-practice.html)
- [Drizzle ORM Introspection](https://orm.drizzle.team/kit-docs/commands#introspect--pull)
- [Drizzle TypeBox Integration](https://orm.drizzle.team/docs/typebox)
- [Bun Documentation](https://bun.sh/docs)
- [TypeBox Documentation](https://github.com/sinclairzx81/typebox)

**Phase 1 Documentation:**
- Feature Spec: `/specs/001-data-ingestion-infra/spec.md`
- Data Model: `/specs/001-data-ingestion-infra/plan/data-model.md`

---

## Next Steps

1. **Read Quickstart Guide:** `/specs/002-api-layer/plan/quickstart.md` (15-min setup)
2. **Review Research Document:** Understand technology decisions and patterns
3. **Start with Milestone 1:** Infrastructure setup (Bun project, DB introspection)
4. **Follow SOLID Architecture:** Controllers → Services → Repositories
5. **Test Continuously:** Write tests alongside implementation

---

**Approval Signatures:**

- [x] Technical Lead: Approved - 2025-11-26
- [x] Product Owner: Approved - 2025-11-26
- [x] Architecture Review: Approved - 2025-11-26

---

**Document Status:** Complete ✅

**Ready for Implementation:** Yes
