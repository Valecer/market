/**
 * DuplicatesReviewPage
 *
 * Admin page for reviewing and managing potential duplicate products.
 * Supports filtering by status, merge and dismiss actions.
 *
 * Phase 11: Pipeline Stabilization - US2 Auto-Creation + Duplicate Detection
 *
 * @see /specs/011-pipeline-stabilization/spec.md - FR-5: Potential Duplicate Detection
 */

import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  useDuplicates,
  useDuplicateStats,
  useMergeDuplicate,
  useDismissDuplicate,
} from '@/hooks/useDuplicates'
import { PotentialDuplicatesTable } from '@/components/admin/PotentialDuplicatesTable'
import { ProductMergeModal } from '@/components/admin/ProductMergeModal'
import type { PotentialDuplicate, DuplicateStatus, DuplicateListQuery } from '@/types/duplicate'

// =============================================================================
// Icons
// =============================================================================

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
// Help Panel Component
// =============================================================================

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
          {t('duplicates.help.title', 'How does duplicate detection work?')}
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
            <div>
              <h4 className="font-semibold text-slate-900 mb-1">
                {t('duplicates.help.whatIsThis.title', 'What is this page?')}
              </h4>
              <p>
                {t(
                  'duplicates.help.whatIsThis.content',
                  'This page shows product pairs that were automatically flagged as potential duplicates during ingestion. Products with 85-90% name similarity and similar prices may be the same product listed differently.'
                )}
              </p>
            </div>

            <div>
              <h4 className="font-semibold text-slate-900 mb-1">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 bg-primary rounded-full" />
                  {t('duplicates.help.merge.title', 'Merge')}
                </span>
              </h4>
              <p>
                {t(
                  'duplicates.help.merge.content',
                  'Combines both products into one. Select which product to keep, and all supplier items will be transferred to it. The other product will be archived.'
                )}
              </p>
            </div>

            <div>
              <h4 className="font-semibold text-slate-900 mb-1">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 bg-slate-400 rounded-full" />
                  {t('duplicates.help.dismiss.title', 'Dismiss')}
                </span>
              </h4>
              <p>
                {t(
                  'duplicates.help.dismiss.content',
                  'Marks the pair as a false positive. Both products remain unchanged. Use this when products are similar but actually different (e.g., different brands, models).'
                )}
              </p>
            </div>

            <div className="pt-3 border-t border-slate-200">
              <h4 className="font-semibold text-slate-900 mb-2">
                {t('duplicates.help.tips.title', '💡 Tips')}
              </h4>
              <ul className="list-disc list-inside space-y-1 text-slate-600">
                <li>
                  {t(
                    'duplicates.help.tips.compare',
                    'Compare prices and supplier counts - duplicates often have similar values'
                  )}
                </li>
                <li>
                  {t(
                    'duplicates.help.tips.category',
                    'Check categories - products in the same category are more likely to be duplicates'
                  )}
                </li>
                <li>
                  {t(
                    'duplicates.help.tips.keep',
                    'When merging, keep the product with more supplier items or better data'
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

const PAGE_SIZE = 25

export function DuplicatesReviewPage() {
  const { t } = useTranslation()

  // Query state
  const [query, setQuery] = useState<DuplicateListQuery>({
    status: 'pending',
    limit: PAGE_SIZE,
    offset: 0,
  })

  // Modal state
  const [selectedDuplicate, setSelectedDuplicate] = useState<PotentialDuplicate | null>(null)
  const [mergeModalOpen, setMergeModalOpen] = useState(false)
  const [processingId, setProcessingId] = useState<string | null>(null)
  const [processingAction, setProcessingAction] = useState<'merge' | 'dismiss' | null>(null)

  // Queries
  const { data, isLoading, error, refetch } = useDuplicates(query)
  const { data: stats } = useDuplicateStats()

  // Mutations
  const mergeMutation = useMergeDuplicate()
  const dismissMutation = useDismissDuplicate()

  // Handle status filter change
  const handleStatusChange = useCallback((status: DuplicateStatus) => {
    setQuery((prev) => ({ ...prev, status, offset: 0 }))
  }, [])

  // Handle page change
  const handlePageChange = useCallback((newOffset: number) => {
    setQuery((prev) => ({ ...prev, offset: newOffset }))
  }, [])

  // Open merge modal
  const handleMergeClick = useCallback((duplicate: PotentialDuplicate) => {
    setSelectedDuplicate(duplicate)
    setMergeModalOpen(true)
  }, [])

  // Close merge modal
  const handleCloseModal = useCallback(() => {
    setMergeModalOpen(false)
    setSelectedDuplicate(null)
  }, [])

  // Execute merge
  const handleMerge = useCallback(
    async (keepProductId: string, archiveProductId: string) => {
      if (!selectedDuplicate) return

      setProcessingId(selectedDuplicate.id)
      setProcessingAction('merge')

      try {
        await mergeMutation.mutateAsync({
          duplicateId: selectedDuplicate.id,
          request: { keepProductId, archiveProductId },
        })
        handleCloseModal()
      } finally {
        setProcessingId(null)
        setProcessingAction(null)
      }
    },
    [selectedDuplicate, mergeMutation, handleCloseModal]
  )

  // Execute dismiss
  const handleDismiss = useCallback(
    async (duplicate: PotentialDuplicate) => {
      setProcessingId(duplicate.id)
      setProcessingAction('dismiss')

      try {
        await dismissMutation.mutateAsync(duplicate.id)
      } finally {
        setProcessingId(null)
        setProcessingAction(null)
      }
    },
    [dismissMutation]
  )

  // Pagination info
  const currentPage = Math.floor((query.offset || 0) / PAGE_SIZE) + 1
  const totalPages = Math.ceil((data?.total || 0) / PAGE_SIZE)

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-50 to-slate-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
            {t('duplicates.review.title')}
          </h1>
          <p className="mt-2 text-sm text-slate-600">{t('duplicates.review.description')}</p>
        </div>

        {/* Help Panel */}
        <HelpPanel />

        {/* Stats Summary */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-xl shadow-md border border-border p-4">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                {t('duplicates.stats.total')}
              </span>
              <p className="mt-1 text-2xl font-bold text-slate-900">{stats.total}</p>
            </div>
            <div className="bg-white rounded-xl shadow-md border border-border p-4">
              <span className="text-xs font-medium text-amber-500 uppercase tracking-wider">
                {t('duplicates.stats.pending')}
              </span>
              <p className="mt-1 text-2xl font-bold text-amber-600">{stats.pending}</p>
            </div>
            <div className="bg-white rounded-xl shadow-md border border-border p-4">
              <span className="text-xs font-medium text-green-500 uppercase tracking-wider">
                {t('duplicates.stats.merged')}
              </span>
              <p className="mt-1 text-2xl font-bold text-green-600">{stats.merged}</p>
            </div>
            <div className="bg-white rounded-xl shadow-md border border-border p-4">
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                {t('duplicates.stats.dismissed')}
              </span>
              <p className="mt-1 text-2xl font-bold text-slate-600">{stats.dismissed}</p>
            </div>
          </div>
        )}

        {/* Filters Bar */}
        <div className="bg-white rounded-xl shadow-md border border-border p-4 mb-6">
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
            {/* Status Filter */}
            <div className="relative">
              <select
                value={query.status || 'pending'}
                onChange={(e) => handleStatusChange(e.target.value as DuplicateStatus)}
                className="appearance-none pl-3 pr-10 py-2 border border-border rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary cursor-pointer"
              >
                <option value="pending">{t('duplicates.filter.pending')}</option>
                <option value="merged">{t('duplicates.filter.merged')}</option>
                <option value="dismissed">{t('duplicates.filter.dismissed')}</option>
              </select>
              <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                <FilterIcon />
              </div>
            </div>

            {/* Refresh Button */}
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

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
            <p className="text-sm text-red-700">{error.message}</p>
          </div>
        )}

        {/* Table */}
        <PotentialDuplicatesTable
          duplicates={data?.duplicates || []}
          isLoading={isLoading}
          onMerge={handleMergeClick}
          onDismiss={handleDismiss}
          mergingId={processingAction === 'merge' ? processingId : null}
          dismissingId={processingAction === 'dismiss' ? processingId : null}
        />

        {/* Pagination */}
        {data && totalPages > 1 && (
          <div className="mt-6 flex items-center justify-between">
            <p className="text-sm text-slate-600">
              {t('common.pagination.showing', {
                from: (query.offset || 0) + 1,
                to: Math.min((query.offset || 0) + PAGE_SIZE, data.total),
                total: data.total,
              })}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handlePageChange((query.offset || 0) - PAGE_SIZE)}
                disabled={currentPage === 1}
                className="p-2 rounded-lg border border-border text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeftIcon />
              </button>

              <span className="text-sm text-slate-600">
                {currentPage} / {totalPages}
              </span>

              <button
                onClick={() => handlePageChange((query.offset || 0) + PAGE_SIZE)}
                disabled={currentPage === totalPages}
                className="p-2 rounded-lg border border-border text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRightIcon />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Merge Modal */}
      <ProductMergeModal
        open={mergeModalOpen}
        duplicate={selectedDuplicate}
        onClose={handleCloseModal}
        onMerge={handleMerge}
        isMerging={mergeMutation.isPending}
      />
    </div>
  )
}

export default DuplicatesReviewPage
