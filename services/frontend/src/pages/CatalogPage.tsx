/**
 * CatalogPage
 *
 * Public product catalog page with filtering and search.
 * Implements URL query parameter sync for shareable filter states.
 *
 * Features:
 * - Category, price range, and search filtering
 * - URL-based filter state (shareable links)
 * - Pagination
 * - Responsive grid layout
 */

import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useCatalog } from '@/hooks/useCatalog'
import { useCategories } from '@/hooks/useCategories'
import { useCart } from '@/hooks/useCart'
import { FilterBar } from '@/components/catalog/FilterBar'
import { ProductGrid, PaginationInfo, Pagination } from '@/components/catalog/ProductGrid'
import { FilterBarSkeleton } from '@/components/shared/LoadingSkeleton'
import type { CatalogFilters } from '@/types/filters'
import type { CartProduct } from '@/types/cart'

const ITEMS_PER_PAGE = 12

/**
 * Parse URL search params into CatalogFilters
 */
function parseFiltersFromURL(searchParams: URLSearchParams): CatalogFilters {
  return {
    search: searchParams.get('search') || undefined,
    category_id: searchParams.get('category') || undefined,
    min_price: searchParams.get('min') ? parseFloat(searchParams.get('min')!) : undefined,
    max_price: searchParams.get('max') ? parseFloat(searchParams.get('max')!) : undefined,
    page: searchParams.get('page') ? parseInt(searchParams.get('page')!, 10) : 1,
    limit: ITEMS_PER_PAGE,
  }
}

/**
 * Convert CatalogFilters to URL search params
 */
function filtersToURLParams(filters: CatalogFilters): Record<string, string> {
  const params: Record<string, string> = {}

  if (filters.search) params.search = filters.search
  if (filters.category_id) params.category = filters.category_id
  if (filters.min_price !== undefined) params.min = filters.min_price.toString()
  if (filters.max_price !== undefined) params.max = filters.max_price.toString()
  if (filters.page && filters.page > 1) params.page = filters.page.toString()

  return params
}

/**
 * Catalog page component
 */
export function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { addItem } = useCart()

  // Parse filters from URL
  const filters = useMemo(
    () => parseFiltersFromURL(searchParams),
    [searchParams]
  )

  // Update URL when filters change
  const handleFiltersChange = useCallback(
    (newFilters: CatalogFilters) => {
      setSearchParams(filtersToURLParams(newFilters), { replace: true })
    },
    [setSearchParams]
  )

  // Handle page change
  const handlePageChange = useCallback(
    (page: number) => {
      handleFiltersChange({ ...filters, page })
      // Scroll to top on page change
      window.scrollTo({ top: 0, behavior: 'smooth' })
    },
    [filters, handleFiltersChange]
  )

  // Fetch catalog data
  const {
    data: catalogData,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useCatalog(filters)

  // Fetch categories for filter dropdown
  const { categories, isLoading: categoriesLoading } = useCategories()

  // Handle add to cart
  const handleAddToCart = useCallback(
    (productId: string) => {
      const product = catalogData?.data?.find((p) => p.id === productId)
      if (product) {
        const cartProduct: CartProduct = {
          id: product.id,
          name: product.name,
          sku: product.internal_sku,
          price: product.min_price, // Use min price for cart
          category: product.category_id ?? undefined,
        }
        addItem(cartProduct)
      }
    },
    [catalogData?.data, addItem]
  )

  // Calculate pagination info
  const totalPages = catalogData
    ? Math.ceil(catalogData.total_count / ITEMS_PER_PAGE)
    : 0

  return (
    <div className="min-h-screen bg-surface">
      {/* Page Header */}
      <div className="bg-white border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-slate-900">
                Product Catalog
              </h1>
              <p className="mt-1 text-slate-500">
                Browse our selection of products from multiple suppliers
              </p>
            </div>

            {/* Loading indicator for background refetches */}
            {isFetching && !isLoading && (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <svg
                  className="w-4 h-4 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Updating...
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Filter Bar */}
        {categoriesLoading && !categories.length ? (
          <FilterBarSkeleton />
        ) : (
          <FilterBar
            filters={filters}
            onFiltersChange={handleFiltersChange}
            categories={categories}
            categoriesLoading={categoriesLoading}
          />
        )}

        {/* Results Info */}
        {catalogData && catalogData.total_count > 0 && (
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <PaginationInfo
              page={filters.page || 1}
              limit={ITEMS_PER_PAGE}
              totalCount={catalogData.total_count}
            />
          </div>
        )}

        {/* Product Grid */}
        <ProductGrid
          products={catalogData?.data || []}
          isLoading={isLoading}
          error={error}
          onRetry={() => refetch()}
          onAddToCart={handleAddToCart}
          skeletonCount={6}
        />

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-border">
            <PaginationInfo
              page={filters.page || 1}
              limit={ITEMS_PER_PAGE}
              totalCount={catalogData?.total_count || 0}
            />
            <Pagination
              page={filters.page || 1}
              totalPages={totalPages}
              onPageChange={handlePageChange}
            />
          </div>
        )}
      </div>
    </div>
  )
}

