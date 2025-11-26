# Task List: High-Performance API Layer (Bun + ElysiaJS)

**Epic/Feature:** Phase 2 - API Layer for Product Catalog Management

**Specification:** `/specs/002-api-layer/spec.md`

**Implementation Plan:** `/specs/002-api-layer/plan/`

**Owner:** Development Team

---

## Task Organization

This task list is organized by **user story** to enable independent implementation and testing of each feature. Each phase represents a complete, independently testable increment of functionality.

**Key:**
- `[P]` - Task can be executed in parallel with other `[P]` tasks in the same phase
- `[US1]`, `[US2]`, etc. - User Story label from spec.md
- Tasks without story labels are setup/foundational/polish tasks

---

## Phase 1: Setup & Project Initialization

**Goal:** Bootstrap the Bun API project with all necessary infrastructure, dependencies, and configuration.

**Duration Estimate:** 3-4 hours

**Independent Test Criteria:**
- ✅ `bun --watch src/index.ts` starts successfully
- ✅ `curl http://localhost:3000/health` returns healthy status
- ✅ Database connection verified
- ✅ Redis connection verified
- ✅ Swagger UI accessible at `/docs`

### Tasks

- [X] T001 Install Bun runtime (v1.0+) and verify installation with `bun --version`
- [X] T002 Create project directory structure: `services/bun-api/{src,migrations,tests}`
- [X] T003 Initialize Bun project with `bun init -y` in services/bun-api/
- [X] T004 [P] Install core dependencies: elysia, @elysiajs/jwt, @elysiajs/swagger, @elysiajs/cors
- [X] T005 [P] Install database dependencies: drizzle-orm, drizzle-typebox, pg, drizzle-kit
- [X] T006 [P] Install queue dependency: ioredis
- [X] T007 Create `.env` file with environment variables (DATABASE_URL, REDIS_URL, JWT_SECRET, etc.)
- [X] T008 Create `drizzle.config.ts` for Drizzle Kit configuration
- [X] T009 Create database migration for users table: `migrations/001_create_users.sql`
- [X] T010 Generate bcrypt password hashes for seed users (admin, sales, procurement)
- [X] T011 Run users table migration: `psql $DATABASE_URL -f migrations/001_create_users.sql`
- [X] T012 Run Drizzle introspection: `bun run drizzle-kit introspect:pg` to generate schema
- [X] T013 Create database client in `src/db/client.ts` with connection pooling
- [X] T014 Create minimal API entry point in `src/index.ts` with Elysia app
- [X] T015 [P] Configure CORS middleware with allowed origins from env
- [X] T016 [P] Configure JWT plugin with secret from env
- [X] T017 [P] Configure Swagger plugin for API documentation
- [X] T018 Implement health check endpoint at `/health` checking DB and Redis connectivity
- [X] T019 Create project structure for controllers: `src/controllers/{auth,catalog,admin}`
- [X] T020 Create project structure for services: `src/services/`
- [X] T021 Create project structure for types: `src/types/`
- [X] T022 Create project structure for repositories: `src/db/repositories/`
- [X] T023 Create project structure for middleware: `src/middleware/`
- [X] T024 Verify server starts and health check passes: `bun --watch src/index.ts`
- [X] T025 Create README.md in services/bun-api/ with setup instructions

---

## Phase 2: Foundational Infrastructure

**Goal:** Implement foundational components that are prerequisites for all user stories (authentication, error handling, logging, base types).

**Duration Estimate:** 4-5 hours

**Independent Test Criteria:**
- ✅ JWT token can be generated and verified
- ✅ Error responses follow standard format
- ✅ Database queries return typed results
- ✅ Redis connection can publish messages

### Tasks

