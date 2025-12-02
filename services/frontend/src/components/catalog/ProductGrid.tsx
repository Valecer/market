/**
 * ProductGrid Component
 *
 * Responsive grid layout for displaying product cards.
 * Handles loading, error, and empty states.
 *
 * Responsive breakpoints:
 * - Mobile (< 640px): 1 column
 * - Tablet (640-1024px): 2 columns
 * - Desktop (> 1024px): 3 columns
 * 
 * i18n: All text content is translatable
 */

import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { ProductCard } from './ProductCard'
import { ProductGridSkeleton } from '@/components/shared/LoadingSkeleton'
import { ErrorState, EmptyState } from '@/components/shared/ErrorState'
import type { CatalogProduct } from '@/lib/api-client'

interface ProductGridProps {
  /** Array of products to display */
  products: CatalogProduct[]
  /** Loading state */
  isLoading?: boolean
  /** Error object if fetch failed */
  error?: Error | null
  /** Callback for retry on error */
  onRetry?: () => void
  /** Optional callback for add to cart (Phase 4) */
  onAddToCart?: (productId: string) => void
  /** Number of skeleton cards to show while loading */
  skeletonCount?: number
  /** Additional CSS classes */
  className?: string
}

/**
 * Product grid with loading, error, and empty states
 */
export function ProductGrid({
  products,
  isLoading,
  error,
  onRetry,
  onAddToCart,
  skeletonCount = 6,
  className,
}: ProductGridProps) {
  const { t } = useTranslation()

  // Loading state
  if (isLoading) {
    return <ProductGridSkeleton count={skeletonCount} />
  }

  // Error state
  if (error) {
    return (
      <ErrorState
        title={t('error.failedToLoad')}
        message={error.message || t('error.message')}
        onRetry={onRetry}
      />
    )
  }

  // Empty state
  if (!products || products.length === 0) {
    return (
      <EmptyState
        title={t('catalog.noResults.title')}
        message={t('catalog.noResults.message')}
        icon={
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary/10 mb-4">
            <svg
              className="w-8 h-8 text-primary"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>
        }
      />
    )
  }

  // Product grid
  return (
    <div
      className={cn(
        'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6',
        className
      )}
    >
      {products.map((product) => (
        <ProductCard
          key={product.id}
          product={product}
          onAddToCart={onAddToCart}
        />
      ))}
    </div>
  )
}

/**
 * Pagination info component
 * i18n: Uses interpolated translation string
 */
export function PaginationInfo({
  page,
  limit,
  totalCount,
}: {
  page: number
  limit: number
  totalCount: number
}) {
  const { t } = useTranslation()
  const start = (page - 1) * limit + 1
  const end = Math.min(page * limit, totalCount)

  return (
    <p className="text-sm text-muted">
      {t('catalog.paginationInfo', { start, end, total: totalCount })}
    </p>
  )
}

/**
 * Pagination controls component
 * i18n: All button labels are translatable
 */
export function Pagination({
  page,
  totalPages,
  onPageChange,
}: {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
}) {
  const { t } = useTranslation()

  if (totalPages <= 1) return null

  return (
    <nav
      className="flex items-center gap-2"
      aria-label="Pagination"
    >
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page === 1}
        className={cn(
          'px-3 py-2 rounded-lg text-sm font-medium transition-colors',
          page === 1
            ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
            : 'bg-white border border-border text-slate-700 hover:bg-slate-50'
        )}
        aria-label={t('pagination.previous')}
      >
        {t('pagination.previous')}
      </button>

      <span className="px-4 py-2 text-sm text-slate-600">
        {t('pagination.pageInfo', { page, total: totalPages })}
      </span>

      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page === totalPages}
        className={cn(
          'px-3 py-2 rounded-lg text-sm font-medium transition-colors',
          page === totalPages
            ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
            : 'bg-white border border-border text-slate-700 hover:bg-slate-50'
        )}
        aria-label={t('pagination.next')}
      >
        {t('pagination.next')}
      </button>
    </nav>
  )
}
