# Feature Specification: High-Performance API Layer

**Version:** 1.0.0

**Last Updated:** 2025-11-26

**Status:** Draft

---

## Constitutional Alignment

**Relevant Principles:**

- **Single Responsibility:** The Bun API service exclusively handles HTTP requests, validation, and response formatting. Business logic is delegated to service layers. Database access is abstracted through repositories. No business rules exist in route handlers.

- **Separation of Concerns:** The Bun service handles API/User logic exclusively and does NOT perform data parsing or normalization. Communication with the Python worker (Phase 1) occurs asynchronously via Redis queues. No direct HTTP calls between services.

- **Strong Typing:** All API contracts use TypeScript with strict mode enabled. Request validation uses schema libraries (Zod/TypeBox). Database models are typed via Drizzle ORM. No `any` types without explicit justification.

- **KISS:** Product matching starts with simple manual linking by staff. Margin calculations use straightforward arithmetic. Authentication uses standard JWT patterns without custom cryptography.

- **DRY:** API response schemas are defined once and reused across endpoints. Database types are generated from existing PostgreSQL schema (Phase 1). Validation schemas are shared between request/response handling.

**Compliance Statement:**

This specification adheres to all constitutional principles. The Bun service reads from the existing database (owned by Python/Alembic) and enqueues tasks to Redis without managing migrations. All deviations are documented in the Exceptions section below.

---

## Overview

### Purpose

This feature provides a high-performance REST API that exposes the product catalog to three user roles (public clients, internal sales staff, and procurement staff) while enabling manual product matching and triggering background data ingestion tasks.

### Scope

**In Scope:**

- Public catalog API with filtering (category, price range, search)
- Internal admin API with supplier details and calculated margins
- JWT-based authentication for internal routes with login endpoint
- Manual product-to-supplier-item matching interface (link/unlink)
- Product creation API with "split SKU" support (create new product + link supplier item)
- Triggering parsing jobs via Redis queue
- Auto-generated OpenAPI/Swagger documentation
- Read-only database access using Drizzle ORM (introspection of Phase 1 schema)
- Users table for authentication (requires migration)

**Out of Scope:**

- Database migrations for Phase 1 tables (owned by Python/Alembic)
- User registration/password reset endpoints (users managed by admin or external system)
- Automated product matching algorithms (future feature)
- Real-time price updates (polling via periodic sync is acceptable)
- Frontend implementation (API-only feature)
- Payment processing or order management
- Password complexity enforcement (MVP uses basic validation)
- Multi-factor authentication (MFA)

---

## User Roles & Scenarios

### Role 1: Public Client (Unauthenticated)

**Scenario:** Browse available products with filters

1. Client opens catalog page
2. System displays list of active products with names, prices, and categories
3. Client applies filters:
   - Category selection (e.g., "Electronics")
   - Price range (e.g., $10-$50)
   - Search query (e.g., "USB cable")
4. System returns filtered results sorted by relevance
5. Client views product details (name, lowest price, available suppliers count)

**Acceptance Criteria:**

- Catalog endpoint accessible without authentication
- Only products with `status = 'active'` are visible
- Filters can be combined (category AND price AND search)
- Results include aggregated data (min price, supplier count)
- Response time under 500ms for queries returning up to 1000 items

---

### Role 2: Sales Staff (Authenticated)

**Scenario:** View internal product data with margins

1. Sales staff authenticates with JWT token
2. Accesses admin products endpoint
3. System displays products with:
   - All supplier items linked to each product
   - Current prices from each supplier
   - Calculated margin percentage (if internal price target exists)
4. Staff filters by low-margin products (<15%)
5. Staff exports data for pricing review

**Acceptance Criteria:**

- Admin endpoint requires valid JWT token
- Returns supplier details (supplier name, SKU, price)
- Margin calculation: `(internal_price - min_supplier_price) / internal_price * 100`
- Filterable by margin threshold
- Supports pagination (default 50 items per page)

---

### Role 3: Procurement Staff (Authenticated)

**Scenario 1: Link supplier item to existing product**

1. Procurement staff authenticates with JWT token
2. Views unmatched supplier items (where `product_id = NULL`)
3. Searches for existing internal product by SKU or name
4. Links supplier item to internal product via PATCH request
5. System updates `supplier_items.product_id` field
6. Updated product now shows additional supplier option in catalog