- [X] T026 Create TypeBox validation schemas for error responses in `src/types/errors.ts`
- [X] T027 Create global error handler middleware in `src/middleware/error-handler.ts`
- [X] T028 Create request logging middleware in `src/middleware/logger.ts`
- [X] T029 Create JWT authentication middleware in `src/middleware/auth.ts`
- [X] T030 Create role-based authorization guard in `src/middleware/rbac.ts`
- [X] T031 [P] Define TypeScript interfaces for Drizzle schemas in `src/db/schema/types.ts`
- [X] T032 [P] Create TypeBox validation schemas for catalog types in `src/types/catalog.types.ts`
- [X] T033 [P] Create TypeBox validation schemas for admin types in `src/types/admin.types.ts`
- [X] T034 [P] Create TypeBox validation schemas for auth types in `src/types/auth.types.ts`
- [X] T035 Create user repository interface in `src/db/repositories/user.repository.ts`
- [X] T036 Implement user repository with findByUsername and findById methods
- [X] T037 Create Redis client wrapper in `src/services/queue.service.ts`
- [X] T038 Implement Redis health check in queue service
- [X] T039 Create utility for generating internal SKUs in `src/utils/sku-generator.ts`
- [X] T040 Create utility for JWT token generation in `src/utils/jwt-utils.ts`

---

## Phase 3: User Story 1 - Authentication (FR-6)

**User Story:** As an internal user (sales/procurement/admin), I need to authenticate with the API to access protected endpoints.

**Priority:** Critical (P1)

**Duration Estimate:** 3-4 hours

**Independent Test Criteria:**
- ✅ POST `/api/v1/auth/login` with valid credentials returns JWT token
- ✅ POST `/api/v1/auth/login` with invalid credentials returns 401
- ✅ JWT token includes correct payload (sub, role, exp, iss)
- ✅ Token can be verified by auth middleware
- ✅ Expired tokens are rejected with 401

### Tasks

- [X] T041 [US1] Create LoginRequest and LoginResponse TypeBox schemas in auth types
- [X] T042 [US1] Create authentication service in `src/services/auth.service.ts`
- [X] T043 [US1] Implement login method: validate credentials against users table
- [X] T044 [US1] Implement password verification using Bun.password.verify with bcrypt
- [X] T045 [US1] Implement JWT token generation with user claims (sub, role, exp, iss)
- [X] T046 [US1] Create auth controller in `src/controllers/auth/index.ts`
- [X] T047 [US1] Implement POST `/api/v1/auth/login` endpoint with request validation
- [X] T048 [US1] Add login endpoint to main app in src/index.ts
- [X] T049 [US1] Test login flow: valid credentials return token with 200
- [X] T050 [US1] Test login flow: invalid username returns 401
- [X] T051 [US1] Test login flow: invalid password returns 401
- [X] T052 [US1] Test login flow: missing fields return 400
- [X] T053 [US1] Verify JWT payload structure matches specification
- [X] T054 [US1] Test token expiration after configured hours

---

## Phase 4: User Story 2 - Public Catalog (FR-1)

**User Story:** As a public client, I need to browse active products with filters (category, price, search) to find products I'm interested in.

**Priority:** Critical (P1)

**Duration Estimate:** 5-6 hours

**Independent Test Criteria:**
- ✅ GET `/api/v1/catalog` returns paginated active products without authentication
- ✅ Filtering by category_id works correctly
- ✅ Filtering by min_price and max_price works correctly
- ✅ Search by product name works correctly
- ✅ Pagination works correctly (page, limit)
- ✅ Response includes aggregated data (min_price, max_price, supplier_count)
- ✅ Response time p95 < 500ms for up to 1000 products

### Tasks

- [ ] T055 [P] [US2] Create CatalogProduct and CatalogResponse TypeBox schemas in catalog types
- [ ] T056 [P] [US2] Create CatalogQuery interface for query parameters in catalog types
- [ ] T057 [US2] Create product repository interface in `src/db/repositories/product.repository.ts`
- [ ] T058 [US2] Implement findActive method with filters (category, price range, search)
- [ ] T059 [US2] Add aggregations for min_price, max_price, supplier_count using Drizzle SQL
- [ ] T060 [US2] Implement pagination logic with offset and limit
- [ ] T061 [US2] Add sorting by product name (ascending)
- [ ] T062 [US2] Create catalog service in `src/services/catalog.service.ts`
- [ ] T063 [US2] Implement getProducts method calling repository with filters
- [ ] T064 [US2] Implement total count query for pagination metadata
- [ ] T065 [US2] Create catalog controller in `src/controllers/catalog/index.ts`
- [ ] T066 [US2] Implement GET `/api/v1/catalog` endpoint with query parameter validation
- [ ] T067 [US2] Add catalog routes to main app in src/index.ts
- [ ] T068 [US2] Test catalog endpoint: no auth required
- [ ] T069 [US2] Test catalog endpoint: only active products returned
- [ ] T070 [US2] Test catalog endpoint: category filter works
- [ ] T071 [US2] Test catalog endpoint: price range filter works
- [ ] T072 [US2] Test catalog endpoint: search filter works
- [ ] T073 [US2] Test catalog endpoint: combined filters work
- [ ] T074 [US2] Test catalog endpoint: pagination metadata correct
- [ ] T075 [US2] Test catalog endpoint: response time meets p95 < 500ms target

