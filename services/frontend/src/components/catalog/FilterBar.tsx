/**
 * FilterBar Component
 *
 * Filter controls for the product catalog including:
 * - Search input (debounced)
 * - Category dropdown
 * - Price range inputs
 *
 * Design System: Tailwind CSS with form styling
 * Accessibility: Labels, aria-labels, keyboard navigation
 */

import { useState, useEffect, useCallback, useId } from 'react'
import { cn, debounce } from '@/lib/utils'
import type { CatalogFilters } from '@/types/filters'

interface FilterBarProps {
  /** Current filter values */
  filters: CatalogFilters
  /** Callback when filters change */
  onFiltersChange: (filters: CatalogFilters) => void
  /** Available categories for dropdown */
  categories?: Array<{ id: string; name: string }>
  /** Whether categories are loading */
  categoriesLoading?: boolean
  /** Additional CSS classes */
  className?: string
}

/**
 * Filter bar for catalog page
 */
export function FilterBar({
  filters,
  onFiltersChange,
  categories = [],
  categoriesLoading,
  className,
}: FilterBarProps) {
  const searchId = useId()
  const categoryId = useId()
  const minPriceId = useId()
  const maxPriceId = useId()

  // Local state for immediate input feedback
  const [searchValue, setSearchValue] = useState(filters.search || '')

  // Sync local search when filters change externally (e.g., URL params)
  useEffect(() => {
    setSearchValue(filters.search || '')
  }, [filters.search])

  // Debounced search handler
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const debouncedSearch = useCallback(
    debounce((value: string) => {
      onFiltersChange({
        ...filters,
        search: value || undefined,
        page: 1, // Reset to first page on search
      })
    }, 300),
    [filters, onFiltersChange]
  )

  // Handle search input change
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setSearchValue(value)
    debouncedSearch(value)
  }

  // Handle category change
  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value
    onFiltersChange({
      ...filters,
      category_id: value || undefined,
      page: 1, // Reset to first page
    })
  }

  // Handle price range changes
  const handleMinPriceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    onFiltersChange({
      ...filters,
      min_price: value ? parseFloat(value) : undefined,
      page: 1,
    })
  }

  const handleMaxPriceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    onFiltersChange({
      ...filters,
      max_price: value ? parseFloat(value) : undefined,
      page: 1,
    })
  }

  // Clear all filters
  const handleClearFilters = () => {
    setSearchValue('')
    onFiltersChange({
      page: 1,
      limit: filters.limit,
    })
  }

  // Check if any filters are active
  const hasActiveFilters =
    filters.search || filters.category_id || filters.min_price || filters.max_price

  return (
    <div
      className={cn(
        'bg-white rounded-xl shadow-md p-4 md:p-5 border border-border',
        className
      )}
    >
      <div className="flex flex-col lg:flex-row gap-4">
        {/* Search Input */}
        <div className="flex-1 min-w-0">
          <label htmlFor={searchId} className="sr-only">
            Search products
          </label>
          <div className="relative">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400"
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
            <input
              id={searchId}
              type="search"
              value={searchValue}
              onChange={handleSearchChange}
              placeholder="Search products by name or SKU..."
              className={cn(
                'w-full pl-10 pr-4 py-2.5 rounded-lg border border-border',
                'bg-white text-slate-900 placeholder:text-slate-400',
                'focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent',
                'transition-shadow'
              )}
            />
          </div>
        </div>

        {/* Category Dropdown */}
        <div className="w-full lg:w-48">
          <label htmlFor={categoryId} className="sr-only">
            Category
          </label>
          <select
            id={categoryId}
            value={filters.category_id || ''}
            onChange={handleCategoryChange}
            disabled={categoriesLoading}
            className={cn(
              'w-full px-4 py-2.5 rounded-lg border border-border',
              'bg-white text-slate-900 appearance-none cursor-pointer',
              'focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent',
              'disabled:bg-slate-50 disabled:cursor-not-allowed',
              'transition-shadow'
            )}
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2394a3b8'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'/%3E%3C/svg%3E")`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'right 0.75rem center',
              backgroundSize: '1.25rem',
              paddingRight: '2.5rem',
            }}
          >
            <option value="">All Categories</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </div>

        {/* Price Range */}
        <div className="flex items-center gap-2">
          <div className="w-28">
            <label htmlFor={minPriceId} className="sr-only">
              Minimum price
            </label>
            <input
              id={minPriceId}
              type="number"
              min="0"
              step="0.01"
              value={filters.min_price ?? ''}
              onChange={handleMinPriceChange}
              placeholder="Min $"
              className={cn(
                'w-full px-3 py-2.5 rounded-lg border border-border',
                'bg-white text-slate-900 placeholder:text-slate-400',
                'focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent',
                'transition-shadow'
              )}
            />
          </div>
          <span className="text-slate-400" aria-hidden="true">
            —
          </span>
          <div className="w-28">
            <label htmlFor={maxPriceId} className="sr-only">
              Maximum price
            </label>
            <input
              id={maxPriceId}
              type="number"
              min="0"
              step="0.01"
              value={filters.max_price ?? ''}
              onChange={handleMaxPriceChange}
              placeholder="Max $"
              className={cn(
                'w-full px-3 py-2.5 rounded-lg border border-border',
                'bg-white text-slate-900 placeholder:text-slate-400',
                'focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent',
                'transition-shadow'
              )}
            />
          </div>
        </div>

        {/* Clear Filters Button */}
        {hasActiveFilters && (
          <button
            onClick={handleClearFilters}
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2.5 rounded-lg',
              'text-sm font-medium text-slate-600 bg-slate-100',
              'hover:bg-slate-200 transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2'
            )}
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
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
            Clear
          </button>
        )}
      </div>

      {/* Active Filters Summary */}
      {hasActiveFilters && (
        <div className="mt-4 pt-4 border-t border-border flex flex-wrap gap-2">
          {filters.search && (
            <FilterTag label={`Search: "${filters.search}"`} />
          )}
          {filters.category_id && (
            <FilterTag
              label={`Category: ${categories.find((c) => c.id === filters.category_id)?.name || filters.category_id}`}
            />
          )}
          {filters.min_price !== undefined && (
            <FilterTag label={`Min: $${filters.min_price}`} />
          )}
          {filters.max_price !== undefined && (
            <FilterTag label={`Max: $${filters.max_price}`} />
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Filter tag component for active filters display
 */
function FilterTag({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center px-2.5 py-1 bg-primary/10 text-primary text-sm rounded-full">
      {label}
    </span>
  )
}