**Scenario 2: Create new product and link supplier item (Split SKU)**

1. Procurement staff identifies incorrectly matched supplier item
2. Decides to "split" into a new internal SKU
3. Submits POST request to create new product with:
   - Generated or provided internal SKU
   - Product name (can default from supplier item name)
   - Category selection
   - Initial supplier item to link
4. System creates new product with `status = 'draft'`
5. System links supplier item to new product automatically
6. Staff can later activate product or link additional suppliers

**Acceptance Criteria:**

- Endpoints require JWT token with procurement role
- Can link supplier_item to existing product (PATCH)
- Can unlink supplier_item (set `product_id = NULL`)
- Can create new product with initial supplier item link (POST)
- Validation prevents linking to archived products
- Validation ensures unique internal_sku when creating products
- Returns updated/created product with all linked supplier items

---

### Role 4: System Administrator (Authenticated)

**Scenario:** Trigger data ingestion for supplier

1. Admin authenticates with JWT token
2. Selects supplier from list
3. Initiates sync via POST `/admin/sync`
4. System enqueues parsing task to Redis
5. System returns task ID for tracking
6. Admin can check parsing logs for errors

**Acceptance Criteria:**

- Endpoint requires JWT token with admin role
- Enqueues message to Redis queue (contract matches Phase 1 worker expectations)
- Returns task ID immediately (does not wait for completion)
- Handles Redis connection errors gracefully
- Rate limiting: max 10 sync requests per minute per user

---

## Functional Requirements

### FR-1: Public Catalog Endpoint

**Priority:** Critical

**Description:** Provide a public API endpoint that returns a list of active products with filtering, searching, and pagination capabilities. Products must include aggregated pricing data from linked supplier items.

**Acceptance Criteria:**

- [ ] AC-1: `GET /api/v1/catalog` endpoint accessible without authentication
- [ ] AC-2: Returns only products where `status = 'active'`
- [ ] AC-3: Supports query parameters:
  - `category_id` (UUID): Filter by category
  - `min_price` (decimal): Minimum price threshold
  - `max_price` (decimal): Maximum price threshold
  - `search` (string): Full-text search on product name
  - `page` (integer): Page number (default 1)
  - `limit` (integer): Items per page (default 50, max 200)
- [ ] AC-4: Each product includes:
  - `id`, `internal_sku`, `name`, `category_id`
  - `min_price`: Lowest current price from linked supplier items
  - `max_price`: Highest current price from linked supplier items
  - `supplier_count`: Number of suppliers offering this product
- [ ] AC-5: Results sorted by `name` ascending by default
- [ ] AC-6: Returns paginated response with `total_count`, `page`, `limit`, `data` fields
- [ ] AC-7: Response time p95 < 500ms for up to 10,000 products

**Dependencies:** Phase 1 database schema (products, supplier_items, categories)

---

### FR-2: Admin Products Endpoint

**Priority:** Critical

**Description:** Provide an authenticated endpoint for internal staff to view detailed product information including all supplier prices, margins, and supplier metadata.

**Acceptance Criteria:**

- [ ] AC-1: `GET /api/v1/admin/products` requires valid JWT token
- [ ] AC-2: Returns products with all statuses (draft, active, archived)
- [ ] AC-3: Each product includes:
  - Base fields: `id`, `internal_sku`, `name`, `category_id`, `status`
  - Array of linked supplier items with:
    - `supplier_id`, `supplier_name`, `supplier_sku`
    - `current_price`, `last_ingested_at`
    - `characteristics` (JSONB object)
- [ ] AC-4: Calculates margin if internal target price exists (formula: `(target - min_supplier_price) / target * 100`)
- [ ] AC-5: Supports filtering by:
  - `status`: Filter by product status enum
  - `min_margin`: Minimum margin percentage
  - `max_margin`: Maximum margin percentage
  - `supplier_id`: Products from specific supplier
- [ ] AC-6: Supports pagination (default 50, max 200 per page)
- [ ] AC-7: Returns 401 Unauthorized if token missing or invalid

**Dependencies:** JWT authentication system, Phase 1 database schema

---

### FR-3: Sync Trigger Endpoint

**Priority:** High

**Description:** Allow authenticated users to trigger a background data ingestion task for a specific supplier by enqueuing a message to Redis.

