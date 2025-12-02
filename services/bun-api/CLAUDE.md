# Bun API Service Context

## Overview
REST API layer for Marketbel catalog system. Built with ElysiaJS + Drizzle ORM.

**Port:** 3000  
**Docs:** http://localhost:3000/docs (Swagger)

---

## Stack
- **Runtime:** Bun (not Node.js)
- **Framework:** ElysiaJS
- **ORM:** Drizzle ORM + node-postgres
- **Validation:** TypeBox
- **Auth:** @elysiajs/jwt + bcrypt

---

## Architecture (SOLID)

```
Controllers (HTTP) → Services (Logic) → Repositories (Data)
```

- **Controllers:** HTTP only - routing, validation, response serialization
- **Services:** Business logic, static classes or pure functions
- **Repositories:** Database access via Drizzle, implement interfaces

---

## Structure

```
src/
├── controllers/
│   ├── auth/        # Login, register
│   ├── catalog/     # Public product/category endpoints
│   └── admin/       # Sales, procurement, suppliers, sync
├── services/        # Business logic
├── db/
│   ├── schema/      # Drizzle schemas (introspected from Phase 1)
│   └── repositories/
├── middleware/      # Auth, RBAC, error handling
├── types/           # TypeBox schemas + TS types
└── utils/
```

---

## Commands

```bash
bun install
bun --watch src/index.ts     # Dev with hot reload
bun test                      # Run tests
bun run tsc --noEmit         # Type check
```

---

## Key Patterns

### ElysiaJS Plugin Scoping

**Problem:** `new Elysia()` creates isolated scope - JWT not inherited.

```typescript
// ❌ Wrong - isolated scope, jwt undefined
export const middleware = new Elysia()
  .derive(({ jwt }) => { /* jwt undefined! */ })

// ✅ Correct - functional plugin, uses parent context
export const middleware = (app: Elysia) =>
  app.derive(({ jwt }) => { /* jwt available */ })
```

### TypeBox Validation

```typescript
import { t } from 'elysia'

const CreateUserSchema = t.Object({
  email: t.String({ format: 'email' }),
  password: t.String({ minLength: 8 })
})
```

### Repository Pattern

```typescript
// db/repositories/product.repository.ts
export class ProductRepository {
  async findById(id: string): Promise<Product | null> {
    return db.query.products.findFirst({ where: eq(products.id, id) })
  }
}
```

---

## Roles & Auth

| Role | Access |
|------|--------|
| `sales` | Catalog, orders |
| `procurement` | Suppliers, matching |
| `admin` | Everything + sync |

```typescript
// Usage in controller
.use(requireAuth)           // Any authenticated user
.use(requireRole('admin'))  // Specific role
```

---

## Queue Communication

API publishes tasks to Redis, Python worker consumes:

```typescript
// services/queue.service.ts
await QueueService.enqueue('parse_task', { supplier_id: '...' })
```

---

## Database

- **READ-ONLY** for Phase 1 tables (products, supplier_items, etc.)
- **MANAGED** for users table (local migration)
- Drizzle introspects schema from PostgreSQL

---

## Testing

```typescript
import { describe, test, expect } from 'bun:test'

// Create isolated test app
const app = new Elysia()
  .use(errorHandler)
  .use(jwt({ name: 'jwt', secret: 'test' }))
  .use(controller)

test('GET /api/products', async () => {
  const res = await app.handle(new Request('http://localhost/api/products'))
  expect(res.status).toBe(200)
})
```

---

## Common Issues

1. **JWT undefined in middleware** → Use functional plugin pattern
2. **Type errors with Drizzle** → Run `bun run drizzle-kit introspect`
3. **CORS errors** → Check `cors()` plugin in `index.ts`
