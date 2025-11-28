# Task List: Unified Frontend Application

**Epic/Feature:** [Phase 3 Frontend App](./spec.md) | [Implementation Plan](./plan.md)

**Sprint/Milestone:** Phase 3 - Frontend Implementation

**Owner:** Development Team

---

## Overview

This task list implements a React frontend for the Marketbel product catalog system. Tasks are organized by user story to enable independent implementation and testing.

**User Stories (from spec.md):**
- **US1:** Public Catalog Browsing (Critical)
- **US2:** Shopping Cart Mock (Medium)
- **US3:** Sales Internal Catalog (High)
- **US4:** Procurement Supplier Matching (High)

---

## Phase 1: Setup

**Goal:** Initialize project with Vite, React, TypeScript, and Tailwind CSS v4.1

### Tasks

- [X] T001 Create Vite + React + TypeScript project in `services/frontend/`
- [X] T002 Install core dependencies (react, react-dom, react-router-dom, @tanstack/react-query, @tanstack/react-table, @radix-ui/themes, openapi-fetch) in `services/frontend/package.json`
- [X] T003 Install dev dependencies (typescript, vite, @vitejs/plugin-react, @tailwindcss/vite, tailwindcss, openapi-typescript, vitest, @testing-library/react) in `services/frontend/package.json`
- [X] T004 Configure Tailwind CSS v4.1 CSS-first with `@import "tailwindcss"` and `@theme` block in `services/frontend/src/index.css`
- [X] T005 Configure Vite with tailwindcss plugin BEFORE react plugin and path aliases in `services/frontend/vite.config.ts`
- [X] T006 Configure TypeScript strict mode with path aliases in `services/frontend/tsconfig.json`
- [X] T007 [P] Create environment files (.env.development, .env.production) in `services/frontend/`
- [X] T008 [P] Add npm scripts (dev, build, preview, test, lint, type-check, generate-api-types) to `services/frontend/package.json`
- [X] T009 Generate API types from Bun API OpenAPI spec to `services/frontend/src/types/api.ts`
- [X] T010 Create API client with JWT token injection and 401 redirect in `services/frontend/src/lib/api-client.ts`

**Independent Test Criteria:**
- `bun run dev` starts development server on port 5173
- `bun run type-check` passes with no errors
- API types generated successfully from running Bun API
- Tailwind CSS classes render correctly

---

## Phase 2: Foundational (Routing & Authentication)

**Goal:** Implement routing structure and JWT authentication flow (blocking for all user stories)

### Tasks

- [X] T011 Create folder structure (pages/, components/shared/, components/catalog/, components/admin/, components/cart/, hooks/, lib/, types/, contexts/) in `services/frontend/src/`
- [X] T012 Create PublicLayout component with header and navigation in `services/frontend/src/components/shared/PublicLayout.tsx`
- [X] T013 Create AdminLayout component with sidebar navigation in `services/frontend/src/components/shared/AdminLayout.tsx`
- [X] T014 Create ProtectedRoute component that redirects unauthenticated users to /login in `services/frontend/src/components/shared/ProtectedRoute.tsx`
- [X] T015 Create AuthContext with user, token, login, logout, and isAuthenticated in `services/frontend/src/contexts/AuthContext.tsx`
- [X] T016 Create useAuth hook that consumes AuthContext in `services/frontend/src/hooks/useAuth.ts`
- [X] T017 Create LoginPage with username/password form in `services/frontend/src/pages/LoginPage.tsx`
- [X] T018 Create router configuration with public and protected routes in `services/frontend/src/routes.tsx`
- [X] T019 Setup TanStack Query provider with default options (staleTime 5min, gcTime 10min) in `services/frontend/src/main.tsx`
- [X] T020 Setup Radix UI Theme provider with accentColor and grayColor in `services/frontend/src/main.tsx`
- [X] T021 Wire App.tsx with RouterProvider in `services/frontend/src/App.tsx`
- [X] T022 [P] Create query keys factory for catalog, admin, and auth queries in `services/frontend/src/lib/query-keys.ts`

