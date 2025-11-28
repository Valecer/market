# Feature Specification: Unified Frontend Application

**Version:** 1.0.0

**Last Updated:** 2025-11-29

**Status:** Draft

---

## Constitutional Alignment

**Relevant Principles:**

- **Single Responsibility:** Each React component handles one specific UI concern (catalog display, filtering, authentication, etc.). Routes are organized by user role with clear boundaries.
- **Separation of Concerns:** Frontend handles presentation and user interaction only. All business logic resides in the Bun API service (Phase 2). Data fetching is abstracted through TanStack Query hooks.
- **Strong Typing:** Full TypeScript strict mode with types auto-generated from OpenAPI specification. No runtime type errors through compile-time validation.
- **KISS:** Use standard React patterns with minimal abstraction. Tailwind CSS for styling without complex CSS-in-JS. Client-side routing with React Router. TanStack Query for server state (industry standard, proven solution).
- **DRY:** Shared UI components (ProductCard, FilterBar, DataTable) reused across roles. API client generated once from OpenAPI spec. Common layouts and navigation components prevent duplication.

**Compliance Statement:**

This specification adheres to all constitutional principles. Any deviations are documented in the Exceptions section below.

---

## Overview

### Purpose

Build a responsive web application that provides role-based access to the Marketbel product catalog, enabling public clients to browse products, sales teams to analyze margins, and procurement teams to manage supplier relationships.

### Scope

**In Scope:**

- Public catalog interface with product browsing, filtering, and search
- Shopping cart and checkout mock (display-only, no payment processing)
- Role-based routing for Client, Sales, and Procurement user types
- Internal catalog view showing product margins and supplier comparisons
- Supplier item matching interface for linking external SKUs to internal products
- TypeScript client auto-generation from Swagger/OpenAPI specification
- Responsive design supporting mobile, tablet, and desktop viewports
- TanStack Query integration for server state management and caching
- Tailwind CSS v4.1 with CSS-first configuration (no tailwind.config.js)
- JWT-based authentication flow with token storage and refresh

**Out of Scope:**

- Actual payment processing (Phase 4+)
- User registration and account management UI (Phase 4+)
- Advanced analytics dashboards (Phase 4+)
- Real-time inventory updates via WebSockets (Phase 4+)
- Multi-language internationalization (Phase 4+)
- PDF export of product catalogs (Phase 4+)
- Bulk import/export functionality (Phase 4+)
- Mobile native applications (web-only for Phase 3)

---

## Functional Requirements

### FR-1: Public Catalog Access

**Priority:** Critical

**Description:**

Public users (clients) can browse the product catalog without authentication, view product details, and explore available items with rich filtering and search capabilities.

**Acceptance Criteria:**

- [ ] AC-1.1: Catalog displays products in a responsive grid/table layout
- [ ] AC-1.2: Each product shows name, price, category, image (if available), and basic characteristics
- [ ] AC-1.3: Users can filter by category, price range (min/max), and search by product name/SKU
- [ ] AC-1.4: Clicking a product opens a detailed view with all characteristics and supplier information
- [ ] AC-1.5: Catalog loads and displays within 2 seconds on broadband connection
- [ ] AC-1.6: No authentication required for catalog access (public route)

**Dependencies:**

- Phase 2 Bun API `/catalog` endpoint
- Product and Category data from Phase 1 database

### FR-2: Role-Based Routing

**Priority:** Critical

**Description:**

Application enforces access control through route-based authentication, redirecting unauthorized users and providing role-specific navigation menus.

**Acceptance Criteria:**

- [ ] AC-2.1: Public route `/` accessible without authentication (Client Store)
- [ ] AC-2.2: Admin routes `/admin/sales` and `/admin/procurement` require JWT authentication
- [ ] AC-2.3: Unauthenticated users redirected to login when accessing protected routes
- [ ] AC-2.4: Navigation menu adapts based on user role (shows only authorized sections)
- [ ] AC-2.5: JWT token stored securely (httpOnly cookie or secure localStorage with CSRF protection)
- [ ] AC-2.6: Token automatically included in API requests via Authorization header

**Dependencies:**

- Phase 2 Bun API `/auth/login` endpoint
- JWT token validation middleware in Bun API

### FR-3: Product Filtering and Search

**Priority:** High

**Description:**

Users can refine catalog results using multiple filter criteria and free-text search, with filters applied client-side or server-side based on dataset size.

**Acceptance Criteria:**

