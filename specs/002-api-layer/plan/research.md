# Research Document: API Layer Technology Stack

**Date:** 2025-11-26

**Feature:** 002-api-layer (High-Performance API Layer)

---

## Executive Summary

This document captures the technology decisions, best practices, and architectural patterns for implementing the Bun-based API layer. All decisions align with constitutional principles (SOLID, KISS, DRY, Strong Typing, Separation of Concerns).

---

## Technology Stack Decisions

### 1. Runtime: Bun (Latest)

**Decision:** Use Bun as the JavaScript/TypeScript runtime

**Rationale:**
- **Performance:** Bun is significantly faster than Node.js for HTTP handling (~3x faster in benchmarks)
- **Native TypeScript:** No transpilation required, reducing build complexity
- **Built-in Features:** Native SQLite, password hashing (bcrypt), fetch API
- **Compatibility:** Drop-in replacement for Node.js with npm package support
- **Alignment:** Supports high-performance requirements (NFR-1: p95 < 500ms)

**Alternatives Considered:**
- **Node.js:** Mature ecosystem but slower performance
- **Deno:** Good performance but less mature ecosystem

**Constitutional Alignment:** KISS principle - Bun simplifies tooling by eliminating transpilation overhead

---

### 2. Framework: ElysiaJS

**Decision:** Use ElysiaJS as the web framework

**Rationale:**
- **Performance:** Designed for Bun, optimized for low latency
- **Type Safety:** End-to-end type inference with TypeScript
- **Built-in Validation:** Native TypeBox integration (no additional library)
- **Plugin Ecosystem:** Official JWT, CORS, Swagger plugins
- **Developer Experience:** Declarative API with excellent IDE support

**Best Practices (from documentation):**

#### Recommended Architecture Pattern

```typescript
// Feature-based folder structure
src/
  auth/
    index.ts       // Elysia controller (HTTP layer)
    service.ts     // Business logic (decoupled)
    model.ts       // TypeBox schemas
  catalog/
    index.ts
    service.ts
    model.ts
  admin/
    index.ts
    service.ts
    model.ts
```

#### Controller Pattern (Single Responsibility)

```typescript
// controllers/auth/index.ts
import { Elysia } from 'elysia'
import { AuthService } from './service'
import { AuthModel } from './model'

export const authController = new Elysia({ prefix: '/auth' })
  .post('/login', async ({ body }) => {
    return AuthService.login(body)
  }, {
    body: 'auth.login',
    response: { 200: 'auth.loginResponse', 401: 'auth.unauthorized' }
  })
```

#### Service Pattern (Business Logic Decoupled)

```typescript
// services/auth/service.ts
export abstract class AuthService {
  static async login({ username, password }: LoginRequest) {
    const user = await UserRepository.findByUsername(username)
    if (!user || !await Bun.password.verify(password, user.password_hash)) {
      throw new Error('Invalid credentials')
    }
    return { token: generateJWT(user) }
  }
}
```

**Alternatives Considered:**
- **Fastify:** Mature but slower, requires more setup for validation
- **Express:** Too slow for performance requirements

**Constitutional Alignment:**
- Single Responsibility: Controllers handle HTTP only
- Dependency Inversion: Services depend on repository abstractions

---

### 3. ORM: Drizzle ORM + node-postgres

**Decision:** Use Drizzle ORM with PostgreSQL driver

**Rationale:**
- **Type Safety:** SQL-like syntax with full TypeScript inference
- **Introspection:** Can read existing schema without managing migrations (critical for Phase 1 compatibility)
- **Performance:** Minimal overhead, generates efficient queries
- **Zero Magic:** No heavy abstractions, predictable behavior
- **TypeBox Integration:** Native schema generation for validation

**Introspection Workflow:**

```bash
# One-time setup to pull existing schema
bun run drizzle-kit introspect:pg
# Generates: src/db/schema/index.ts with typed models
```

**Usage Pattern:**

```typescript
import { drizzle } from 'drizzle-orm/node-postgres'
import { Pool } from 'pg'
import * as schema from './schema'

const pool = new Pool({ connectionString: process.env.DATABASE_URL })
export const db = drizzle(pool, { schema })

// Type-safe queries
const products = await db
  .select()
  .from(schema.products)
  .where(eq(schema.products.status, 'active'))
```

**TypeBox Schema Generation:**

```typescript
import { createSelectSchema, createInsertSchema } from 'drizzle-typebox'
import { products } from './schema'

// Auto-generate validation schemas
export const ProductSelectSchema = createSelectSchema(products)
export const ProductInsertSchema = createInsertSchema(products, {
  // Exclude generated fields
  id: false,
  created_at: false
})
```

**Alternatives Considered:**
- **Prisma:** Too heavy, manages migrations (conflicts with Phase 1 ownership)
- **TypeORM:** Performance issues, complex decorators
- **Kysely:** Good but less integrated with TypeBox

**Constitutional Alignment:**
- DRY: Schema is single source of truth (introspected from DB)
- Separation of Concerns: Respects Phase 1 ownership of migrations

