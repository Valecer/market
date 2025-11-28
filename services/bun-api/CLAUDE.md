---
description: Use Bun instead of Node.js, npm, pnpm, or vite.
globs: "*.ts, *.tsx, *.html, *.css, *.js, *.jsx, package.json"
alwaysApply: false
---

Default to using Bun instead of Node.js.

- Use `bun <file>` instead of `node <file>` or `ts-node <file>`
- Use `bun test` instead of `jest` or `vitest`
- Use `bun build <file.html|file.ts|file.css>` instead of `webpack` or `esbuild`
- Use `bun install` instead of `npm install` or `yarn install` or `pnpm install`
- Use `bun run <script>` instead of `npm run <script>` or `yarn run <script>` or `pnpm run <script>`
- Bun automatically loads .env, so don't use dotenv.

## APIs

- `Bun.serve()` supports WebSockets, HTTPS, and routes. Don't use `express`.
- `bun:sqlite` for SQLite. Don't use `better-sqlite3`.
- `Bun.redis` for Redis. Don't use `ioredis`.
- `Bun.sql` for Postgres. Don't use `pg` or `postgres.js`.
- `WebSocket` is built-in. Don't use `ws`.
- Prefer `Bun.file` over `node:fs`'s readFile/writeFile
- Bun.$`ls` instead of execa.

## Testing

Use `bun test` to run tests.

```ts#index.test.ts
import { test, expect } from "bun:test";

test("hello world", () => {
  expect(1).toBe(1);
});
```

## Frontend

Use HTML imports with `Bun.serve()`. Don't use `vite`. HTML imports fully support React, CSS, Tailwind.

Server:

```ts#index.ts
import index from "./index.html"

Bun.serve({
  routes: {
    "/": index,
    "/api/users/:id": {
      GET: (req) => {
        return new Response(JSON.stringify({ id: req.params.id }));
      },
    },
  },
  // optional websocket support
  websocket: {
    open: (ws) => {
      ws.send("Hello, world!");
    },
    message: (ws, message) => {
      ws.send(message);
    },
    close: (ws) => {
      // handle close
    }
  },
  development: {
    hmr: true,
    console: true,
  }
})
```

HTML files can import .tsx, .jsx or .js files directly and Bun's bundler will transpile & bundle automatically. `<link>` tags can point to stylesheets and Bun's CSS bundler will bundle.

```html#index.html
<html>
  <body>
    <h1>Hello, world!</h1>
    <script type="module" src="./frontend.tsx"></script>
  </body>
</html>
```

With the following `frontend.tsx`:

```tsx#frontend.tsx
import React from "react";

// import .css files directly and it works
import './index.css';

import { createRoot } from "react-dom/client";

const root = createRoot(document.body);

export default function Frontend() {
  return <h1>Hello, world!</h1>;
}

root.render(<Frontend />);
```

Then, run index.ts

```sh
bun --hot ./index.ts
```

For more information, read the Bun API docs in `node_modules/bun-types/docs/**.md`.

## ElysiaJS Plugin Scoping

### Problem: Plugin Context Isolation

When creating a new Elysia instance with `new Elysia()`, it creates an **isolated scope**. Plugins from the parent app (like JWT) are **not automatically inherited** by child instances.

**❌ Incorrect Pattern (Isolated Scope):**
```typescript
// This creates an isolated scope - JWT plugin from parent won't be accessible
export const authMiddleware = new Elysia({ name: 'auth' })
  .derive(async ({ jwt, headers }) => {
    // jwt will be undefined or not accessible here!
    const payload = await jwt.verify(token)
  })
```

### Solution: Functional Plugin Pattern

Use a **functional plugin pattern** - export a function that takes the app instance and returns it with your middleware. This ensures the middleware uses the parent app's context where plugins are already initialized.

**✅ Correct Pattern (Functional Plugin):**
```typescript
// Export a function that receives the parent app instance
export const authMiddleware = (app: Elysia) =>
  app.derive(async ({ jwt, headers }) => {
    // jwt is now accessible from parent app's context!
    const payload = await jwt.verify(token)
    return { user: payload }
  })
```

**Usage:**
```typescript
const app = new Elysia()
  .use(jwt({ name: 'jwt', secret: '...' }))
  .use(authMiddleware) // Elysia automatically calls the function with app context
  .get('/protected', ({ user }) => {
    // user is available here
  })
```

### Why This Works

1. **Context Sharing**: The function receives the parent app instance, which already has the JWT plugin registered
2. **No Isolation**: The middleware is added directly to the parent app, not as a separate isolated instance
3. **Plugin Access**: All plugins from the parent (like `jwt`) are accessible in `derive` functions

### When to Use Each Pattern

- **Functional Plugin Pattern** (`(app) => app.derive(...)`): 
  - ✅ When middleware needs access to plugins from parent app
  - ✅ When using `derive` to enrich context
  - ✅ For authentication/authorization middleware

- **Instance Pattern** (`new Elysia().derive(...)`):
  - ✅ When middleware is completely self-contained
  - ✅ When middleware doesn't need parent plugins
  - ✅ For reusable, independent middleware modules

### Example: Auth Middleware

```typescript
// src/middleware/auth.ts
import { Elysia } from 'elysia'
import type { JWTPayload } from '../types/auth.types'

export const authMiddleware = (app: Elysia) =>
  app.derive(async ({ jwt, headers }) => {
    const authHeader = headers.authorization
    
    if (!authHeader?.startsWith('Bearer ')) {
      return { user: null }
    }
    
    const token = authHeader.substring(7)
    const payload = await jwt.verify(token)
    
    return {
      user: payload as JWTPayload | null,
    }
  })
```

### Testing Context

**In tests, `new Elysia()` is the correct pattern** because:
- Tests create isolated app instances from scratch
- Each test app initializes its own plugins (JWT, error handler, etc.)
- No parent app context exists to share plugins from
- Functional plugin pattern is only needed when middleware must access plugins from a parent app

**Example in tests:**
```typescript
// tests/helpers.ts - Correct for tests
export function createAuthTestApp() {
  return new Elysia()  // ✅ Correct - creating isolated test app
    .use(errorHandler)
    .use(jwt({ name: 'jwt', secret: '...' }))
    .use(authController)
}
```

**Example in middleware:**
```typescript
// src/middleware/auth.ts - Must use functional pattern
export const authMiddleware = (app: Elysia) =>  // ✅ Correct - needs parent JWT plugin
  app.derive(async ({ jwt, headers }) => {
    // jwt is from parent app's context
  })
```

### References

- See `src/middleware/auth.ts` for auth middleware implementation
- See `src/middleware/rbac.ts` for RBAC implementation with type assertions
- See `src/controllers/auth/index.ts` for controller using functional pattern
- See `src/controllers/admin/index.ts` for controller using functional pattern with group
- See `tests/helpers.ts` for test app creation patterns
- Elysia Plugin Documentation: https://elysiajs.com/essential/plugin