- [ ] AC-3.1: Category filter displays all available categories from database
- [ ] AC-3.2: Price range filter accepts min and max values (numeric input or slider)
- [ ] AC-3.3: Search input filters by product name, SKU, or description (debounced, 300ms delay)
- [ ] AC-3.4: Multiple filters combine with AND logic (all conditions must match)
- [ ] AC-3.5: Filter state preserved in URL query parameters (shareable links)
- [ ] AC-3.6: "Clear Filters" button resets all filters to default state
- [ ] AC-3.7: Filter results update within 500ms of user input

**Dependencies:**

- Phase 2 Bun API `/catalog` endpoint with query parameters
- Category data from Phase 1 database

### FR-4: Product Detail View

**Priority:** High

**Description:**

Detailed product page displays comprehensive information including characteristics, pricing history, and supplier comparisons (visible to appropriate roles).

**Acceptance Criteria:**

- [ ] AC-4.1: Product detail shows all fields: name, SKU, description, price, category, status
- [ ] AC-4.2: Dynamic characteristics (JSONB data) rendered as key-value pairs
- [ ] AC-4.3: Sales role sees calculated margin percentage and supplier comparison table
- [ ] AC-4.4: Supplier comparison shows all linked supplier items with prices and sources
- [ ] AC-4.5: Detail view loads within 1 second of navigation
- [ ] AC-4.6: Mobile layout stacks information vertically, desktop uses multi-column layout

**Dependencies:**

- Phase 2 Bun API `/catalog/:id` or `/admin/products/:id` endpoints
- Product, SupplierItem, and PriceHistory data from Phase 1 database

### FR-5: Shopping Cart and Checkout Mock

**Priority:** Medium

**Description:**

Public users can add products to a shopping cart and proceed through a mock checkout flow for demonstration purposes (no actual order creation or payment).

**Acceptance Criteria:**

- [ ] AC-5.1: "Add to Cart" button visible on catalog and product detail pages
- [ ] AC-5.2: Cart icon in header shows item count badge
- [ ] AC-5.3: Cart page displays all added items with quantity controls (+/- buttons)
- [ ] AC-5.4: Cart calculates and displays subtotal, tax estimate, and total (mock calculations)
- [ ] AC-5.5: "Proceed to Checkout" button navigates to mock checkout form
- [ ] AC-5.6: Checkout form collects shipping/billing information (no validation, display-only)
- [ ] AC-5.7: "Place Order" button shows success message without backend submission
- [ ] AC-5.8: Cart state persists in localStorage across page refreshes

**Dependencies:**

- None (frontend-only feature, no backend integration)

### FR-6: Internal Catalog for Sales Role

**Priority:** High

**Description:**

Sales users access an internal catalog view that displays product margins, cost analysis, and multi-supplier pricing for strategic decision-making.

**Acceptance Criteria:**

- [ ] AC-6.1: `/admin/sales` route displays all products with internal pricing data
- [ ] AC-6.2: Each product row shows: name, SKU, selling price, cost price, margin %, category
- [ ] AC-6.3: Margin percentage calculated as `((selling_price - cost_price) / selling_price) * 100`
- [ ] AC-6.4: Cost price derived from lowest-priced supplier item linked to product
- [ ] AC-6.5: Table sortable by any column (name, price, margin, etc.)
- [ ] AC-6.6: Filters include: category, margin range (min/max %), status (draft/active/archived)
- [ ] AC-6.7: Clicking product opens detail view with all supplier items and historical pricing

**Dependencies:**

- Phase 2 Bun API `/admin/products` endpoint
- Product and SupplierItem data with pricing information

### FR-7: Supplier Matching Interface for Procurement

**Priority:** High

**Description:**

Procurement users can link supplier items to internal products (SKU matching) and unlink existing associations through an intuitive interface.

**Acceptance Criteria:**

- [ ] AC-7.1: `/admin/procurement` route displays unmatched supplier items in a table
- [ ] AC-7.2: Each supplier item shows: supplier name, supplier SKU, name, price, characteristics
- [ ] AC-7.3: "Link to Product" button opens a search modal to find internal products
- [ ] AC-7.4: Product search supports fuzzy matching on name and SKU
- [ ] AC-7.5: Selecting product sends `PATCH /admin/products/:id/match` request with supplier item ID
- [ ] AC-7.6: Successful match removes item from unmatched list and shows success notification
- [ ] AC-7.7: Matched items section displays product ↔ supplier item associations
- [ ] AC-7.8: "Unlink" button sends PATCH request to remove association
- [ ] AC-7.9: Match/unmatch actions complete within 1 second with optimistic UI updates

