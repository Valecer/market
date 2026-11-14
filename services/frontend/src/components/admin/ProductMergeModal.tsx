/**
 * ProductMergeModal
 *
 * Confirmation dialog for merge action, showing supplier item counts
 * and preview of kept product.
 *
 * Phase 11: Pipeline Stabilization - US2 Duplicate Detection
 *
 * @see /specs/011-pipeline-stabilization/spec.md
 */

import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import type { PotentialDuplicate } from '@/types/duplicate'
import { ProductCard } from './PotentialDuplicatesTable'

// =============================================================================
// Icons
// =============================================================================

const CloseIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
)

const MergeIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"
    />
  </svg>
)

const LoadingSpinner = () => (
  <svg
    className="animate-spin w-5 h-5"
    xmlns="http://www.w3.org/2000/svg"
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
    ></circle>
    <path
      className="opacity-75"
      fill="currentColor"
      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
    ></path>
  </svg>
)

const WarningIcon = () => (
  <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
    />
  </svg>
)

const ArrowRightIcon = () => (
  <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
  </svg>
)

// =============================================================================
// Component
// =============================================================================

interface ProductMergeModalProps {
  open: boolean
  duplicate: PotentialDuplicate | null
  onClose: () => void
  onMerge: (keepProductId: string, archiveProductId: string) => void
  isMerging: boolean
}

export function ProductMergeModal({
  open,
  duplicate,
  onClose,
  onMerge,
  isMerging,
}: ProductMergeModalProps) {
  const { t } = useTranslation()
  const [selectedKeepId, setSelectedKeepId] = useState<string | null>(null)

  // Reset selection when modal opens/closes
  const handleClose = useCallback(() => {
    setSelectedKeepId(null)
    onClose()
  }, [onClose])

  // Handle merge confirmation
  const handleMerge = useCallback(() => {
    if (!duplicate || !selectedKeepId) return

    const archiveId =
      selectedKeepId === duplicate.product1.id ? duplicate.product2.id : duplicate.product1.id

    onMerge(selectedKeepId, archiveId)
  }, [duplicate, selectedKeepId, onMerge])

  if (!open || !duplicate) return null

  const selectedProduct =
    selectedKeepId === duplicate.product1.id
      ? duplicate.product1
      : selectedKeepId === duplicate.product2.id
      ? duplicate.product2
      : null

  const archivedProduct =
    selectedKeepId === duplicate.product1.id
      ? duplicate.product2
      : selectedKeepId === duplicate.product2.id
      ? duplicate.product1
      : null

  const totalSupplierItems =
    (selectedProduct?.supplierCount || 0) + (archivedProduct?.supplierCount || 0)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-900">{t('duplicates.modal.title')}</h2>
            <p className="text-sm text-slate-500 mt-1">{t('duplicates.modal.subtitle')}</p>
          </div>
          <button
            onClick={handleClose}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Similarity Badge */}
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-500">{t('duplicates.modal.similarity')}:</span>
            <span className="inline-flex px-2.5 py-1 rounded-full bg-orange-50 text-orange-600 font-medium">
              {duplicate.similarityScore.toFixed(1)}%
            </span>
          </div>

          {/* Instructions */}
          <div className="p-4 bg-blue-50 border border-blue-100 rounded-lg">
            <p className="text-sm text-blue-800">
              {t('duplicates.modal.instructions')}
            </p>
          </div>

          {/* Product Selection */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ProductCard
              product={duplicate.product1}
              isSelected={selectedKeepId === duplicate.product1.id}
              onSelect={() => setSelectedKeepId(duplicate.product1.id)}
              showSelectButton
            />
            <ProductCard
              product={duplicate.product2}
              isSelected={selectedKeepId === duplicate.product2.id}
              onSelect={() => setSelectedKeepId(duplicate.product2.id)}
              showSelectButton
            />
          </div>

          {/* Merge Preview */}
          {selectedProduct && archivedProduct && (
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-4">
              <div className="flex items-center gap-3">
                <WarningIcon />
                <span className="font-medium text-slate-900">{t('duplicates.modal.preview')}</span>
              </div>

              <div className="flex items-center justify-center gap-4">
                <div className="text-center">
                  <div className="text-sm text-slate-500 mb-1">{t('duplicates.modal.archived')}</div>
                  <div className="px-4 py-2 bg-red-50 border border-red-200 rounded-lg">
                    <span className="font-medium text-red-700 line-clamp-1">
                      {archivedProduct.name}
                    </span>
                  </div>
                </div>

                <ArrowRightIcon />

                <div className="text-center">
                  <div className="text-sm text-slate-500 mb-1">{t('duplicates.modal.kept')}</div>
                  <div className="px-4 py-2 bg-green-50 border border-green-200 rounded-lg">
                    <span className="font-medium text-green-700 line-clamp-1">
                      {selectedProduct.name}
                    </span>
                  </div>
                </div>
              </div>

              <div className="text-sm text-slate-600 text-center">
                {t('duplicates.modal.supplierItemsAfter', { count: totalSupplierItems })}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-white border-t border-slate-200 px-6 py-4 flex items-center justify-end gap-3">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors"
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={handleMerge}
            disabled={!selectedKeepId || isMerging}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isMerging ? (
              <>
                <LoadingSpinner />
                {t('duplicates.modal.merging')}
              </>
            ) : (
              <>
                <MergeIcon />
                {t('duplicates.modal.confirmMerge')}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ProductMergeModal