**Acceptance Criteria:**

- [ ] AC-1: `POST /api/v1/admin/sync` requires valid JWT token
- [ ] AC-2: Request body contains `supplier_id` (UUID)
- [ ] AC-3: Validates that supplier exists in database
- [ ] AC-4: Enqueues task message to Redis with structure:
  ```json
  {
    "task_id": "generated-uuid",
    "parser_type": "supplier.source_type",
    "supplier_name": "supplier.name",
    "source_config": "supplier.metadata",
    "retry_count": 0,
    "max_retries": 3,
    "enqueued_at": "ISO-8601 timestamp"
  }
  ```
- [ ] AC-5: Returns response:
  ```json
  {
    "task_id": "uuid",
    "supplier_id": "uuid",
    "status": "queued",
    "enqueued_at": "timestamp"
  }
  ```
- [ ] AC-6: Returns 404 Not Found if supplier doesn't exist
- [ ] AC-7: Returns 503 Service Unavailable if Redis connection fails
- [ ] AC-8: Rate limiting: Maximum 10 requests per minute per user
- [ ] AC-9: Returns 429 Too Many Requests if rate limit exceeded

**Dependencies:** Redis connection, Phase 1 queue consumer (Python worker)

---

### FR-4: Product Matching Endpoint

**Priority:** High

**Description:** Enable procurement staff to manually link or unlink supplier items to internal products, updating the `supplier_items.product_id` field.

**Acceptance Criteria:**

- [ ] AC-1: `PATCH /api/v1/admin/products/:id/match` requires valid JWT token
- [ ] AC-2: Request body structure:
  ```json
  {
    "action": "link" | "unlink",
    "supplier_item_id": "uuid"
  }
  ```
- [ ] AC-3: **Link action:**
  - Updates `supplier_items.product_id` to `:id`
  - Validates product exists and is not archived
  - Validates supplier_item exists and is not already linked
- [ ] AC-4: **Unlink action:**
  - Sets `supplier_items.product_id` to NULL
  - Validates supplier_item is currently linked to `:id`
- [ ] AC-5: Returns updated product with all linked supplier items
- [ ] AC-6: Returns 400 Bad Request if validation fails (with error message)
- [ ] AC-7: Returns 404 Not Found if product or supplier_item doesn't exist
- [ ] AC-8: Returns 409 Conflict if supplier_item already linked to different product (link action)
- [ ] AC-9: Transaction ensures atomicity (rollback on error)

**Dependencies:** Phase 1 database schema (products, supplier_items)

---

### FR-5: Product Creation Endpoint

**Priority:** High

**Description:** Enable procurement staff to create new internal products with optional initial supplier item linkage. This supports the "split SKU" workflow where an incorrectly matched supplier item needs to be assigned to a new product.

**Acceptance Criteria:**

- [ ] AC-1: `POST /api/v1/admin/products` requires valid JWT token with procurement or admin role
- [ ] AC-2: Request body structure:
  ```json
  {
    "internal_sku": "string (optional, auto-generated if not provided)",
    "name": "string (required, 1-500 chars)",
    "category_id": "uuid (optional)",
    "status": "draft | active (optional, defaults to 'draft')",
    "supplier_item_id": "uuid (optional, links on creation)"
  }
  ```
- [ ] AC-3: Auto-generates `internal_sku` if not provided (format: `PROD-{timestamp}-{random}`)
- [ ] AC-4: Validates `internal_sku` is unique across all products
- [ ] AC-5: Validates `category_id` exists if provided
- [ ] AC-6: If `supplier_item_id` provided:
  - Validates supplier item exists and is not already linked
  - Links supplier item to new product automatically (sets `supplier_items.product_id`)
- [ ] AC-7: Returns created product with:
  ```json
  {
    "id": "uuid",
    "internal_sku": "string",
    "name": "string",
    "category_id": "uuid | null",
    "status": "draft | active",
    "supplier_items": [/* array if supplier_item_id was provided */],
    "created_at": "ISO-8601 timestamp"
  }
  ```
- [ ] AC-8: Returns 400 Bad Request if:
  - `name` is empty or exceeds 500 characters
  - `internal_sku` already exists
  - `category_id` references non-existent category
  - `supplier_item_id` references non-existent or already-linked item
