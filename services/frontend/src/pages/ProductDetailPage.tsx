/**
 * ProductDetailPage
 *
 * Public product detail page showing full product information.
 * Uses the catalog list data to display product details.
 *
 * Note: Since there's no dedicated /catalog/:id endpoint yet,
 * this page uses data from the catalog list or admin endpoint.
 */

import { useMemo } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useCatalog } from '@/hooks/useCatalog'
import { formatPrice, getPlaceholderImage, cn } from '@/lib/utils'
import { ProductDetailSkeleton } from '@/components/shared/LoadingSkeleton'
import { ErrorState } from '@/components/shared/ErrorState'

/**
 * Product detail page component
 */
export function ProductDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  // Fetch catalog to find the product
  // In a real app, there would be a dedicated /catalog/:id endpoint
  const { data: catalogData, isLoading, error, refetch } = useCatalog({ limit: 200 })

  // Find the product in the catalog data
  const product = useMemo(() => {
    if (!catalogData?.data || !id) return null
    return catalogData.data.find((p) => p.id === id)
  }, [catalogData?.data, id])

  // Loading state
  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <ProductDetailSkeleton />
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <ErrorState
          title="Failed to load product"
          message={error.message || 'Please try again later.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  // Product not found
  if (!product) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <ErrorState
          title="Product not found"
          message="The product you're looking for doesn't exist or has been removed."
          onRetry={() => navigate('/')}
        />
      </div>
    )
  }

  const {
    name,
    internal_sku,
    min_price,
    max_price,
    supplier_count,
    category_id,
  } = product

  // Price display
  const priceDisplay =
    min_price === max_price
      ? formatPrice(min_price)
      : `${formatPrice(min_price)} - ${formatPrice(max_price)}`

  return (
    <div className="min-h-screen bg-surface">
      {/* Breadcrumb */}
      <div className="bg-white border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <nav className="flex items-center gap-2 text-sm" aria-label="Breadcrumb">
            <Link
              to="/"
              className="text-slate-500 hover:text-primary transition-colors"
            >
              Catalog
            </Link>
            <svg
              className="w-4 h-4 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
            <span className="text-slate-900 font-medium truncate max-w-xs">
              {name}
            </span>
          </nav>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Back Button */}
        <button
          onClick={() => navigate(-1)}
          className={cn(
            'inline-flex items-center gap-2 mb-6',
            'text-slate-600 hover:text-primary transition-colors',
            'focus:outline-none focus-visible:text-primary'
          )}
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 19l-7-7m0 0l7-7m-7 7h18"
            />
          </svg>
          Back to Catalog
        </button>

        {/* Product Details */}
        <div className="bg-white rounded-xl shadow-md overflow-hidden border border-border">
          <div className="grid grid-cols-1 lg:grid-cols-2">
            {/* Product Image */}
            <div className="relative aspect-square lg:aspect-auto bg-slate-50">
              <img
                src={getPlaceholderImage(name)}
                alt={`Product: ${name}`}
                className="w-full h-full object-cover"
              />
              {/* Supplier badge */}
              {supplier_count > 0 && (
                <span className="absolute top-4 right-4 px-3 py-1.5 bg-white/90 backdrop-blur-sm rounded-full text-sm font-medium text-slate-700 shadow-sm">
                  {supplier_count} supplier{supplier_count !== 1 ? 's' : ''}
                </span>
              )}
            </div>

            {/* Product Info */}
            <div className="p-6 lg:p-8 space-y-6">
              {/* Category */}
              {category_id && (
                <span className="inline-block px-3 py-1 bg-primary/10 text-primary text-sm font-medium rounded-full">
                  {category_id}
                </span>
              )}

              {/* Name */}
              <h1 className="text-2xl lg:text-3xl font-bold text-slate-900">
                {name}
              </h1>

              {/* SKU */}
              <p className="text-slate-500 font-mono">SKU: {internal_sku}</p>

              {/* Price */}
              <div className="py-4 border-y border-border">
                <p className="text-sm text-slate-500 mb-1">Price Range</p>
                <p className="text-3xl font-bold text-slate-900">{priceDisplay}</p>
              </div>

              {/* Product Details */}
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-slate-900">
                  Product Details
                </h2>
                <dl className="grid grid-cols-2 gap-4">
                  <div>
                    <dt className="text-sm text-slate-500">Product ID</dt>
                    <dd className="font-mono text-sm text-slate-700 truncate">
                      {id}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm text-slate-500">Available From</dt>
                    <dd className="text-slate-700">
                      {supplier_count} supplier{supplier_count !== 1 ? 's' : ''}
                    </dd>
                  </div>
                  {category_id && (
                    <div className="col-span-2">
                      <dt className="text-sm text-slate-500">Category ID</dt>
                      <dd className="font-mono text-sm text-slate-700 truncate">
                        {category_id}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>

              {/* CTA Button - Placeholder for Phase 4 */}
              <div className="pt-4">
                <button
                  className={cn(
                    'w-full sm:w-auto inline-flex items-center justify-center gap-2',
                    'px-6 py-3 bg-primary text-white font-medium rounded-lg',
                    'hover:bg-primary/90 transition-colors',
                    'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2'
                  )}
                  onClick={() => {
                    // TODO: Implement add to cart in Phase 4
                    alert('Shopping cart feature coming in Phase 4!')
                  }}
                >
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"
                    />
                  </svg>
                  Add to Cart
                </button>
                <p className="mt-2 text-xs text-muted">
                  * Shopping cart functionality coming in Phase 4
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

