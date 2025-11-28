# Feature Plan: Unified Frontend Application

**Date:** 2025-11-29

**Status:** Draft

**Owner:** Development Team

---

## Overview

Build a responsive React web application that provides role-based access to the Marketbel product catalog. The application serves three distinct user types: public clients browsing the catalog, sales teams analyzing margins, and procurement teams managing supplier relationships. This frontend interfaces exclusively with the Bun API (Phase 2) and never directly accesses the database or Python worker service.

---

## Constitutional Compliance Check

This feature aligns with the following constitutional principles:

- **Single Responsibility Principle (SOLID-S):** Each React component handles one specific UI concern. Public catalog components are separate from admin components. Routing, data fetching, and state management are handled by dedicated layers (React Router, TanStack Query, React Context).

- **Open/Closed Principle (SOLID-O):** Component architecture uses composition and props for extensibility. Shared UI components (Button, Input, DataTable) can be styled and extended without modification. API client abstraction allows switching between fetch implementations without changing consuming code.

- **Liskov Substitution Principle (SOLID-L):** All API hooks follow consistent interfaces (return `{ data, isLoading, error }`). Component props use discriminated unions for polymorphic behavior. Mock implementations for testing honor production contracts.

- **Interface Segregation Principle (SOLID-I):** Components receive only the props they need. API hooks expose focused capabilities (useCatalog, useProduct, useMatchSupplier) rather than monolithic data access. Layouts provide specific navigation based on role.

- **Dependency Inversion Principle (SOLID-D):** Components depend on hooks (abstractions) not API client (implementation). Business logic in custom hooks, not components. TanStack Query abstracts data fetching implementation details.

- **KISS (Keep It Simple):** No Redux or complex state management. TanStack Query handles server state, React Context for simple app state (cart, auth). Standard React patterns without over-abstraction. Client-side filtering for small datasets, server-side when needed.

