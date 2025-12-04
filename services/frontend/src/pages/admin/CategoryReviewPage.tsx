/**
 * CategoryReviewPage
 *
 * Admin page for reviewing and managing categories that need approval.
 * Supports filtering, bulk actions, and merge operations.
 *
 * @see /specs/009-semantic-etl/spec.md - US3: Category Review Workflow
 */

import { useState, useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useCategoriesReview, useCategoryMergeSuggestions } from '@/hooks/useCategoriesReview'
import { useCategoryApproval, useBulkCategoryApproval, useCategoryUpdate, useCategoryDelete } from '@/hooks/useCategoryApproval'
import { CategoryReviewTable } from '@/components/admin/CategoryReviewTable'
import { CategoryApprovalDialog } from '@/components/admin/CategoryApprovalDialog'
import { CategoryEditDialog } from '@/components/admin/CategoryEditDialog'
import type { CategoryReviewItem, CategoryReviewQuery } from '@/types/category'

// =============================================================================
// Icons
// =============================================================================

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

const FilterIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
    />
  </svg>
)

const CheckIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
)

const ChevronLeftIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
  </svg>
)

const ChevronRightIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
  </svg>
)

const RefreshIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
    />
  </svg>
)

const InfoIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
    />
  </svg>
)

const ChevronDownIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
  </svg>
)

// =============================================================================
// Component
// =============================================================================

// =============================================================================
// Help Panel Component
// =============================================================================

/**
 * Collapsible help panel that explains the category review workflow.
 * Shows guidance for approve, merge, and bulk actions.
 */