---

### 4. Validation: TypeBox (Native to Elysia)

**Decision:** Use TypeBox for request/response validation

**Rationale:**
- **Native Integration:** Built into Elysia, zero additional setup
- **Performance:** Compiles to optimized validators (~10x faster than Zod)
- **JSON Schema:** Generates OpenAPI schemas automatically
- **Type Inference:** Full TypeScript support

**Usage Pattern:**

```typescript
import { t } from 'elysia'

// Define schemas
const LoginSchema = t.Object({
  username: t.String({ minLength: 3 }),
  password: t.String({ minLength: 8 })
})

// Use in routes
app.post('/login', handler, { body: LoginSchema })
```

**Alternatives Considered:**
- **Zod:** Popular but slower, requires separate OpenAPI generation
- **Joi:** Legacy, no TypeScript inference

**Constitutional Alignment:** Strong Typing principle

---

### 5. Authentication: @elysiajs/jwt + bcryptjs

**Decision:** Use Elysia JWT plugin with bcrypt password hashing

**Rationale:**
- **Official Plugin:** Maintained by Elysia team
- **Type Safety:** JWT payload types inferred automatically
- **Simplicity:** Minimal configuration
- **Security:** Industry-standard bcrypt for passwords (Bun has native support)

**Usage Pattern:**

```typescript
import { Elysia } from 'elysia'
import { jwt } from '@elysiajs/jwt'

const app = new Elysia()
  .use(jwt({
    name: 'jwt',
    secret: process.env.JWT_SECRET!,
    exp: '24h'
  }))
  .post('/login', async ({ body, jwt }) => {
    // Validate user...
    const token = await jwt.sign({
      sub: user.id,
      role: user.role,
      iss: 'marketbel-api'
    })
    return { token }
  })
  .derive(async ({ jwt, headers }) => {
    const token = headers.authorization?.replace('Bearer ', '')
    const payload = await jwt.verify(token)
    return { user: payload }
  })
  .get('/admin/products', ({ user }) => {
    // user is typed from JWT payload
  }, {
    beforeHandle: ({ user }) => {
      if (!user) throw new Error('Unauthorized')
    }
  })
```

**Password Hashing:**

```typescript
// Bun native (no library needed)
const hash = await Bun.password.hash(plainPassword, { algorithm: 'bcrypt' })
const isValid = await Bun.password.verify(plainPassword, hash)
```

**Alternatives Considered:**
- **Passport.js:** Too heavy for simple JWT
- **Custom JWT:** Reinventing the wheel

**Constitutional Alignment:** KISS principle - use official plugin

---

### 6. Documentation: @elysiajs/swagger

**Decision:** Use Elysia Swagger plugin for API documentation

**Rationale:**
- **Auto-Generation:** Reads TypeBox schemas automatically
- **Interactive UI:** Swagger UI for testing endpoints
- **Zero Config:** Works out of the box with Elysia

**Usage Pattern:**

```typescript
import { swagger } from '@elysiajs/swagger'

const app = new Elysia()
  .use(swagger({
    documentation: {
      info: {
        title: 'Marketbel API',
        version: '1.0.0'
      }
    }
  }))
  // Routes automatically documented
```

**Output:**
- `/docs` - Swagger UI
- `/docs/json` - OpenAPI spec

**Constitutional Alignment:** DRY - documentation generated from code

---

### 7. Queue: ioredis

**Decision:** Use ioredis for Redis queue publishing

**Rationale:**
- **Publisher-Only:** Simple JSON message publishing
- **Reliability:** Industry standard, battle-tested
- **Performance:** Connection pooling, pipelining
- **TypeScript:** Full type definitions

**Usage Pattern:**

```typescript
import Redis from 'ioredis'

const redis = new Redis(process.env.REDIS_URL)

// Publish task to queue
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

**Alternatives Considered:**
- **BullMQ:** Too heavy for publisher-only mode
- **redis package:** Less maintained

**Constitutional Alignment:** Separation of Concerns - async queue communication

---

## Architectural Patterns

### SOLID Implementation

#### Single Responsibility Principle

```
Controllers → Handle HTTP (routing, validation, serialization)
Services → Handle business logic (margins, filtering, SKU generation)
Repositories → Handle database access (Drizzle queries)
Models → Handle validation schemas (TypeBox)
```

#### Dependency Inversion

```typescript
// Repository interface (abstraction)
interface IProductRepository {
  findActive(filters: CatalogFilters): Promise<Product[]>
  findById(id: string): Promise<Product | null>
}

// Service depends on abstraction
class CatalogService {
  constructor(private repo: IProductRepository) {}

  async getProducts(filters: CatalogFilters) {
    return this.repo.findActive(filters)
  }
}

