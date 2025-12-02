/**
 * ProductCard Component
 *
 * Displays a single product in the catalog grid.
 * Shows name, price range, SKU, and supplier count.
 *
 * Design System: Tailwind CSS with custom shadows
 * Accessibility: Focusable card, proper alt text
 * i18n: All text content is translatable
 */

import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { cn, formatPrice, getPlaceholderImage, truncate } from '@/lib/utils'
import type { CatalogProduct } from '@/lib/api-client'

interface ProductCardProps {
  /** Product data from API */
  product: CatalogProduct
  /** Optional callback for add to cart (Phase 4) */
  onAddToCart?: (productId: string) => void
  /** Additional CSS classes */
  className?: string
}

/**
 * Product card for catalog grid display
 */
export function ProductCard({
  product,
  onAddToCart,
  className,
}: ProductCardProps) {
  const { t } = useTranslation()
  const {
    id,
    name,
    internal_sku,
    min_price,
    max_price,
    supplier_count,
    category_id,
  } = product

  // Format price display
  const priceDisplay =
    min_price === max_price
      ? formatPrice(min_price)
      : `${formatPrice(min_price)} - ${formatPrice(max_price)}`

  return (
    <article
      className={cn(
        'group bg-white rounded-xl shadow-md overflow-hidden border border-border',
        'hover:shadow-lg hover:border-primary/20 transition-all duration-200',
        'focus-within:ring-2 focus-within:ring-primary focus-within:ring-offset-2',
        className
      )}
    >
      {/* Product Image */}
      <Link
        to={`/product/${id}`}
        className="block relative aspect-[4/3] overflow-hidden bg-slate-50"
      >
        <img
          src={getPlaceholderImage(name)}
          alt={`${t('product.viewDetails')}: ${name}`}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          loading="lazy"
        />

        {/* Supplier count badge */}
        {supplier_count > 0 && (
          <span className="absolute top-3 right-3 px-2 py-1 bg-white/90 backdrop-blur-sm rounded-full text-xs font-medium text-slate-600 shadow-sm">
            {t('product.supplierCount', { count: supplier_count })}
          </span>
        )}
      </Link>

      {/* Product Details */}
      <div className="p-4 space-y-3">
        {/* Category Badge */}
        {category_id && (
          <span className="inline-block px-2.5 py-0.5 bg-primary/10 text-primary text-xs font-medium rounded-full">
            {truncate(category_id, 20)}
          </span>
        )}

        {/* Product Name */}
        <h3 className="font-semibold text-slate-900 leading-tight">
          <Link
            to={`/product/${id}`}
            className="hover:text-primary transition-colors line-clamp-2"
            title={name}
          >
            {name}
          </Link>
        </h3>

        {/* SKU */}
        <p className="text-sm text-muted font-mono">{internal_sku}</p>

        {/* Price and Actions */}
        <div className="flex items-center justify-between pt-2 border-t border-border">
          <span className="text-lg font-bold text-slate-900">{priceDisplay}</span>

          {onAddToCart && (
            <button
              onClick={() => onAddToCart(id)}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5',
                'text-sm font-medium text-primary bg-primary/10 rounded-lg',
                'hover:bg-primary hover:text-white transition-colors',
                'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary'
              )}
              aria-label={`${t('product.addToCartFull')}: ${name}`}
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 6v6m0 0v6m0-6h6m-6 0H6"
                />
              </svg>
              {t('product.addToCart')}
            </button>
          )}
        </div>
      </div>
    </article>
  )
}
