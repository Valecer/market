# Data Model: API Layer

**Date:** 2025-11-26

**Feature:** 002-api-layer

---

## Overview

This document defines the data model for the Bun API service. The API uses a **hybrid database strategy**:

1. **Phase 1 Tables (READ-ONLY):** Introspected via Drizzle ORM, managed by Python/Alembic
2. **Phase 2 Tables (MANAGED LOCALLY):** Authentication tables created by this service

---

## Database Schema Strategy

### Phase 1 Tables (Introspected - READ-ONLY)

These tables are owned by the Python ingestion service and managed via Alembic migrations. The Bun API **introspects** the schema using Drizzle Kit and generates TypeScript types.

**Introspection Command:**

```bash
cd services/bun-api
bun run drizzle-kit introspect:pg --out=src/db/schema
```

**Generated Output:** `src/db/schema/index.ts`

#### Tables Used by API:

| Table | Purpose | Access Pattern |
|-------|---------|----------------|
| `products` | Internal product catalog | Read (SELECT with filters, JOIN supplier_items) |
| `supplier_items` | Raw supplier data linked to products | Read + Write (UPDATE product_id for matching) |
| `suppliers` | External data sources | Read (SELECT for sync endpoint) |
| `categories` | Product classification | Read (SELECT for filters) |
| `price_history` | Time-series price tracking | Read (future analytics) |
| `parsing_logs` | Ingestion error logs | Read (admin diagnostics) |

---

### Phase 2 Tables (Managed Locally)

#### `users` Table

**Purpose:** Store user credentials and roles for JWT authentication

**Schema:**

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(50) NOT NULL CHECK (role IN ('sales', 'procurement', 'admin')),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for login performance
CREATE INDEX idx_users_username ON users(username);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
```

**Migration Script:** `services/bun-api/migrations/001_create_users.sql`

**Seed Data:**

```sql
-- Default admin user (password: admin123)
INSERT INTO users (username, password_hash, role) VALUES (
  'admin',
  '$2b$10$rXw8nQZ8aKd5z7X5J8Y5cO3Y7X5J8Y5cO3Y7X5J8Y5cO3Y7X5J8Y5u',
  'admin'
);

-- Sales user (password: sales123)
INSERT INTO users (username, password_hash, role) VALUES (
  'sales',
  '$2b$10$sXw8nQZ8aKd5z7X5J8Y5cO3Y7X5J8Y5cO3Y7X5J8Y5cO3Y7X5J8Y5v',
  'sales'
);

-- Procurement user (password: procurement123)
INSERT INTO users (username, password_hash, role) VALUES (
  'procurement',
  '$2b$10$tXw8nQZ8aKd5z7X5J8Y5cO3Y7X5J8Y5cO3Y7X5J8Y5cO3Y7X5J8Y5w',
  'procurement'
);
```

**Note:** Actual bcrypt hashes will be generated during deployment using:

```typescript
await Bun.password.hash(plainPassword, { algorithm: 'bcrypt', cost: 10 })
```

---

## Drizzle ORM Schema

### Directory Structure

```
services/bun-api/src/db/
├── schema/
│   ├── index.ts          # Exported schemas (auto-generated from introspection)
│   ├── products.ts       # Product table schema
│   ├── supplier_items.ts # Supplier items table schema
│   ├── suppliers.ts      # Suppliers table schema
│   ├── categories.ts     # Categories table schema
│   └── users.ts          # Users table schema (manual)
├── client.ts             # Database connection
└── repositories/         # Repository pattern implementations
    ├── product.repository.ts
    ├── supplier_item.repository.ts
    └── user.repository.ts
```

---

### Example Schema Definitions

#### `products` Table (Introspected)

```typescript
// src/db/schema/products.ts
import { pgTable, uuid, varchar, text, timestamp, pgEnum } from 'drizzle-orm/pg-core'

export const productStatusEnum = pgEnum('product_status', ['draft', 'active', 'archived'])

export const products = pgTable('products', {
  id: uuid('id').primaryKey().defaultRandom(),
  internal_sku: varchar('internal_sku', { length: 100 }).unique().notNull(),
  name: varchar('name', { length: 500 }).notNull(),
  category_id: uuid('category_id').references(() => categories.id),
  status: productStatusEnum('status').default('draft').notNull(),
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull()
})

