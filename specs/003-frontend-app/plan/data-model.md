# Data Models & Type Definitions
**Feature:** Unified Frontend Application
**Date:** 2025-11-29
**Status:** Complete

---

## Overview

This document defines all TypeScript types, interfaces, and data models for the frontend application. Types are categorized into:
1. **API Types** (auto-generated from OpenAPI spec)
2. **Frontend-Only Types** (Cart, Auth, UI state)
3. **Component Prop Interfaces**
4. **Validation Schemas** (TanStack Query integration)

---

## 1. API Types (Auto-Generated)

### Generation Command

```bash
# Run after Bun API is running on port 3000
bunx openapi-typescript http://localhost:3000/docs/json -o src/types/api.ts
```

### Expected Generated Types

```typescript
// src/types/api.ts (auto-generated, DO NOT EDIT MANUALLY)

export interface paths {
  "/catalog": {
    get: operations["getCatalog"]
  }
  "/catalog/{id}": {
    get: operations["getProduct"]
  }
  "/auth/login": {
    post: operations["login"]
  }
  "/admin/products": {
    get: operations["getAdminProducts"]
  }
  "/admin/products/{id}": {
    get: operations["getAdminProduct"]
  }
  "/admin/products/{id}/match": {
    patch: operations["matchSupplierItem"]
  }
  "/admin/sync": {
    post: operations["triggerSync"]
  }
}

export interface operations {
  getCatalog: {
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
  // ... other operations
}

export interface components {
  schemas: {
    Product: {
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
    SupplierItem: {
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
    Category: {
      id: string
      name: string
      parent_id: string | null
    }
    Supplier: {
      id: string
      name: string
      source_type: "google_sheets" | "csv" | "excel"
      created_at: string
      updated_at: string
    }
    User: {
      id: string
      username: string
      role: "sales" | "procurement" | "admin"
      created_at: string
      updated_at: string
    }
  }
}

// Type aliases for convenience
export type Product = components["schemas"]["Product"]
export type SupplierItem = components["schemas"]["SupplierItem"]
export type Category = components["schemas"]["Category"]
export type Supplier = components["schemas"]["Supplier"]
export type User = components["schemas"]["User"]
```

### Usage with openapi-fetch

```typescript
// src/lib/api-client.ts
import createClient from 'openapi-fetch'
import type { paths } from '@/types/api'

export const apiClient = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:3000'
})

// Type-safe API calls
const { data, error } = await apiClient.GET('/catalog', {
  params: {
    query: {
      category: 'electronics',
      minPrice: 100,
      maxPrice: 500
    }
  }
})
// data is typed as Product[] | undefined
// error is typed with error response schema
```

---

## 2. Frontend-Only Types

### Cart Types

```typescript
// src/types/cart.ts

export interface CartItem {
  /** Product ID from catalog */
  productId: string
  /** Product name (cached for display) */
  name: string
  /** Current price (cached at time of adding) */
  price: number
  /** Quantity in cart */
  quantity: number
  /** Optional product image URL */
  image?: string
}

export interface Cart {
  /** All items in cart */
  items: CartItem[]
  /** Sum of (price * quantity) for all items */
  subtotal: number
  /** Estimated tax (mock calculation) */
  tax: number
  /** subtotal + tax */
  total: number
}

export type CartAction =
  | { type: 'ADD_ITEM'; payload: CartItem }
  | { type: 'REMOVE_ITEM'; payload: string } // productId
  | { type: 'UPDATE_QUANTITY'; payload: { productId: string; quantity: number } }
  | { type: 'CLEAR_CART' }
  | { type: 'LOAD_CART'; payload: CartItem[] }

export interface CartContextValue {
  state: Cart
  dispatch: React.Dispatch<CartAction>
  addItem: (item: Omit<CartItem, 'quantity'>) => void
  removeItem: (productId: string) => void
  updateQuantity: (productId: string, quantity: number) => void
  clearCart: () => void
}
```

### Authentication Types

```typescript
// src/types/auth.ts
import type { User } from './api'

export interface AuthState {
  /** Current authenticated user (null if not logged in) */
  user: User | null
  /** JWT token */
  token: string | null
  /** Convenience flag */
  isAuthenticated: boolean
}

export type AuthAction =
  | { type: 'LOGIN'; payload: { user: User; token: string } }
  | { type: 'LOGOUT' }
  | { type: 'REFRESH_TOKEN'; payload: string }

export interface AuthContextValue {
  state: AuthState
  dispatch: React.Dispatch<AuthAction>
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
  userRole: User['role'] | null
}

export interface LoginCredentials {
  username: string
  password: string
}

export interface LoginResponse {
  user: User
  token: string
}
```

### Filter Types

```typescript
// src/types/filters.ts

export interface CatalogFilters {
  /** Category ID or name */
  category?: string
  /** Minimum price (inclusive) */
  minPrice?: number
  /** Maximum price (inclusive) */
  maxPrice?: number
  /** Search query (product name, SKU, description) */
  search?: string
}

export interface AdminProductFilters extends CatalogFilters {
  /** Product status filter */
  status?: "draft" | "active" | "archived"
  /** Minimum margin percentage */
  minMargin?: number
  /** Maximum margin percentage */
  maxMargin?: number
}

export interface ProcurementFilters {
  /** Supplier ID */
  supplierId?: string
  /** Search query */
  search?: string
  /** Show only unmatched items */
  unmatchedOnly?: boolean
}
```

