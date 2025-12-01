/**
 * SalesCatalogPage
 *
 * Sales internal catalog page showing products with pricing, margins,
 * and supplier information. Accessible only to sales and admin roles.
 *
 * Features:
 * - Product table with sorting
 * - Filters for status and margin range
 * - Pagination
 * - Click to view product details
 *
 * Route: /admin/sales
 * Roles: sales, admin
 * i18n: All text content is translatable
 */

import { useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAdminProducts } from '@/hooks/useAdminProducts'
import { SalesTable } from '@/components/admin/SalesTable'
import { SalesFilterBar } from '@/components/admin/SalesFilterBar'
import { ErrorState } from '@/components/shared/ErrorState'
import type { AdminProduct, AdminProductFilters, ProductStatus } from '@/lib/api-client'

// =============================================================================
// Helpers
// =============================================================================

/**
 * Parse filters from URL search params
 */
function parseFiltersFromParams(params: URLSearchParams): AdminProductFilters {
  const status = params.get('status') as ProductStatus | null
  const minMargin = params.get('min_margin')
  const maxMargin = params.get('max_margin')
  const page = params.get('page')
  const limit = params.get('limit')
  const supplierId = params.get('supplier_id')

  return {
    status: status || undefined,
    min_margin: minMargin ? parseFloat(minMargin) : undefined,
    max_margin: maxMargin ? parseFloat(maxMargin) : undefined,
    page: page ? parseInt(page, 10) : 1,
    limit: limit ? parseInt(limit, 10) : 25,
    supplier_id: supplierId || undefined,
  }
}

/**
 * Convert filters to URL search params
 */
function filtersToParams(filters: AdminProductFilters): URLSearchParams {
  const params = new URLSearchParams()
  
  if (filters.status) params.set('status', filters.status)
  if (filters.min_margin !== undefined) params.set('min_margin', filters.min_margin.toString())
  if (filters.max_margin !== undefined) params.set('max_margin', filters.max_margin.toString())
  if (filters.page && filters.page > 1) params.set('page', filters.page.toString())
  if (filters.limit && filters.limit !== 25) params.set('limit', filters.limit.toString())
  if (filters.supplier_id) params.set('supplier_id', filters.supplier_id)
  
  return params
}

// =============================================================================
// Component
// =============================================================================

export function SalesCatalogPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  
  // Parse filters from URL
  const filters = parseFiltersFromParams(searchParams)
  
  // Fetch products with filters
  const { data, isLoading, error, refetch } = useAdminProducts(filters)

  // Handle filter changes - update URL
  const handleFiltersChange = useCallback((newFilters: AdminProductFilters) => {
    setSearchParams(filtersToParams(newFilters))
  }, [setSearchParams])

  // Handle row click - navigate to product detail
  const handleRowClick = useCallback((product: AdminProduct) => {
    navigate(`/admin/products/${product.id}`)
  }, [navigate])

  // Handle pagination
  const handlePageChange = useCallback((page: number) => {
    handleFiltersChange({ ...filters, page })
  }, [filters, handleFiltersChange])

  // Error state
  if (error && !isLoading) {
    return (
      <div className="space-y-4">
        <PageHeader />
        <ErrorState
          message={error.message || t('error.failedToLoad')}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  const products = data?.data ?? []
  const totalCount = data?.total_count ?? 0
  const currentPage = data?.page ?? 1
  const limit = data?.limit ?? 25
  const totalPages = Math.ceil(totalCount / limit)

  return (
    <div className="space-y-4">
      <PageHeader />
      
      {/* Filters */}
      <SalesFilterBar
        filters={filters}
        onFiltersChange={handleFiltersChange}
        totalCount={totalCount}
      />
      
      {/* Table */}
      <SalesTable
        products={products}
        isLoading={isLoading}
        onRowClick={handleRowClick}
      />
      
      {/* Pagination */}
      {totalPages > 1 && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={handlePageChange}
        />
      )}
    </div>
  )
}

// =============================================================================
// Sub-Components
// =============================================================================

function PageHeader() {
  const { t } = useTranslation()
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{t('admin.salesCatalog')}</h1>
        <p className="text-slate-500 mt-1">
          {t('admin.salesCatalogSubtitle')}
        </p>
      </div>
    </div>
  )
}

interface PaginationProps {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
}

function Pagination({ currentPage, totalPages, onPageChange }: PaginationProps) {
  const { t } = useTranslation()
  const canGoPrev = currentPage > 1
  const canGoNext = currentPage < totalPages

  // Generate page numbers to show
  const getPageNumbers = () => {
    const pages: (number | 'ellipsis')[] = []
    const delta = 2 // Pages to show around current

    for (let i = 1; i <= totalPages; i++) {
      if (
        i === 1 ||
        i === totalPages ||
        (i >= currentPage - delta && i <= currentPage + delta)
      ) {
        pages.push(i)
      } else if (pages[pages.length - 1] !== 'ellipsis') {
        pages.push('ellipsis')
      }
    }

    return pages
  }

  return (
    <nav 
      className="flex items-center justify-between bg-white rounded-lg border border-border px-4 py-3"
      aria-label="Pagination"
    >
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={!canGoPrev}
          className="p-2 rounded-md border border-border text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          aria-label={t('pagination.previousPage')}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        <div className="flex items-center gap-1">
          {getPageNumbers().map((page, index) => (
            page === 'ellipsis' ? (
              <span key={`ellipsis-${index}`} className="px-2 text-slate-400">…</span>
            ) : (
              <button
                key={page}
                onClick={() => onPageChange(page)}
                className={`min-w-[36px] h-9 px-3 rounded-md text-sm font-medium transition-colors ${
                  page === currentPage
                    ? 'bg-primary text-white'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
                aria-current={page === currentPage ? 'page' : undefined}
              >
                {page}
              </button>
            )
          ))}
        </div>

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={!canGoNext}
          className="p-2 rounded-md border border-border text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          aria-label={t('pagination.nextPage')}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      <span className="text-sm text-slate-500">
        {t('pagination.pageInfo', { page: currentPage, total: totalPages })}
      </span>
    </nav>
  )
}