---

## Phase 5: User Story 3 - Admin Products View (FR-2)

**User Story:** As internal staff (sales/procurement/admin), I need to view detailed product information including all supplier prices and margins to make pricing decisions.

**Priority:** Critical (P1)

**Duration Estimate:** 4-5 hours

**Independent Test Criteria:**
- ✅ GET `/api/v1/admin/products` requires valid JWT token
- ✅ Returns products with all statuses (draft, active, archived)
- ✅ Includes supplier item details for each product
- ✅ Calculates margin percentage if target price exists
- ✅ Filtering by status, margin, supplier_id works
- ✅ Pagination works correctly
- ✅ Returns 401 if token missing or invalid

### Tasks

- [ ] T076 [P] [US3] Create AdminProduct and AdminProductsResponse TypeBox schemas in admin types
- [ ] T077 [P] [US3] Create SupplierItemDetail TypeBox schema in admin types
- [ ] T078 [US3] Extend product repository with findAll method for admin view
- [ ] T079 [US3] Implement JOIN query to fetch supplier items with supplier details
- [ ] T080 [US3] Implement margin calculation logic: (target - min_price) / target * 100
- [ ] T081 [US3] Add filtering by status, min_margin, max_margin, supplier_id
- [ ] T082 [US3] Add pagination with default 50 items per page
- [ ] T083 [US3] Create admin service in `src/services/admin.service.ts`
- [ ] T084 [US3] Implement getAdminProducts method with filters and pagination
- [ ] T085 [US3] Create admin controller in `src/controllers/admin/index.ts`
- [ ] T086 [US3] Implement GET `/api/v1/admin/products` endpoint with auth middleware
- [ ] T087 [US3] Add role check: sales, procurement, or admin roles allowed
- [ ] T088 [US3] Add admin routes to main app in src/index.ts
- [ ] T089 [US3] Test admin products endpoint: requires authentication
- [ ] T090 [US3] Test admin products endpoint: returns all product statuses
- [ ] T091 [US3] Test admin products endpoint: includes supplier details
- [ ] T092 [US3] Test admin products endpoint: margin calculation correct
- [ ] T093 [US3] Test admin products endpoint: status filter works
- [ ] T094 [US3] Test admin products endpoint: margin filters work
- [ ] T095 [US3] Test admin products endpoint: supplier filter works
- [ ] T096 [US3] Test admin products endpoint: pagination works
- [ ] T097 [US3] Test admin products endpoint: 401 without token

---

## Phase 6: User Story 4 - Product Matching (FR-4)

**User Story:** As procurement staff, I need to manually link or unlink supplier items to products so I can maintain accurate product-supplier relationships.

**Priority:** High (P2)

**Duration Estimate:** 4-5 hours

**Independent Test Criteria:**
- ✅ PATCH `/api/v1/admin/products/:id/match` requires procurement or admin role
- ✅ Link action updates supplier_items.product_id correctly
- ✅ Unlink action sets supplier_items.product_id to NULL
- ✅ Returns updated product with all supplier items
- ✅ Validation prevents linking to archived products
- ✅ Validation prevents linking already-linked items
- ✅ Returns 409 if supplier item already linked to different product
- ✅ Transaction ensures atomicity

### Tasks