**Dependencies:**

- Phase 2 Bun API `PATCH /admin/products/:id/match` endpoint
- SupplierItem and Product data from Phase 1 database

### FR-8: TypeScript Type Safety

**Priority:** Critical

**Description:**

All API interactions, component props, and application state use TypeScript types auto-generated from the Bun API OpenAPI specification.

**Acceptance Criteria:**

- [ ] AC-8.1: TypeScript client generated from Swagger/OpenAPI spec using `openapi-typescript` or similar tool
- [ ] AC-8.2: All API request/response types imported from generated client
- [ ] AC-8.3: React component props defined with TypeScript interfaces
- [ ] AC-8.4: TanStack Query hooks use generic types for request/response data
- [ ] AC-8.5: No `any` types in codebase (except explicit `@ts-expect-error` with justification)
- [ ] AC-8.6: TypeScript strict mode enabled (`strict: true` in tsconfig.json)
- [ ] AC-8.7: Build fails on type errors (no runtime type surprises)

**Dependencies:**

- Phase 2 Bun API with Swagger documentation at `/docs` endpoint

### FR-9: Data Fetching and Caching

**Priority:** High

**Description:**

Application uses TanStack Query for efficient server state management with automatic caching, background refetching, and optimistic updates.

**Acceptance Criteria:**

- [ ] AC-9.1: All API calls wrapped in TanStack Query hooks (`useQuery`, `useMutation`)
- [ ] AC-9.2: Catalog data cached for 5 minutes with stale-while-revalidate pattern
- [ ] AC-9.3: Product detail data cached per product ID with automatic invalidation
- [ ] AC-9.4: Mutations (match/unmatch) trigger cache invalidation for affected queries
- [ ] AC-9.5: Loading states displayed during data fetching (spinners, skeletons)
- [ ] AC-9.6: Error states show user-friendly messages with retry option
- [ ] AC-9.7: Optimistic updates for match/unmatch actions (instant UI feedback)
- [ ] AC-9.8: Background refetching when user refocuses browser tab

**Dependencies:**

- Phase 2 Bun API endpoints with consistent response formats

---

## Technical Requirements

### TR-1: Project Setup and Build Configuration

**React + Vite Configuration:**

- Package manager: Bun (latest version)
- Framework: React 18+ with TypeScript
- Build tool: Vite 5+ with `@vitejs/plugin-react`
- Development server: Vite dev server with HMR (Hot Module Replacement)

**Tailwind CSS v4.1 Setup:**

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:3000' // Proxy API calls to Bun backend
    }
  }
})
```

```css
/* src/index.css - CSS-first Tailwind configuration */
@import "tailwindcss";

@theme {
  --color-primary: #3b82f6;
  --color-secondary: #8b5cf6;
  --color-success: #10b981;
  --color-danger: #ef4444;
  --font-sans: 'Inter', system-ui, sans-serif;
  --breakpoint-sm: 640px;
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
  --breakpoint-xl: 1280px;
}
```

**Dependencies:**

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.20.0",
    "@tanstack/react-query": "^5.17.0",
    "openapi-fetch": "^0.9.0",
    "openapi-typescript": "^6.7.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.2.0",
    "@tailwindcss/vite": "^4.1.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0"
  }
}
```

### TR-2: Routing Architecture

**React Router Configuration:**

```typescript
// src/routes.tsx
import { createBrowserRouter } from 'react-router-dom'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <PublicLayout />,
    children: [
      { index: true, element: <CatalogPage /> },
      { path: 'products/:id', element: <ProductDetailPage /> },
      { path: 'cart', element: <CartPage /> },
      { path: 'checkout', element: <CheckoutMockPage /> }
    ]
  },
  {
    path: '/admin',
    element: <ProtectedLayout />, // Checks JWT authentication
    children: [
      { path: 'sales', element: <SalesCatalogPage /> },
      { path: 'procurement', element: <ProcurementMatchingPage /> },
      { path: 'products/:id', element: <InternalProductDetailPage /> }
    ]
  },
  {
    path: '/login',
    element: <LoginPage />
  }
])
```

**Protected Route Component:**

```typescript
// src/components/ProtectedLayout.tsx
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export function ProtectedLayout() {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
```

### TR-3: API Client Generation

**OpenAPI TypeScript Client:**

```bash
# Generate types from Swagger spec
bunx openapi-typescript http://localhost:3000/docs/json -o src/types/api.ts
```

