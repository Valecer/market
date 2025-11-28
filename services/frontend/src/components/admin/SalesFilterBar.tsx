/**
 * SalesFilterBar Component
 *
 * Filter controls for the sales internal catalog.
 * Includes: category dropdown, margin range inputs, status filter.
 *
 * Design System: Tailwind CSS with consistent form styling
 * Accessibility: Proper labels, ARIA attributes, keyboard navigation
 */

import { useState, useCallback } from 'react'
import type { AdminProductFilters, ProductStatus } from '@/lib/api-client'

// =============================================================================
// Types
// =============================================================================

interface SalesFilterBarProps {
  /** Current filter values */
  filters: AdminProductFilters
  /** Callback when filters change */
  onFiltersChange: (filters: AdminProductFilters) => void
  /** Total count to display */
  totalCount?: number
}

// =============================================================================
// Status Options
// =============================================================================

const statusOptions: { value: ProductStatus | ''; label: string }[] = [
  { value: '', label: 'All Statuses' },
  { value: 'active', label: 'Active' },
  { value: 'draft', label: 'Draft' },
  { value: 'archived', label: 'Archived' },
]

// =============================================================================
// Component
// =============================================================================

export function SalesFilterBar({ 
  filters, 
  onFiltersChange, 
  totalCount 
}: SalesFilterBarProps) {
  // Local state for margin inputs (debounced)
  const [localMinMargin, setLocalMinMargin] = useState(filters.min_margin?.toString() ?? '')
  const [localMaxMargin, setLocalMaxMargin] = useState(filters.max_margin?.toString() ?? '')

  // Handle status change
  const handleStatusChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value as ProductStatus | ''
    onFiltersChange({
      ...filters,
      status: value || undefined,
      page: 1, // Reset to first page
    })
  }, [filters, onFiltersChange])

  // Handle margin change with debounce
  const handleMarginChange = useCallback((type: 'min' | 'max', value: string) => {
    if (type === 'min') {
      setLocalMinMargin(value)
    } else {
      setLocalMaxMargin(value)
    }
  }, [])

  // Apply margin filter on blur or enter
  const applyMarginFilter = useCallback(() => {
    const minMargin = localMinMargin ? parseFloat(localMinMargin) : undefined
    const maxMargin = localMaxMargin ? parseFloat(localMaxMargin) : undefined
    
    // Only update if values actually changed
    if (minMargin !== filters.min_margin || maxMargin !== filters.max_margin) {
      onFiltersChange({
        ...filters,
        min_margin: isNaN(minMargin ?? 0) ? undefined : minMargin,
        max_margin: isNaN(maxMargin ?? 0) ? undefined : maxMargin,
        page: 1,
      })
    }
  }, [localMinMargin, localMaxMargin, filters, onFiltersChange])

  // Handle key press for margin inputs
  const handleMarginKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      applyMarginFilter()
    }
  }, [applyMarginFilter])

  // Clear all filters
  const handleClearFilters = useCallback(() => {
    setLocalMinMargin('')
    setLocalMaxMargin('')
    onFiltersChange({
      page: 1,
      limit: filters.limit,
    })
  }, [filters.limit, onFiltersChange])

  // Check if any filters are active
  const hasActiveFilters = Boolean(
    filters.status || 
    filters.min_margin !== undefined || 
    filters.max_margin !== undefined ||
    filters.supplier_id
  )

  return (
    <div className="bg-white rounded-lg border border-border p-4 mb-4">
      <div className="flex flex-wrap items-end gap-4">
        {/* Status Filter */}
        <div className="flex-1 min-w-[160px] max-w-[200px]">
          <label 
            htmlFor="status-filter" 
            className="block text-sm font-medium text-slate-700 mb-1.5"
          >
            Status
          </label>
          <select
            id="status-filter"
            value={filters.status ?? ''}
            onChange={handleStatusChange}
            className="w-full px-3 py-2 bg-white border border-border rounded-md text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
          >
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {/* Margin Range Filter */}
        <div className="flex-1 min-w-[240px] max-w-[320px]">
          <label 
            className="block text-sm font-medium text-slate-700 mb-1.5"
          >
            Margin Range (%)
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              placeholder="Min"
              value={localMinMargin}
              onChange={(e) => handleMarginChange('min', e.target.value)}
              onBlur={applyMarginFilter}
              onKeyDown={handleMarginKeyDown}
              min="0"
              max="100"
              step="1"
              className="flex-1 px-3 py-2 bg-white border border-border rounded-md text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
              aria-label="Minimum margin percentage"
            />
            <span className="text-slate-400">—</span>
            <input
              type="number"
              placeholder="Max"
              value={localMaxMargin}
              onChange={(e) => handleMarginChange('max', e.target.value)}
              onBlur={applyMarginFilter}
              onKeyDown={handleMarginKeyDown}
              min="0"
              max="100"
              step="1"
              className="flex-1 px-3 py-2 bg-white border border-border rounded-md text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
              aria-label="Maximum margin percentage"
            />
          </div>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Clear Filters */}
        {hasActiveFilters && (
          <button
            type="button"
            onClick={handleClearFilters}
            className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors"
          >
            Clear filters
          </button>
        )}

        {/* Result Count */}
        {totalCount !== undefined && (
          <div className="text-sm text-slate-500">
            <span className="font-medium text-slate-900">{totalCount.toLocaleString()}</span> product{totalCount !== 1 ? 's' : ''}
          </div>
        )}
      </div>
    </div>
  )
}

