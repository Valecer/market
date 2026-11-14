/**
 * ProductDetailPage
 *
 * Public product detail page showing full product information.
 * Phase 10: Now uses dedicated /catalog/:id endpoint with variants support.
 * Phase 11 US3: Updated breadcrumb to show 3-level category hierarchy.
 */

import { useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useProduct } from '@/hooks/useProduct'
import { useCart } from '@/hooks/useCart'
import { formatPrice, getPlaceholderImage, cn } from '@/lib/utils'
import { ProductDetailSkeleton } from '@/components/shared/LoadingSkeleton'
import { ErrorState } from '@/components/shared/ErrorState'
import { CategoryBreadcrumb } from '@/components/shared/CategoryBreadcrumb'
import { VariantSelector } from '@/components/catalog/VariantSelector'
import type { CartProduct } from '@/types/cart'
import type { ProductVariant } from '@/lib/api-client'

/**
 * Product detail page component
 */
export function ProductDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { addItem, getItemQuantity } = useCart()

  // Phase 10: Use dedicated product endpoint with variants
  const { data: product, isLoading, error, refetch } = useProduct(id)

  // Selected variant state (for products with variants)
  const [selectedVariant, setSelectedVariant] = useState<ProductVariant | null>(null)

  // Current quantity in cart - MUST be called before any conditional returns
  const quantityInCart = getItemQuantity(id ?? '')

  // Handle add to cart - MUST be called before any conditional returns
  const handleAddToCart = useCallback(() => {
    if (!product) return
    const cartProduct: CartProduct = {
      id: selectedVariant ? `${product.id}:${selectedVariant.id}` : product.id,
      name: selectedVariant 
        ? `${product.name} (${selectedVariant.variant_key})`
        : product.name,
      sku: product.internal_sku,
      price: parseFloat(selectedVariant?.min_price ?? product.min_price),
      category: product.category_id ?? undefined,
    }
    addItem(cartProduct)
  }, [product, selectedVariant, addItem])

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
    has_variants,
    variant_schema,
    variants,
  } = product

  // Use selected variant prices if available
  const displayMinPrice = selectedVariant?.min_price ?? min_price
  const displayMaxPrice = selectedVariant?.max_price ?? max_price

  // Price display
  const priceDisplay =
    displayMinPrice === displayMaxPrice
      ? formatPrice(displayMinPrice)
      : `${formatPrice(displayMinPrice)} - ${formatPrice(displayMaxPrice)}`

  return (
    <div className="min-h-screen bg-surface">
      {/* Breadcrumb - Phase 11 US3: 3-level category hierarchy */}
      <div className="bg-white border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <CategoryBreadcrumb
            categoryId={category_id ?? undefined}
            productName={name}
            showCatalogLink={true}
          />
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

              {/* Phase 10: Variant Selector */}
              {has_variants && variants.length > 0 && (
                <VariantSelector
                  variants={variants}
                  variantSchema={variant_schema}
                  selectedVariant={selectedVariant}
                  onSelectVariant={setSelectedVariant}
                />
              )}

              {/* Price */}
              <div className="py-4 border-y border-border">
                <p className="text-sm text-slate-500 mb-1">
                  {selectedVariant ? 'Selected Variant Price' : 'Price Range'}
                </p>
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
                  {has_variants && (
                    <div className="col-span-2">
                      <dt className="text-sm text-slate-500">Variants Available</dt>
                      <dd className="text-slate-700">
                        {variants.length} variant{variants.length !== 1 ? 's' : ''}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>

              {/* Add to Cart Button */}
              <div className="pt-4 space-y-3">
                <button
                  className={cn(
                    'w-full sm:w-auto inline-flex items-center justify-center gap-2',
                    'px-6 py-3 bg-primary text-white font-medium rounded-lg',
                    'hover:bg-primary/90 transition-colors',
                    'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
                    has_variants && !selectedVariant && 'opacity-50 cursor-not-allowed'
                  )}
                  onClick={handleAddToCart}
                  disabled={has_variants && !selectedVariant}
                  aria-label={`Add ${name} to cart`}
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
                  {has_variants && !selectedVariant ? 'Select a Variant' : 'Add to Cart'}
                </button>

                {/* Show quantity if already in cart */}
                {quantityInCart > 0 && (
                  <p className="text-sm text-success flex items-center gap-1">
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    {quantityInCart} in your cart
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
