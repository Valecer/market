/**
 * CategoryBreadcrumb Component
 *
 * Phase 11 US3: Category Hierarchy Enforcement
 *
 * Displays a 3-level category breadcrumb:
 * - Level 1 (Top Category) → Level 2 (Sub-category) → Level 3 (Brand)
 *
 * Features:
 * - T105: Displays 3 levels consistently
 * - T106: Pads incomplete hierarchies with "Uncategorized" placeholder
 * - Visual indicator for categories needing review
 * - Accessible navigation structure
 */

import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'

// =============================================================================
// Types
// =============================================================================

export interface CategoryBreadcrumbItem {
  id: string | null
  name: string
  level: number
  needs_review: boolean
  is_placeholder?: boolean
}

export interface CategoryBreadcrumbResponse {
  category_id: string | null
  breadcrumb: CategoryBreadcrumbItem[]
  is_complete: boolean
}

interface CategoryBreadcrumbProps {
  /** Category ID to fetch breadcrumb for */
  categoryId?: string | null
  /** Optional custom class name */
  className?: string
  /** Whether to show product name at the end */
  productName?: string
  /** Show skeleton while loading */
  showSkeleton?: boolean
  /** Optional prefix link (e.g., "Catalog" → categories) */
  showCatalogLink?: boolean
}

// =============================================================================
// Chevron Icon Component
// =============================================================================

function ChevronRight({ className }: { className?: string }) {
  return (
    <svg
      className={cn('w-4 h-4 text-slate-400', className)}
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
  )
}

// =============================================================================
// Loading Skeleton
// =============================================================================

function BreadcrumbSkeleton() {
  return (
    <nav className="flex items-center gap-2 text-sm animate-pulse" aria-label="Loading breadcrumb">
      <div className="h-4 w-16 bg-slate-200 rounded" />
      <ChevronRight />
      <div className="h-4 w-20 bg-slate-200 rounded" />
      <ChevronRight />
      <div className="h-4 w-24 bg-slate-200 rounded" />
    </nav>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function CategoryBreadcrumb({
  categoryId,
  className,
  productName,
  showSkeleton = true,
  showCatalogLink = true,
}: CategoryBreadcrumbProps) {
  const { t } = useTranslation()

  // Fetch breadcrumb from API
  const { data, isLoading, error } = useQuery({
    queryKey: ['category-breadcrumb', categoryId],
    queryFn: async () => {
      if (!categoryId) return null

      const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3000'
      const token = localStorage.getItem('jwt_token')
      const url = `${API_BASE}/api/v1/admin/categories/${categoryId}/breadcrumb`

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Authorization': token ? `Bearer ${token}` : '',
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error('Failed to fetch category breadcrumb')
      }

      return response.json() as Promise<CategoryBreadcrumbResponse>
    },
    enabled: !!categoryId,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  })

  // Show skeleton while loading
  if (isLoading && showSkeleton && categoryId) {
    return <BreadcrumbSkeleton />
  }

  // If no category or error, show simple breadcrumb
  if (!categoryId || error || !data) {
    return (
      <nav className={cn('flex items-center gap-2 text-sm', className)} aria-label="Breadcrumb">
        {showCatalogLink && (
          <>
            <Link
              to="/"
              className="text-slate-500 hover:text-primary transition-colors"
            >
              {t('common.catalog', 'Catalog')}
            </Link>
            <ChevronRight />
          </>
        )}
        {productName && (
          <span className="text-slate-900 font-medium truncate max-w-xs">
            {productName}
          </span>
        )}
      </nav>
    )
  }

  const { breadcrumb, is_complete } = data

  return (
    <nav className={cn('flex items-center gap-2 text-sm flex-wrap', className)} aria-label="Breadcrumb">
      {/* Optional Catalog link */}
      {showCatalogLink && (
        <>
          <Link
            to="/"
            className="text-slate-500 hover:text-primary transition-colors"
          >
            {t('common.catalog', 'Catalog')}
          </Link>
          <ChevronRight />
        </>
      )}

      {/* Category hierarchy (3 levels) */}
      {breadcrumb.map((item, index) => (
        <span key={`level-${item.level}`} className="flex items-center gap-2">
          {item.is_placeholder ? (
            // Placeholder for incomplete hierarchy
            <span
              className={cn(
                'text-slate-400 italic',
                item.needs_review && 'text-amber-600'
              )}
              title={t('category.incomplete_hierarchy', 'Incomplete category hierarchy')}
            >
              {t('category.uncategorized', 'Uncategorized')}
            </span>
          ) : item.id ? (
            // Real category - could be a link to filtered catalog
            <span
              className={cn(
                'text-slate-600',
                item.needs_review && 'text-amber-600',
                // Level 3 is more prominent
                index === 2 && 'font-medium text-slate-700'
              )}
              title={item.needs_review ? t('category.needs_review', 'This category needs review') : undefined}
            >
              {item.name}
              {item.needs_review && (
                <span className="ml-1 text-amber-500" aria-label={t('category.review_indicator', 'Needs review')}>
                  •
                </span>
              )}
            </span>
          ) : (
            <span className="text-slate-400 italic">
              {item.name}
            </span>
          )}

          {/* Show chevron unless it's the last item OR we're showing product name */}
          {(index < breadcrumb.length - 1 || productName) && (
            <ChevronRight />
          )}
        </span>
      ))}

      {/* Product name at the end */}
      {productName && (
        <span className="text-slate-900 font-medium truncate max-w-xs">
          {productName}
        </span>
      )}

      {/* Incomplete hierarchy indicator */}
      {!is_complete && !productName && (
        <span
          className="ml-2 px-2 py-0.5 text-xs bg-amber-100 text-amber-700 rounded-full"
          title={t('category.incomplete_hierarchy_tooltip', 'Category hierarchy is incomplete')}
        >
          {t('category.incomplete', 'Incomplete')}
        </span>
      )}
    </nav>
  )
}

export default CategoryBreadcrumb

