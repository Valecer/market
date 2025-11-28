# Quickstart Guide: Unified Frontend Application
**Goal:** Get the frontend running in 15 minutes
**Date:** 2025-11-29

---

## Prerequisites

Before starting, ensure you have:

- **Bun:** Latest version installed (`curl -fsSL https://bun.sh/install | bash`)
- **Bun API (Phase 2):** Running on `http://localhost:3000` with Swagger at `/docs`
- **Git:** Initialized repository on branch `003-frontend-app`
- **Code Editor:** VS Code recommended with TypeScript/React extensions

**Check Prerequisites:**

```bash
# Verify Bun
bun --version  # Should be 1.x.x or higher

# Verify Phase 2 API is running
curl http://localhost:3000/docs  # Should return Swagger HTML

# Verify git branch
git branch --show-current  # Should show: 003-frontend-app
```

---

## Step 1: Scaffold Project (3 minutes)

### 1.1 Create React + TypeScript Project

```bash
# Navigate to project root
cd /Users/valecer/work/sites/marketbel

# Create frontend directory
mkdir -p services/frontend
cd services/frontend

# Initialize Vite + React + TypeScript
bun create vite . --template react-ts

# Answer prompts:
# Project name: frontend
# Overwrite? Yes
```

### 1.2 Install Dependencies

```bash
# Core dependencies
bun add react react-dom react-router-dom
bun add @tanstack/react-query @tanstack/react-table
bun add @radix-ui/themes
bun add tailwindcss @tailwindcss/vite
bun add openapi-fetch

# Dev dependencies
bun add -d @types/react @types/react-dom
bun add -d @vitejs/plugin-react
bun add -d typescript
bun add -d openapi-typescript
bun add -d vitest @testing-library/react @testing-library/user-event
bun add -d eslint @typescript-eslint/eslint-plugin @typescript-eslint/parser
```

**Expected time:** 2-3 minutes

---

## Step 2: Configure Tailwind CSS v4.1 (2 minutes)