// TypeScript type inference
export type Product = typeof products.$inferSelect
export type NewProduct = typeof products.$inferInsert
```

#### `supplier_items` Table (Introspected)

```typescript
// src/db/schema/supplier_items.ts
import { pgTable, uuid, varchar, decimal, jsonb, timestamp } from 'drizzle-orm/pg-core'

export const supplierItems = pgTable('supplier_items', {
  id: uuid('id').primaryKey().defaultRandom(),
  supplier_id: uuid('supplier_id').notNull().references(() => suppliers.id),
  product_id: uuid('product_id').references(() => products.id), // Nullable - manual matching
  supplier_sku: varchar('supplier_sku', { length: 255 }).notNull(),
  name: varchar('name', { length: 500 }).notNull(),
  price: decimal('price', { precision: 10, scale: 2 }).notNull(),
  characteristics: jsonb('characteristics'), // JSONB for flexible attributes
  last_ingested_at: timestamp('last_ingested_at').defaultNow().notNull(),
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull()
})

export type SupplierItem = typeof supplierItems.$inferSelect
export type NewSupplierItem = typeof supplierItems.$inferInsert
```

#### `users` Table (Manual Definition)

```typescript
// src/db/schema/users.ts
import { pgTable, uuid, varchar, timestamp } from 'drizzle-orm/pg-core'

export const userRoleEnum = pgEnum('user_role', ['sales', 'procurement', 'admin'])

export const users = pgTable('users', {
  id: uuid('id').primaryKey().defaultRandom(),
  username: varchar('username', { length: 255 }).unique().notNull(),
  password_hash: varchar('password_hash', { length: 255 }).notNull(),
  role: userRoleEnum('role').notNull(),
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull()
})

export type User = typeof users.$inferSelect
export type NewUser = typeof users.$inferInsert
```

---

## TypeBox Validation Schemas

### Auto-Generated from Drizzle

```typescript
// src/db/schema/validation.ts
import { createSelectSchema, createInsertSchema } from 'drizzle-typebox'
import { products, supplierItems, users } from './index'

// SELECT schemas (for responses)
export const ProductSelectSchema = createSelectSchema(products)
export const SupplierItemSelectSchema = createSelectSchema(supplierItems)
export const UserSelectSchema = createSelectSchema(users, {
  password_hash: false // Never expose password hash
})

// INSERT schemas (for requests)
export const ProductInsertSchema = createInsertSchema(products, {
  id: false,           // Auto-generated
  created_at: false,   // Auto-generated
  updated_at: false    // Auto-generated
})

export const SupplierItemUpdateSchema = createInsertSchema(supplierItems, {
  id: false,
  supplier_id: false,  // Cannot change supplier
  created_at: false,
  updated_at: false
})
```

---

## API Request/Response Types

### TypeScript DTOs

```typescript
// src/types/catalog.types.ts
import { Type, Static } from '@sinclair/typebox'

// Catalog Request
export const CatalogQuerySchema = Type.Object({
  category_id: Type.Optional(Type.String({ format: 'uuid' })),
  min_price: Type.Optional(Type.Number({ minimum: 0 })),
  max_price: Type.Optional(Type.Number({ minimum: 0 })),
  search: Type.Optional(Type.String({ minLength: 1 })),
  page: Type.Optional(Type.Integer({ minimum: 1, default: 1 })),
  limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 200, default: 50 }))
})

export type CatalogQuery = Static<typeof CatalogQuerySchema>

// Catalog Product Response
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

// Paginated Response
export const CatalogResponseSchema = Type.Object({
  total_count: Type.Integer({ minimum: 0 }),
  page: Type.Integer({ minimum: 1 }),
  limit: Type.Integer({ minimum: 1 }),
  data: Type.Array(CatalogProductSchema)
})

export type CatalogResponse = Static<typeof CatalogResponseSchema>
```

```typescript
// src/types/admin.types.ts
import { Type, Static } from '@sinclair/typebox'

// Admin Product (with supplier details)
export const SupplierItemDetailSchema = Type.Object({
  id: Type.String({ format: 'uuid' }),
  supplier_id: Type.String({ format: 'uuid' }),
  supplier_name: Type.String(),
  supplier_sku: Type.String(),
  current_price: Type.String(), // Decimal as string
  characteristics: Type.Record(Type.String(), Type.Any()), // JSONB
  last_ingested_at: Type.String({ format: 'date-time' })
})

