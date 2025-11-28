# Marketbel Frontend

React-based web application for the Marketbel product catalog system. Provides role-based access for public catalog browsing, sales team analysis, and procurement supplier matching.

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| **React** | 19.x | UI framework |
| **TypeScript** | 5.9+ | Type safety |
| **Vite** | 7.x | Build tool & dev server |
| **Bun** | Latest | JavaScript runtime & package manager |
| **TanStack Query** | 5.x | Server state management |
| **TanStack Table** | 8.x | Data tables |
| **React Router** | 7.x | Client-side routing |
| **Radix UI Themes** | 3.x | Accessible UI components |
| **Tailwind CSS** | 4.1.x | CSS-first styling |

## Quick Start

### Prerequisites

- [Bun](https://bun.sh/) (latest version)
- Bun API running on `http://localhost:3000` (see `services/bun-api/`)

### Development

```bash
# Install dependencies
bun install

# Start development server
bun run dev
# → Opens http://localhost:5173

# Run type check
bun run type-check

# Run linter
bun run lint

# Run tests
bun test
```

### Production Build

```bash
# Build for production
bun run build

# Preview production build locally
bun run preview

# Build Docker image
docker build -t marketbel-frontend .

# Run with Docker
docker run -p 80:80 marketbel-frontend
```

## Project Structure

```
src/
├── components/
│   ├── admin/          # Admin-specific components
│   │   ├── MatchedItemsSection.tsx
│   │   ├── ProductSearchModal.tsx
│   │   ├── SalesFilterBar.tsx
│   │   ├── SalesTable.tsx
│   │   ├── SupplierComparison.tsx
│   │   └── UnmatchedItemsTable.tsx
│   ├── cart/           # Shopping cart components
│   │   ├── CartIcon.tsx
│   │   ├── CartItemRow.tsx
│   │   └── CartSummary.tsx
│   ├── catalog/        # Public catalog components
│   │   ├── FilterBar.tsx
│   │   ├── ProductCard.tsx
│   │   └── ProductGrid.tsx
│   └── shared/         # Reusable UI components
│       ├── AdminLayout.tsx
│       ├── Button.tsx
│       ├── ErrorBoundary.tsx
│       ├── ErrorState.tsx
│       ├── Input.tsx
│       ├── LoadingSkeleton.tsx
│       ├── ProtectedRoute.tsx
│       ├── PublicLayout.tsx
│       ├── Select.tsx
│       └── Toast.tsx
├── contexts/
│   ├── AuthContext.tsx     # JWT authentication state
│   └── CartContext.tsx     # Shopping cart state
├── hooks/
│   ├── useAdminProduct.ts  # Single product (admin)
│   ├── useAdminProducts.ts # Product list (admin)
│   ├── useAuth.ts          # Authentication hook
│   ├── useCart.ts          # Cart operations
│   ├── useCatalog.ts       # Public catalog
│   ├── useCategories.ts    # Category list
│   ├── useMatchSupplier.ts # Link/unlink supplier items
│   ├── useProductSearch.ts # Product search (modal)
│   └── useUnmatchedItems.ts # Unmatched supplier items
├── lib/
│   ├── api-client.ts   # OpenAPI fetch client
│   ├── query-keys.ts   # TanStack Query key factory
│   └── utils.ts        # Helper functions
├── pages/
│   ├── admin/
│   │   ├── InternalProductDetailPage.tsx
│   │   ├── ProcurementMatchingPage.tsx
│   │   └── SalesCatalogPage.tsx
│   ├── CartPage.tsx
│   ├── CatalogPage.tsx
│   ├── CheckoutMockPage.tsx
│   ├── LoginPage.tsx
│   ├── OrderSuccessPage.tsx
│   └── ProductDetailPage.tsx
├── types/
│   ├── api.ts          # Auto-generated API types
│   ├── auth.ts         # Authentication types
│   ├── cart.ts         # Cart types
│   └── filters.ts      # Filter types
├── App.tsx             # Root component
├── main.tsx            # Entry point
├── routes.tsx          # Route configuration
└── index.css           # Tailwind CSS config
```

## Routes

### Public Routes

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | CatalogPage | Product catalog with filters |
| `/product/:id` | ProductDetailPage | Product details |
| `/cart` | CartPage | Shopping cart |
| `/checkout` | CheckoutMockPage | Mock checkout form |
| `/order-success` | OrderSuccessPage | Order confirmation |
| `/login` | LoginPage | Authentication |

### Admin Routes (Protected)

| Route | Component | Required Role |
|-------|-----------|---------------|
| `/admin` | Dashboard | admin, sales, procurement |
| `/admin/sales` | SalesCatalogPage | admin, sales |
| `/admin/products/:id` | InternalProductDetailPage | admin, sales |
| `/admin/procurement` | ProcurementMatchingPage | admin, procurement |

## Authentication

The app uses JWT tokens for authentication. Token is stored in localStorage and automatically included in API requests.

**Demo Credentials:**

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin123` |
| Sales | `sales` | `sales123` |
| Procurement | `procurement` | `procurement123` |

## API Client

Types are auto-generated from the Bun API OpenAPI specification:

```bash
# Regenerate API types (requires Bun API running)
bun run generate-api-types
```

Example usage:

```tsx
import { apiClient } from '@/lib/api-client'

// Fetch products with type safety
const response = await apiClient.GET('/catalog', {
  params: { query: { category_id: '123', limit: 20 } }
})

if (response.data) {
  // response.data is fully typed
  response.data.items.forEach(product => console.log(product.name))
}
```

## State Management

| State Type | Solution | Scope |
|------------|----------|-------|
| Server State | TanStack Query | API data caching |
| Auth State | React Context | User + JWT token |
| Cart State | React Context + localStorage | Cart items |
| UI State | Component state | Forms, modals |

## Styling

Using **Tailwind CSS v4.1** with CSS-first configuration:

```css
/* src/index.css */
@import "tailwindcss";

@theme {
  --color-primary: #2563eb;
  --color-danger: #dc2626;
  /* ... */
}
```

**NO** `tailwind.config.js` file - all configuration via `@theme` blocks.

## Shared Components

### Button

```tsx
import { Button } from '@/components/shared'

<Button variant="primary">Save</Button>
<Button variant="danger" icon={<TrashIcon />}>Delete</Button>
<Button variant="ghost" loading>Loading...</Button>
```

Variants: `primary`, `secondary`, `danger`, `ghost`
Sizes: `sm`, `md`, `lg`

### Input

```tsx
import { Input } from '@/components/shared'

<Input label="Email" type="email" error="Invalid email" />
<Input label="Name" helperText="Your full name" />
```

### Select

```tsx
import { Select } from '@/components/shared'

<Select
  label="Category"
  options={[
    { value: '1', label: 'Electronics' },
    { value: '2', label: 'Clothing' },
  ]}
  error="Please select a category"
/>
```

## Environment Variables

```bash
# .env.development
VITE_API_URL=http://localhost:3000
VITE_ENV=development

# .env.production
VITE_API_URL=https://api.marketbel.com
VITE_ENV=production
```

## Docker

```bash
# Build image
docker build -t marketbel-frontend \
  --build-arg VITE_API_URL=https://api.example.com \
  .

# Run container
docker run -p 80:80 marketbel-frontend

# Or use docker-compose from project root
docker-compose up frontend
```

## Testing

```bash
# Run all tests
bun test

# Run with coverage
bun test --coverage

# Run specific test file
bun test src/hooks/useAuth.test.ts
```

## Performance Targets

| Metric | Target |
|--------|--------|
| Initial Load | < 3 seconds (3G) |
| Catalog Render | < 2 seconds (100 products) |
| Filter Response | < 500ms |
| Bundle Size | < 200KB gzipped |
| Lighthouse Score | > 80 |

## Accessibility

- WCAG 2.1 Level AA compliance
- Semantic HTML throughout
- ARIA labels on interactive elements
- Keyboard navigation support
- Focus management for modals
- Color contrast requirements met

## Browser Support

- Chrome (latest 2 versions)
- Firefox (latest 2 versions)
- Safari (latest 2 versions)
- Edge (latest 2 versions)

## License

Internal use only - Marketbel © 2025