- [ ] T098 [P] [US4] Create MatchRequest and MatchResponse TypeBox schemas in admin types
- [ ] T099 [US4] Create supplier item repository in `src/db/repositories/supplier-item.repository.ts`
- [ ] T100 [US4] Implement findById method in supplier item repository
- [ ] T101 [US4] Implement updateProductId method with transaction support
- [ ] T102 [US4] Add product repository method: findByIdWithSuppliers for response
- [ ] T103 [US4] Create matching service method in admin service
- [ ] T104 [US4] Implement validation: product exists and not archived
- [ ] T105 [US4] Implement validation: supplier item exists
- [ ] T106 [US4] Implement validation: supplier item not already linked (for link action)
- [ ] T107 [US4] Implement validation: supplier item linked to correct product (for unlink action)
- [ ] T108 [US4] Implement link action: update supplier_items.product_id in transaction
- [ ] T109 [US4] Implement unlink action: set supplier_items.product_id to NULL in transaction
- [ ] T110 [US4] Implement PATCH `/api/v1/admin/products/:id/match` endpoint
- [ ] T111 [US4] Add role check: procurement or admin only
- [ ] T112 [US4] Add request body validation for action and supplier_item_id
- [ ] T113 [US4] Test matching endpoint: requires authentication
- [ ] T114 [US4] Test matching endpoint: requires procurement or admin role
- [ ] T115 [US4] Test matching endpoint: link action works correctly
- [ ] T116 [US4] Test matching endpoint: unlink action works correctly
- [ ] T117 [US4] Test matching endpoint: 400 if product archived
- [ ] T118 [US4] Test matching endpoint: 409 if item already linked to different product
- [ ] T119 [US4] Test matching endpoint: 404 if product not found
- [ ] T120 [US4] Test matching endpoint: 404 if supplier item not found
- [ ] T121 [US4] Test matching endpoint: transaction rollback on error

---

## Phase 7: User Story 5 - Product Creation (FR-5)

**User Story:** As procurement staff, I need to create new internal products with optional supplier item linkage to support the "split SKU" workflow.

**Priority:** High (P2)

**Duration Estimate:** 4-5 hours

**Independent Test Criteria:**
- ✅ POST `/api/v1/admin/products` requires procurement or admin role
- ✅ Creates new product with auto-generated SKU if not provided
- ✅ Creates new product with provided internal_sku
- ✅ Links supplier item if supplier_item_id provided
- ✅ Validates internal_sku uniqueness
- ✅ Validates category_id exists if provided
- ✅ Returns created product with supplier items
- ✅ Returns 400 for validation errors
- ✅ Transaction ensures atomicity (product creation + item link)

### Tasks

- [ ] T122 [P] [US5] Create CreateProductRequest and CreateProductResponse schemas in admin types
- [ ] T123 [US5] Implement product repository create method
- [ ] T124 [US5] Implement category repository findById method for validation
- [ ] T125 [US5] Implement SKU uniqueness check in product repository
- [ ] T126 [US5] Create product creation service method in admin service
- [ ] T127 [US5] Implement validation: name required (1-500 chars)
- [ ] T128 [US5] Implement validation: internal_sku unique if provided
- [ ] T129 [US5] Implement validation: category_id exists if provided
- [ ] T130 [US5] Implement validation: supplier_item_id exists and not linked if provided
- [ ] T131 [US5] Implement auto-generation of internal_sku using sku-generator utility
- [ ] T132 [US5] Implement product creation with default status='draft'
- [ ] T133 [US5] Implement supplier item linking in same transaction if supplier_item_id provided
- [ ] T134 [US5] Implement POST `/api/v1/admin/products` endpoint
- [ ] T135 [US5] Add role check: procurement or admin only
- [ ] T136 [US5] Add request body validation
- [ ] T137 [US5] Test product creation: requires authentication
- [ ] T138 [US5] Test product creation: requires procurement or admin role
- [ ] T139 [US5] Test product creation: creates with auto-generated SKU
- [ ] T140 [US5] Test product creation: creates with provided SKU
- [ ] T141 [US5] Test product creation: links supplier item if provided
- [ ] T142 [US5] Test product creation: 400 if internal_sku duplicate
- [ ] T143 [US5] Test product creation: 400 if category_id invalid
- [ ] T144 [US5] Test product creation: 400 if supplier_item_id invalid
- [ ] T145 [US5] Test product creation: 400 if name empty or too long
- [ ] T146 [US5] Test product creation: transaction rollback on error

