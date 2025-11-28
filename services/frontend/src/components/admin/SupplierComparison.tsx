/**
 * SupplierComparison Component
 *
 * Displays all supplier items linked to a product with price comparison.
 * Shows supplier name, SKU, price, last updated, and characteristics.
 *
 * Design System: Tailwind CSS with card-based layout
 * Accessibility: Semantic HTML, proper heading hierarchy
 */

import type { SupplierItem } from '@/lib/api-client'

// =============================================================================
// Types
// =============================================================================

interface SupplierComparisonProps {
  /** Supplier items linked to the product */
  supplierItems: SupplierItem[]
  /** Loading state */
  isLoading?: boolean
}

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
 * Format date for display
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

/**
 * Calculate relative time
 */
function getRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`
  return `${Math.floor(diffDays / 365)} years ago`
}

// =============================================================================
// Component
// =============================================================================

export function SupplierComparison({ supplierItems, isLoading = false }: SupplierComparisonProps) {
  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-slate-900">Supplier Comparison</h3>
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="bg-white rounded-lg border border-border p-4">
              <div className="space-y-3">
                <div className="h-5 bg-slate-100 rounded animate-pulse w-3/4" />
                <div className="h-4 bg-slate-100 rounded animate-pulse w-1/2" />
                <div className="h-8 bg-slate-100 rounded animate-pulse w-1/3" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // Empty state
  if (supplierItems.length === 0) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-slate-900">Supplier Comparison</h3>
        <div className="bg-slate-50 rounded-lg border border-dashed border-border p-6 text-center">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-slate-100 mb-3">
            <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
          <p className="text-slate-600 font-medium">No suppliers linked</p>
          <p className="text-sm text-slate-500 mt-1">
            Link supplier items to this product to see price comparisons.
          </p>
        </div>
      </div>
    )
  }

  // Sort by price (lowest first)
  const sortedItems = [...supplierItems].sort((a, b) => {
    const priceA = parseFloat(a.current_price)
    const priceB = parseFloat(b.current_price)
    return priceA - priceB
  })

  const lowestPrice = parseFloat(sortedItems[0].current_price)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-900">Supplier Comparison</h3>
        <span className="text-sm text-slate-500">
          {supplierItems.length} supplier{supplierItems.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {sortedItems.map((item) => {
          const price = parseFloat(item.current_price)
          const isLowest = price === lowestPrice
          const priceDiff = price - lowestPrice
          const priceDiffPercent = lowestPrice > 0 ? (priceDiff / lowestPrice) * 100 : 0

          return (
            <div
              key={item.id}
              className={`relative bg-white rounded-lg border p-4 transition-shadow hover:shadow-md ${
                isLowest ? 'border-success ring-1 ring-success/20' : 'border-border'
              }`}
            >
              {/* Best Price Badge */}
              {isLowest && (
                <div className="absolute -top-2 -right-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-success text-white shadow-sm">
                    Best Price
                  </span>
                </div>
              )}

              {/* Supplier Header */}
              <div className="mb-3">
                <h4 className="font-medium text-slate-900 truncate" title={item.supplier_name}>
                  {item.supplier_name}
                </h4>
                <p className="text-sm text-slate-500 font-mono truncate" title={item.supplier_sku}>
                  {item.supplier_sku}
                </p>
              </div>

              {/* Price */}
              <div className="mb-3">
                <div className="flex items-baseline gap-2">
                  <span className={`text-2xl font-bold ${isLowest ? 'text-success' : 'text-slate-900'}`}>
                    {formatCurrency(price)}
                  </span>
                  {!isLowest && priceDiff > 0 && (
                    <span className="text-sm text-slate-500">
                      +{formatCurrency(priceDiff)} (+{priceDiffPercent.toFixed(1)}%)
                    </span>
                  )}
                </div>
              </div>

              {/* Last Updated */}
              <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-3">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span title={formatDate(item.last_ingested_at)}>
                  Updated {getRelativeTime(item.last_ingested_at)}
                </span>
              </div>

              {/* Characteristics */}
              {Object.keys(item.characteristics || {}).length > 0 && (
                <div className="pt-3 border-t border-border">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">
                    Characteristics
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(item.characteristics).slice(0, 4).map(([key, value]) => (
                      <span
                        key={key}
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-600"
                        title={`${key}: ${String(value)}`}
                      >
                        <span className="font-medium">{key}:</span>
                        <span className="ml-1 truncate max-w-[80px]">{String(value)}</span>
                      </span>
                    ))}
                    {Object.keys(item.characteristics).length > 4 && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-500">
                        +{Object.keys(item.characteristics).length - 4} more
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