- [ ] AC-9: Returns 403 Forbidden if user role is not procurement or admin
- [ ] AC-10: Transaction ensures atomicity (product creation + supplier item link)
- [ ] AC-11: Newly created products default to `status = 'draft'` unless explicitly set to `active`

**Dependencies:** Phase 1 database schema (products, supplier_items, categories)

---

### FR-6: JWT Authentication

**Priority:** Critical

**Description:** Implement JWT-based authentication for internal routes, validating tokens and extracting user roles for authorization. Provide login endpoint to issue tokens.

**Acceptance Criteria:**

- [ ] AC-1: Public routes (`/api/v1/catalog`) accessible without token
- [ ] AC-2: Admin routes (`/api/v1/admin/*`) require `Authorization: Bearer <token>` header
- [ ] AC-3: Token validation checks:
  - Signature verification using secret key
  - Expiration time (`exp` claim)
  - Issuer (`iss` claim matches configured value)
- [ ] AC-4: Token payload includes:
  ```json
  {
    "sub": "user-id",
    "role": "sales" | "procurement" | "admin",
    "exp": 1234567890,
    "iss": "marketbel-api"
  }
  ```
- [ ] AC-5: Returns 401 Unauthorized if token missing, expired, or invalid
- [ ] AC-6: Returns 403 Forbidden if token valid but user lacks required role
- [ ] AC-7: Token expiration: 24 hours from issuance (configurable via env var)
- [ ] AC-8: Login endpoint `POST /api/v1/auth/login` accepts username/password
- [ ] AC-9: Login validates credentials against users table
- [ ] AC-10: Login returns JWT token on success, 401 on invalid credentials
- [ ] AC-11: Passwords stored as bcrypt hashes (never plaintext)

**Dependencies:** JWT secret stored in environment variable, users table in database with password hashes

---

### FR-7: OpenAPI Documentation

**Priority:** Medium

**Description:** Auto-generate interactive API documentation using OpenAPI/Swagger specification, leveraging Elysia's built-in plugin.

**Acceptance Criteria:**

- [ ] AC-1: Swagger UI accessible at `/docs` endpoint
- [ ] AC-2: OpenAPI specification available at `/docs/json`
- [ ] AC-3: Documentation includes:
  - All endpoints with methods, paths, descriptions
  - Request body schemas with examples
  - Response schemas with status codes
  - Authentication requirements per endpoint
- [ ] AC-4: Swagger UI allows "Try it out" functionality
- [ ] AC-5: Documentation automatically updates when code changes
- [ ] AC-6: Examples use realistic sample data

**Dependencies:** Elysia Swagger plugin

---

## Non-Functional Requirements

### NFR-1: Performance

- API response time p95:
  - Catalog endpoint: < 500ms (up to 10,000 products)
  - Admin endpoints: < 1000ms (up to 10,000 products)
  - Matching endpoint: < 200ms
  - Sync trigger endpoint: < 100ms
- Database connection pooling with min 5, max 20 connections
- Query optimization using proper indexes from Phase 1 schema

### NFR-2: Scalability

- Support 1,000 concurrent users
- Horizontal scaling via load balancer (stateless API)
- Redis queue handles spikes in sync requests without blocking API
- Pagination prevents memory exhaustion on large result sets

### NFR-3: Security

- Input validation at all endpoints (schema-based via Zod/TypeBox)
- SQL injection prevention via parameterized queries (Drizzle ORM)
- JWT secret stored in environment variable (never hardcoded)
- CORS configuration for production domain whitelist
- Rate limiting on sync endpoint (10 req/min per user)
- Helmet middleware for security headers

### NFR-4: Observability

- Structured JSON logging for all requests (timestamp, method, path, status, duration)
- Error logging with stack traces for 5xx responses
- Request ID propagation for distributed tracing
- Metrics exposed:
  - Request count by endpoint and status code
  - Response time percentiles (p50, p95, p99)
  - Redis queue depth
  - Database connection pool usage

### NFR-5: Reliability

- Graceful shutdown on SIGTERM (finish in-flight requests)
- Health check endpoint at `/health` (checks database and Redis connectivity)
- Database connection retry logic with exponential backoff (3 retries, max 10s)
- Redis connection failover handling (return 503 on sync endpoint if Redis unavailable)
- Transaction rollback on database errors (matching endpoint)

---

## Data Models

