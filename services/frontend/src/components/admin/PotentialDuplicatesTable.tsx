/**
 * PotentialDuplicatesTable
 *
 * Admin table showing side-by-side product comparison with Merge/Dismiss actions.
 *
 * Phase 11: Pipeline Stabilization - US2 Duplicate Detection
 *
 * @see /specs/011-pipeline-stabilization/spec.md - FR-5: Potential Duplicate Detection
 */

import { useTranslation } from 'react-i18next'
import type { PotentialDuplicate, ProductSummary } from '@/types/duplicate'

// =============================================================================
// Icons
// =============================================================================

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

const DismissIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
)

const LoadingSpinner = () => (
  <svg
    className="animate-spin w-4 h-4"
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

// =============================================================================
// Product Card Component
// =============================================================================

interface ProductCardProps {
  product: ProductSummary
  isSelected?: boolean
  onSelect?: () => void
  showSelectButton?: boolean
}

function ProductCard({ product, isSelected, onSelect, showSelectButton }: ProductCardProps) {
  const { t } = useTranslation()

  return (
    <div
      className={`
        p-4 rounded-lg border transition-all
        ${isSelected ? 'border-primary bg-primary/5 ring-2 ring-primary/20' : 'border-slate-200 bg-white'}
        ${showSelectButton && onSelect ? 'cursor-pointer hover:border-primary/50' : ''}
      `}
      onClick={showSelectButton ? onSelect : undefined}
    >
      <h4 className="font-medium text-slate-900 mb-2 line-clamp-2">{product.name}</h4>

      <div className="space-y-1.5 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-500">{t('duplicates.table.category')}:</span>
          <span className="text-slate-700 font-medium">{product.category || 'Uncategorized'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">{t('duplicates.table.price')}:</span>
          <span className="text-slate-700 font-medium">
            {product.price.toLocaleString('ru-RU', { style: 'currency', currency: 'BYN' })}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">{t('duplicates.table.suppliers')}:</span>
          <span className="text-slate-700 font-medium">{product.supplierCount}</span>
        </div>
      </div>

      {showSelectButton && (
        <div className="mt-3 pt-3 border-t border-slate-100">
          <div className="flex items-center justify-center gap-2 text-xs">
            {isSelected ? (
              <>
                <div className="w-2 h-2 bg-primary rounded-full" />
                <span className="text-primary font-medium">{t('duplicates.modal.keep')}</span>
              </>
            ) : (
              <span className="text-slate-400">{t('duplicates.modal.clickToSelect')}</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Table Row Component
// =============================================================================

interface DuplicateRowProps {
  duplicate: PotentialDuplicate
  onMerge: (duplicate: PotentialDuplicate) => void
  onDismiss: (duplicate: PotentialDuplicate) => void
  isMerging: boolean
  isDismissing: boolean
}

function DuplicateRow({
  duplicate,
  onMerge,
  onDismiss,
  isMerging,
  isDismissing,
}: DuplicateRowProps) {
  const { t } = useTranslation()

  const similarityColor =
    duplicate.similarityScore >= 88
      ? 'text-red-600 bg-red-50'
      : duplicate.similarityScore >= 85
      ? 'text-orange-600 bg-orange-50'
      : 'text-yellow-600 bg-yellow-50'

  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50/50 transition-colors">
      {/* Similarity Score */}
      <td className="px-4 py-4 whitespace-nowrap">
        <span className={`inline-flex px-2.5 py-1 rounded-full text-sm font-medium ${similarityColor}`}>
          {duplicate.similarityScore.toFixed(1)}%
        </span>
      </td>

      {/* Product 1 */}
      <td className="px-4 py-4">
        <div className="max-w-xs">
          <div className="font-medium text-slate-900 line-clamp-2 mb-1">{duplicate.product1.name}</div>
          <div className="text-xs text-slate-500">
            {duplicate.product1.category || 'Uncategorized'} •{' '}
            {duplicate.product1.price.toLocaleString('ru-RU', { style: 'currency', currency: 'BYN' })} •{' '}
            {duplicate.product1.supplierCount} {t('duplicates.table.supplierItems')}
          </div>
        </div>
      </td>

      {/* VS Indicator */}
      <td className="px-2 py-4 text-center">
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 text-slate-500 text-xs font-medium">
          VS
        </span>
      </td>

      {/* Product 2 */}
      <td className="px-4 py-4">
        <div className="max-w-xs">
          <div className="font-medium text-slate-900 line-clamp-2 mb-1">{duplicate.product2.name}</div>
          <div className="text-xs text-slate-500">
            {duplicate.product2.category || 'Uncategorized'} •{' '}
            {duplicate.product2.price.toLocaleString('ru-RU', { style: 'currency', currency: 'BYN' })} •{' '}
            {duplicate.product2.supplierCount} {t('duplicates.table.supplierItems')}
          </div>
        </div>
      </td>

      {/* Actions */}
      <td className="px-4 py-4 whitespace-nowrap">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onMerge(duplicate)}
            disabled={isMerging || isDismissing}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-primary bg-primary/10 rounded-lg hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isMerging ? <LoadingSpinner /> : <MergeIcon />}
            {t('duplicates.actions.merge')}
          </button>
          <button
            onClick={() => onDismiss(duplicate)}
            disabled={isMerging || isDismissing}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isDismissing ? <LoadingSpinner /> : <DismissIcon />}
            {t('duplicates.actions.dismiss')}
          </button>
        </div>
      </td>
    </tr>
  )
}

// =============================================================================
// Main Component
// =============================================================================

interface PotentialDuplicatesTableProps {
  duplicates: PotentialDuplicate[]
  isLoading?: boolean
  onMerge: (duplicate: PotentialDuplicate) => void
  onDismiss: (duplicate: PotentialDuplicate) => void
  mergingId: string | null
  dismissingId: string | null
}

export function PotentialDuplicatesTable({
  duplicates,
  isLoading = false,
  onMerge,
  onDismiss,
  mergingId,
  dismissingId,
}: PotentialDuplicatesTableProps) {
  const { t } = useTranslation()

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl shadow-md border border-border">
        <div className="flex items-center justify-center py-16">
          <div className="flex items-center gap-3 text-slate-500">
            <LoadingSpinner />
            <span>{t('common.loading')}</span>
          </div>
        </div>
      </div>
    )
  }

  if (duplicates.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-md border border-border">
        <div className="flex flex-col items-center justify-center py-16 text-slate-500">
          <svg
            className="w-12 h-12 mb-4 text-slate-300"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span className="text-lg font-medium">{t('duplicates.empty.title')}</span>
          <span className="text-sm">{t('duplicates.empty.description')}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-md border border-border overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-50 border-b border-border">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                {t('duplicates.table.similarity')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                {t('duplicates.table.product1')}
              </th>
              <th className="px-2 py-3"></th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                {t('duplicates.table.product2')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                {t('duplicates.table.actions')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {duplicates.map((duplicate) => (
              <DuplicateRow
                key={duplicate.id}
                duplicate={duplicate}
                onMerge={onMerge}
                onDismiss={onDismiss}
                isMerging={mergingId === duplicate.id}
                isDismissing={dismissingId === duplicate.id}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// Also export ProductCard for use in modal
export { ProductCard }
