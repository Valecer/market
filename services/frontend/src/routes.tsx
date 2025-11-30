/**
 * Router Configuration
 *
 * Defines all routes for the application with proper nesting.
 * Public routes use PublicLayout, admin routes use AdminLayout.
 *
 * Route Structure:
 * - / (public) → CatalogPage
 * - /product/:id (public) → ProductDetailPage
 * - /cart (public) → CartPage
 * - /checkout (public) → CheckoutMockPage
 * - /order-success (public) → OrderSuccessPage
 * - /login → LoginPage
 * - /admin (protected) → Admin Dashboard
 * - /admin/sales (protected, sales|admin) → SalesCatalogPage
 * - /admin/procurement (protected, procurement|admin) → ProcurementMatchingPage
 */

import { createBrowserRouter } from 'react-router-dom'
import { PublicLayout } from '@/components/shared/PublicLayout'
import { AdminLayout } from '@/components/shared/AdminLayout'
import { ProtectedRoute } from '@/components/shared/ProtectedRoute'
import { LoginPage } from '@/pages/LoginPage'
import { CatalogPage } from '@/pages/CatalogPage'
import { ProductDetailPage } from '@/pages/ProductDetailPage'
import { CartPage } from '@/pages/CartPage'
import { CheckoutMockPage } from '@/pages/CheckoutMockPage'
import { OrderSuccessPage } from '@/pages/OrderSuccessPage'
import { SalesCatalogPage } from '@/pages/admin/SalesCatalogPage'
import { InternalProductDetailPage } from '@/pages/admin/InternalProductDetailPage'
import { ProcurementMatchingPage } from '@/pages/admin/ProcurementMatchingPage'

// =============================================================================
// Placeholder Pages (will be replaced in later phases)
// =============================================================================

function AdminDashboardPlaceholder() {
  return (
    <div className="bg-white rounded-lg shadow-md p-8">
      <h2 className="text-xl font-semibold text-slate-900 mb-4">
        Admin Dashboard
      </h2>
      <p className="text-slate-500 mb-6">
        Welcome to the admin area. Select a section from the sidebar to get started.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 bg-slate-50 rounded-lg border border-border">
          <h3 className="font-medium text-slate-900 mb-1">Sales Catalog</h3>
          <p className="text-sm text-slate-500">
            View products with margins and supplier comparisons
          </p>
        </div>
        <div className="p-4 bg-slate-50 rounded-lg border border-border">
          <h3 className="font-medium text-slate-900 mb-1">Procurement</h3>
          <p className="text-sm text-slate-500">
            Link supplier items to internal products
          </p>
        </div>
      </div>
    </div>
  )
}

// SalesCatalogPlaceholder removed - now using actual SalesCatalogPage component

// ProcurementPlaceholder removed - now using actual ProcurementMatchingPage component

// AdminProductDetailPlaceholder removed - now using actual InternalProductDetailPage component


function UnauthorizedPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="bg-white rounded-lg shadow-md p-8 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-danger/10 mb-4">
          <svg
            className="w-8 h-8 text-danger"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-slate-900 mb-2">
          Access Denied
        </h2>
        <p className="text-slate-500 mb-4">
          You don't have permission to access this page.
        </p>
        <a
          href="/"
          className="inline-block px-4 py-2 bg-primary text-white rounded-md hover:bg-primary/90"
        >
          Go to Home
        </a>
      </div>
    </div>
  )
}

function NotFoundPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="bg-white rounded-lg shadow-md p-8 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-muted/20 mb-4">
          <span className="text-4xl font-bold text-muted">404</span>
        </div>
        <h2 className="text-xl font-semibold text-slate-900 mb-2">
          Page Not Found
        </h2>
        <p className="text-slate-500 mb-4">
          The page you're looking for doesn't exist.
        </p>
        <a
          href="/"
          className="inline-block px-4 py-2 bg-primary text-white rounded-md hover:bg-primary/90"
        >
          Go to Home
        </a>
      </div>
    </div>
  )
}

// =============================================================================
// Router Configuration
// =============================================================================

export const router = createBrowserRouter([
  // Public routes with PublicLayout
  {
    path: '/',
    element: <PublicLayout />,
    children: [
      {
        index: true,
        element: <CatalogPage />,
      },
      {
        path: 'product/:id',
        element: <ProductDetailPage />,
      },
      {
        path: 'cart',
        element: <CartPage />,
      },
      {
        path: 'checkout',
        element: <CheckoutMockPage />,
      },
      {
        path: 'order-success',
        element: <OrderSuccessPage />,
      },
      {
        path: 'unauthorized',
        element: <UnauthorizedPage />,
      },
    ],
  },

  // Login page (no layout)
  {
    path: '/login',
    element: <LoginPage />,
  },

  // Admin routes with AdminLayout (protected)
  {
    path: '/admin',
    element: (
      <ProtectedRoute allowedRoles={['admin', 'sales', 'procurement']}>
        <AdminLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <AdminDashboardPlaceholder />,
      },
      {
        path: 'sales',
        element: (
          <ProtectedRoute allowedRoles={['admin', 'sales']}>
            <SalesCatalogPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'products/:id',
        element: (
          <ProtectedRoute allowedRoles={['admin', 'sales']}>
            <InternalProductDetailPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'procurement',
        element: (
          <ProtectedRoute allowedRoles={['admin', 'procurement']}>
            <ProcurementMatchingPage />
          </ProtectedRoute>
        ),
      },
    ],
  },

  // Catch-all for 404
  {
    path: '*',
    element: <PublicLayout />,
    children: [
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
])