### 2.1 Update `vite.config.ts`

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [
    tailwindcss(), // MUST be before react()
    react()
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
```

### 2.2 Update `src/index.css`

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
}

/* Global styles */
body {
  @apply font-sans antialiased;
}
```

### 2.3 Update `tsconfig.json`

```json
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

---

## Step 3: Generate API Types (2 minutes)

### 3.1 Create API Client Directory

```bash
mkdir -p src/lib src/types
```

### 3.2 Generate Types from OpenAPI

```bash
# Ensure Bun API is running on port 3000
bunx openapi-typescript http://localhost:3000/docs/json -o src/types/api.ts
```

**Expected output:** `src/types/api.ts` file created with auto-generated types

### 3.3 Create API Client

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
  },
  onResponse: (res) => {
    // Redirect to login on 401
    if (res.status === 401) {
      localStorage.removeItem('jwt_token')
      localStorage.removeItem('user_role')
      window.location.href = '/login?expired=true'
    }
  }
})
```

---

## Step 4: Setup TanStack Query (1 minute)

### 4.1 Update `src/main.tsx`

```tsx
// src/main.tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Theme } from '@radix-ui/themes'
import '@radix-ui/themes/styles.css'
import './index.css'
import App from './App'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes
      retry: 1,
      refetchOnWindowFocus: true
    }
  }
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Theme accentColor="blue" grayColor="slate" radius="medium">
        <App />
      </Theme>
    </QueryClientProvider>
  </StrictMode>
)
```

---

## Step 5: Create Basic Routing (3 minutes)

### 5.1 Create Route Structure

```bash
mkdir -p src/pages src/components/shared
```

### 5.2 Create Pages

```tsx
// src/pages/CatalogPage.tsx
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export function CatalogPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['catalog'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/catalog')
      if (error) throw error
      return data
    }
  })

  if (isLoading) return <div>Loading...</div>
  if (error) return <div>Error: {error.message}</div>

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-4">Product Catalog</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {data?.map((product) => (
          <div key={product.id} className="border rounded-lg p-4 shadow">
            <h2 className="text-xl font-semibold">{product.name}</h2>
            <p className="text-gray-600">{product.sku}</p>
            <p className="text-2xl font-bold mt-2">${product.price.toFixed(2)}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
```

```tsx
// src/pages/LoginPage.tsx
export function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="bg-white p-8 rounded-lg shadow-md w-96">
        <h1 className="text-2xl font-bold mb-4">Login</h1>
        <p className="text-gray-600">Login functionality coming soon...</p>
      </div>
    </div>
  )
}
```

### 5.3 Update `src/App.tsx`

```tsx
// src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { CatalogPage } from './pages/CatalogPage'
import { LoginPage } from './pages/LoginPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<CatalogPage />} />
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
```

---

## Step 6: Create Environment Variables (1 minute)

```bash
# Create .env.development
cat > .env.development << 'EOF'
VITE_API_URL=http://localhost:3000
VITE_ENV=development
EOF

# Create .env.production
cat > .env.production << 'EOF'
VITE_API_URL=https://api.marketbel.com
VITE_ENV=production
EOF

# Add to .gitignore
echo ".env.local" >> .gitignore
```

---

## Step 7: Run Development Server (1 minute)

```bash
# Start dev server
bun run dev
```

**Expected output:**

```
  VITE v5.0.8  ready in 234 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h to show help
```

**Open browser:** http://localhost:5173/

You should see:
- Product catalog page loading products from Bun API
- Products displayed in a grid layout
- Tailwind CSS styling applied

---

## Step 8: Verify Setup (2 minutes)

### 8.1 Test Catalog Page

1. Navigate to http://localhost:5173/
2. Verify products load from API
3. Check browser console for errors (should be none)
4. Check Network tab: should see GET request to `/catalog`

### 8.2 Test Type Safety

```bash
# Run TypeScript type check
bun run tsc --noEmit
```

**Expected output:** No errors

### 8.3 Test Build

```bash
# Build for production
bun run build
```

**Expected output:**

```
vite v5.0.8 building for production...
✓ 1234 modules transformed.
dist/index.html                  0.45 kB │ gzip:  0.30 kB
dist/assets/index-abc123.css    12.34 kB │ gzip:  3.21 kB
dist/assets/index-def456.js    145.67 kB │ gzip: 46.78 kB
✓ built in 3.45s
```

---

## Troubleshooting

### Issue: API types not generated

**Solution:**

```bash
# Verify Bun API is running
curl http://localhost:3000/docs/json

# If 404, check if Swagger is enabled in Bun API
# If API is running, regenerate types:
bunx openapi-typescript http://localhost:3000/docs/json -o src/types/api.ts
```

### Issue: Tailwind styles not applied

**Solution:**

1. Check `vite.config.ts`: `tailwindcss()` must be **before** `react()`
2. Check `src/index.css`: should have `@import "tailwindcss"`
3. Restart dev server: `bun run dev`

### Issue: Proxy not working

**Solution:**

Check `vite.config.ts` proxy configuration:

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:3000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, '')
    }
  }
}
```

---

## Next Steps

Now that the basic frontend is running, proceed with:

1. **Authentication:** Implement login page and JWT token management
2. **Routing:** Add protected routes for admin pages
3. **Admin Pages:** Create sales and procurement interfaces
4. **Cart:** Implement shopping cart with localStorage
5. **Testing:** Add unit and integration tests

---

## Package Scripts

Add these to `package.json`:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "lint": "eslint . --ext ts,tsx",
    "type-check": "tsc --noEmit",
    "generate-api-types": "bunx openapi-typescript http://localhost:3000/docs/json -o src/types/api.ts"
  }
}
```

**Useful commands:**

```bash
bun run dev                    # Start dev server
bun run build                  # Build for production
bun run preview                # Preview production build
bun run test                   # Run tests
bun run lint                   # Lint code
bun run type-check             # Check TypeScript types
bun run generate-api-types     # Regenerate API types
```

---

## Folder Structure (after setup)

```
services/frontend/
├── src/
│   ├── assets/
│   ├── components/
│   │   └── shared/
│   ├── hooks/
│   ├── lib/
│   │   └── api-client.ts
│   ├── pages/
│   │   ├── CatalogPage.tsx
│   │   └── LoginPage.tsx
│   ├── types/
│   │   └── api.ts (generated)
│   ├── App.tsx
│   ├── index.css
│   └── main.tsx
├── .env.development
├── .env.production
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.node.json
└── vite.config.ts
```

---

## Constitutional Compliance

This quickstart adheres to:

- **KISS:** Minimal setup, standard tools
- **Strong Typing:** TypeScript strict mode, auto-generated API types
- **Tailwind v4.1 CSS-first:** No `tailwind.config.js`, uses `@theme` blocks
- **Separation of Concerns:** Frontend presentation only, no business logic
- **Design System Consistency:** Radix UI + Tailwind CSS

---

**Time to Complete:** ~15 minutes (excluding downloads)

**Next:** Implement full feature set per `plan.md` → Phase 1: Project Setup → Phase 2: Routing & Auth → etc.
