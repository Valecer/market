> **Refer to: [[../../CLAUDE.md]] and [[../../docs/PROJECT_SUMMARY.md]]**

# Bun API Service

**Role:** REST API layer
**Phase:** 2 (API Layer)

## Stack

Bun (not Node.js), ElysiaJS, Drizzle ORM + node-postgres, TypeBox validation, @elysiajs/jwt

## Commands

```bash
cd services/bun-api

bun install
bun --watch src/index.ts    # Dev with hot reload
bun test                     # Tests
bun run tsc --noEmit        # Type check
```

## Architecture

```
Controllers (HTTP) → Services (Logic) → Repositories (Data)
```

**SOLID:** Controllers handle HTTP only, Services handle logic, Repositories handle data

## Critical Pattern: ElysiaJS Plugin Scoping

**Problem:** `new Elysia()` creates isolated scope - JWT not inherited.

```typescript
// ❌ Wrong - isolated scope, jwt undefined
export const middleware = new Elysia()
  .derive(({ jwt }) => { /* jwt undefined! */ })

// ✅ Correct - functional plugin, uses parent context
export const middleware = (app: Elysia) =>
  app.derive(({ jwt }) => { /* jwt available */ })
```

## TypeBox Validation

```typescript
import { t } from 'elysia'

const CreateUserSchema = t.Object({
  email: t.String({ format: 'email' }),
  password: t.String({ minLength: 8 })
})
```

## Roles & Auth

| Role | Access |
|------|--------|
| `sales` | Catalog, orders |
| `procurement` | Suppliers, matching |
| `admin` | Everything + sync |

```typescript
.use(requireAuth)           // Any authenticated user
.use(requireRole('admin'))  // Specific role
```

## Queue Communication

```typescript
// services/queue.service.ts
await QueueService.enqueue('parse_task', { supplier_id: '...' })
```

## Database

- **READ-ONLY** for Phase 1 tables (products, supplier_items, etc.)
- **MANAGED** for users table (local SQL migration)
- Drizzle introspects schema from PostgreSQL

## Common Issues

1. **JWT undefined in middleware** → Use functional plugin pattern (see above)
2. **Type errors with Drizzle** → Run `bun run drizzle-kit introspect`
3. **CORS errors** → Check `cors()` plugin in `index.ts`