---

## Phase 8: User Story 6 - Sync Trigger (FR-3)

**User Story:** As an administrator, I need to trigger background data ingestion for a supplier so the catalog stays up-to-date with supplier pricing.

**Priority:** High (P2)

**Duration Estimate:** 3-4 hours

**Independent Test Criteria:**
- ✅ POST `/api/v1/admin/sync` requires admin role
- ✅ Enqueues task message to Redis with correct format
- ✅ Returns task_id immediately without waiting for completion
- ✅ Validates supplier exists before enqueuing
- ✅ Returns 404 if supplier not found
- ✅ Returns 503 if Redis unavailable
- ✅ Rate limiting: max 10 requests per minute per user
- ✅ Returns 429 if rate limit exceeded

### Tasks

- [ ] T147 [P] [US6] Create SyncRequest and SyncResponse TypeBox schemas in admin types
- [ ] T148 [P] [US6] Create ParseTaskMessage TypeBox schema in types/queue.types.ts
- [ ] T149 [US6] Create supplier repository in `src/db/repositories/supplier.repository.ts`
- [ ] T150 [US6] Implement findById method in supplier repository
- [ ] T151 [US6] Implement enqueueParseTask method in queue service
- [ ] T152 [US6] Implement message serialization matching queue-messages.json contract
- [ ] T153 [US6] Add Redis error handling with 503 response
- [ ] T154 [US6] Create sync service method in admin service
- [ ] T155 [US6] Implement validation: supplier exists
- [ ] T156 [US6] Implement task message construction with all required fields
- [ ] T157 [US6] Implement POST `/api/v1/admin/sync` endpoint
- [ ] T158 [US6] Add role check: admin only
- [ ] T159 [US6] Add rate limiting middleware: 10 requests per minute per user
- [ ] T160 [US6] Add request body validation for supplier_id
- [ ] T161 [US6] Test sync endpoint: requires authentication
- [ ] T162 [US6] Test sync endpoint: requires admin role (403 for non-admin)
- [ ] T163 [US6] Test sync endpoint: enqueues message to Redis
- [ ] T164 [US6] Test sync endpoint: message format matches contract
- [ ] T165 [US6] Test sync endpoint: returns task_id immediately
- [ ] T166 [US6] Test sync endpoint: 404 if supplier not found
- [ ] T167 [US6] Test sync endpoint: 503 if Redis unavailable
- [ ] T168 [US6] Test sync endpoint: rate limit enforced (429 after 10 requests)

---

## Phase 9: User Story 7 - API Documentation (FR-7)

**User Story:** As a developer, I need interactive API documentation to understand how to integrate with the API without reading source code.

**Priority:** Medium (P3)

**Duration Estimate:** 2-3 hours

**Independent Test Criteria:**
- ✅ Swagger UI accessible at `/docs`
- ✅ OpenAPI spec accessible at `/docs/json`
- ✅ All endpoints documented with methods, paths, descriptions
- ✅ Request/response schemas visible with examples
- ✅ Authentication requirements shown per endpoint
- ✅ "Try it out" functionality works for public endpoints

### Tasks

- [ ] T169 [P] [US7] Configure Swagger plugin with API metadata (title, version, description)
- [ ] T170 [P] [US7] Add OpenAPI tags for endpoint grouping (auth, catalog, admin)
- [ ] T171 [US7] Add example request bodies to all POST/PATCH endpoints
- [ ] T172 [US7] Add example responses to all endpoints (200, 400, 401, 404, etc.)
- [ ] T173 [US7] Document authentication using bearer token security scheme
- [ ] T174 [US7] Add endpoint descriptions and summaries
- [ ] T175 [US7] Test Swagger UI: accessible at /docs
- [ ] T176 [US7] Test Swagger UI: all endpoints listed
- [ ] T177 [US7] Test Swagger UI: request/response schemas visible
- [ ] T178 [US7] Test Swagger UI: examples provided
- [ ] T179 [US7] Test Swagger UI: try it out works for catalog endpoint
- [ ] T180 [US7] Test OpenAPI spec: valid JSON at /docs/json