```typescript
// src/lib/api-client.ts
import createClient from 'openapi-fetch'
import type { paths } from '@/types/api'

export const apiClient = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:3000'
})

// Automatically inject JWT token
apiClient.use({
  onRequest: (req) => {
    const token = localStorage.getItem('jwt_token')
    if (token) {
      req.headers.set('Authorization', `Bearer ${token}`)
    }
  }
})
```

### TR-4: TanStack Query Setup

**Query Provider Configuration:**

```typescript
// src/main.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
      retry: 1,
      refetchOnWindowFocus: true
    }
  }
})

root.render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
)
```

**Example Query Hook:**

```typescript
// src/hooks/useCatalog.ts
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

interface CatalogFilters {
  category?: string
  minPrice?: number
  maxPrice?: number
  search?: string
}

export function useCatalog(filters: CatalogFilters) {
  return useQuery({
    queryKey: ['catalog', filters],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/catalog', {
        params: { query: filters }
      })
      if (error) throw error
      return data
    }
  })
}
```

### TR-5: Component Architecture

**Feature-Based Structure:**

```
src/
├── components/
│   ├── catalog/
│   │   ├── ProductCard.tsx
│   │   ├── ProductGrid.tsx
│   │   ├── FilterBar.tsx
│   │   └── SearchInput.tsx
│   ├── admin/
│   │   ├── SalesTable.tsx
│   │   ├── MatchingInterface.tsx
│   │   └── ProductSearchModal.tsx
│   ├── cart/
│   │   ├── CartItem.tsx
│   │   ├── CartSummary.tsx
│   │   └── CheckoutForm.tsx
│   └── shared/
│       ├── Header.tsx
│       ├── Navigation.tsx
│       ├── Button.tsx
│       ├── Input.tsx
│       └── DataTable.tsx
├── pages/
│   ├── CatalogPage.tsx
│   ├── ProductDetailPage.tsx
│   ├── SalesCatalogPage.tsx
│   ├── ProcurementMatchingPage.tsx
│   └── LoginPage.tsx
├── hooks/
│   ├── useCatalog.ts
│   ├── useProduct.ts
│   ├── useMatchSupplier.ts
│   └── useAuth.ts
├── lib/
│   ├── api-client.ts
│   └── utils.ts
└── types/
    └── api.ts (generated)
```

**Shared UI Components:**

- `ProductCard.tsx`: Reusable card component displaying product summary
- `DataTable.tsx`: Generic table with sorting, pagination, and filtering
- `FilterBar.tsx`: Reusable filter controls (category, price range, search)
- `Button.tsx`: Styled button component with variants (primary, secondary, danger)
- `Input.tsx`: Styled input component with validation states

**State Management:**

- Server State: TanStack Query (catalog, products, supplier items)
- Authentication State: React Context + localStorage for JWT token
- UI State: React useState/useReducer (filters, modals, form inputs)
- Cart State: localStorage + React Context (persisted client-side)

### TR-6: Responsive Design

**Breakpoint Strategy:**

- **Mobile (< 640px):** Single column layout, stacked navigation, hamburger menu
- **Tablet (640px - 1024px):** Two-column grid, side navigation visible
- **Desktop (> 1024px):** Multi-column grid, full navigation, optimal spacing

**Tailwind Utilities:**

```tsx
// Example responsive component
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {products.map(product => (
    <ProductCard key={product.id} product={product} />
  ))}
</div>
```

### TR-7: Authentication Flow

**JWT Token Management:**

1. User submits login form with credentials
2. POST request to `/auth/login` returns JWT token
3. Token stored in localStorage (or httpOnly cookie if backend supports)
4. Token included in Authorization header for all API requests
5. Token refresh handled via background query or interceptor
6. Logout clears token and redirects to login page

```typescript
// src/hooks/useAuth.ts
export function useAuth() {
  const login = async (username: string, password: string) => {
    const { data } = await apiClient.POST('/auth/login', {
      body: { username, password }
    })
    localStorage.setItem('jwt_token', data.token)
    localStorage.setItem('user_role', data.role)
  }

  const logout = () => {
    localStorage.removeItem('jwt_token')
    localStorage.removeItem('user_role')
  }

  const isAuthenticated = !!localStorage.getItem('jwt_token')

  return { login, logout, isAuthenticated }
}
```

---

## Non-Functional Requirements

### NFR-1: Performance