- **DRY (Don't Repeat Yourself):** Shared UI components reused across all routes. API types auto-generated from OpenAPI spec (single source of truth). Tailwind CSS theme configuration in one `@theme` block. Common layouts prevent navigation duplication.

- **Separation of Concerns:** Frontend handles presentation only. All business logic in Bun API (Phase 2). No direct database access. Clear separation between public routes (catalog) and admin routes (sales/procurement).

- **Strong Typing:** TypeScript strict mode enabled. API types auto-generated from Bun API OpenAPI spec. All component props typed. TanStack Query hooks use generics for type safety. No `any` types without justification.

- **Design System Consistency:** All UI components follow atomic design (atoms → molecules → organisms). Tailwind CSS v4.1 CSS-first configuration. No arbitrary styling. Accessibility (a11y) via semantic HTML and ARIA labels.

- **Tailwind CSS v4.1 Requirements:** CSS-first configuration with `@import "tailwindcss"`. Theme customization via `@theme` blocks. Native `@tailwindcss/vite` plugin. NO `tailwind.config.js` file.

**Violations/Exceptions:** None. This feature fully adheres to all constitutional principles.

---

## Goals

- [x] Public catalog accessible without authentication (browse, filter, search)
- [x] Shopping cart and checkout mock for demonstration
- [x] Role-based routing with JWT authentication for admin routes
- [x] Internal catalog for sales team (margins, supplier comparison)
- [x] Supplier matching interface for procurement team
- [x] Full TypeScript type safety with auto-generated API client
- [x] TanStack Query for efficient server state management
- [x] Tailwind CSS v4.1 CSS-first responsive design
- [x] Accessibility (WCAG 2.1 Level AA compliance)
- [x] Performance targets (< 3s initial load, < 2s catalog render)

---

## Non-Goals

Explicitly list what this feature will NOT accomplish to maintain scope discipline.

- Payment processing (deferred to Phase 4+)
- User registration UI (deferred to Phase 4+)
- Advanced analytics dashboards (deferred to Phase 4+)
- Real-time inventory via WebSockets (deferred to Phase 4+)
- Multi-language internationalization (deferred to Phase 4+)
- PDF export or bulk operations (deferred to Phase 4+)
- Mobile native applications (web-only)
- Server-side rendering or static site generation (client-side only)

---

## Success Metrics

How will we measure success?

- **Initial Load Time:** < 3 seconds on 3G connection (Lighthouse score > 80)
- **Catalog Render Time:** < 2 seconds for 100 products with filters
- **Filter Response Time:** < 500ms from input to UI update
- **Product Detail Navigation:** < 1 second to load and render
- **Match/Unmatch Operations:** < 1 second round-trip with optimistic updates
- **Bundle Size:** < 200KB gzipped for initial route
- **Test Coverage:** ≥ 80% for components and hooks
- **Accessibility Score:** 100% WCAG 2.1 Level AA compliance
- **Browser Support:** Latest 2 versions of Chrome, Firefox, Safari, Edge
- **Concurrent Users:** Support 1,000 concurrent users on public catalog

---

## User Stories

### Story 1: Public Catalog Browsing

**As a** public client (unauthenticated user)
**I want** to browse the product catalog, filter by category and price, and search for specific items
**So that** I can find products I'm interested in purchasing

**Acceptance Criteria:**

- [x] Catalog displays products in responsive grid layout
- [x] Filter by category (dropdown), price range (min/max inputs), and search (debounced)
- [x] Clicking product navigates to detail view with full information
- [x] No authentication required for catalog access
- [x] Filters preserved in URL for shareable links
- [x] Mobile-responsive design (< 640px single column, 640-1024px two columns, > 1024px three columns)

### Story 2: Shopping Cart Mock

**As a** public client
**I want** to add products to a cart and proceed through a mock checkout
**So that** I can simulate the purchasing experience

**Acceptance Criteria:**

- [x] "Add to Cart" button on catalog and product detail pages
- [x] Cart icon shows item count badge
- [x] Cart page displays items with quantity controls (+/-)
- [x] Checkout form collects shipping/billing (display-only, no validation)
- [x] "Place Order" shows success message (no backend submission)
- [x] Cart state persists in localStorage

### Story 3: Sales Internal Catalog

**As a** sales team member
**I want** to view products with margins and supplier comparisons
**So that** I can make informed pricing and sourcing decisions

**Acceptance Criteria:**

- [x] `/admin/sales` route requires JWT authentication
- [x] Table shows: name, SKU, selling price, cost price, margin %, category
- [x] Margin calculated as `((selling_price - cost_price) / selling_price) * 100`
- [x] Sortable by any column
- [x] Filters: category, margin range, status (draft/active/archived)
- [x] Clicking product opens detail with supplier items and price history

### Story 4: Procurement Supplier Matching

**As a** procurement team member
**I want** to link supplier items to internal products and manage those associations
**So that** I can maintain accurate product-supplier mappings

**Acceptance Criteria:**

- [x] `/admin/procurement` route requires JWT authentication
- [x] Displays unmatched supplier items in table
- [x] "Link to Product" opens search modal with fuzzy matching
- [x] Selecting product sends `PATCH /admin/products/:id/match` request
- [x] Successful match updates UI optimistically and shows notification
- [x] Matched items section shows product ↔ supplier item associations
- [x] "Unlink" button removes association
- [x] All operations complete within 1 second

---

## Technical Approach

### Architecture

**Frontend Service (React + Vite + Bun):**

- **Responsibilities:**
  - Render UI components based on user role
  - Fetch data from Bun API via TanStack Query
  - Manage client-side state (cart, filters, UI state)
  - Handle JWT authentication and route protection
  - Provide responsive, accessible user interface

- **Technology Stack:**
  - Build Tool: Vite 5+ with Bun runtime
  - Framework: React 18+ with TypeScript (strict mode)
  - Routing: React Router v6 (client-side routing)
  - Data Fetching: TanStack Query v5 (server state)
  - State Management: React Context (auth, cart)
  - Styling: Tailwind CSS v4.1 (CSS-first configuration)
  - UI Components: Headless UI or Radix UI + Tailwind (**NEEDS RESEARCH**)
  - Tables: TanStack Table v8 for procurement view
  - API Client: openapi-fetch with types from openapi-typescript (**NEEDS RESEARCH: vs elysia/eden**)

- **Endpoints Consumed:**
  - `GET /catalog` - Public product list with filters
  - `GET /catalog/:id` - Product detail (public)
  - `POST /auth/login` - JWT authentication
  - `GET /admin/products` - Internal catalog (sales)
  - `GET /admin/products/:id` - Product detail (admin)
  - `PATCH /admin/products/:id/match` - Link/unlink supplier items
  - `POST /admin/sync` - Trigger parsing job (optional)

- **Data Flow:**
  ```
  [User Browser] → [React Components] → [TanStack Query Hooks] → [API Client]
                                                                         ↓
                                                                   [Bun API (Phase 2)]
  ```

**Bun API (Phase 2 - Already Implemented):**

- Provides RESTful endpoints for catalog, admin, and auth
- Returns JSON responses with TypeScript-defined schemas
- Validates requests with TypeBox
- Handles JWT authentication and authorization
- Publishes sync jobs to Redis queue (consumed by Python worker)

**No Direct Backend Communication:**

- Frontend NEVER accesses PostgreSQL directly
- Frontend NEVER communicates with Python worker
- Frontend NEVER accesses Redis queue
- All data flows through Bun API exclusively

### Design System

- [x] **Will consult** `mcp 21st-dev/magic` for UI component inspiration during implementation
- [x] **Will collect** documentation via `mcp context7` for:
  - React Router v6 best practices
  - TanStack Query v5 patterns
  - TanStack Table v8 setup
  - Headless UI or Radix UI component library
  - Tailwind CSS v4.1 CSS-first configuration
  - openapi-typescript or elysia/eden for type generation

- [x] **Tailwind v4.1 CSS-first approach confirmed:**
  - NO `tailwind.config.js` file
  - Use `@import "tailwindcss";` in CSS
  - Use `@theme` blocks for customization
  - Use `@tailwindcss/vite` plugin

### Algorithm Choice

Following KISS principle, no complex algorithms needed in frontend:

- **Filtering:** Simple array filter/reduce for client-side (< 500 items), server-side for larger datasets
- **Search:** Debounced input (300ms) with server-side search via API
- **Sorting:** Native JavaScript sort with comparison functions
- **No ML/AI:** All matching logic handled by backend

### Data Flow

**Public Catalog Flow:**
```
[User] → [CatalogPage] → [useCatalog hook] → [GET /catalog?filters] → [Bun API]
                                                                             ↓
                                                                       [PostgreSQL]
                                                                             ↓
                                                                    [JSON Response]
                                                                             ↓
                                                            [TanStack Query Cache]
                                                                             ↓
                                                                  [ProductGrid Component]
```

**Admin Matching Flow:**
```
[Procurement User] → [MatchingInterface] → [useMatchSupplier hook] → [PATCH /admin/products/:id/match] → [Bun API]
                                                                                                               ↓
                                                                                                         [PostgreSQL Update]
                                                                                                               ↓
                                                                                                          [Success Response]
                                                                                                               ↓
                                                                                              [Optimistic UI Update + Cache Invalidation]
```

**Cart Flow (Frontend-Only):**
```
[User] → [Add to Cart] → [CartContext.dispatch] → [localStorage.setItem] → [Cart State Updated]
                                                                                    ↓
                                                                          [CartItem Component Re-renders]
```

---

## Type Safety

### TypeScript Configuration

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

### Auto-Generated API Types

```bash
# Generate types from Bun API OpenAPI spec
bunx openapi-typescript http://localhost:3000/docs/json -o src/types/api.ts
```

```typescript
// src/types/api.ts (generated)
export interface paths {
  "/catalog": {
    get: {
      parameters: {
        query?: {
          category?: string
          minPrice?: number
          maxPrice?: number
          search?: string
        }
      }
      responses: {
        200: {
          content: {
            "application/json": Product[]
          }
        }
      }
    }
  }
  // ... other endpoints
}

export interface Product {
  id: string
  name: string
  sku: string
  description: string | null
  price: number
  category_id: string
  status: "draft" | "active" | "archived"
  characteristics: Record<string, unknown>
  created_at: string
  updated_at: string
}
```

### Frontend-Only Types

```typescript
// src/types/cart.ts
export interface CartItem {
  productId: string
  name: string
  price: number
  quantity: number
  image?: string
}

export interface Cart {
  items: CartItem[]
  subtotal: number
  tax: number
  total: number
}

// src/types/filters.ts
export interface CatalogFilters {
  category?: string
  minPrice?: number
  maxPrice?: number
  search?: string
}

// src/types/auth.ts
export interface User {
  id: string
  username: string
  role: "sales" | "procurement" | "admin"
}

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
}
```

### Component Props Types

```typescript
// src/components/catalog/ProductCard.tsx
interface ProductCardProps {
  product: Product
  onAddToCart?: (productId: string) => void
  showAdminControls?: boolean
}

export function ProductCard({ product, onAddToCart, showAdminControls = false }: ProductCardProps) {
  // Implementation
}
```

---

## Testing Strategy

### Unit Tests (Vitest + React Testing Library)

**Components:**
- Test rendering with different props and states
- Test user interactions (clicks, form inputs)
- Test conditional rendering based on auth/role
- Mock TanStack Query hooks with predefined data

**Hooks:**
- Test custom hooks (`useAuth`, `useCatalog`, `useCart`)
- Mock API client responses
- Verify cache invalidation logic
- Test error handling and retry logic

**Example:**
```typescript
// src/hooks/useCatalog.test.ts
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useCatalog } from './useCatalog'

const wrapper = ({ children }) => (
  <QueryClientProvider client={new QueryClient()}>
    {children}
  </QueryClientProvider>
)

test('useCatalog fetches and caches data', async () => {
  const { result } = renderHook(() => useCatalog({}), { wrapper })

  expect(result.current.isLoading).toBe(true)

  await waitFor(() => expect(result.current.isSuccess).toBe(true))

  expect(result.current.data).toHaveLength(10)
})
```

### Integration Tests

**Route Testing:**
- Test navigation between public and admin routes
- Test protected route redirects for unauthenticated users
- Test URL query parameter handling for filters

**API Integration (MSW Mocks):**
- Mock API responses with Mock Service Worker
- Test request/response transformations
- Test error scenarios (network failures, 4xx/5xx responses)

### E2E Tests (Playwright - Optional for Phase 3)

**User Flows:**
- Public user: browse catalog → apply filters → view product → add to cart → checkout mock
- Sales user: login → view internal catalog → sort by margin → view product detail
- Procurement user: login → view unmatched items → search product → link supplier item

**Coverage Target:** ≥80% for components and hooks

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Bun API (Phase 2) not fully implemented | High | Low | Verify Phase 2 completion before starting. Use MSW mocks for parallel development. |
| OpenAPI spec out of sync with actual API | Medium | Medium | Auto-generate types in CI/CD. Document manual regeneration process. |
| Tailwind v4.1 CSS-first configuration issues | Medium | Low | Research documentation via `mcp context7` before implementation. Test CSS compilation early. |
| Performance degradation with large product catalogs | Medium | Medium | Implement pagination and virtual scrolling early. Test with 10,000+ products. |
| Authentication token expiration handling | Medium | Medium | Implement token refresh logic. Show clear error messages and redirect to login. |
| Browser compatibility issues | Low | Low | Use Vite's default browser targets (ES2020). Test on latest 2 versions of major browsers. |
| Accessibility violations | Medium | Low | Use semantic HTML and ARIA labels from start. Run Lighthouse audits regularly. |

---

## Dependencies

### Bun Packages (package.json)

```json
{
  "name": "marketbel-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "lint": "eslint . --ext ts,tsx",
    "type-check": "tsc --noEmit",
    "generate-api-types": "bunx openapi-typescript http://localhost:3000/docs/json -o src/types/api.ts"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.20.0",
    "@tanstack/react-query": "^5.17.0",
    "@tanstack/react-table": "^8.11.0",
    "@headlessui/react": "^1.7.17",
    "openapi-fetch": "^0.9.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.2.1",
    "@tailwindcss/vite": "^4.1.0",
    "tailwindcss": "^4.1.0",
    "typescript": "^5.3.3",
    "vite": "^5.0.8",
    "vitest": "^1.1.0",
    "@testing-library/react": "^14.1.2",
    "@testing-library/user-event": "^14.5.1",
    "openapi-typescript": "^6.7.3",
    "eslint": "^8.55.0",
    "@typescript-eslint/eslint-plugin": "^6.15.0",
    "@typescript-eslint/parser": "^6.15.0"
  }
}
```

**NOTE:** Final choice between Headless UI and Radix UI requires research (see Phase 0).

### External Services

- **Bun API (Phase 2):** Running on `http://localhost:3000` in development
- **OpenAPI Documentation:** Available at `http://localhost:3000/docs`

### Infrastructure

**Environment Variables:**

```bash
# .env.development
VITE_API_URL=http://localhost:3000
VITE_ENV=development

# .env.production
VITE_API_URL=https://api.marketbel.com
VITE_ENV=production
```

**Docker (Optional for Development):**

```dockerfile
# Dockerfile (multi-stage build)
FROM oven/bun:1 AS builder
WORKDIR /app
COPY package.json bun.lockb ./
RUN bun install
COPY . .
RUN bun run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

## Timeline

**Note:** Avoid absolute dates. Break into phases with relative durations.

| Phase | Tasks | Estimated Effort |
|-------|-------|------------------|
| **Phase 0: Research** | Research Headless UI vs Radix UI, TanStack Table v8 setup, API type generation (eden vs openapi-typescript), Tailwind v4.1 configuration | 1-2 days |
| **Phase 1: Project Setup** | Scaffold Vite project, configure Tailwind v4.1, set up TypeScript, install dependencies, generate API types | 1 day |
| **Phase 2: Routing & Auth** | Implement React Router, protected routes, login page, JWT token management, auth context | 2 days |
| **Phase 3: Public Catalog** | Catalog page, product grid, filters, search, product detail, responsive design | 3 days |
| **Phase 4: Shopping Cart Mock** | Cart context, cart page, checkout form, localStorage persistence | 1-2 days |
| **Phase 5: Admin - Sales** | Sales catalog page, TanStack Table setup, margin calculations, supplier comparison | 2-3 days |
| **Phase 6: Admin - Procurement** | Procurement matching interface, search modal, match/unmatch actions, optimistic updates | 2-3 days |
| **Phase 7: Shared UI Components** | Button, Input, DataTable, Loading/Error states, accessibility refinements | 2 days |
| **Phase 8: Testing** | Unit tests for components and hooks, integration tests, E2E tests (optional) | 2-3 days |
| **Phase 9: Documentation & Deployment** | README, deployment guide, Docker configuration, production build | 1 day |

**Total Estimated Effort:** 17-22 days (individual developer time, not calendar time)

---

## Open Questions

**Resolved via Research (Phase 0):**

- [ ] **Headless UI vs Radix UI:** Which component library provides better TypeScript support and accessibility for our use case?
- [ ] **API Type Generation:** Should we use `elysia/eden` for end-to-end type safety with ElysiaJS, or `openapi-typescript` for broader OpenAPI compatibility?
- [ ] **TanStack Table v8:** What's the recommended setup for server-side sorting/filtering? Do we need virtualization for large datasets?
- [ ] **Tailwind v4.1 Migration:** Are there any gotchas migrating from v3 patterns? How do `@theme` blocks work in practice?
- [ ] **Token Refresh Strategy:** Should we implement silent token refresh, or redirect to login on expiration?

**To Be Clarified with Product/Stakeholders:**

- [ ] **Cart Persistence:** Should cart data sync across devices (requires backend), or remain local-only?
- [ ] **Error Reporting:** Do we need client-side error logging (e.g., Sentry integration)?
- [ ] **Feature Flags:** Do we need gradual rollout capabilities (e.g., LaunchDarkly)?

---

## References

**Phase 2 Specifications:**
- [Phase 2 Spec - Bun API Layer](../002-api-layer/spec.md)
- [Phase 2 Plan - API Implementation](../002-api-layer/plan.md)

**Phase 1 Specifications:**
- [Phase 1 Spec - Data Ingestion Infrastructure](../001-data-ingestion-infra/spec.md)

**External Documentation (To Be Collected via mcp context7):**
- [React Router v6 Documentation](https://reactrouter.com/)
- [TanStack Query v5 Documentation](https://tanstack.com/query/latest)
- [TanStack Table v8 Documentation](https://tanstack.com/table/latest)
- [Tailwind CSS v4 Documentation](https://tailwindcss.com/docs)
- [Headless UI Documentation](https://headlessui.com/)
- [Radix UI Documentation](https://www.radix-ui.com/)
- [openapi-typescript Documentation](https://github.com/drwpow/openapi-typescript)
- [Elysia Eden Documentation](https://elysiajs.com/eden/overview.html)
- [Vite Documentation](https://vitejs.dev/)

---

**Approval Signatures:**

- [ ] Technical Lead
- [ ] Product Owner
- [ ] Architecture Review

---

**Next Steps:**

1. ✅ Plan.md created with Technical Context and Constitution Check
2. ⏭️ Execute Phase 0: Generate research.md to resolve open questions
3. ⏭️ Execute Phase 1: Generate data-model.md and contracts
4. ⏭️ Update agent context with new technologies
5. ⏭️ Re-evaluate Constitution Check post-design