---

## Phase 10: Cross-Cutting Concerns & Polish

**Goal:** Implement cross-cutting concerns that span multiple user stories (logging, error handling improvements, performance optimization).

**Duration Estimate:** 4-5 hours

**Independent Test Criteria:**
- ✅ All requests logged with structured JSON format
- ✅ Error responses consistent across all endpoints
- ✅ Database connection pool monitored
- ✅ Performance targets met (p95 < 500ms catalog, < 1000ms admin)
- ✅ Graceful shutdown on SIGTERM

### Tasks

- [ ] T181 [P] Implement structured logging with request ID propagation
- [ ] T182 [P] Add response time logging for all endpoints
- [ ] T183 [P] Add error context logging (stack traces for 5xx errors)
- [ ] T184 Implement graceful shutdown handler for SIGTERM
- [ ] T185 Add database connection pool monitoring
- [ ] T186 Add Redis connection monitoring
- [ ] T187 Optimize catalog query: add database indexes if needed
- [ ] T188 Optimize admin products query: add JOINs indexes if needed
- [ ] T189 Add request/response compression middleware
- [ ] T190 Add security headers middleware (helmet)
- [ ] T191 Create performance benchmarking script for catalog endpoint
- [ ] T192 Create performance benchmarking script for admin endpoints
- [ ] T193 Verify p95 response times meet targets
- [ ] T194 Add error monitoring/alerting configuration (optional)
- [ ] T195 Document environment variables in README
- [ ] T196 Document deployment steps in README
- [ ] T197 Create docker-compose service definition for bun-api
- [ ] T198 Test Docker build and container startup
- [ ] T199 Update root README with Phase 2 API information
- [ ] T200 Create architecture decision record for Bun + ElysiaJS choice

---

## Dependencies & Execution Strategy

### Dependency Graph (User Story Completion Order)

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational Infrastructure)
    ↓
    ├─→ Phase 3 (US1: Authentication) ← Required by all authenticated endpoints
    │       ↓
    │       ├─→ Phase 4 (US2: Public Catalog) ← Independent, no auth
    │       ├─→ Phase 5 (US3: Admin Products View) ← Depends on US1
    │       ├─→ Phase 6 (US4: Product Matching) ← Depends on US1, US3
    │       ├─→ Phase 7 (US5: Product Creation) ← Depends on US1
    │       └─→ Phase 8 (US6: Sync Trigger) ← Depends on US1
    │
    └─→ Phase 9 (US7: API Documentation) ← Can start after any endpoint implemented
        ↓
    Phase 10 (Polish & Cross-Cutting Concerns)