- Initial page load: < 3 seconds on 3G connection (Lighthouse performance score > 80)
- Catalog rendering: < 2 seconds for 100 products with filters applied
- Filter updates: < 500ms from user input to UI update (debounced search)
- Product detail view: < 1 second navigation and render time
- Match/unmatch operations: < 1 second round-trip with optimistic UI update

### NFR-2: Scalability

- Support 1,000 concurrent users on public catalog (frontend static assets via CDN)
- Handle catalog with 10,000+ products (pagination and virtual scrolling)
- Client-side filtering efficient up to 500 items, server-side beyond that
- Code splitting by route to minimize initial bundle size (< 200KB gzipped)

### NFR-3: Accessibility

- WCAG 2.1 Level AA compliance (semantic HTML, ARIA labels)
- Keyboard navigation for all interactive elements (tab order, focus management)
- Screen reader support with descriptive alt text and labels
- Sufficient color contrast ratios (4.5:1 for normal text, 3:1 for large text)
- Focus indicators visible on all interactive elements

### NFR-4: Security

- XSS prevention via React's built-in escaping (no `dangerouslySetInnerHTML`)
- CSRF protection for stateful operations (SameSite cookies or CSRF tokens)
- JWT token validation on backend (frontend trusts backend, no client-side verification)
- Secure token storage (httpOnly cookies preferred, localStorage with caution)
- Input sanitization for search queries (prevent injection attacks)
- HTTPS enforced in production (redirect HTTP to HTTPS)

### NFR-5: Browser Support

- Modern browsers: Chrome, Firefox, Safari, Edge (latest 2 versions)
- No Internet Explorer support (ES6+ JavaScript, modern CSS)
- Mobile browsers: iOS Safari, Chrome for Android (latest versions)
- Progressive enhancement: core functionality without JavaScript (minimal)

### NFR-6: Observability

- Error boundary components for graceful error handling (React Error Boundaries)
- Client-side error logging to backend error tracking service (optional integration)
- Performance monitoring via Web Vitals (LCP, FID, CLS)
- TanStack Query DevTools enabled in development mode

---

## Data Models

### Frontend Types (TypeScript)

**Auto-Generated from OpenAPI Spec:**

```typescript
// src/types/api.ts (generated via openapi-typescript)
export interface Product {
  id: string
  name: string
  sku: string
  description: string | null
  price: number
  category_id: string
  status: 'draft' | 'active' | 'archived'
  characteristics: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface SupplierItem {
  id: string
  supplier_id: string
  supplier_sku: string
  name: string
  price: number
  product_id: string | null
  characteristics: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Category {
  id: string
  name: string
  parent_id: string | null
}
```

