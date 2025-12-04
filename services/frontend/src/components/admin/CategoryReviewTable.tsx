/**
 * CategoryReviewTable Component
 *
 * Displays categories needing admin review in a table format.
 * Supports bulk selection, approve, and merge actions.
 *
 * @see /specs/009-semantic-etl/spec.md - US3: Category Review Workflow
 */

import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import type { CategoryReviewItem } from '@/types/category'

// =============================================================================
// Icons
// =============================================================================

const CheckIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
)

const MergeIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"
    />
  </svg>
)

const EditIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
    />
  </svg>
)

const FolderIcon = () => (
  <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
    />
  </svg>
)

const EmptyStateIcon = () => (
  <svg className="w-12 h-12 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.5}
      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
    />
  </svg>
)

// =============================================================================
// Types
// =============================================================================

interface CategoryReviewTableProps {
  categories: CategoryReviewItem[]
  isLoading: boolean
  selectedIds: string[]
  onSelectChange: (ids: string[]) => void
  onApprove: (category: CategoryReviewItem) => void
  onMerge: (category: CategoryReviewItem) => void
  onEdit: (category: CategoryReviewItem) => void
  isApproving?: string | null // ID of category being approved
  isMerging?: string | null // ID of category being merged
}

// =============================================================================
// Component
// =============================================================================