### API Request/Response Schemas (TypeScript)

#### Catalog Response

```typescript
// GET /api/v1/catalog
interface CatalogResponse {
  total_count: number;
  page: number;
  limit: number;
  data: CatalogProduct[];
}

interface CatalogProduct {
  id: string; // UUID
  internal_sku: string;
  name: string;
  category_id: string | null; // UUID
  min_price: string; // Decimal as string (e.g., "19.99")
  max_price: string; // Decimal as string
  supplier_count: number;
}
```

#### Admin Products Response

```typescript
// GET /api/v1/admin/products
interface AdminProductsResponse {
  total_count: number;
  page: number;
  limit: number;
  data: AdminProduct[];
}

interface AdminProduct {
  id: string; // UUID
  internal_sku: string;
  name: string;
  category_id: string | null; // UUID
  status: "draft" | "active" | "archived";
  supplier_items: SupplierItemDetail[];
  margin_percentage: number | null; // Calculated if target price exists
}

interface SupplierItemDetail {
  id: string; // UUID
  supplier_id: string; // UUID
  supplier_name: string;
  supplier_sku: string;
  current_price: string; // Decimal as string
  characteristics: Record<string, any>; // JSONB
  last_ingested_at: string; // ISO-8601 timestamp
}
```

#### Sync Request/Response

```typescript
// POST /api/v1/admin/sync
interface SyncRequest {
  supplier_id: string; // UUID
}

interface SyncResponse {
  task_id: string; // UUID
  supplier_id: string; // UUID
  status: "queued";
  enqueued_at: string; // ISO-8601 timestamp
}
```

#### Product Matching Request/Response

```typescript
// PATCH /api/v1/admin/products/:id/match
interface MatchRequest {
  action: "link" | "unlink";
  supplier_item_id: string; // UUID
}

interface MatchResponse {
  product: AdminProduct; // Updated product with all supplier items
}
```

#### Product Creation Request/Response

```typescript
// POST /api/v1/admin/products
interface CreateProductRequest {
  internal_sku?: string; // Optional, auto-generated if not provided
  name: string; // 1-500 characters
  category_id?: string; // UUID, optional
  status?: "draft" | "active"; // Optional, defaults to 'draft'
  supplier_item_id?: string; // UUID, optional initial link
}

interface CreateProductResponse {
  id: string; // UUID
  internal_sku: string;
  name: string;
  category_id: string | null; // UUID
  status: "draft" | "active";
  supplier_items: SupplierItemDetail[]; // Empty array or single item if supplier_item_id provided
  created_at: string; // ISO-8601 timestamp
}
```

#### Login Request/Response

```typescript
// POST /api/v1/auth/login
interface LoginRequest {
  username: string;
  password: string;
}

interface LoginResponse {
  token: string; // JWT token
  expires_at: string; // ISO-8601 timestamp
  user: {
    id: string; // UUID
    username: string;
    role: "sales" | "procurement" | "admin";
  };
}
```

#### Error Response

```typescript
// Standard error format for all endpoints
interface ErrorResponse {
  error: {
    code: string; // e.g., "VALIDATION_ERROR", "NOT_FOUND", "UNAUTHORIZED"
    message: string; // Human-readable description
    details?: unknown; // Optional additional context
  };
}
```

---

### Database Schema (Read-Only Access)

The API uses Drizzle ORM to introspect the existing PostgreSQL schema created by Phase 1 (Python/Alembic). No migrations are managed by this service.

**Key Tables Used:**

- `products`: Internal product catalog
- `supplier_items`: Raw supplier data linked to products
- `suppliers`: External data sources
- `categories`: Product classification hierarchy
- `price_history`: Time-series price tracking (future use for trends)
- `parsing_logs`: Error logs from ingestion (for admin diagnostics)

**Drizzle Configuration:**

```typescript
// Database types are generated via:
// $ drizzle-kit introspect:pg --out=src/db/schema
// This creates TypeScript types matching the existing schema
import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import * as schema from './schema'; // Auto-generated from introspection

const client = postgres(process.env.DATABASE_URL!);
const db = drizzle(client, { schema });
```

---

## Error Handling

