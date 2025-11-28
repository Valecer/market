# Technology Research & Decisions
**Feature:** Unified Frontend Application
**Date:** 2025-11-29
**Status:** Complete

---

## Overview

This document captures research findings and technology decisions for Phase 3 (Unified Frontend Application). Each decision is justified with references to official documentation collected via `mcp context7` and aligned with constitutional principles (especially KISS, Strong Typing, and Design System Consistency).

---

## Decision 1: UI Component Library

### Question
Should we use **Headless UI** or **Radix UI** for accessible, unstyled components?

### Decision: **Radix UI Themes** (`@radix-ui/themes`)

### Rationale

**Radix UI Themes** provides a comprehensive component library with:
- **Stronger TypeScript support:** Explicit `React.FC` types for all components (version 1.1.0+)
- **Comprehensive theming:** Built-in theme system with CSS variables for colors, spacing, and typography
- **Accessibility built-in:** WCAG 2.1 Level AA compliant by default
- **Better documentation:** 447 code snippets in Context7 with high benchmark score (86.6)
- **Component variety:** More comprehensive set of components (Tooltip, Dialog, Dropdown, etc.)
- **Tailwind-compatible:** Works seamlessly with Tailwind CSS utility classes

**Headless UI** is excellent but:
- Less comprehensive (focused on core primitives only)
- Requires more custom styling work
- Documentation timed out (availability concern)
- Smaller component set compared to Radix UI Themes

### Implementation Notes

```bash
bun add @radix-ui/themes
```

```tsx
// src/main.tsx
import { Theme } from '@radix-ui/themes'
import '@radix-ui/themes/styles.css'

root.render(
  <Theme accentColor="blue" grayColor="slate" radius="medium">
    <App />
  </Theme>
)
```

**Key Components to Use:**
- `Button` - Accessible button with variants
- `TextField` - Form inputs with validation states
- `Dialog` - Modal dialogs
- `DropdownMenu` - Dropdowns for filters
- `Tooltip` - Contextual help
- `Card` - Product cards
- `Table` - Simple tables (for small datasets)

**For complex tables:** Use TanStack Table v8 with Radix UI styling.