// Concrete implementation
class DrizzleProductRepository implements IProductRepository {
  async findActive(filters: CatalogFilters) {
    return db.select().from(products).where(eq(products.status, 'active'))
  }
}
```

---

### Database Strategy (Hybrid Approach)

**Phase 1 Tables (READ-ONLY):**
- `products`, `supplier_items`, `suppliers`, `categories`, `price_history`, `parsing_logs`
- Accessed via Drizzle introspection
- NO migrations managed by Bun service

**Phase 2 Tables (MANAGED LOCALLY):**
- `users` table for authentication
- Requires SQL migration script
- Schema:

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(50) NOT NULL CHECK (role IN ('sales', 'procurement', 'admin')),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed default admin user (password: admin123)
INSERT INTO users (username, password_hash, role) VALUES (
  'admin',
  '$2b$10$...',  -- bcrypt hash of 'admin123'
  'admin'
);
```

---

## Performance Optimizations

### Connection Pooling

```typescript
import { Pool } from 'pg'

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  min: 5,
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000
})
```

### Query Optimization

- Leverage existing indexes from Phase 1 schema
- Use `LIMIT` and `OFFSET` for pagination
- Use `JOIN` efficiently for supplier items

### Response Caching (Future Enhancement)

- Redis caching for catalog endpoint (TTL: 5 minutes)
- Invalidate on product updates

---

## Security Considerations

### Input Validation
- TypeBox schemas enforce strict types at API boundaries
- Prevents SQL injection via parameterized queries (Drizzle)

### Authentication
- JWT tokens expire after 24 hours (configurable)
- Passwords hashed with bcrypt (cost factor: 10)
- Tokens validated on every admin route

### CORS Configuration

```typescript
import { cors } from '@elysiajs/cors'

app.use(cors({
  origin: process.env.ALLOWED_ORIGINS.split(','),
  credentials: true
}))
```

### Rate Limiting

```typescript
import { rateLimit } from '@elysiajs/rate-limit'

app.use(rateLimit({
  duration: 60000, // 1 minute
  max: 10, // 10 requests per minute
  generator: ({ headers }) => headers.authorization // Per user
}))
```

---

## Testing Strategy

### Unit Tests (Bun Test)

```typescript
import { describe, it, expect } from 'bun:test'
import { CatalogService } from './service'

describe('CatalogService', () => {
  it('filters products by category', async () => {
    const mockRepo = {
      findActive: async () => [{ id: '1', name: 'Product' }]
    }
    const service = new CatalogService(mockRepo)
    const results = await service.getProducts({ category_id: '123' })
    expect(results).toHaveLength(1)
  })
})
```

### Integration Tests

```typescript
import { Elysia } from 'elysia'
import { treaty } from '@elysiajs/eden'

const app = new Elysia().get('/', () => 'Hello')
const api = treaty(app)

it('returns catalog', async () => {
  const { data } = await api.catalog.get()
  expect(data).toBeDefined()
})
```

**Coverage Target:** ≥80% for business logic

---

## Deployment Configuration

### Environment Variables

```bash
# Server
BUN_PORT=3000
NODE_ENV=production

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/marketbel

# Redis
REDIS_URL=redis://localhost:6379
REDIS_QUEUE_NAME=parse-tasks

# Auth
JWT_SECRET=your-secure-secret-key
JWT_ISSUER=marketbel-api
JWT_EXPIRATION_HOURS=24

# CORS
ALLOWED_ORIGINS=https://app.marketbel.com

# Rate Limiting
SYNC_RATE_LIMIT_PER_MINUTE=10

# Logging
LOG_LEVEL=info
```

### Docker Setup

```dockerfile
FROM oven/bun:latest

WORKDIR /app

COPY package.json bun.lockb ./
RUN bun install --frozen-lockfile

COPY . .

EXPOSE 3000

CMD ["bun", "run", "src/index.ts"]
```

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|-----------|
| How to handle database migrations for users table? | Create SQL migration script, run manually before deployment |
| Should we use Redis for rate limiting? | Yes for production, in-memory for MVP (single instance) |
| How to generate internal_sku? | Format: `PROD-{timestamp}-{random}` |
| Password complexity requirements? | Out of scope for MVP, document as future enhancement |

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Drizzle introspection fails if Phase 1 schema changes | High | Pin to specific schema version, add CI check |
| Redis unavailable blocks sync endpoint | Medium | Return 503 gracefully, other endpoints unaffected |
| JWT secret leaked | Critical | Store in environment variable, rotate on compromise |
| Database connection pool exhaustion | High | Monitor pool usage, alert at 80% utilization |

---

## References

- ElysiaJS Documentation: https://elysiajs.com/
- ElysiaJS Best Practices: https://elysiajs.com/essential/best-practice.html
- Drizzle ORM Introspection: https://orm.drizzle.team/kit-docs/commands#introspect--pull
- Drizzle TypeBox Integration: https://orm.drizzle.team/docs/typebox
- Bun Documentation: https://bun.sh/docs
- ioredis Documentation: https://github.com/redis/ioredis

---

**Document Status:** Complete ✅

**Next Steps:** Proceed to Phase 1 (Data Model Design)
