/**
 * CategoryApprovalDialog Component
 *
 * Modal dialog for approving categories or merging them with existing ones.
 * Provides merge suggestions based on similarity.
 *
 * @see /specs/009-semantic-etl/spec.md - US3: Category Review Workflow
 */

import { useState, useEffect, useMemo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import type { CategoryReviewItem, CategoryMatchSuggestion } from '@/types/category'

// =============================================================================
// Icons
// =============================================================================

const CloseIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
)

const SearchIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
    />
  </svg>
)

const MergeIcon = () => (
  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"
    />
  </svg>
)

const FolderIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
    />
  </svg>
)

const CheckIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
)

const AlertIcon = () => (
  <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
    />
  </svg>
)

// =============================================================================
// Types
// =============================================================================

interface CategoryApprovalDialogProps {
  open: boolean
  category: CategoryReviewItem | null
  suggestions?: CategoryMatchSuggestion[]
  isLoadingSuggestions?: boolean
  onClose: () => void
  onApprove: () => void
  onMerge: (targetId: string) => void
  isApproving?: boolean
  isMerging?: boolean
}

// =============================================================================
// Component
// =============================================================================

export function CategoryApprovalDialog({
  open,
  category,
  suggestions = [],
  isLoadingSuggestions = false,
  onClose,
  onApprove,
  onMerge,
  isApproving = false,
  isMerging = false,
}: CategoryApprovalDialogProps) {
  const { t } = useTranslation()
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'approve' | 'merge'>('approve')

  // Reset state when dialog opens/closes or category changes
  useEffect(() => {
    if (open && category) {
      setSearchTerm('')
      setSelectedTargetId(null)
      setActiveTab('approve')
    }
  }, [open, category?.id])

  // Filter suggestions by search term
  const filteredSuggestions = useMemo(() => {
    if (!searchTerm.trim()) return suggestions
    const term = searchTerm.toLowerCase()
    return suggestions.filter((s) => s.name.toLowerCase().includes(term))
  }, [suggestions, searchTerm])

  // Handle merge
  const handleMerge = useCallback(() => {
    if (selectedTargetId) {
      onMerge(selectedTargetId)
    }
  }, [selectedTargetId, onMerge])

  // Handle backdrop click
  const handleBackdropClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }, [onClose])

  // Don't render if not open or no category
  if (!open || !category) return null

  const isProcessing = isApproving || isMerging

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="dialog-title"
    >
      <div className="w-full max-w-2xl bg-white rounded-2xl shadow-2xl animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-amber-100">
              <FolderIcon />
            </div>
            <div>
              <h2 id="dialog-title" className="text-lg font-semibold text-slate-900">
                {t('categories.dialog.title')}
              </h2>
              <p className="text-sm text-slate-500">{category.name}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50"
            aria-label={t('common.close')}
          >
            <CloseIcon />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border">
          <button
            onClick={() => setActiveTab('approve')}
            disabled={isProcessing}
            className={`
              flex-1 px-6 py-3 text-sm font-medium transition-colors
              ${activeTab === 'approve'
                ? 'text-green-700 border-b-2 border-green-500 bg-green-50/50'
                : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }
            `}
          >
            <div className="flex items-center justify-center gap-2">
              <CheckIcon />
              {t('categories.dialog.tabApprove')}
            </div>
          </button>
          <button
            onClick={() => setActiveTab('merge')}
            disabled={isProcessing}
            className={`
              flex-1 px-6 py-3 text-sm font-medium transition-colors
              ${activeTab === 'merge'
                ? 'text-blue-700 border-b-2 border-blue-500 bg-blue-50/50'
                : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }
            `}
          >
            <div className="flex items-center justify-center gap-2">
              <MergeIcon />
              {t('categories.dialog.tabMerge')}
            </div>
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-6">
          {activeTab === 'approve' ? (
            // Approve Tab Content
            <div className="space-y-4">
              <div className="flex items-start gap-3 p-4 bg-green-50 rounded-xl border border-green-200">
                <CheckIcon />
                <div>
                  <h3 className="font-medium text-green-800">
                    {t('categories.dialog.approveTitle')}
                  </h3>
                  <p className="mt-1 text-sm text-green-700">
                    {t('categories.dialog.approveDescription')}
                  </p>
                </div>
              </div>

              {/* Category Info */}
              <div className="grid grid-cols-2 gap-4 p-4 bg-slate-50 rounded-xl">
                <div>
                  <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                    {t('categories.dialog.categoryName')}
                  </span>
                  <p className="mt-1 font-medium text-slate-900">{category.name}</p>
                </div>
                <div>
                  <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                    {t('categories.dialog.productCount')}
                  </span>
                  <p className="mt-1 font-medium text-slate-900">{category.product_count}</p>
                </div>
                {category.parent_name && (
                  <div>
                    <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                      {t('categories.dialog.parentCategory')}
                    </span>
                    <p className="mt-1 font-medium text-slate-900">{category.parent_name}</p>
                  </div>
                )}
                {category.supplier_name && (
                  <div>
                    <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                      {t('categories.dialog.supplier')}
                    </span>
                    <p className="mt-1 font-medium text-slate-900">{category.supplier_name}</p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            // Merge Tab Content
            <div className="space-y-4">
              {/* Warning */}
              <div className="flex items-start gap-3 p-4 bg-amber-50 rounded-xl border border-amber-200">
                <AlertIcon />
                <div>
                  <h3 className="font-medium text-amber-800">
                    {t('categories.dialog.mergeWarningTitle')}
                  </h3>
                  <p className="mt-1 text-sm text-amber-700">
                    {t('categories.dialog.mergeWarningDescription', {
                      count: category.product_count,
                    })}
                  </p>
                </div>
              </div>

              {/* Search */}
              <div className="relative">
                <SearchIcon />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder={t('categories.dialog.searchPlaceholder')}
                  className="w-full pl-10 pr-4 py-2.5 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                  disabled={isProcessing}
                />
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                  <SearchIcon />
                </div>
              </div>

              {/* Suggestions List */}
              <div className="max-h-64 overflow-y-auto rounded-xl border border-border">
                {isLoadingSuggestions ? (
                  <div className="p-8 text-center">
                    <div className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 animate-pulse mb-2">
                      <span className="animate-spin w-4 h-4 border-2 border-primary border-t-transparent rounded-full" />
                    </div>
                    <p className="text-sm text-slate-500">{t('common.loading')}</p>
                  </div>
                ) : filteredSuggestions.length === 0 ? (
                  <div className="p-8 text-center">
                    <p className="text-sm text-slate-500">
                      {searchTerm
                        ? t('categories.dialog.noSearchResults')
                        : t('categories.dialog.noSuggestions')}
                    </p>
                  </div>
                ) : (
                  <ul className="divide-y divide-border">
                    {filteredSuggestions.map((suggestion) => (
                      <li key={suggestion.id}>
                        <button
                          onClick={() => setSelectedTargetId(suggestion.id)}
                          disabled={isProcessing}
                          className={`
                            w-full flex items-center justify-between px-4 py-3 text-left transition-colors
                            ${
                              selectedTargetId === suggestion.id
                                ? 'bg-blue-50 border-l-4 border-l-blue-500'
                                : 'hover:bg-slate-50 border-l-4 border-l-transparent'
                            }
                          `}
                        >
                          <div className="flex items-center gap-3">
                            <FolderIcon />
                            <div>
                              <p className="font-medium text-slate-900">{suggestion.name}</p>
                              <p className="text-xs text-slate-500">
                                {t('categories.dialog.productsCount', {
                                  count: suggestion.product_count,
                                })}
                              </p>
                            </div>
                          </div>
                          {suggestion.similarity_score > 0 && (
                            <span className="text-xs font-medium text-blue-600 bg-blue-100 px-2 py-1 rounded-full">
                              {Math.round(suggestion.similarity_score * 100)}%{' '}
                              {t('categories.dialog.match')}
                            </span>
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border bg-slate-50 rounded-b-2xl">
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-200 rounded-lg transition-colors disabled:opacity-50"
          >
            {t('common.cancel')}
          </button>

          {activeTab === 'approve' ? (
            <button
              onClick={onApprove}
              disabled={isProcessing}
              className="inline-flex items-center gap-2 px-5 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isApproving ? (
                <>
                  <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                  {t('categories.actions.approving')}
                </>
              ) : (
                <>
                  <CheckIcon />
                  {t('categories.actions.approve')}
                </>
              )}
            </button>
          ) : (
            <button
              onClick={handleMerge}
              disabled={isProcessing || !selectedTargetId}
              className="inline-flex items-center gap-2 px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isMerging ? (
                <>
                  <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                  {t('categories.actions.merging')}
                </>
              ) : (
                <>
                  <MergeIcon />
                  {t('categories.actions.merge')}
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