export function CategoryReviewTable({
  categories,
  isLoading,
  selectedIds,
  onSelectChange,
  onApprove,
  onMerge,
  onEdit,
  isApproving,
  isMerging,
}: CategoryReviewTableProps) {
  const { t } = useTranslation()

  // Toggle single selection
  const toggleSelect = useCallback(
    (id: string) => {
      if (selectedIds.includes(id)) {
        onSelectChange(selectedIds.filter((i) => i !== id))
      } else {
        onSelectChange([...selectedIds, id])
      }
    },
    [selectedIds, onSelectChange]
  )

  // Toggle all selection
  const toggleSelectAll = useCallback(() => {
    if (selectedIds.length === categories.length) {
      onSelectChange([])
    } else {
      onSelectChange(categories.map((c) => c.id))
    }
  }, [selectedIds.length, categories, onSelectChange])

  // Loading state
  if (isLoading) {
    return (
      <div className="bg-white rounded-xl shadow-md border border-border overflow-hidden">
        <div className="animate-pulse">
          <div className="h-12 bg-slate-100 border-b border-border" />
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 border-b border-border last:border-b-0">
              <div className="flex items-center gap-4 p-4">
                <div className="w-4 h-4 bg-slate-200 rounded" />
                <div className="h-4 bg-slate-200 rounded w-48" />
                <div className="h-4 bg-slate-200 rounded w-32 ml-auto" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // Empty state
  if (categories.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-md border border-border p-12 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-100 mb-4">
          <EmptyStateIcon />
        </div>
        <h3 className="text-lg font-semibold text-slate-900 mb-2">
          {t('categories.empty.noReview')}
        </h3>
        <p className="text-sm text-slate-500 max-w-sm mx-auto">
          {t('categories.empty.noReviewHint')}
        </p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-md border border-border overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          {/* Header */}
          <thead className="bg-slate-50/80 border-b border-border">
            <tr>
              <th className="w-12 px-4 py-3 text-left">
                <input
                  type="checkbox"
                  checked={selectedIds.length === categories.length && categories.length > 0}
                  onChange={toggleSelectAll}
                  className="w-4 h-4 rounded border-slate-300 text-primary focus:ring-primary/20"
                  aria-label={t('common.selectAll')}
                />
              </th>
              <th className="px-4 py-3 text-left font-medium text-slate-700">
                {t('categories.columns.name')}
              </th>
              <th className="px-4 py-3 text-left font-medium text-slate-700">
                {t('categories.columns.parent')}
              </th>
              <th className="px-4 py-3 text-left font-medium text-slate-700">
                {t('categories.columns.supplier')}
              </th>
              <th className="px-4 py-3 text-center font-medium text-slate-700">
                {t('categories.columns.products')}
              </th>
              <th className="px-4 py-3 text-center font-medium text-slate-700">
                {t('categories.columns.status')}
              </th>
              <th className="px-4 py-3 text-right font-medium text-slate-700">
                {t('categories.columns.actions')}
              </th>
            </tr>
          </thead>

          {/* Body */}
          <tbody className="divide-y divide-border">
            {categories.map((category) => {
              const isSelected = selectedIds.includes(category.id)
              const isProcessing = isApproving === category.id || isMerging === category.id

              return (
                <tr
                  key={category.id}
                  className={`
                    transition-colors hover:bg-slate-50/50
                    ${isSelected ? 'bg-primary/5' : ''}
                    ${isProcessing ? 'opacity-60' : ''}
                  `}
                >
                  {/* Checkbox */}
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(category.id)}
                      disabled={isProcessing}
                      className="w-4 h-4 rounded border-slate-300 text-primary focus:ring-primary/20"
                      aria-label={`Select ${category.name}`}
                    />
                  </td>

                  {/* Category Name */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <FolderIcon />
                      <span className="font-medium text-slate-900">{category.name}</span>
                    </div>
                  </td>

                  {/* Parent Category */}
                  <td className="px-4 py-3 text-slate-600">
                    {category.parent_name || (
                      <span className="text-slate-400 italic">—</span>
                    )}
                  </td>

                  {/* Supplier */}
                  <td className="px-4 py-3 text-slate-600">
                    {category.supplier_name || (
                      <span className="text-slate-400 italic">—</span>
                    )}
                  </td>

                  {/* Product Count */}
                  <td className="px-4 py-3 text-center">
                    <span className="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-xs font-medium">
                      {category.product_count}
                    </span>
                  </td>

                  {/* Status Badge */}
                  <td className="px-4 py-3 text-center">
                    {category.needs_review ? (
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                        {t('categories.status.needsReview')}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-green-100 text-green-700 text-xs font-medium">
                        <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                        {t('categories.status.approved')}
                      </span>
                    )}
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      {/* Approve Button */}
                      <button
                        onClick={() => onApprove(category)}
                        disabled={isProcessing || !category.needs_review}
                        className={`
                          inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
                          ${
                            category.needs_review && !isProcessing
                              ? 'bg-green-50 text-green-700 hover:bg-green-100 border border-green-200'
                              : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                          }
                        `}
                        title={t('categories.actions.approve')}
                      >
                        {isApproving === category.id ? (
                          <span className="animate-spin w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full" />
                        ) : (
                          <CheckIcon />
                        )}
                        <span className="hidden sm:inline">
                          {isApproving === category.id
                            ? t('categories.actions.approving')
                            : t('categories.actions.approve')}
                        </span>
                      </button>

                      {/* Merge Button */}
                      <button
                        onClick={() => onMerge(category)}
                        disabled={isProcessing}
                        className={`
                          inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
                          ${
                            !isProcessing
                              ? 'bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200'
                              : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                          }
                        `}
                        title={t('categories.actions.merge')}
                      >
                        {isMerging === category.id ? (
                          <span className="animate-spin w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full" />
                        ) : (
                          <MergeIcon />
                        )}
                        <span className="hidden sm:inline">
                          {isMerging === category.id
                            ? t('categories.actions.merging')
                            : t('categories.actions.merge')}
                        </span>
                      </button>

                      {/* Edit/Delete Button */}
                      <button
                        onClick={() => onEdit(category)}
                        disabled={isProcessing}
                        className={`
                          inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
                          ${
                            !isProcessing
                              ? 'bg-slate-50 text-slate-700 hover:bg-slate-100 border border-slate-200'
                              : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                          }
                        `}
                        title={t('categories.edit.title')}
                      >
                        <EditIcon />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