export const AdminProductSchema = Type.Object({
  id: Type.String({ format: 'uuid' }),
  internal_sku: Type.String(),
  name: Type.String(),
  category_id: Type.Union([Type.String({ format: 'uuid' }), Type.Null()]),
  status: Type.Union([
    Type.Literal('draft'),
    Type.Literal('active'),
    Type.Literal('archived')
  ]),
  supplier_items: Type.Array(SupplierItemDetailSchema),
  margin_percentage: Type.Union([Type.Number(), Type.Null()])
})

export type AdminProduct = Static<typeof AdminProductSchema>

// Product Matching Request
export const MatchRequestSchema = Type.Object({
  action: Type.Union([Type.Literal('link'), Type.Literal('unlink')]),
  supplier_item_id: Type.String({ format: 'uuid' })
})

export type MatchRequest = Static<typeof MatchRequestSchema>

// Product Creation Request
export const CreateProductRequestSchema = Type.Object({
  internal_sku: Type.Optional(Type.String({ maxLength: 100 })),
  name: Type.String({ minLength: 1, maxLength: 500 }),
  category_id: Type.Optional(Type.String({ format: 'uuid' })),
  status: Type.Optional(Type.Union([Type.Literal('draft'), Type.Literal('active')])),
  supplier_item_id: Type.Optional(Type.String({ format: 'uuid' }))
})

export type CreateProductRequest = Static<typeof CreateProductRequestSchema>
```

```typescript
// src/types/auth.types.ts
import { Type, Static } from '@sinclair/typebox'

// Login Request
export const LoginRequestSchema = Type.Object({
  username: Type.String({ minLength: 3 }),
  password: Type.String({ minLength: 8 })
})

export type LoginRequest = Static<typeof LoginRequestSchema>

// Login Response
export const LoginResponseSchema = Type.Object({
  token: Type.String(),
  expires_at: Type.String({ format: 'date-time' }),
  user: Type.Object({
    id: Type.String({ format: 'uuid' }),
    username: Type.String(),
    role: Type.Union([
      Type.Literal('sales'),
      Type.Literal('procurement'),
      Type.Literal('admin')
    ])
  })
})

export type LoginResponse = Static<typeof LoginResponseSchema>

// JWT Payload
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

---

## Repository Pattern

### Interface Definitions

```typescript
// src/repositories/interfaces/product.repository.interface.ts
export interface IProductRepository {
  findActive(filters: CatalogQuery): Promise<CatalogProduct[]>
  findById(id: string): Promise<AdminProduct | null>
  findAll(filters: AdminQuery): Promise<AdminProduct[]>
  create(product: NewProduct): Promise<Product>
  updateStatus(id: string, status: ProductStatus): Promise<void>
}
```

### Implementation Example

```typescript
// src/repositories/product.repository.ts
import { eq, and, like, gte, lte, sql } from 'drizzle-orm'
import { db } from '../db/client'
import { products, supplierItems, suppliers } from '../db/schema'
import type { IProductRepository } from './interfaces/product.repository.interface'
import type { CatalogQuery, CatalogProduct } from '../types/catalog.types'

export class ProductRepository implements IProductRepository {
  async findActive(filters: CatalogQuery): Promise<CatalogProduct[]> {
    const { category_id, min_price, max_price, search, page = 1, limit = 50 } = filters
    const offset = (page - 1) * limit

    // Build WHERE clauses
    const conditions = [eq(products.status, 'active')]

    if (category_id) {
      conditions.push(eq(products.category_id, category_id))
    }

    if (search) {
      conditions.push(like(products.name, `%${search}%`))
    }

    // Query with aggregations
    const result = await db
      .select({
        id: products.id,
        internal_sku: products.internal_sku,
        name: products.name,
        category_id: products.category_id,
        min_price: sql<string>`COALESCE(MIN(${supplierItems.price}), '0')`,
        max_price: sql<string>`COALESCE(MAX(${supplierItems.price}), '0')`,
        supplier_count: sql<number>`COUNT(DISTINCT ${supplierItems.supplier_id})`
      })
      .from(products)
      .leftJoin(supplierItems, eq(products.id, supplierItems.product_id))
      .where(and(...conditions))
      .groupBy(products.id)
      .having(
        and(
          min_price ? gte(sql`MIN(${supplierItems.price})`, min_price.toString()) : undefined,
          max_price ? lte(sql`MIN(${supplierItems.price})`, max_price.toString()) : undefined
        )
      )
      .orderBy(products.name)
      .limit(limit)
      .offset(offset)

    return result
  }

  async findById(id: string): Promise<AdminProduct | null> {
    // Implementation with JOIN for supplier details
    // ...
  }
}
```