### UI State Types

```typescript
// src/types/ui.ts

export interface LoadingState {
  isLoading: boolean
  message?: string
}

export interface ErrorState {
  hasError: boolean
  message?: string
  code?: string
  details?: unknown
}

export interface PaginationState {
  page: number
  pageSize: number
  total: number
  totalPages: number
}

export interface SortState<T = string> {
  column: T
  direction: "asc" | "desc"
}

export type ToastType = "success" | "error" | "warning" | "info"

export interface Toast {
  id: string
  type: ToastType
  message: string
  duration?: number // milliseconds
}
```

---

## 3. Component Prop Interfaces

### Catalog Components

```typescript
// src/components/catalog/ProductCard.tsx
import type { Product } from '@/types/api'

export interface ProductCardProps {
  /** Product to display */
  product: Product
  /** Callback when "Add to Cart" is clicked */
  onAddToCart?: (productId: string) => void
  /** Show admin controls (edit, delete) */
  showAdminControls?: boolean
  /** CSS class name for custom styling */
  className?: string
}

// src/components/catalog/ProductGrid.tsx
export interface ProductGridProps {
  /** Products to display */
  products: Product[]
  /** Loading state */
  isLoading?: boolean
  /** Error state */
  error?: Error | null
  /** Callback for product card click */
  onProductClick?: (product: Product) => void
  /** Callback for add to cart */
  onAddToCart?: (productId: string) => void
  /** Grid columns (responsive) */
  columns?: number
}

// src/components/catalog/FilterBar.tsx
import type { CatalogFilters } from '@/types/filters'
import type { Category } from '@/types/api'

export interface FilterBarProps {
  /** Current filter state */
  filters: CatalogFilters
  /** Callback when filters change */
  onFiltersChange: (filters: CatalogFilters) => void
  /** Available categories */
  categories: Category[]
  /** Show category filter */
  showCategoryFilter?: boolean
  /** Show price range filter */
  showPriceFilter?: boolean
  /** Show search input */
  showSearch?: boolean
}
```

### Admin Components

```typescript
// src/components/admin/SalesTable.tsx
import type { Product } from '@/types/api'

export interface SalesTableProps {
  /** Products with pricing data */
  products: Product[]
  /** Loading state */
  isLoading?: boolean
  /** Error state */
  error?: Error | null
  /** Callback for row click */
  onRowClick?: (product: Product) => void
  /** Show pagination */
  showPagination?: boolean
  /** Items per page */
  pageSize?: number
}

// src/components/admin/MatchingInterface.tsx
import type { SupplierItem } from '@/types/api'

export interface MatchingInterfaceProps {
  /** Unmatched supplier items */
  unmatchedItems: SupplierItem[]
  /** Loading state */
  isLoading?: boolean
  /** Callback when match is created */
  onMatch: (supplierItemId: string, productId: string) => Promise<void>
  /** Callback when match is removed */
  onUnmatch: (supplierItemId: string) => Promise<void>
}

// src/components/admin/ProductSearchModal.tsx
export interface ProductSearchModalProps {
  /** Modal open state */
  isOpen: boolean
  /** Close callback */
  onClose: () => void
  /** Select callback (returns product ID) */
  onSelect: (productId: string) => void
  /** Initial search query */
  initialQuery?: string
}
```

### Shared Components

```typescript
// src/components/shared/Button.tsx
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Button variant */
  variant?: "primary" | "secondary" | "danger" | "ghost"
  /** Button size */
  size?: "sm" | "md" | "lg"
  /** Loading state */
  isLoading?: boolean
  /** Icon before text */
  leftIcon?: React.ReactNode
  /** Icon after text */
  rightIcon?: React.ReactNode
}

// src/components/shared/Input.tsx
export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** Input label */
  label?: string
  /** Error message */
  error?: string
  /** Helper text */
  helperText?: string
  /** Icon before input */
  leftIcon?: React.ReactNode
  /** Icon after input */
  rightIcon?: React.ReactNode
}

// src/components/shared/DataTable.tsx
export interface Column<T> {
  /** Column key */
  key: keyof T | string
  /** Column header */
  header: string
  /** Cell renderer */
  cell?: (value: unknown, row: T) => React.ReactNode
  /** Sortable flag */
  sortable?: boolean
  /** Filterable flag */
  filterable?: boolean
}

export interface DataTableProps<T> {
  /** Data rows */
  data: T[]
  /** Column definitions */
  columns: Column<T>[]
  /** Loading state */
  isLoading?: boolean
  /** Error state */
  error?: Error | null
  /** Row click callback */
  onRowClick?: (row: T) => void
  /** Sort state */
  sortState?: SortState<keyof T>
  /** Sort change callback */
  onSortChange?: (state: SortState<keyof T>) => void
}
```

