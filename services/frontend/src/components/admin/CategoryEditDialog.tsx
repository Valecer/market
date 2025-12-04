/**
 * CategoryEditDialog Component
 *
 * Modal dialog for editing or deleting a category.
 * Provides rename and delete actions with confirmation.
 *
 * @see /specs/009-semantic-etl/spec.md - US3: Category Review Workflow
 */

import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import type { CategoryReviewItem } from '@/types/category'

// =============================================================================
// Icons
// =============================================================================

const CloseIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
)

const EditIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
    />
  </svg>
)

const TrashIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
    />
  </svg>
)

const AlertIcon = () => (
  <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
    />
  </svg>
)

const SaveIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
)

// =============================================================================
// Types
// =============================================================================

interface CategoryEditDialogProps {
  open: boolean
  category: CategoryReviewItem | null
  onClose: () => void
  onSave: (name: string) => void
  onDelete: () => void
  isSaving?: boolean
  isDeleting?: boolean
}

// =============================================================================
// Component
// =============================================================================

export function CategoryEditDialog({
  open,
  category,
  onClose,
  onSave,
  onDelete,
  isSaving = false,
  isDeleting = false,
}: CategoryEditDialogProps) {
  const { t } = useTranslation()
  const [name, setName] = useState('')
  const [activeTab, setActiveTab] = useState<'edit' | 'delete'>('edit')
  const [deleteConfirmation, setDeleteConfirmation] = useState('')

  // Reset state when dialog opens/closes or category changes
  useEffect(() => {
    if (open && category) {
      setName(category.name)
      setActiveTab('edit')
      setDeleteConfirmation('')
    }
  }, [open, category?.id, category?.name])

  // Handle save
  const handleSave = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      if (name.trim() && name.trim() !== category?.name) {
        onSave(name.trim())
      }
    },
    [name, category?.name, onSave]
  )

  // Handle delete
  const handleDelete = useCallback(() => {
    if (deleteConfirmation === category?.name) {
      onDelete()
    }
  }, [deleteConfirmation, category?.name, onDelete])

  // Handle backdrop click
  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) {
        onClose()
      }
    },
    [onClose]
  )

  // Don't render if not open or no category
  if (!open || !category) return null

  const isProcessing = isSaving || isDeleting
  const canSave = name.trim() && name.trim() !== category.name
  const canDelete = deleteConfirmation === category.name

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-dialog-title"
    >
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-blue-100 text-blue-600">
              <EditIcon />
            </div>
            <div>
              <h2 id="edit-dialog-title" className="text-lg font-semibold text-slate-900">
                {t('categories.edit.title')}
              </h2>
              <p className="text-sm text-slate-500 truncate max-w-xs">{category.name}</p>
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
        <div className="flex border-b border-slate-200">
          <button
            onClick={() => setActiveTab('edit')}
            disabled={isProcessing}
            className={`
              flex-1 px-6 py-3 text-sm font-medium transition-colors
              ${
                activeTab === 'edit'
                  ? 'text-blue-700 border-b-2 border-blue-500 bg-blue-50/50'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }
            `}
          >
            <div className="flex items-center justify-center gap-2">
              <EditIcon />
              {t('categories.edit.tabEdit')}
            </div>
          </button>
          <button
            onClick={() => setActiveTab('delete')}
            disabled={isProcessing}
            className={`
              flex-1 px-6 py-3 text-sm font-medium transition-colors
              ${
                activeTab === 'delete'
                  ? 'text-red-700 border-b-2 border-red-500 bg-red-50/50'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }
            `}
          >
            <div className="flex items-center justify-center gap-2">
              <TrashIcon />
              {t('categories.edit.tabDelete')}
            </div>
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-6">
          {activeTab === 'edit' ? (
            // Edit Tab Content
            <form onSubmit={handleSave} className="space-y-4">
              <div>
                <label
                  htmlFor="category-name"
                  className="block text-sm font-medium text-slate-700 mb-1"
                >
                  {t('categories.edit.nameLabel')}
                </label>
                <input
                  id="category-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t('categories.edit.namePlaceholder')}
                  disabled={isProcessing}
                  className="w-full px-4 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 disabled:bg-slate-50 disabled:text-slate-500"
                  autoFocus
                />
              </div>

              {/* Category Info */}
              <div className="grid grid-cols-2 gap-4 p-4 bg-slate-50 rounded-xl text-sm">
                <div>
                  <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                    {t('categories.edit.productCount')}
                  </span>
                  <p className="mt-1 font-medium text-slate-900">{category.product_count}</p>
                </div>
                {category.parent_name && (
                  <div>
                    <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                      {t('categories.edit.parentCategory')}
                    </span>
                    <p className="mt-1 font-medium text-slate-900">{category.parent_name}</p>
                  </div>
                )}
                {category.supplier_name && (
                  <div className="col-span-2">
                    <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                      {t('categories.edit.supplier')}
                    </span>
                    <p className="mt-1 font-medium text-slate-900">{category.supplier_name}</p>
                  </div>
                )}
              </div>
            </form>
          ) : (
            // Delete Tab Content
            <div className="space-y-4">
              {/* Warning */}
              <div className="flex items-start gap-3 p-4 bg-red-50 rounded-xl border border-red-200">
                <AlertIcon />
                <div>
                  <h3 className="font-medium text-red-800">{t('categories.edit.deleteWarningTitle')}</h3>
                  <p className="mt-1 text-sm text-red-700">
                    {t('categories.edit.deleteWarningDescription', {
                      count: category.product_count,
                    })}
                  </p>
                </div>
              </div>

              {/* Confirmation Input */}
              <div>
                <label htmlFor="delete-confirm" className="block text-sm font-medium text-slate-700 mb-1">
                  {t('categories.edit.deleteConfirmLabel')}
                </label>
                <p className="text-sm text-slate-500 mb-2">
                  {t('categories.edit.deleteConfirmHint', { name: category.name })}
                </p>
                <input
                  id="delete-confirm"
                  type="text"
                  value={deleteConfirmation}
                  onChange={(e) => setDeleteConfirmation(e.target.value)}
                  placeholder={category.name}
                  disabled={isProcessing}
                  className="w-full px-4 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500 disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 bg-slate-50 rounded-b-2xl">
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-200 rounded-lg transition-colors disabled:opacity-50"
          >
            {t('common.cancel')}
          </button>

          {activeTab === 'edit' ? (
            <button
              onClick={() => canSave && handleSave({ preventDefault: () => {} } as React.FormEvent)}
              disabled={isProcessing || !canSave}
              className="inline-flex items-center gap-2 px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSaving ? (
                <>
                  <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                  {t('categories.edit.saving')}
                </>
              ) : (
                <>
                  <SaveIcon />
                  {t('categories.edit.save')}
                </>
              )}
            </button>
          ) : (
            <button
              onClick={handleDelete}
              disabled={isProcessing || !canDelete}
              className="inline-flex items-center gap-2 px-5 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isDeleting ? (
                <>
                  <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                  {t('categories.edit.deleting')}
                </>
              ) : (
                <>
                  <TrashIcon />
                  {t('categories.edit.delete')}
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