### API Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request body or query parameters invalid |
| `UNAUTHORIZED` | 401 | Missing, expired, or invalid JWT token |
| `FORBIDDEN` | 403 | Valid token but insufficient role permissions |
| `NOT_FOUND` | 404 | Resource (product, supplier, supplier_item) doesn't exist |
| `CONFLICT` | 409 | State conflict (e.g., supplier_item already linked) |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests within time window |
| `REDIS_UNAVAILABLE` | 503 | Redis connection failed (sync endpoint) |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

### Error Response Format

All errors follow this structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "min_price",
      "issue": "must be a positive number"
    }
  }
}
```

### Logging Strategy

- **4xx errors:** Log at INFO level (client errors, expected)
- **5xx errors:** Log at ERROR level with full stack trace
- **Validation errors:** Include field names and validation rules violated
- **Database errors:** Log query details (sanitized, no sensitive data)
- **Redis errors:** Log connection string (without credentials) and error type

---

## Testing Requirements

### Unit Tests

- **Validation schemas:** Test all request body and query parameter schemas
- **Service functions:** Test business logic (margin calculation, filtering logic)
- **JWT utilities:** Test token generation, validation, and expiration

### Integration Tests

- **Database queries:** Test Drizzle ORM queries against test PostgreSQL instance
  - Catalog endpoint with various filter combinations
  - Admin products with pagination
  - Product matching link/unlink operations
- **Redis operations:** Test message enqueuing with embedded Redis
- **Authentication:** Test JWT validation and role-based access

### End-to-End Tests

- **Public catalog flow:**
  1. Request catalog without auth
  2. Apply filters (category, price, search)
  3. Verify results match database state
- **Admin matching flow:**
  1. Authenticate with JWT
  2. Link supplier item to product
  3. Verify database update
  4. Query admin products and confirm change
- **Sync flow:**
  1. Authenticate with JWT
  2. Trigger sync for supplier
  3. Verify Redis queue contains message
  4. Mock Python worker processing

**Coverage Target:** ≥80% for all business logic (service layer, validation, queries)

---

## Deployment

### Environment Variables

```bash
# Server Configuration
BUN_PORT=3000
NODE_ENV=production

# Database
DATABASE_URL=postgresql://marketbel_user:password@localhost:5432/marketbel

# Redis
REDIS_URL=redis://localhost:6379
REDIS_QUEUE_NAME=parse-tasks

# Authentication
JWT_SECRET=your-secure-secret-key-here
JWT_ISSUER=marketbel-api
JWT_EXPIRATION_HOURS=24

# CORS
ALLOWED_ORIGINS=https://app.marketbel.com,https://admin.marketbel.com

# Rate Limiting
SYNC_RATE_LIMIT_PER_MINUTE=10

# Logging
LOG_LEVEL=info
```

### Docker Configuration

Service defined in `docker-compose.yml`:

```yaml
services:
  bun-api:
    build:
      context: ./services/bun-api
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://redis:6379
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      - postgres
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
```

### Migration Strategy

**Initial Deployment:**

1. Ensure Phase 1 (Python ingestion service) is running and database is populated
2. Run Drizzle introspection: `bun run drizzle-kit introspect:pg`
3. Build Bun application: `bun run build`
4. Start Bun service: `bun run start`
5. Verify health endpoint: `curl http://localhost:3000/health`
6. Test public catalog endpoint (no auth)
7. Issue test JWT token and verify admin endpoints

**Rolling Updates:**

- Deploy new Bun instances behind load balancer
- Health checks ensure new instances are ready before routing traffic
- Graceful shutdown of old instances (finish in-flight requests)
- No database migrations required (read-only access)

---

## Documentation

- [ ] OpenAPI/Swagger documentation auto-generated at `/docs`
- [ ] README in `services/bun-api/` with:
  - Setup instructions (Bun installation, dependencies)
  - Environment variable reference
  - Local development guide
  - Testing instructions
- [ ] API usage examples:
  - cURL commands for each endpoint
  - Example request/response payloads
  - JWT token generation for testing
- [ ] Architecture Decision Record (ADR) for:
  - Why Bun + ElysiaJS (performance requirements)
  - Why Drizzle introspection vs shared schema definitions

---

## Rollback Plan

**Trigger Conditions:**

- Error rate > 5% on any endpoint
- Response time p95 > 2000ms (degraded performance)
- Database connection pool exhaustion
- Redis connection failures blocking critical flows

**Rollback Steps:**