**Frontend-Only Types:**

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
```

```typescript
// src/types/filters.ts
export interface CatalogFilters {
  category?: string
  minPrice?: number
  maxPrice?: number
  search?: string
  status?: 'draft' | 'active' | 'archived'
}
```

---

## Error Handling

### API Error Responses

**Standard Error Format (from Phase 2 API):**

```typescript
interface ApiErrorResponse {
  error: {
    code: string
    message: string
    details?: unknown
  }
}
```

### Frontend Error Handling

**TanStack Query Error Handling:**

```typescript
export function useCatalog(filters: CatalogFilters) {
  return useQuery({
    queryKey: ['catalog', filters],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/catalog', {
        params: { query: filters }
      })
      if (error) {
        throw new Error(error.error.message || 'Failed to fetch catalog')
      }
      return data
    },
    retry: (failureCount, error) => {
      // Retry network errors, not validation errors
      return failureCount < 2 && !(error.message.includes('validation'))
    }
  })
}
```

**Error Boundary Component:**

```typescript
// src/components/ErrorBoundary.tsx
import { Component, ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="p-4 bg-danger/10 text-danger rounded">
          <h2>Something went wrong</h2>
          <p>{this.state.error?.message}</p>
          <button onClick={() => window.location.reload()}>
            Reload Page
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
```

**User-Facing Error States:**

- Network errors: "Unable to connect. Please check your internet connection."
- Authentication errors: "Session expired. Please log in again."
- Validation errors: Display field-specific messages from API response
- Server errors: "Something went wrong. Please try again later."
- Empty states: "No products found. Try adjusting your filters."

---

## Testing Requirements

### Unit Tests

**Component Testing (Vitest + React Testing Library):**

- Test component rendering with different props
- Test user interactions (clicks, form submissions)
- Test conditional rendering based on state
- Mock TanStack Query hooks with MSW (Mock Service Worker)

**Hook Testing:**

- Test custom hooks (useAuth, useCatalog, useCart)
- Mock API client responses
- Verify cache invalidation logic

### Integration Tests

**Route Testing:**

- Test navigation between pages
- Test protected route redirects
- Test URL query parameter handling for filters

**API Integration:**

- Test end-to-end flows with real API calls (optional, use MSW mocks)
- Verify request/response transformations
- Test error scenarios and retry logic

### E2E Tests (Optional for Phase 3)

**Playwright/Cypress Scenarios:**

- User browses catalog, applies filters, views product detail
- User adds products to cart, proceeds to checkout mock
- Sales user logs in, views internal catalog, sorts by margin
- Procurement user matches supplier item to product

**Coverage Target:** ≥80% for components and hooks

---

## Deployment

### Environment Variables

```bash
# Frontend (.env file)
VITE_API_URL=http://localhost:3000
VITE_ENV=development
```

```bash
# Production
VITE_API_URL=https://api.marketbel.com
VITE_ENV=production
```

### Build Configuration

**Development:**

```bash
bun install
bun run dev  # Starts Vite dev server on port 5173
```

**Production:**

```bash
bun run build  # Creates optimized bundle in dist/
bun run preview  # Preview production build locally
```

### Docker Configuration (Optional)

```dockerfile
# Dockerfile for frontend (multi-stage build)
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

### Deployment Strategy

1. Build frontend assets (`bun run build`)
2. Deploy static files to CDN or static hosting (Vercel, Netlify, S3 + CloudFront)
3. Configure reverse proxy to route `/api/*` to Bun backend
4. Enable HTTPS with SSL certificates
5. Set cache headers for static assets (max-age=31536000 for versioned files)
6. Deploy with zero-downtime (blue-green or rolling deployment)

---

## Documentation

- [ ] README with setup instructions and npm scripts
- [ ] Component documentation with Storybook (optional, Phase 4+)
- [ ] API integration guide (how to regenerate types from OpenAPI spec)
- [ ] Deployment guide for production environment
- [ ] Architecture Decision Records (ADRs) for key technical choices

---

## Rollback Plan

**Trigger Conditions:**

- Critical bugs affecting user experience (e.g., broken authentication, catalog not loading)
- Performance degradation > 50% (p95 response time doubles)
- Security vulnerability discovered in dependencies

**Rollback Steps:**

1. Revert frontend deployment to previous version (CDN or static hosting)
2. Clear CDN cache to serve old version immediately
3. Notify users of temporary downtime if necessary
4. Investigate root cause in development environment
5. Deploy hotfix or wait for next release cycle

**Mitigation:**

- Use feature flags for gradual rollout (enable for 10% → 50% → 100% of users)
- Maintain previous version assets for quick rollback
- Monitor error rates and performance metrics post-deployment

---

## Exceptions & Deviations

**None**

This specification fully adheres to constitutional principles. The frontend is purely presentational with no business logic, ensuring clear separation of concerns. All data processing occurs in the Bun API (Phase 2) and Python worker (Phase 1) services.

---

## Appendix

### References

- [Phase 2 Specification - Bun API Layer](../002-api-layer/spec.md)
- [Phase 1 Specification - Data Ingestion Infrastructure](../001-data-ingestion-infra/spec.md)
- [React Router Documentation](https://reactrouter.com/)
- [TanStack Query Documentation](https://tanstack.com/query/latest)
- [Tailwind CSS v4 Documentation](https://tailwindcss.com/docs)
- [OpenAPI TypeScript Generator](https://github.com/drwpow/openapi-typescript)
- [Vite Documentation](https://vitejs.dev/)

### Glossary

- **Public Catalog:** Product listing accessible without authentication (client-facing storefront)
- **Internal Catalog:** Admin view showing margins and supplier details (sales team tool)
- **Matching:** Process of linking supplier items to internal product SKUs (procurement workflow)
- **Mock:** Non-functional prototype for demonstration (e.g., cart/checkout without backend)
- **Optimistic Update:** UI updates immediately before server confirmation (improves perceived performance)
- **TanStack Query:** Data fetching library for React (formerly React Query)
- **OpenAPI/Swagger:** API specification format used to generate TypeScript types
- **JWT (JSON Web Token):** Authentication token format used for role-based access control
- **SSR (Server-Side Rendering):** Not used in Phase 3 (client-side only, potential for Phase 4+)

---

**Approval:**

- [ ] Tech Lead: [Name] - [Date]
- [ ] Product: [Name] - [Date]
- [ ] QA: [Name] - [Date]