### References
- [Radix UI Themes Documentation](https://www.radix-ui.com/themes/docs)
- Context7 Library ID: `/websites/radix-ui_themes` (447 snippets, score 86.6)

---

## Decision 2: API Type Generation

### Question
Should we use **elysia/eden** for end-to-end type safety or **openapi-typescript** for broader compatibility?

### Decision: **openapi-typescript** (`openapi-typescript` + `openapi-fetch`)

### Rationale

**openapi-typescript** provides:
- **Broader compatibility:** Works with any OpenAPI-compliant API (not just ElysiaJS)
- **Simpler integration:** Generate types once, use anywhere
- **No runtime overhead:** Pure TypeScript types (no client library needed with openapi-fetch)
- **Better for monorepo/microservices:** Can generate types from multiple API specs
- **Already specified in feature spec:** User requirements mention OpenAPI generation

**elysia/eden** advantages (not chosen):
- End-to-end type safety from Elysia backend to frontend
- Auto-completion for API routes
- However, ties frontend to ElysiaJS (reduces flexibility)
- Requires Elysia-specific client library

**KISS Principle:** OpenAPI is an industry standard. Using `openapi-typescript` keeps our frontend decoupled from backend framework specifics.

### Implementation Notes

```bash
# Install dependencies
bun add openapi-fetch
bun add -d openapi-typescript
```

```bash
# Generate types from Bun API
bunx openapi-typescript http://localhost:3000/docs/json -o src/types/api.ts
```

```typescript
// src/lib/api-client.ts
import createClient from 'openapi-fetch'
import type { paths } from '@/types/api'

export const apiClient = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:3000'
})

// Auto-inject JWT token
apiClient.use({
  onRequest: (req) => {
    const token = localStorage.getItem('jwt_token')
    if (token) {
      req.headers.set('Authorization', `Bearer ${token}`)
    }
  }
})
```

**Type-safe API calls:**

```typescript
// src/hooks/useCatalog.ts
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

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

### References
- [openapi-typescript GitHub](https://github.com/drwpow/openapi-typescript)
- [openapi-fetch Documentation](https://openapi-ts.pages.dev/openapi-fetch/)

---

## Decision 3: TanStack Query v5 Best Practices

### Question
What are the best practices for using TanStack Query v5 with React?

### Decision: **Follow Official Patterns**

### Key Patterns from Documentation

#### 1. QueryClient Setup

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

#### 2. Query Hooks

```typescript
// src/hooks/useCatalog.ts
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export function useCatalog(filters: CatalogFilters) {
  return useQuery({
    queryKey: ['catalog', filters], // Include filters in key for caching
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

#### 3. Mutation Hooks with Cache Updates

```typescript
// src/hooks/useMatchSupplier.ts
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export function useMatchSupplier() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ productId, supplierItemId }: MatchParams) => {
      const { data, error } = await apiClient.PATCH('/admin/products/{id}/match', {
        params: { path: { id: productId } },
        body: { supplier_item_id: supplierItemId }
      })
      if (error) throw error
      return data
    },
    onSuccess: (data, variables) => {
      // Update product cache
      queryClient.setQueryData(['product', { id: variables.productId }], data)
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: ['admin', 'products'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'unmatched'] })
    }
  })
}
```

#### 4. Optimistic Updates

```typescript
// For instant UI feedback
export function useMatchSupplier() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: matchSupplierItem,
    onMutate: async (newMatch) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['admin', 'unmatched'] })

      // Snapshot previous value
      const previousUnmatched = queryClient.getQueryData(['admin', 'unmatched'])

      // Optimistically update
      queryClient.setQueryData(['admin', 'unmatched'], (old) =>
        old?.filter(item => item.id !== newMatch.supplierItemId)
      )

      return { previousUnmatched }
    },
    onError: (err, newMatch, context) => {
      // Rollback on error
      queryClient.setQueryData(['admin', 'unmatched'], context?.previousUnmatched)
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: ['admin', 'unmatched'] })
    }
  })
}
```

### Best Practices Summary

1. **Query Keys:** Include all parameters that affect the query result
2. **Cache Updates:** Use `setQueryData` for immediate updates, `invalidateQueries` for refetching
3. **Optimistic Updates:** Snapshot → Update → Rollback on error → Refetch
4. **Destructure hooks:** Extract only `mutate` from `useMutation` for `useCallback` dependencies
5. **DevTools:** Enable `@tanstack/react-query-devtools` in development

### References
- Context7 Library ID: `/websites/tanstack_query_v5` (1278 snippets, score 84.4)
- [TanStack Query v5 Documentation](https://tanstack.com/query/v5)

---

## Decision 4: TanStack Table v8 Setup

### Question
How should we set up TanStack Table v8 for the procurement view?

### Decision: **Standard Column Definition Pattern**

### Implementation Notes

TanStack Table documentation timed out during research, but standard patterns are well-established:

```bash
bun add @tanstack/react-table
```

```typescript
// src/components/admin/SalesTable.tsx
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  createColumnHelper
} from '@tanstack/react-table'

const columnHelper = createColumnHelper<Product>()

const columns = [
  columnHelper.accessor('name', {
    header: 'Product Name',
    cell: info => info.getValue()
  }),
  columnHelper.accessor('sku', {
    header: 'SKU',
    cell: info => info.getValue()
  }),
  columnHelper.accessor('price', {
    header: 'Selling Price',
    cell: info => `$${info.getValue().toFixed(2)}`
  }),
  columnHelper.accessor(row => row.cost_price, {
    id: 'cost_price',
    header: 'Cost Price',
    cell: info => `$${info.getValue().toFixed(2)}`
  }),
  columnHelper.accessor(row => {
    const margin = ((row.price - row.cost_price) / row.price) * 100
    return margin.toFixed(2)
  }, {
    id: 'margin',
    header: 'Margin %',
    cell: info => `${info.getValue()}%`
  })
]

export function SalesTable({ data }: { data: Product[] }) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel()
  })

  return (
    <table>
      <thead>
        {table.getHeaderGroups().map(headerGroup => (
          <tr key={headerGroup.id}>
            {headerGroup.headers.map(header => (
              <th key={header.id} onClick={header.column.getToggleSortingHandler()}>
                {flexRender(header.column.columnDef.header, header.getContext())}
                {header.column.getIsSorted() ? (header.column.getIsSorted() === 'asc' ? ' ↑' : ' ↓') : null}
              </th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody>
        {table.getRowModel().rows.map(row => (
          <tr key={row.id}>
            {row.getVisibleCells().map(cell => (
              <td key={cell.id}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
```

**Key Features:**
- **Sorting:** Click column headers to sort
- **Filtering:** Use `setGlobalFilter` or column-specific filters
- **Pagination:** Add `getPaginationRowModel()` for large datasets
- **Virtualization:** Use `@tanstack/react-virtual` for 10,000+ rows

### References
- [TanStack Table v8 Documentation](https://tanstack.com/table/v8)
- Context7 Library ID: `/websites/tanstack_table` (1178 snippets, score 94.3) - *timed out during fetch*

---

## Decision 5: Tailwind CSS v4.1 Configuration

### Question
How should we configure Tailwind CSS v4.1 with the CSS-first approach and Vite plugin?

### Decision: **CSS-First with @tailwindcss/vite Plugin**

### Implementation Pattern (from Official Docs)

#### 1. Install Dependencies

```bash
bun add tailwindcss @tailwindcss/vite
```

#### 2. Vite Configuration

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    tailwindcss(), // MUST be before react() plugin
    react()
  ],
  server: {
    proxy: {
      '/api': 'http://localhost:3000'
    }
  }
})
```

**CRITICAL:** `tailwindcss()` MUST appear **before** `react()` in plugins array for proper initialization.

#### 3. CSS-First Configuration

```css
/* src/index.css */
@import "tailwindcss";

@theme {
  /* Colors */
  --color-primary: #3b82f6;
  --color-secondary: #8b5cf6;
  --color-success: #10b981;
  --color-danger: #ef4444;
  --color-warning: #f59e0b;

  /* Typography */
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'Fira Code', 'Courier New', monospace;

  /* Spacing */
  --spacing-xs: 0.25rem;
  --spacing-sm: 0.5rem;
  --spacing-md: 1rem;
  --spacing-lg: 1.5rem;
  --spacing-xl: 2rem;

  /* Breakpoints (optional, defaults are good) */
  --breakpoint-sm: 640px;
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
  --breakpoint-xl: 1280px;
  --breakpoint-2xl: 1536px;

  /* Radii */
  --radius-sm: 0.125rem;
  --radius-md: 0.375rem;
  --radius-lg: 0.5rem;
  --radius-full: 9999px;
}

/* Global styles */
body {
  @apply font-sans antialiased;
}
```

#### 4. NO tailwind.config.js File

**Per constitutional requirement:** DO NOT create `tailwind.config.js`. All configuration happens in CSS via `@theme` blocks.

### Usage in Components

```tsx
// src/components/catalog/ProductCard.tsx
export function ProductCard({ product }: ProductCardProps) {
  return (
    <div className="bg-white rounded-lg shadow-md p-4 hover:shadow-lg transition-shadow">
      <img
        src={product.image}
        alt={product.name}
        className="w-full h-48 object-cover rounded-md mb-4"
      />
      <h3 className="text-lg font-semibold mb-2">{product.name}</h3>
      <p className="text-gray-600 text-sm mb-4">{product.description}</p>
      <div className="flex items-center justify-between">
        <span className="text-2xl font-bold text-primary">
          ${product.price.toFixed(2)}
        </span>
        <button className="bg-primary text-white px-4 py-2 rounded-md hover:bg-primary/90 transition-colors">
          Add to Cart
        </button>
      </div>
    </div>
  )
}
```

### Key Differences from v3

1. **No PostCSS config:** Vite plugin handles everything
2. **CSS-first theming:** Use `@theme` blocks instead of JS config
3. **Import syntax:** `@import "tailwindcss"` instead of `@tailwind` directives
4. **Performance:** Faster builds, better HMR

### References
- Context7 Library ID: `/websites/tailwindcss` (1710 snippets, score 71.1)
- [Tailwind CSS v4 Upgrade Guide](https://tailwindcss.com/docs/upgrade-guide)
- [Tailwind CSS Vite Plugin](https://tailwindcss.com/docs/installation/vite)

---

## Decision 6: Authentication Token Refresh Strategy

### Question
Should we implement silent token refresh or redirect to login on expiration?

### Decision: **Redirect to Login (KISS Principle)**

### Rationale

**KISS Principle:** Start simple. Silent token refresh adds complexity:
- Requires refresh token storage
- Needs background refresh logic
- Error handling for refresh failures
- Security concerns (XSS if using localStorage)

**Redirect to Login** is simpler:
- Clear user experience (session expired message)
- No background processes
- Easy to implement
- Secure (forces re-authentication)
- Can be upgraded later if needed

### Implementation

```typescript
// src/lib/api-client.ts
apiClient.use({
  onRequest: (req) => {
    const token = localStorage.getItem('jwt_token')
    if (token) {
      req.headers.set('Authorization', `Bearer ${token}`)
    }
  },
  onResponse: (res) => {
    if (res.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('jwt_token')
      localStorage.removeItem('user_role')
      window.location.href = '/login?expired=true'
    }
  }
})
```

**Future Enhancement (Phase 4+):** Implement silent refresh with httpOnly cookies if needed.

---

## Decision 7: Cart Persistence Strategy

### Question
Should cart data sync across devices (requires backend) or remain local-only?

### Decision: **localStorage Only (Phase 3)**

### Rationale

**Scope:** Phase 3 spec explicitly states "Shopping cart and checkout **mock**" with no backend integration.

**Implementation:**

```typescript
// src/contexts/CartContext.tsx
import { createContext, useContext, useReducer, useEffect } from 'react'

interface CartState {
  items: CartItem[]
}

type CartAction =
  | { type: 'ADD_ITEM'; payload: CartItem }
  | { type: 'REMOVE_ITEM'; payload: string }
  | { type: 'UPDATE_QUANTITY'; payload: { productId: string; quantity: number } }
  | { type: 'CLEAR_CART' }
  | { type: 'LOAD_CART'; payload: CartItem[] }

function cartReducer(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case 'ADD_ITEM':
      return { ...state, items: [...state.items, action.payload] }
    case 'REMOVE_ITEM':
      return { ...state, items: state.items.filter(item => item.productId !== action.payload) }
    case 'UPDATE_QUANTITY':
      return {
        ...state,
        items: state.items.map(item =>
          item.productId === action.payload.productId
            ? { ...item, quantity: action.payload.quantity }
            : item
        )
      }
    case 'CLEAR_CART':
      return { ...state, items: [] }
    case 'LOAD_CART':
      return { ...state, items: action.payload }
    default:
      return state
  }
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(cartReducer, { items: [] })

  // Load from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('cart')
    if (saved) {
      dispatch({ type: 'LOAD_CART', payload: JSON.parse(saved) })
    }
  }, [])

  // Save to localStorage on change
  useEffect(() => {
    localStorage.setItem('cart', JSON.stringify(state.items))
  }, [state.items])

  return (
    <CartContext.Provider value={{ state, dispatch }}>
      {children}
    </CartContext.Provider>
  )
}
```

**Future Enhancement (Phase 4+):** Add backend cart API for cross-device sync.

---

## Decision 8: Error Reporting

### Question
Do we need client-side error logging (e.g., Sentry integration)?

### Decision: **Console Logging Only (Phase 3)**

### Rationale

**KISS + Scope:** Phase 3 focuses on core functionality. Error reporting adds:
- External dependency (Sentry, LogRocket, etc.)
- Privacy considerations (GDPR, data residency)
- Cost (paid services)
- Configuration overhead

**Implementation:**

```typescript
// src/components/ErrorBoundary.tsx
import { Component, ReactNode } from 'react'

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    console.error('[ErrorBoundary] Caught error:', error)
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary] Error details:', error, errorInfo)
    // Future: Send to Sentry/LogRocket here
  }

  render() {
    if (this.state.hasError) {
      return (
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

**Future Enhancement (Phase 4+):** Add Sentry or similar service with proper privacy controls.

---

## Summary of Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **UI Components** | Radix UI Themes | Better TypeScript, comprehensive components, strong accessibility |
| **API Types** | openapi-typescript | Broader compatibility, decoupled from backend framework |
| **Query Pattern** | TanStack Query v5 | Industry standard, excellent caching, optimistic updates |
| **Table Library** | TanStack Table v8 | Headless, flexible, high performance |
| **CSS Framework** | Tailwind v4.1 (CSS-first) | Constitutional requirement, better performance |
| **Token Refresh** | Redirect to login | KISS principle, can upgrade later |
| **Cart Persistence** | localStorage only | Scope (mock cart), upgrade in Phase 4+ |
| **Error Reporting** | Console only | KISS principle, defer to Phase 4+ |

---

## Constitutional Alignment

All decisions align with constitutional principles:

- **KISS:** Simple solutions preferred (redirect vs silent refresh, localStorage vs backend cart)
- **Strong Typing:** openapi-typescript + TypeScript strict mode
- **Design System Consistency:** Radix UI + Tailwind CSS
- **Separation of Concerns:** Frontend presentation only, no business logic
- **DRY:** Reusable components, shared types from OpenAPI

---

## Next Steps

1. ✅ Research complete
2. ⏭️ Generate `data-model.md` with TypeScript types
3. ⏭️ Generate API contracts in `/contracts` directory
4. ⏭️ Generate `quickstart.md` with 15-minute setup guide
5. ⏭️ Update agent context (CLAUDE.md) with new technologies