1. Route traffic to previous Bun API version via load balancer
2. Stop new Bun instances
3. Verify previous version handles traffic successfully
4. Investigate root cause:
   - Check application logs for errors
   - Review database query performance (`EXPLAIN ANALYZE`)
   - Verify Redis connectivity
5. Fix issues and redeploy after validation in staging

**Database Considerations:**

- No migrations managed by this service, so no database rollback needed
- Product matching changes (supplier_items.product_id updates) are data changes, not schema changes
- If data corruption suspected, restore from Phase 1 database backups

---

## Success Criteria

1. **Catalog Accessibility:**
   - Public clients can browse active products without authentication
   - Search and filter operations return results in under 500ms for typical queries

2. **Internal Operations:**
   - Sales staff can view detailed product information with supplier prices and margins
   - Procurement staff can manually link supplier items to products with single-click operations

3. **Task Orchestration:**
   - Administrators can trigger data ingestion tasks that complete successfully
   - System handles up to 100 concurrent sync requests without degradation

4. **Performance:**
   - API serves 1,000 concurrent users with p95 response time < 1000ms
   - Database connection pool does not exceed 80% utilization under normal load

5. **Reliability:**
   - System maintains 99.9% uptime during business hours
   - Graceful degradation when Redis unavailable (sync endpoint returns 503, other endpoints unaffected)

6. **Developer Experience:**
   - Interactive API documentation allows developers to test endpoints without external tools
   - Type safety catches 90% of integration errors at compile time

---

## Assumptions

1. **Users Table Required:** A `users` table must exist in the database with the following fields:
   - `id` (UUID, primary key)
   - `username` (VARCHAR, unique, not null)
   - `password_hash` (VARCHAR, bcrypt hash, not null)
   - `role` (ENUM: 'sales', 'procurement', 'admin', not null)
   - `created_at`, `updated_at` (timestamps)

   This table is not part of Phase 1 schema and must be added via migration before deploying the API.

2. **Internal Price Targets:** Products may have an optional `target_price` field (not in Phase 1 schema) for margin calculation. If this field doesn't exist, margin calculation is skipped and `margin_percentage` returns `null`.

3. **Rate Limiting Storage:** Rate limiting uses in-memory storage for MVP. For production with multiple API instances, use Redis-backed rate limiting.

4. **Password Requirements:** Password complexity requirements (minimum length, special characters) are out of scope for MVP. Production deployment should enforce strong password policies via validation or external identity provider.

5. **Category Hierarchy:** Category filtering is flat (single category_id). Hierarchical filtering (include subcategories) is out of scope.

6. **Real-Time Updates:** Product data updates require manual sync triggers. Automatic periodic syncing is handled by an external scheduler (e.g., cron) calling the sync endpoint.

---

## Exceptions & Deviations

**None**

This specification fully complies with constitutional principles:

- **Bun service** handles API logic only (Separation of Concerns)
- **Python service** handles data parsing only (Phase 1)
- Communication via **Redis queues** (async, decoupled)
- **Strong typing** enforced via TypeScript strict mode
- **Drizzle introspection** respects existing schema ownership (Python/Alembic)

---

## Appendix

### References

- Phase 1 Specification: `/specs/001-data-ingestion-infra/spec.md`
- Phase 1 Data Model: `/specs/001-data-ingestion-infra/plan/data-model.md`
- ElysiaJS Documentation: https://elysiajs.com/
- Drizzle ORM Introspection: https://orm.drizzle.team/kit-docs/commands#introspect--pull
- OpenAPI Specification: https://swagger.io/specification/

### Glossary

- **Catalog:** Public-facing list of active products available for browsing
- **Admin Products:** Internal view with supplier details, margins, and all product statuses
- **Product Matching:** Manually linking supplier items to internal products (setting `supplier_items.product_id`)
- **Sync:** Triggering a background data ingestion task for a supplier via Redis queue
- **Margin:** Percentage difference between internal target price and lowest supplier price: `(target - min_price) / target * 100`
- **JWT (JSON Web Token):** Compact token format for authentication containing user identity and role claims
- **Drizzle Introspection:** Process of generating TypeScript types from existing database schema without managing migrations

---

**Approval:**

- [ ] Tech Lead: [Name] - [Date]
- [ ] Product: [Name] - [Date]
- [ ] QA: [Name] - [Date]