---

## Data Flow Diagrams

### Catalog Query Flow

```
User Request
    ↓
GET /api/v1/catalog?category_id=abc&min_price=10
    ↓
[CatalogController] → Validate query params with TypeBox
    ↓
[CatalogService] → Business logic (none for simple query)
    ↓
[ProductRepository] → Drizzle ORM query
    ↓
PostgreSQL: SELECT products JOIN supplier_items WHERE status='active'
    ↓
[ProductRepository] → Map results to CatalogProduct[]
    ↓
[CatalogController] → Serialize response with TypeBox
    ↓
User Response: { total_count: 42, page: 1, limit: 50, data: [...] }
```

### Product Matching Flow

```
User Request
    ↓
PATCH /api/v1/admin/products/:id/match
Body: { action: "link", supplier_item_id: "xyz" }
    ↓
[AuthMiddleware] → Verify JWT token
    ↓
[MatchController] → Validate request body with TypeBox
    ↓
[MatchService] → Business logic
    ├─→ Validate product exists and not archived
    ├─→ Validate supplier_item exists and not linked
    └─→ Check for conflicts
    ↓
[SupplierItemRepository] → UPDATE supplier_items SET product_id = :id WHERE id = :xyz
    ↓
PostgreSQL: Transaction (BEGIN → UPDATE → COMMIT)
    ↓
[ProductRepository] → Fetch updated product with supplier details
    ↓
User Response: { product: { id, internal_sku, name, supplier_items: [...] } }
```

---

## Database Indexes (Phase 1 - Already Exist)

```sql
-- Products
CREATE INDEX idx_products_status ON products(status);
CREATE INDEX idx_products_category_id ON products(category_id);
CREATE UNIQUE INDEX idx_products_internal_sku ON products(internal_sku);

-- Supplier Items
CREATE INDEX idx_supplier_items_product_id ON supplier_items(product_id);
CREATE INDEX idx_supplier_items_supplier_id ON supplier_items(supplier_id);
CREATE UNIQUE INDEX idx_supplier_items_supplier_sku ON supplier_items(supplier_id, supplier_sku);
CREATE INDEX idx_supplier_items_characteristics ON supplier_items USING GIN(characteristics);
```

---

## Migration Strategy

### Initial Setup

1. **Run Phase 1 migrations** (Python/Alembic) to create base schema
2. **Run Phase 2 migration** to create `users` table:

```bash
psql -U marketbel_user -d marketbel -f services/bun-api/migrations/001_create_users.sql
```

3. **Introspect schema** with Drizzle:

```bash
cd services/bun-api
bun run drizzle-kit introspect:pg
```

4. **Generate TypeScript types** from introspected schema
5. **Seed users** with default credentials

### Ongoing Maintenance

- **Phase 1 schema changes:** Re-run introspection after Python migrations
- **Phase 2 schema changes:** Create new SQL migration files, run manually
- **Schema validation:** Add CI check to ensure introspection matches database

---

## Type Safety Guarantees

### Compile-Time Checks

- ✅ Database queries type-checked via Drizzle
- ✅ API request/response schemas validated via TypeBox
- ✅ JWT payload types enforced
- ✅ Repository interfaces ensure consistent contracts

### Runtime Validation

- ✅ Request bodies validated before processing
- ✅ Query parameters validated against schemas
- ✅ Database results mapped to typed DTOs
- ✅ Error responses follow standard format

---

## Constitutional Alignment

| Principle | Implementation |
|-----------|----------------|
| **Single Responsibility** | Controllers (HTTP) → Services (logic) → Repositories (data) |
| **DRY** | Schema introspected once, TypeBox schemas generated from Drizzle |
| **Strong Typing** | End-to-end type safety: DB → ORM → API → Response |
| **Separation of Concerns** | Phase 1 owns base schema, Phase 2 owns auth schema |
| **Dependency Inversion** | Services depend on repository interfaces, not concrete implementations |

---

**Document Status:** Complete ✅

**Next Steps:** Define API contracts in `/contracts/`