```

### Parallel Execution Opportunities

**Phase 1 (Setup):**
- Tasks T004, T005, T006 (dependency installations) can run in parallel
- Tasks T015, T016, T017 (middleware configurations) can run in parallel

**Phase 2 (Foundational):**
- Tasks T031, T032, T033, T034 (TypeBox schemas) can run in parallel

**Phase 4 (US2: Public Catalog):**
- Tasks T055, T056 (schema definitions) can run in parallel

**Phase 5 (US3: Admin Products View):**
- Tasks T076, T077 (schema definitions) can run in parallel

**Phase 6 (US4: Product Matching):**
- Task T098 (schema definitions) and T099 (repository creation) can overlap

**Phase 7 (US5: Product Creation):**
- Tasks T122 (schema definitions) and T123-T125 (repository methods) can overlap

**Phase 8 (US6: Sync Trigger):**
- Tasks T147, T148 (schema definitions) can run in parallel

**Phase 9 (US7: Documentation):**
- Tasks T169, T170 (Swagger configuration) can run in parallel

**Phase 10 (Polish):**
- Tasks T181, T182, T183 (logging improvements) can run in parallel

---

## Implementation Strategy

### MVP Scope (Minimum Viable Product)

**Recommended MVP includes:**
- Phase 1: Setup & Project Initialization (all tasks)
- Phase 2: Foundational Infrastructure (all tasks)
- Phase 3: User Story 1 - Authentication (all tasks)
- Phase 4: User Story 2 - Public Catalog (all tasks)
- Phase 5: User Story 3 - Admin Products View (all tasks)

**MVP Success Criteria:**
- ✅ Public clients can browse catalog without auth
- ✅ Internal staff can log in and view detailed product information
- ✅ API is documented via Swagger UI
- ✅ Basic error handling and logging in place

**Post-MVP Features:**
- Phase 6: Product Matching (enables procurement workflow)
- Phase 7: Product Creation (enables split SKU workflow)
- Phase 8: Sync Trigger (enables background data updates)
- Phase 9: API Documentation (comprehensive docs)
- Phase 10: Polish & Performance Optimization

### Incremental Delivery

1. **Week 1:** Phases 1-3 (Setup + Auth)
   - Deliverable: Authenticated API with health checks
2. **Week 2:** Phases 4-5 (Catalog + Admin View)
   - Deliverable: MVP with read-only functionality
3. **Week 3:** Phases 6-8 (Write Operations)
   - Deliverable: Full CRUD functionality
4. **Week 4:** Phases 9-10 (Documentation + Polish)
   - Deliverable: Production-ready API

---

## Task Summary

- **Total Tasks:** 200
- **Phase 1 (Setup):** 25 tasks
- **Phase 2 (Foundational):** 15 tasks
- **Phase 3 (US1: Authentication):** 14 tasks
- **Phase 4 (US2: Public Catalog):** 21 tasks
- **Phase 5 (US3: Admin Products View):** 22 tasks
- **Phase 6 (US4: Product Matching):** 24 tasks
- **Phase 7 (US5: Product Creation):** 25 tasks
- **Phase 8 (US6: Sync Trigger):** 22 tasks
- **Phase 9 (US7: API Documentation):** 12 tasks
- **Phase 10 (Polish):** 20 tasks

**Estimated Total Effort:** 38-47 hours

**Parallel Opportunities:** 15+ tasks can be executed in parallel per phase

---

## Testing Summary

### Test Coverage by Phase

**Phase 3 (Authentication):**
- Unit tests: T049-T054 (6 test scenarios)
- Coverage target: 100% of auth service logic

**Phase 4 (Public Catalog):**
- Integration tests: T068-T075 (8 test scenarios)
- Performance test: T075 (p95 < 500ms)
- Coverage target: ≥80% of catalog service + repository

**Phase 5 (Admin Products View):**
- Integration tests: T089-T097 (9 test scenarios)
- Coverage target: ≥80% of admin service

**Phase 6 (Product Matching):**
- Integration tests: T113-T121 (9 test scenarios)
- Transaction test: T121 (rollback verification)
- Coverage target: ≥80% of matching logic

**Phase 7 (Product Creation):**
- Integration tests: T137-T146 (10 test scenarios)
- Transaction test: T146 (rollback verification)
- Coverage target: ≥80% of creation logic

**Phase 8 (Sync Trigger):**
- Integration tests: T161-T168 (8 test scenarios)
- Redis integration: T163-T164 (message format validation)
- Coverage target: ≥80% of queue service

**Overall Coverage Target:** ≥80% for all business logic (services, repositories, controllers)

---

## Notes

- All tasks follow strict checklist format: `- [ ] [TaskID] [P?] [Story?] Description with file path`
- Tasks marked `[P]` can be parallelized within their phase
- Tasks marked `[USX]` belong to specific user stories from spec.md
- Dependencies are explicit - later phases depend on earlier phases completing
- Each user story phase is independently testable with clear acceptance criteria
- Performance targets defined: p95 < 500ms (catalog), p95 < 1000ms (admin)
- Constitutional alignment verified: SOLID, Strong Typing, KISS, DRY, Separation of Concerns
- Testing is integrated throughout implementation phases (not deferred to end)

---

**Document Status:** Complete ✅

**Next Steps:** Begin Phase 1 (Setup & Project Initialization)

**Questions?** Refer to:
- Feature Spec: `/specs/002-api-layer/spec.md`
- Research Doc: `/specs/002-api-layer/plan/research.md`
- Data Model: `/specs/002-api-layer/plan/data-model.md`
- Quickstart Guide: `/specs/002-api-layer/plan/quickstart.md`
- API Contracts: `/specs/002-api-layer/plan/contracts/`
