/**
 * SalesFilterBar Component
 *
 * Filter controls for the sales internal catalog.
 * Includes: category dropdown, margin range inputs, status filter.
 *
 * Design System: Tailwind CSS with consistent form styling
 * Accessibility: Proper labels, ARIA attributes, keyboard navigation
 * i18n: All text content is translatable
 */

import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
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
// Component
// =============================================================================

export function SalesFilterBar({ 
  filters, 
  onFiltersChange, 
  totalCount 
}: SalesFilterBarProps) {
  const { t } = useTranslation()
  
  // Local state for margin inputs (debounced)
  const [localMinMargin, setLocalMinMargin] = useState(filters.min_margin?.toString() ?? '')
  const [localMaxMargin, setLocalMaxMargin] = useState(filters.max_margin?.toString() ?? '')

  // Status options with translations
  const statusOptions: { value: ProductStatus | ''; labelKey: string }[] = [
    { value: '', labelKey: 'admin.sales.allStatuses' },
    { value: 'active', labelKey: 'admin.sales.active' },
    { value: 'draft', labelKey: 'admin.sales.draft' },
    { value: 'archived', labelKey: 'admin.sales.archived' },
  ]

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
    <div className="bg-white rounded-xl border border-border shadow-sm mb-4 overflow-hidden">
      <div className="p-4 flex flex-col sm:flex-row sm:items-end gap-4">
        {/* Status Filter */}
        <div className="w-full sm:w-44">
          <label 
            htmlFor="status-filter" 
            className="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1.5"
          >
            {t('admin.sales.status')}
          </label>
          <select
            id="status-filter"
            value={filters.status ?? ''}
            onChange={handleStatusChange}
            className="w-full h-10 px-3 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary focus:bg-white transition-all cursor-pointer"
          >
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {t(option.labelKey)}
              </option>
            ))}
          </select>
        </div>

        {/* Margin Range Filter */}
        <div className="w-full sm:w-auto">
          <label 
            className="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1.5"
          >
            {t('admin.sales.marginRange')}
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              placeholder={t('admin.sales.min')}
              value={localMinMargin}
              onChange={(e) => handleMarginChange('min', e.target.value)}
              onBlur={applyMarginFilter}
              onKeyDown={handleMarginKeyDown}
              min="0"
              max="100"
              step="1"
              className="w-20 h-10 px-3 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary focus:bg-white transition-all"
              aria-label={t('admin.sales.min')}
            />
            <span className="text-slate-300 font-light">—</span>
            <input
              type="number"
              placeholder={t('admin.sales.max')}
              value={localMaxMargin}
              onChange={(e) => handleMarginChange('max', e.target.value)}
              onBlur={applyMarginFilter}
              onKeyDown={handleMarginKeyDown}
              min="0"
              max="100"
              step="1"
              className="w-20 h-10 px-3 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary focus:bg-white transition-all"
              aria-label={t('admin.sales.max')}
            />
          </div>
        </div>

        {/* Spacer - grows to push actions to the right */}
        <div className="hidden sm:block flex-1" />

        {/* Actions */}
        <div className="flex items-center gap-3 sm:ml-auto">
        {/* Clear Filters */}
        {hasActiveFilters && (
          <button
            type="button"
            onClick={handleClearFilters}
              className="h-10 px-4 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
          >
              {t('admin.sales.clearFilters')}
          </button>
        )}

        {/* Result Count */}
        {totalCount !== undefined && (
            <div className="h-10 px-4 flex items-center bg-slate-100 rounded-lg">
              <span className="text-sm font-semibold text-slate-900">{totalCount.toLocaleString()}</span>
              <span className="text-sm text-slate-500 ml-1.5">{t('admin.sales.products')}</span>
          </div>
        )}
        </div>
      </div>
    </div>
  )
}
