> **Refer to: [[../../CLAUDE.md]] and [[../../docs/PROJECT_SUMMARY.md]]**

# Frontend Service

**Role:** React SPA (Public catalog + Admin panels)
**Phases:** 3 (UI), 5 (i18n), 8 (ML Integration UI)

## Stack

React 18, TypeScript (strict), Vite 5+, TanStack Query v5, Radix UI Themes, Tailwind CSS v4.1 (CSS-first), react-i18next

## Commands

```bash
cd services/frontend

bun install
bun run dev          # Dev server (port 5173)
bun run build        # Production build
bun run type-check   # TypeScript check
bun run lint         # ESLint
```

## Critical Patterns

### 1. i18n - All UI Text Must Be Translated

```tsx
// ❌ Wrong
<Button>Save Product</Button>

// ✅ Correct
import { useTranslation } from 'react-i18next'
const { t } = useTranslation()
<Button>{t('common.save')}</Button>
```

**Translation files:** `public/locales/{en,ru}/*.json`

### 2. Tailwind v4.1 - CSS-First Config (NO tailwind.config.js!)

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

Extract to hooks/utils.

## Phase 8: ML Integration Components

### JobPhaseIndicator

Displays multi-phase processing status.

```tsx
import { JobPhaseIndicator } from '@/components/admin/JobPhaseIndicator'

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

**Phase Icons:** downloading 📥, analyzing 🔬, matching 🔗, complete ✅, failed ❌

### useRetryJob Hook

```tsx
import { useRetryJob } from '@/hooks/useRetryJob'

const { mutate: retry, isPending } = useRetryJob()

<Button onClick={() => retry(jobId)} disabled={isPending}>
  {t('admin.ingestion.retry')}
</Button>
```

### TypeScript Types (Phase 8)

```typescript
// types/ingestion.ts
export type JobPhase = 'downloading' | 'analyzing' | 'matching' | 'complete' | 'failed'

export interface IngestionJob {
  job_id: string
  phase: JobPhase
  download_progress: { percentage: number; bytes_downloaded: number } | null
  analysis_progress: { items_processed: number; items_total: number } | null
  error: string | null
  can_retry: boolean
  retry_count: number
  max_retries: number
}
```

### Translation Keys (Phase 8)

```json
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

## Common Issues

1. **Text not translated** → Add key to `public/locales/{lang}/translation.json`
2. **Tailwind classes not working** → Check `@theme` in `index.css`, verify NO tailwind.config.js
3. **Query not refetching** → Check `queryKey` uniqueness
4. **Job status not updating** → Check polling interval in `useIngestionStatus`
5. **Retry button not showing** → Verify `can_retry: true` and `phase: "failed"`