**Independent Test Criteria:**
- Public routes accessible without authentication
- Protected routes (/admin/*) redirect to /login when not authenticated
- Login form submits credentials and stores JWT token
- Token included in Authorization header for API requests
- 401 responses redirect to login with expired=true parameter

---

## Phase 3: User Story 1 - Public Catalog Browsing

**Goal:** As a public client, I want to browse the product catalog, filter by category and price, and search for specific items

### Tasks

- [ ] T023 [US1] Create CatalogFilters type interface in `services/frontend/src/types/filters.ts`
- [ ] T024 [US1] Create useCatalog hook with TanStack Query for GET /catalog in `services/frontend/src/hooks/useCatalog.ts`
- [ ] T025 [US1] Create useProduct hook for GET /catalog/:id in `services/frontend/src/hooks/useProduct.ts`
- [ ] T026 [US1] Create useCategories hook for category dropdown in `services/frontend/src/hooks/useCategories.ts`
- [ ] T027 [P] [US1] Create ProductCard component with name, price, image, category in `services/frontend/src/components/catalog/ProductCard.tsx`
- [ ] T028 [P] [US1] Create ProductGrid component with responsive grid layout in `services/frontend/src/components/catalog/ProductGrid.tsx`
- [ ] T029 [US1] Create FilterBar component with category dropdown, price range inputs, debounced search in `services/frontend/src/components/catalog/FilterBar.tsx`
- [ ] T030 [US1] Create CatalogPage that composes FilterBar and ProductGrid in `services/frontend/src/pages/CatalogPage.tsx`
- [ ] T031 [US1] Implement URL query parameter sync for filters (shareable links) in `services/frontend/src/pages/CatalogPage.tsx`
- [ ] T032 [US1] Create ProductDetailPage with all characteristics and back navigation in `services/frontend/src/pages/ProductDetailPage.tsx`
- [ ] T033 [US1] Add loading skeleton components for catalog and product detail in `services/frontend/src/components/shared/LoadingSkeleton.tsx`
- [ ] T034 [US1] Add error state components with retry button in `services/frontend/src/components/shared/ErrorState.tsx`

**Independent Test Criteria:**
- Catalog page loads and displays products from API
- Category filter updates product list
- Price range filter (min/max) works correctly
- Search input debounces (300ms) and filters results
- Filters preserved in URL (copy/paste URL restores filters)
- Product detail page shows full information
- Mobile responsive (1 column < 640px, 2 columns 640-1024px, 3 columns > 1024px)

---

## Phase 4: User Story 2 - Shopping Cart Mock

**Goal:** As a public client, I want to add products to a cart and proceed through a mock checkout

### Tasks

- [ ] T035 [US2] Create CartItem and Cart type interfaces in `services/frontend/src/types/cart.ts`
- [ ] T036 [US2] Create CartContext with useReducer for cart state management in `services/frontend/src/contexts/CartContext.tsx`
- [ ] T037 [US2] Implement localStorage persistence (save on change, load on mount) in `services/frontend/src/contexts/CartContext.tsx`
- [ ] T038 [US2] Create useCart hook with addItem, removeItem, updateQuantity, clearCart actions in `services/frontend/src/hooks/useCart.ts`
- [ ] T039 [P] [US2] Create CartIcon component with item count badge for header in `services/frontend/src/components/cart/CartIcon.tsx`
- [ ] T040 [P] [US2] Create CartItem component with quantity controls (+/-) in `services/frontend/src/components/cart/CartItem.tsx`
- [ ] T041 [US2] Create CartSummary component with subtotal, tax, total calculations in `services/frontend/src/components/cart/CartSummary.tsx`
- [ ] T042 [US2] Create CartPage displaying all items with quantity controls in `services/frontend/src/pages/CartPage.tsx`
- [ ] T043 [US2] Add "Add to Cart" button to ProductCard and ProductDetailPage in `services/frontend/src/components/catalog/ProductCard.tsx`
- [ ] T044 [US2] Create CheckoutMockPage with shipping/billing form (display-only, no validation) in `services/frontend/src/pages/CheckoutMockPage.tsx`
- [ ] T045 [US2] Create OrderSuccessPage shown after "Place Order" click in `services/frontend/src/pages/OrderSuccessPage.tsx`
- [ ] T046 [US2] Add cart routes (/cart, /checkout, /order-success) to router in `services/frontend/src/routes.tsx`

**Independent Test Criteria:**
- "Add to Cart" button adds item to cart
- Cart icon shows correct item count
- Cart page displays all items with quantities
- Quantity controls update item counts
- Cart totals calculate correctly (subtotal + mock tax)
- Cart persists in localStorage across page refreshes
- Checkout form displays (no validation required)
- "Place Order" shows success message

---

## Phase 5: User Story 3 - Sales Internal Catalog

**Goal:** As a sales team member, I want to view products with margins and supplier comparisons

### Tasks

- [ ] T047 [US3] Create AdminProductFilters type interface in `services/frontend/src/types/filters.ts`
- [ ] T048 [US3] Create useAdminProducts hook for GET /admin/products with pricing in `services/frontend/src/hooks/useAdminProducts.ts`
- [ ] T049 [US3] Create useAdminProduct hook for GET /admin/products/:id with supplier items in `services/frontend/src/hooks/useAdminProduct.ts`
- [ ] T050 [US3] Create SalesTable component using TanStack Table with columns (name, SKU, selling price, cost price, margin%, category) in `services/frontend/src/components/admin/SalesTable.tsx`
- [ ] T051 [US3] Implement column sorting (click header to sort) in SalesTable in `services/frontend/src/components/admin/SalesTable.tsx`
- [ ] T052 [US3] Create SalesFilterBar with category, margin range, status filters in `services/frontend/src/components/admin/SalesFilterBar.tsx`
- [ ] T053 [US3] Create SalesCatalogPage composing SalesFilterBar and SalesTable in `services/frontend/src/pages/admin/SalesCatalogPage.tsx`
- [ ] T054 [US3] Create InternalProductDetailPage with supplier items and price history in `services/frontend/src/pages/admin/InternalProductDetailPage.tsx`
- [ ] T055 [US3] Create SupplierComparison component showing all linked supplier items in `services/frontend/src/components/admin/SupplierComparison.tsx`
- [ ] T056 [US3] Add admin sales routes (/admin/sales, /admin/products/:id) to router in `services/frontend/src/routes.tsx`

**Independent Test Criteria:**
- /admin/sales requires JWT authentication (redirects if not logged in)
- Table shows all columns (name, SKU, selling price, cost price, margin%, category)
- Margin calculated as ((selling_price - cost_price) / selling_price) * 100
- Columns sortable by clicking headers
- Filters work (category, margin range, status)
- Clicking product row opens detail with supplier items
- Only sales/admin roles can access (403 for other roles)

---

## Phase 6: User Story 4 - Procurement Supplier Matching

**Goal:** As a procurement team member, I want to link supplier items to internal products

### Tasks

- [ ] T057 [US4] Create ProcurementFilters type interface in `services/frontend/src/types/filters.ts`
- [ ] T058 [US4] Create useUnmatchedItems hook for GET /admin/suppliers/unmatched in `services/frontend/src/hooks/useUnmatchedItems.ts`
- [ ] T059 [US4] Create useMatchSupplier mutation hook for PATCH /admin/products/:id/match with optimistic updates in `services/frontend/src/hooks/useMatchSupplier.ts`
- [ ] T060 [US4] Create UnmatchedItemsTable component with TanStack Table in `services/frontend/src/components/admin/UnmatchedItemsTable.tsx`
- [ ] T061 [US4] Create ProductSearchModal with fuzzy search for products in `services/frontend/src/components/admin/ProductSearchModal.tsx`
- [ ] T062 [US4] Create useProductSearch hook for modal search functionality in `services/frontend/src/hooks/useProductSearch.ts`
- [ ] T063 [US4] Create MatchedItemsSection showing product ↔ supplier item associations in `services/frontend/src/components/admin/MatchedItemsSection.tsx`
- [ ] T064 [US4] Create ProcurementMatchingPage composing UnmatchedItemsTable and MatchedItemsSection in `services/frontend/src/pages/admin/ProcurementMatchingPage.tsx`
- [ ] T065 [US4] Implement "Link to Product" button that opens ProductSearchModal in `services/frontend/src/components/admin/UnmatchedItemsTable.tsx`
- [ ] T066 [US4] Implement "Unlink" button with confirmation in MatchedItemsSection in `services/frontend/src/components/admin/MatchedItemsSection.tsx`
- [ ] T067 [US4] Create Toast/Notification component for match/unmatch success messages in `services/frontend/src/components/shared/Toast.tsx`
- [ ] T068 [US4] Add procurement routes (/admin/procurement) to router in `services/frontend/src/routes.tsx`

**Independent Test Criteria:**
- /admin/procurement requires JWT authentication
- Unmatched supplier items displayed in table
- "Link to Product" opens search modal
- Product search returns fuzzy matches
- Selecting product creates match (PATCH request)
- UI updates optimistically (item moves to matched section)
- Success notification shown after match
- "Unlink" button removes association
- Only procurement/admin roles can access

---

## Phase 7: Polish & Cross-Cutting Concerns

**Goal:** Improve UX, accessibility, and code quality

### Tasks

- [ ] T069 [P] Create Button component with variants (primary, secondary, danger, ghost) in `services/frontend/src/components/shared/Button.tsx`
- [ ] T070 [P] Create Input component with label, error, helperText props in `services/frontend/src/components/shared/Input.tsx`
- [ ] T071 [P] Create Select component for dropdowns in `services/frontend/src/components/shared/Select.tsx`
- [ ] T072 Create ErrorBoundary component with fallback UI in `services/frontend/src/components/shared/ErrorBoundary.tsx`
- [ ] T073 Wrap root app with ErrorBoundary in `services/frontend/src/main.tsx`
- [ ] T074 Add aria-labels and semantic HTML to all interactive elements in all component files
- [ ] T075 Add keyboard navigation support (tab order, focus management) to modal and form components
- [ ] T076 [P] Create Header component with logo, navigation, cart icon, user menu in `services/frontend/src/components/shared/Header.tsx`
- [ ] T077 [P] Create Footer component with copyright and links in `services/frontend/src/components/shared/Footer.tsx`
- [ ] T078 Add Dockerfile for production build in `services/frontend/Dockerfile`
- [ ] T079 Update docker-compose.yml with frontend service in `docker-compose.yml`
- [ ] T080 Create README with setup instructions, npm scripts, and architecture overview in `services/frontend/README.md`

**Polish Criteria:**
- All buttons have consistent styling via Button component
- All inputs have labels and error states
- Error boundaries prevent white screen crashes
- WCAG 2.1 Level AA accessibility compliance
- Docker container builds and runs successfully

---

## Dependencies

### Task Dependency Graph

```
Phase 1 (Setup)
├── T001 → T002 → T003 → T004 → T005 → T006 → T009 → T010
│                                       ↓
│                              T007 (parallel)
│                              T008 (parallel)

Phase 2 (Auth) - depends on Phase 1
├── T011 → T012, T013 → T014 → T015 → T016 → T017
│                                       ↓
│                              T018 → T019 → T020 → T021
│                                       ↓
│                              T022 (parallel)

Phase 3 (US1) - depends on Phase 2
├── T023 → T024 → T025 → T026
│    ↓                    ↓
│   T027 (P) ←───────────┘
│   T028 (P)
│    ↓
├── T029 → T030 → T031
│                  ↓
├── T032 → T033 (P) → T034 (P)

Phase 4 (US2) - depends on Phase 2, parallel with Phase 3
├── T035 → T036 → T037 → T038
│    ↓                    ↓
│   T039 (P) ←───────────┘
│   T040 (P)
│    ↓
├── T041 → T042 → T043 → T044 → T045 → T046

Phase 5 (US3) - depends on Phase 2, parallel with Phase 3/4
├── T047 → T048 → T049
│    ↓           ↓
├── T050 → T051 → T052 → T053 → T054 → T055 → T056

Phase 6 (US4) - depends on Phase 2, parallel with Phase 3/4/5
├── T057 → T058 → T059
│    ↓           ↓
├── T060 → T061 → T062 → T063 → T064 → T065 → T066 → T067 → T068

Phase 7 (Polish) - depends on all previous phases
├── T069-T071 (P) - can be done anytime
├── T072 → T073
├── T074-T075 - after all components exist
├── T076-T077 (P) - can be done anytime
├── T078-T080 - final tasks
```

### User Story Completion Order

1. **Phase 1: Setup** → Required first
2. **Phase 2: Auth** → Required before any user story
3. **User Stories (Parallel)**:
   - US1 (Public Catalog) - Critical, start first
   - US2 (Cart Mock) - Can parallel with US1
   - US3 (Sales Catalog) - Can parallel with US1/US2
   - US4 (Procurement Matching) - Can parallel with US1/US2/US3
4. **Phase 7: Polish** → After all user stories

---

## Parallel Execution Examples

### Example 1: Two Developers

**Developer A:**
- Phase 1 (T001-T010)
- Phase 2 (T011-T022)
- Phase 3 (US1: T023-T034)
- Phase 5 (US3: T047-T056)

**Developer B:**
- Wait for Phase 2 completion
- Phase 4 (US2: T035-T046)
- Phase 6 (US4: T057-T068)
- Phase 7 (T069-T080)

### Example 2: Three Developers

**Developer A:**
- Phase 1 (T001-T010)
- Phase 2 (T011-T022)

**Developer B (after Phase 2):**
- Phase 3 (US1: T023-T034)
- Phase 5 (US3: T047-T056)

**Developer C (after Phase 2):**
- Phase 4 (US2: T035-T046)
- Phase 6 (US4: T057-T068)
- Phase 7 (T069-T080)

---

## Implementation Strategy

### MVP Scope (Recommended First Iteration)

**Phase 1 + Phase 2 + User Story 1 (US1)**

This delivers:
- Working public catalog with filtering and search
- Product detail pages
- Mobile responsive design
- Foundation for remaining features

**Estimated Effort:** 5-7 days (single developer)

### Full Feature Scope

All phases implemented in order:

| Phase | Tasks | Estimated Effort |
|-------|-------|------------------|
| Phase 1: Setup | T001-T010 | 1 day |
| Phase 2: Auth | T011-T022 | 2 days |
| Phase 3: US1 | T023-T034 | 3 days |
| Phase 4: US2 | T035-T046 | 2 days |
| Phase 5: US3 | T047-T056 | 2-3 days |
| Phase 6: US4 | T057-T068 | 2-3 days |
| Phase 7: Polish | T069-T080 | 2 days |
| **Total** | **80 tasks** | **14-18 days** |

---

## Task Summary

- **Total Tasks:** 80
- **Phase 1 (Setup):** 10 tasks
- **Phase 2 (Auth):** 12 tasks
- **Phase 3 (US1):** 12 tasks
- **Phase 4 (US2):** 12 tasks
- **Phase 5 (US3):** 10 tasks
- **Phase 6 (US4):** 12 tasks
- **Phase 7 (Polish):** 12 tasks

### Parallelizable Tasks

Tasks marked with `[P]` can be executed in parallel with other tasks:
- T007, T008 (Setup)
- T022 (Auth)
- T027, T028, T033, T034 (US1)
- T039, T040 (US2)
- T069, T070, T071, T076, T077 (Polish)

### Constitutional Compliance

All tasks adhere to:
- **KISS:** Standard React patterns, no over-engineering
- **Strong Typing:** TypeScript strict mode, auto-generated API types
- **Tailwind v4.1 CSS-first:** No tailwind.config.js
- **Separation of Concerns:** Components → Hooks → API Client
- **DRY:** Shared components, generated types
- **Accessibility:** Semantic HTML, ARIA labels, keyboard navigation

---

## Notes

- Each user story phase is independently testable
- Tasks should be committed frequently with descriptive messages
- Run `bun run type-check` after each task to catch type errors early
- Test with Bun API running on port 3000
- Consult `mcp 21st-dev/magic` for UI component inspiration during implementation

