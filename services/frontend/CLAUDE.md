# Frontend Service Context

## Overview
React SPA for Marketbel catalog system. Public catalog + Admin panels.

**Port:** 5173  
**Build:** Vite

---

## Stack
- **Framework:** React 18 + TypeScript (strict)
- **Build:** Vite 5+
- **State:** TanStack Query v5 (server), React Context (local)
- **UI:** Radix UI Themes
- **Styling:** Tailwind CSS v4.1 (CSS-first)
- **i18n:** react-i18next

---

## Structure

```
src/
├── components/
│   ├── catalog/     # Public catalog (ProductCard, FilterBar)
│   ├── admin/       # Admin panels (SalesTable, SupplierComparison)
│   ├── cart/        # Cart components
│   └── shared/      # Reusable UI (Button, Input, Layout)
├── pages/           # Route components
├── hooks/           # Custom hooks (useCatalog, useAuth, etc.)
├── contexts/        # AuthContext, CartContext
├── lib/
│   ├── api-client.ts   # Fetch wrapper
│   └── query-keys.ts   # TanStack Query keys
├── types/           # TypeScript interfaces
└── i18n.ts          # i18n config
```

---

## Commands

```bash
bun install
bun run dev          # Dev server (port 5173)
bun run build        # Production build
bun run type-check   # TypeScript check
bun run lint         # ESLint
```

---

## Critical Rules

### 1. i18n - All UI Text Must Be Translated

```tsx
// ❌ Wrong
<Button>Save Product</Button>

// ✅ Correct
import { useTranslation } from 'react-i18next'
const { t } = useTranslation()
<Button>{t('common.save')}</Button>
```

Translation files: `public/locales/{en,ru}/*.json`

### 2. Tailwind v4.1 - CSS-First Config

**NO `tailwind.config.js`!** Use `@theme` in CSS:

```css
/* index.css */
@import "tailwindcss";

@theme {
  --color-primary: #3b82f6;
  --font-sans: "Inter", sans-serif;
}
```

### 3. TanStack Query - Server State

```tsx
// hooks/useCatalog.ts
export function useCatalog(filters: CatalogFilters) {
  return useQuery({
    queryKey: queryKeys.catalog.list(filters),
    queryFn: () => api.catalog.getProducts(filters),
  })
}

// In component
const { data, isLoading, error } = useCatalog(filters)
```

### 4. No Business Logic in Components

```tsx
// ❌ Wrong - logic in component
function ProductCard({ product }) {
  const price = product.price * 1.2 // markup calculation
  return <div>{price}</div>
}

// ✅ Correct - logic in hook/util
function ProductCard({ product }) {
  const displayPrice = useDisplayPrice(product)
  return <div>{displayPrice}</div>
}
```

---

## Pages & Routes

| Path | Page | Auth |
|------|------|------|
| `/` | CatalogPage | Public |
| `/product/:id` | ProductDetailPage | Public |
| `/cart` | CartPage | Public |
| `/login` | LoginPage | Public |
| `/admin/sales` | SalesCatalogPage | Sales+ |
| `/admin/procurement` | ProcurementMatchingPage | Procurement+ |
| `/admin/ingestion` | IngestionPage | Admin |
| `/admin/product/:id` | InternalProductDetailPage | Sales+ |

---

## Key Patterns

### API Client

```typescript
// lib/api-client.ts
const api = {
  catalog: {
    getProducts: (filters) => fetch('/api/catalog/products', ...),
  },
  admin: {
    triggerSync: () => fetch('/api/admin/sync/trigger', { method: 'POST' }),
  }
}
```

### Protected Routes

```tsx
<Route element={<ProtectedRoute requiredRole="admin" />}>
  <Route path="/admin/ingestion" element={<IngestionPage />} />
</Route>
```

### Query Keys Factory

```typescript
// lib/query-keys.ts
export const queryKeys = {
  catalog: {
    all: ['catalog'] as const,
    list: (filters) => [...queryKeys.catalog.all, 'list', filters] as const,
  },
}
```

---

## Contexts

### AuthContext
- `user`, `login()`, `logout()`, `isAuthenticated`
- Token stored in localStorage

### CartContext  
- `items`, `addItem()`, `removeItem()`, `clearCart()`
- Persisted to localStorage (no backend sync)

---

## Common Issues

1. **Text not translated** → Add key to `public/locales/{lang}/common.json`
2. **Tailwind classes not working** → Check `@theme` in `index.css`
3. **Query not refetching** → Check `queryKey` uniqueness
4. **Auth redirect loop** → Check `ProtectedRoute` and token validity

