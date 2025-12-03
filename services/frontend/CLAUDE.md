# Frontend Service Context

## Overview
React SPA for Marketbel catalog system. Public catalog + Admin panels.

**Port:** 5173  
**Build:** Vite
**Phases:** 3 (UI), 5 (i18n), 8 (ML Integration UI)

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
│   ├── admin/       # Admin panels
│   │   ├── JobPhaseIndicator.tsx    # Phase 8: ML processing phases
│   │   ├── SyncControlCard.tsx      # Phase 6+8: Enhanced with jobs array
│   │   ├── SupplierAddModal.tsx     # Phase 8: ML toggle
│   │   ├── SupplierStatusTable.tsx  # Phase 8: ML status badges
│   │   └── ...
│   ├── cart/        # Cart components
│   └── shared/      # Reusable UI (Button, Input, Layout)
├── pages/           # Route components
├── hooks/           # Custom hooks
│   ├── useCatalog.ts
│   ├── useAuth.ts
│   ├── useIngestionStatus.ts  # Phase 6+8: Extended with jobs
│   └── useRetryJob.ts         # Phase 8: Retry failed jobs
├── contexts/        # AuthContext, CartContext
├── lib/
│   ├── api-client.ts   # Fetch wrapper
│   └── query-keys.ts   # TanStack Query keys
├── types/           # TypeScript interfaces
│   ├── ingestion.ts    # Phase 8: JobPhase, IngestionJob, etc.
│   └── supplier.ts     # Phase 8: use_ml_processing field
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

## Phase 8: ML Integration Components

### JobPhaseIndicator

Displays multi-phase processing status with progress bar and icons.

```tsx
import { JobPhaseIndicator } from '@/components/admin/JobPhaseIndicator'

// Usage in SyncControlCard or SupplierStatusTable
<JobPhaseIndicator
  job={{
    job_id: "abc-123",
    phase: "analyzing",
    download_progress: null,
    analysis_progress: { items_processed: 45, items_total: 100 },
    error: null,
    can_retry: false,
    retry_count: 0,
  }}
  onRetry={() => handleRetry("abc-123")}
/>
```

**Phase Icons & Colors:**
| Phase | Icon | Color |
|-------|------|-------|
| `downloading` | 📥 | Blue |
| `analyzing` | 🔬 | Yellow |
| `matching` | 🔗 | Purple |
| `complete` | ✅ | Green |
| `failed` | ❌ | Red |

### useRetryJob Hook

TanStack Query mutation for retrying failed jobs.

```tsx
import { useRetryJob } from '@/hooks/useRetryJob'

function FailedJobCard({ jobId }: { jobId: string }) {
  const { mutate: retry, isPending } = useRetryJob()

  return (
    <Button 
      onClick={() => retry(jobId)}
      disabled={isPending}
    >
      {t('admin.ingestion.retry')}
    </Button>
  )
}
```

### useIngestionStatus Hook (Extended)

Now includes `jobs` array with multi-phase status.

```tsx
import { useIngestionStatus } from '@/hooks/useIngestionStatus'

function IngestionDashboard() {
  const { data } = useIngestionStatus()

  // data.jobs is array of IngestionJob
  data?.jobs?.map(job => (
    <JobPhaseIndicator key={job.job_id} job={job} />
  ))
}
```

### TypeScript Types (Phase 8)

```typescript
// types/ingestion.ts
export type JobPhase = 'downloading' | 'analyzing' | 'matching' | 'complete' | 'failed'

export interface DownloadProgress {
  percentage: number
  bytes_downloaded: number
}

export interface AnalysisProgress {
  items_processed: number
  items_total: number
}

export interface IngestionJob {
  job_id: string
  phase: JobPhase
  download_progress: DownloadProgress | null
  analysis_progress: AnalysisProgress | null
  error: string | null
  can_retry: boolean
  retry_count: number
  max_retries: number
}
```

### ML Toggle in SupplierAddModal

```tsx
// In SupplierAddModal form
<Switch
  checked={form.use_ml_processing ?? true}
  onCheckedChange={(v) => form.setValue('use_ml_processing', v)}
/>
<Label>{t('admin.suppliers.processViaMl')}</Label>
```

### Translation Keys (Phase 8)

```json
// public/locales/en/translation.json
{
  "admin": {
    "ingestion": {
      "phase": {
        "downloading": "Downloading...",
        "analyzing": "Analyzing...",
        "matching": "Matching products...",
        "complete": "Complete",
        "failed": "Failed"
      },
      "retry": "Retry",
      "retryCount": "Retry {{current}} of {{max}}"
    },
    "suppliers": {
      "processViaMl": "Process via ML",
      "mlEnabled": "ML Processing"
    }
  }
}
```

---

## Common Issues

1. **Text not translated** → Add key to `public/locales/{lang}/translation.json`
2. **Tailwind classes not working** → Check `@theme` in `index.css`
3. **Query not refetching** → Check `queryKey` uniqueness
4. **Auth redirect loop** → Check `ProtectedRoute` and token validity
5. **Job status not updating** → Check polling interval in `useIngestionStatus`
6. **Retry button not showing** → Verify `can_retry: true` and `phase: "failed"` in job

