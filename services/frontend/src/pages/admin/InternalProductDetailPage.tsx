/**
 * InternalProductDetailPage
 *
 * Admin view of a single product with detailed information,
 * supplier comparisons, and price history.
 *
 * Features:
 * - Product information header with status badge
 * - Supplier comparison cards with price analysis
 * - Price history chart (future enhancement)
 * - Back navigation
 *
 * Route: /admin/products/:id
 * Roles: sales, admin
 */

import { useParams, useNavigate, Link } from 'react-router-dom'
import { useAdminProduct } from '@/hooks/useAdminProduct'
import { SupplierComparison } from '@/components/admin/SupplierComparison'
import { ErrorState } from '@/components/shared/ErrorState'
import { LoadingSkeleton } from '@/components/shared/LoadingSkeleton'

// =============================================================================
// Helpers
// =============================================================================

/**
 * Format currency display
 */
function formatCurrency(value: string | number): string {
  const numValue = typeof value === 'string' ? parseFloat(value) : value
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(numValue)
}

/**
 * Get lowest price from supplier items
 */
function getLowestPrice(supplierItems: Array<{ current_price: string }>): number {
  if (supplierItems.length === 0) return 0
  return Math.min(...supplierItems.map((item) => parseFloat(item.current_price)))
}

/**
 * Get highest price from supplier items
 */
function getHighestPrice(supplierItems: Array<{ current_price: string }>): number {
  if (supplierItems.length === 0) return 0
  return Math.max(...supplierItems.map((item) => parseFloat(item.current_price)))
}

/**
 * Get status badge styling
 */
function getStatusBadge(status: 'draft' | 'active' | 'archived'): { text: string; className: string } {
  switch (status) {
    case 'active':
      return {
        text: 'Active',
        className: 'bg-success/10 text-success border-success/20',
      }
    case 'draft':
      return {
        text: 'Draft',
        className: 'bg-slate-100 text-slate-600 border-slate-200',
      }
    case 'archived':
      return {
        text: 'Archived',
        className: 'bg-slate-100 text-slate-400 border-slate-200',
      }
  }
}

/**
 * Format margin with color coding
 */
function getMarginDisplay(margin: number | null): { text: string; className: string } {
  if (margin === null) {
    return { text: 'N/A', className: 'text-slate-400' }
  }

  const text = `${margin.toFixed(1)}%`

  if (margin < 10) {
    return { text, className: 'text-danger font-semibold' }
  } else if (margin < 20) {
    return { text, className: 'text-amber-600 font-semibold' }
  } else {
    return { text, className: 'text-success font-semibold' }
  }
}

// =============================================================================
// Component
// =============================================================================

export function InternalProductDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: product, isLoading, error, refetch } = useAdminProduct(id)

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6">
        <BackLink />
        <LoadingSkeleton className="h-48" />
        <LoadingSkeleton className="h-64" />
      </div>
    )
  }

  // Error state
  if (error || !product) {
    return (
      <div className="space-y-6">
        <BackLink />
        <ErrorState
          message={error?.message || 'Product not found'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  const statusBadge = getStatusBadge(product.status)
  const marginDisplay = getMarginDisplay(product.margin_percentage)
  const lowestPrice = getLowestPrice(product.supplier_items)
  const highestPrice = getHighestPrice(product.supplier_items)

  return (
    <div className="space-y-6">
      {/* Back Navigation */}
      <BackLink />

      {/* Product Header */}
      <div className="bg-white rounded-lg border border-border p-6">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
          {/* Left: Product Info */}
          <div className="space-y-4 flex-1">
            <div className="flex items-start gap-3">
              <h1 className="text-2xl font-bold text-slate-900">{product.name}</h1>
              <span
                className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusBadge.className}`}
              >
                {statusBadge.text}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-4 text-sm">
              <div>
                <span className="text-slate-500">SKU:</span>
                <span className="ml-1.5 font-mono text-slate-900">{product.internal_sku}</span>
              </div>
              {product.category_id && (
                <div>
                  <span className="text-slate-500">Category:</span>
                  <span className="ml-1.5 text-slate-900">{product.category_id}</span>
                </div>
              )}
              <div>
                <span className="text-slate-500">Suppliers:</span>
                <span className="ml-1.5 text-slate-900">{product.supplier_items.length}</span>
              </div>
            </div>
          </div>

          {/* Right: Price & Margin Stats */}
          <div className="flex flex-wrap gap-6 lg:gap-8">
            {/* Price Range */}
            <div className="text-center">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
                Price Range
              </p>
              {lowestPrice > 0 ? (
                <div>
                  <p className="text-xl font-bold text-slate-900">
                    {formatCurrency(lowestPrice)}
                  </p>
                  {highestPrice !== lowestPrice && (
                    <p className="text-sm text-slate-500">
                      to {formatCurrency(highestPrice)}
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-xl font-bold text-slate-400">—</p>
              )}
            </div>

            {/* Margin */}
            <div className="text-center">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
                Margin
              </p>
              <p className={`text-xl ${marginDisplay.className}`}>{marginDisplay.text}</p>
            </div>

            {/* Best Price */}
            <div className="text-center">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
                Best Price
              </p>
              <p className="text-xl font-bold text-success">
                {lowestPrice > 0 ? formatCurrency(lowestPrice) : '—'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Supplier Comparison */}
      <SupplierComparison
        supplierItems={product.supplier_items}
        isLoading={false}
      />

      {/* Price History Placeholder */}
      <div className="bg-white rounded-lg border border-border p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Price History</h3>
        <div className="bg-slate-50 rounded-lg border border-dashed border-border p-8 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-slate-100 mb-3">
            <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
            </svg>
          </div>
          <p className="text-slate-600 font-medium">Price history chart coming soon</p>
          <p className="text-sm text-slate-500 mt-1">
            Track price trends across all suppliers over time.
          </p>
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// Sub-Components
// =============================================================================

function BackLink() {
  return (
    <Link
      to="/admin/sales"
      className="inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 transition-colors"
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
      </svg>
      Back to Sales Catalog
    </Link>
  )
}