---

## 4. TanStack Query Integration

### Query Keys

```typescript
// src/lib/query-keys.ts

export const queryKeys = {
  catalog: {
    all: ['catalog'] as const,
    list: (filters: CatalogFilters) => ['catalog', 'list', filters] as const,
    detail: (id: string) => ['catalog', 'detail', id] as const
  },
  admin: {
    products: {
      all: ['admin', 'products'] as const,
      list: (filters: AdminProductFilters) => ['admin', 'products', 'list', filters] as const,
      detail: (id: string) => ['admin', 'products', 'detail', id] as const
    },
    suppliers: {
      all: ['admin', 'suppliers'] as const,
      unmatched: (filters: ProcurementFilters) => ['admin', 'suppliers', 'unmatched', filters] as const
    }
  },
  auth: {
    user: ['auth', 'user'] as const
  }
} as const
```

### Hook Return Types

```typescript
// src/hooks/useCatalog.ts
import type { UseQueryResult } from '@tanstack/react-query'
import type { Product } from '@/types/api'

export type UseCatalogReturn = UseQueryResult<Product[], Error>

// src/hooks/useMatchSupplier.ts
import type { UseMutationResult } from '@tanstack/react-query'

export interface MatchSupplierParams {
  productId: string
  supplierItemId: string
}

export type UseMatchSupplierReturn = UseMutationResult<
  Product,
  Error,
  MatchSupplierParams,
  unknown
>
```

---

## 5. Validation Schemas (Future)

For Phase 4+, add runtime validation with Zod:

```typescript
// src/schemas/product.schema.ts (FUTURE)
import { z } from 'zod'

export const productSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(255),
  sku: z.string().min(1).max(100),
  description: z.string().nullable(),
  price: z.number().positive(),
  category_id: z.string().uuid(),
  status: z.enum(['draft', 'active', 'archived']),
  characteristics: z.record(z.unknown()),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime()
})

export type ProductSchema = z.infer<typeof productSchema>
```

---

## 6. State Management Summary

| State Type | Management Strategy | Storage | Scope |
|------------|---------------------|---------|-------|
| **Server State** | TanStack Query | In-memory cache | Global |
| **Authentication** | React Context | localStorage | Global |
| **Cart** | React Context + Reducer | localStorage | Global |
| **Filters** | URL Query Params | URL state | Per-route |
| **UI State** | useState/useReducer | Component state | Local |
| **Modals** | useState | Component state | Local |
| **Forms** | Controlled components | Component state | Local |

---

## 7. Type Safety Guarantees

### Compile-Time Checks

```typescript
// ✅ Type-safe API calls
const { data } = await apiClient.GET('/catalog', {
  params: {
    query: {
      category: 'electronics',
      minPrice: 100, // ✅ number
      maxPrice: '500' // ❌ Error: Type 'string' is not assignable to type 'number'
    }
  }
})

// ✅ Type-safe component props
<ProductCard
  product={product} // ✅ Product type
  onAddToCart={(id) => console.log(id)} // ✅ string parameter
  showAdminControls={true} // ✅ boolean
  invalidProp="foo" // ❌ Error: Object literal may only specify known properties
/>

// ✅ Type-safe query hooks
const { data, isLoading, error } = useCatalog({ category: 'electronics' })
// data is typed as Product[] | undefined
// isLoading is boolean
// error is Error | null
```

### Runtime Validation (at System Boundaries)

```typescript
// src/lib/api-client.ts
apiClient.use({
  onResponse: async (res) => {
    if (!res.ok) {
      const error = await res.json()
      throw new Error(error.error?.message || 'API request failed')
    }
  }
})
```

---

## 8. Migration Path

### From Phase 3 to Phase 4+

When adding backend features:

1. **Cart Backend Integration:**
   ```typescript
   // Add CartItem to API types
   export interface components {
     schemas: {
       CartItem: { /* ... */ }
       // ...
     }
   }

   // Update CartContext to sync with backend
   const { mutate } = useMutation({
     mutationFn: (item: CartItem) => apiClient.POST('/cart/items', { body: item })
   })
   ```

2. **User Registration:**
   ```typescript
   // Add to API types
   export interface operations {
     register: {
       requestBody: {
         content: {
           "application/json": {
             username: string
             email: string
             password: string
           }
         }
       }
       responses: {
         201: {
           content: {
             "application/json": User
           }
         }
       }
     }
   }
   ```

---

## Constitutional Alignment

All type definitions adhere to constitutional principles:

- **Strong Typing:** TypeScript strict mode, no `any` types
- **DRY:** API types generated once from OpenAPI spec
- **Single Responsibility:** Each type file serves one purpose
- **Interface Segregation:** Narrow, focused prop interfaces
- **Separation of Concerns:** Clear distinction between API types (backend contract) and frontend-only types

---

## References

- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/)
- [openapi-typescript Documentation](https://openapi-ts.pages.dev/introduction)
- [TanStack Query TypeScript Guide](https://tanstack.com/query/latest/docs/react/typescript)
- Feature Spec: `../spec.md`
- Research: `./research.md`