function HelpPanel() {
  const { t } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="mb-6">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-all duration-200"
      >
        <div className="text-blue-600">
          <InfoIcon />
        </div>
        <span className="font-medium text-blue-900 flex-1">
          {t('categories.help.title', 'How does category review work?')}
        </span>
        <div
          className={`transition-transform duration-200 text-blue-600 ${isOpen ? 'rotate-180' : ''}`}
        >
          <ChevronDownIcon />
        </div>
      </button>

      {isOpen && (
        <div className="mt-2 p-4 bg-white border border-blue-100 rounded-lg shadow-sm">
          <div className="space-y-4 text-sm text-slate-700">
            {/* What is this page */}
            <div>
              <h4 className="font-semibold text-slate-900 mb-1">
                {t('categories.help.whatIsThis.title', 'What is this page?')}
              </h4>
              <p>
                {t(
                  'categories.help.whatIsThis.content',
                  'This page shows categories that were automatically created during supplier file processing using AI-based extraction. These categories need your review before they become part of the official catalog.'
                )}
              </p>
            </div>

            {/* Approve action */}
            <div>
              <h4 className="font-semibold text-slate-900 mb-1">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 bg-green-500 rounded-full" />
                  {t('categories.help.approve.title', 'Approve')}
                </span>
              </h4>
              <p>
                {t(
                  'categories.help.approve.content',
                  'Marks the category as reviewed and activates it. The category will be available for future fuzzy matching with a higher confidence score.'
                )}
              </p>
            </div>

            {/* Merge action */}
            <div>
              <h4 className="font-semibold text-slate-900 mb-1">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 bg-blue-500 rounded-full" />
                  {t('categories.help.merge.title', 'Merge')}
                </span>
              </h4>
              <p>
                {t(
                  'categories.help.merge.content',
                  'Combines this category with an existing one. All products will be transferred to the target category, and this category will be deleted. Use this to consolidate duplicates or similar categories.'
                )}
              </p>
            </div>

            {/* Bulk actions */}
            <div>
              <h4 className="font-semibold text-slate-900 mb-1">
                <span className="inline-flex items-center gap-1.5">
                  <CheckIcon />
                  {t('categories.help.bulk.title', 'Bulk Approve')}
                </span>
              </h4>
              <p>
                {t(
                  'categories.help.bulk.content',
                  'Select multiple categories using the checkboxes and approve them all at once. This is useful after reviewing categories from a specific supplier upload.'
                )}
              </p>
            </div>

            {/* Tips */}
            <div className="pt-3 border-t border-slate-200">
              <h4 className="font-semibold text-slate-900 mb-2">
                {t('categories.help.tips.title', '💡 Tips')}
              </h4>
              <ul className="list-disc list-inside space-y-1 text-slate-600">
                <li>
                  {t(
                    'categories.help.tips.similar',
                    'Look for similar category names that might be duplicates (e.g., "Electronics" vs "Электроника")'
                  )}
                </li>
                <li>
                  {t(
                    'categories.help.tips.parent',
                    'Check parent categories - child categories should belong to logical parents'
                  )}
                </li>
                <li>
                  {t(
                    'categories.help.tips.supplier',
                    'Filter by supplier to review categories from a single upload batch'
                  )}
                </li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

/**
 * Status filter value type
 * - 'pending': needs_review=true (default)
 * - 'approved': needs_review=false
 * - 'all': no filter (undefined)
 */
type StatusFilterValue = 'pending' | 'approved' | 'all'

export function CategoryReviewPage() {
  const { t } = useTranslation()

  // Status filter state (separate from query for cleaner UX)
  const [statusFilter, setStatusFilter] = useState<StatusFilterValue>('pending')

  // Query state
  const [query, setQuery] = useState<CategoryReviewQuery>({
    page: 1,
    limit: 25,
    needs_review: true, // Default: pending review
    sort_by: 'created_at',
    sort_order: 'desc',
  })
  const [searchInput, setSearchInput] = useState('')

  // Selection state
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<CategoryReviewItem | null>(null)
  const [processingCategoryId, setProcessingCategoryId] = useState<string | null>(null)
  const [processingAction, setProcessingAction] = useState<'approve' | 'merge' | null>(null)

  // Queries
  const { data, isLoading, error, refetch } = useCategoriesReview(query)
  const { data: mergeSuggestions, isLoading: isLoadingSuggestions } = useCategoryMergeSuggestions(
    selectedCategory?.id || null
  )

  // Mutations
  const approvalMutation = useCategoryApproval()
  const bulkApprovalMutation = useBulkCategoryApproval()
  const updateMutation = useCategoryUpdate()
  const deleteMutation = useCategoryDelete()

  // Handle status filter change
  const handleStatusFilterChange = useCallback((value: StatusFilterValue) => {
    setStatusFilter(value)
    setQuery((prev) => ({
      ...prev,
      needs_review: value === 'all' ? undefined : value === 'pending',
      page: 1,
    }))
    setSelectedIds([]) // Clear selection on filter change
  }, [])

  // Handle search submit
  const handleSearch = useCallback(() => {
    setQuery((prev) => ({
      ...prev,
      search: searchInput || undefined,
      page: 1,
    }))
  }, [searchInput])

  // Handle search on Enter
  const handleSearchKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        handleSearch()
      }
    },
    [handleSearch]
  )

  // Handle page change
  const handlePageChange = useCallback((newPage: number) => {
    setQuery((prev) => ({ ...prev, page: newPage }))
    setSelectedIds([]) // Clear selection on page change
  }, [])

  // Open dialog for approve action
  const handleApprove = useCallback((category: CategoryReviewItem) => {
    setSelectedCategory(category)
    setDialogOpen(true)
  }, [])

  // Open dialog for merge action
  const handleMerge = useCallback((category: CategoryReviewItem) => {
    setSelectedCategory(category)
    setDialogOpen(true)
  }, [])

  // Close dialog
  const handleCloseDialog = useCallback(() => {
    setDialogOpen(false)
    setSelectedCategory(null)
  }, [])

  // Open edit dialog
  const handleEdit = useCallback((category: CategoryReviewItem) => {
    setSelectedCategory(category)
    setEditDialogOpen(true)
  }, [])

  // Close edit dialog
  const handleCloseEditDialog = useCallback(() => {
    setEditDialogOpen(false)
    setSelectedCategory(null)
  }, [])

  // Execute approve
  const handleApproveConfirm = useCallback(async () => {
    if (!selectedCategory) return

    setProcessingCategoryId(selectedCategory.id)
    setProcessingAction('approve')

    try {
      await approvalMutation.mutateAsync({
        category_id: selectedCategory.id,
        action: 'approve',
      })
      handleCloseDialog()
    } finally {
      setProcessingCategoryId(null)
      setProcessingAction(null)
    }
  }, [selectedCategory, approvalMutation, handleCloseDialog])

  // Execute merge
  const handleMergeConfirm = useCallback(
    async (targetId: string) => {
      if (!selectedCategory) return

      setProcessingCategoryId(selectedCategory.id)
      setProcessingAction('merge')

      try {
        await approvalMutation.mutateAsync({
          category_id: selectedCategory.id,
          action: 'merge',
          merge_with_id: targetId,
        })
        handleCloseDialog()
      } finally {
        setProcessingCategoryId(null)
        setProcessingAction(null)
      }
    },
    [selectedCategory, approvalMutation, handleCloseDialog]
  )

  // Bulk approve selected categories
  const handleBulkApprove = useCallback(async () => {
    if (selectedIds.length === 0) return

    try {
      await bulkApprovalMutation.mutateAsync({
        category_ids: selectedIds,
      })
      setSelectedIds([])
    } catch {
      // Error handled by mutation
    }
  }, [selectedIds, bulkApprovalMutation])

  // Execute save (rename)
  const handleSaveConfirm = useCallback(
    async (newName: string) => {
      if (!selectedCategory) return

      try {
        await updateMutation.mutateAsync({
          categoryId: selectedCategory.id,
          name: newName,
        })
        handleCloseEditDialog()
      } catch {
        // Error handled by mutation
      }
    },
    [selectedCategory, updateMutation, handleCloseEditDialog]
  )

  // Execute delete
  const handleDeleteConfirm = useCallback(async () => {
    if (!selectedCategory) return

    try {
      await deleteMutation.mutateAsync(selectedCategory.id)
      handleCloseEditDialog()
    } catch {
      // Error handled by mutation
    }
  }, [selectedCategory, deleteMutation, handleCloseEditDialog])

  // Pagination info
  const totalPages = useMemo(() => {
    if (!data) return 1
    return Math.ceil(data.total_count / (query.limit || 25))
  }, [data, query.limit])

  const currentPage = query.page || 1

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
            {t('categories.review.title')}
          </h1>
          <p className="mt-2 text-sm text-slate-600">{t('categories.review.description')}</p>
        </div>

        {/* Help Panel - Collapsible workflow guide */}
        <HelpPanel />

        {/* Filters Bar */}
        <div className="bg-white rounded-xl shadow-md border border-border p-4 mb-6">
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
            {/* Search */}
            <div className="relative flex-1 max-w-md">
              <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                <SearchIcon />
              </div>
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                placeholder={t('categories.review.searchPlaceholder')}
                className="w-full pl-10 pr-4 py-2.5 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
              />
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              {/* Status filter dropdown */}
              <div className="relative">
                <select
                  value={statusFilter}
                  onChange={(e) => handleStatusFilterChange(e.target.value as StatusFilterValue)}
                  className="appearance-none pl-3 pr-10 py-2 border border-border rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary cursor-pointer"
                >
                  <option value="pending">{t('categories.filter.pending')}</option>
                  <option value="approved">{t('categories.filter.approved')}</option>
                  <option value="all">{t('categories.filter.all')}</option>
                </select>
                <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                  <FilterIcon />
                </div>
              </div>

              {/* Sort dropdown */}
              <div className="relative">
                <select
                  value={`${query.sort_by}-${query.sort_order}`}
                  onChange={(e) => {
                    const [sortBy, sortOrder] = e.target.value.split('-')
                    setQuery((prev) => ({
                      ...prev,
                      sort_by: sortBy as 'created_at' | 'name' | 'product_count',
                      sort_order: sortOrder as 'asc' | 'desc',
                    }))
                  }}
                  className="appearance-none pl-3 pr-10 py-2 border border-border rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary cursor-pointer"
                >
                  <option value="created_at-desc">{t('categories.sort.newestFirst')}</option>
                  <option value="created_at-asc">{t('categories.sort.oldestFirst')}</option>
                  <option value="name-asc">{t('categories.sort.nameAZ')}</option>
                  <option value="name-desc">{t('categories.sort.nameZA')}</option>
                  <option value="product_count-desc">{t('categories.sort.mostProducts')}</option>
                  <option value="product_count-asc">{t('categories.sort.leastProducts')}</option>
                </select>
                <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                  <FilterIcon />
                </div>
              </div>

              {/* Refresh button */}
              <button
                onClick={() => refetch()}
                disabled={isLoading}
                className="inline-flex items-center gap-2 px-4 py-2 border border-border rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50"
              >
                <RefreshIcon />
                <span className="hidden sm:inline">{t('common.refresh')}</span>
              </button>
            </div>
          </div>

          {/* Bulk Actions (when items selected) */}
          {selectedIds.length > 0 && (
            <div className="mt-4 pt-4 border-t border-border flex items-center gap-4">
              <span className="text-sm text-slate-600">
                {t('categories.review.selectedCount', { count: selectedIds.length })}
              </span>
              <button
                onClick={handleBulkApprove}
                disabled={bulkApprovalMutation.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
              >
                {bulkApprovalMutation.isPending ? (
                  <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                ) : (
                  <CheckIcon />
                )}
                {t('categories.actions.approveSelected')}
              </button>
              <button
                onClick={() => setSelectedIds([])}
                className="px-3 py-2 text-sm text-slate-600 hover:text-slate-900 transition-colors"
              >
                {t('common.clearSelection')}
              </button>
            </div>
          )}
        </div>

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
            <p className="text-sm text-red-700">{error.message}</p>
          </div>
        )}

        {/* Stats Summary */}
        {data && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-xl shadow-md border border-border p-4">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                {t('categories.stats.total')}
              </span>
              <p className="mt-1 text-2xl font-bold text-slate-900">{data.total_count}</p>
            </div>
            <div className="bg-white rounded-xl shadow-md border border-border p-4">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                {t('categories.stats.selected')}
              </span>
              <p className="mt-1 text-2xl font-bold text-primary">{selectedIds.length}</p>
            </div>
            <div className="bg-white rounded-xl shadow-md border border-border p-4">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                {t('categories.stats.currentPage')}
              </span>
              <p className="mt-1 text-2xl font-bold text-slate-900">
                {currentPage}/{totalPages}
              </p>
            </div>
            <div className="bg-white rounded-xl shadow-md border border-border p-4">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                {t('categories.stats.perPage')}
              </span>
              <p className="mt-1 text-2xl font-bold text-slate-900">{query.limit}</p>
            </div>
          </div>
        )}

        {/* Table */}
        <CategoryReviewTable
          categories={data?.data || []}
          isLoading={isLoading}
          selectedIds={selectedIds}
          onSelectChange={setSelectedIds}
          onApprove={handleApprove}
          onMerge={handleMerge}
          onEdit={handleEdit}
          isApproving={processingAction === 'approve' ? processingCategoryId : null}
          isMerging={processingAction === 'merge' ? processingCategoryId : null}
        />

        {/* Pagination */}
        {data && totalPages > 1 && (
          <div className="mt-6 flex items-center justify-between">
            <p className="text-sm text-slate-600">
              {t('common.pagination.showing', {
                from: (currentPage - 1) * (query.limit || 25) + 1,
                to: Math.min(currentPage * (query.limit || 25), data.total_count),
                total: data.total_count,
              })}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1}
                className="p-2 rounded-lg border border-border text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeftIcon />
              </button>

              {/* Page numbers */}
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let page: number
                  if (totalPages <= 5) {
                    page = i + 1
                  } else if (currentPage <= 3) {
                    page = i + 1
                  } else if (currentPage >= totalPages - 2) {
                    page = totalPages - 4 + i
                  } else {
                    page = currentPage - 2 + i
                  }

                  return (
                    <button
                      key={page}
                      onClick={() => handlePageChange(page)}
                      className={`
                        w-10 h-10 rounded-lg text-sm font-medium transition-colors
                        ${
                          page === currentPage
                            ? 'bg-primary text-white'
                            : 'text-slate-600 hover:bg-slate-100'
                        }
                      `}
                    >
                      {page}
                    </button>
                  )
                })}
              </div>

              <button
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
                className="p-2 rounded-lg border border-border text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRightIcon />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Approval Dialog */}
      <CategoryApprovalDialog
        open={dialogOpen}
        category={selectedCategory}
        suggestions={mergeSuggestions?.suggestions || []}
        isLoadingSuggestions={isLoadingSuggestions}
        onClose={handleCloseDialog}
        onApprove={handleApproveConfirm}
        onMerge={handleMergeConfirm}
        isApproving={approvalMutation.isPending && processingAction === 'approve'}
        isMerging={approvalMutation.isPending && processingAction === 'merge'}
      />

      {/* Edit/Delete Dialog */}
      <CategoryEditDialog
        open={editDialogOpen}
        category={selectedCategory}
        onClose={handleCloseEditDialog}
        onSave={handleSaveConfirm}
        onDelete={handleDeleteConfirm}
        isSaving={updateMutation.isPending}
        isDeleting={deleteMutation.isPending}
      />
    </div>
  )
}

export default CategoryReviewPage

