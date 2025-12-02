/**
 * SupplierAddModal Component
 *
 * Modal dialog for adding new suppliers with optional file upload.
 * Supports drag-and-drop file upload with automatic format detection.
 *
 * Features:
 * - Add supplier manually (name, source type, URL)
 * - Drag-and-drop file upload (CSV, XLSX)
 * - Automatic format detection from file extension
 * - Real-time validation
 */

import { useState, useCallback } from 'react'
import { useDropzone, type FileRejection } from 'react-dropzone'
import { useTranslation } from 'react-i18next'
import { useCreateSupplier, useUploadSupplierFile } from '@/hooks/useSuppliers'
import type { SourceType, CreateSupplierRequest } from '@/types/supplier'

// =============================================================================
// Types
// =============================================================================

interface SupplierAddModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

// =============================================================================
// Constants
// =============================================================================

const ACCEPTED_FILE_TYPES = {
  'text/csv': ['.csv'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'application/vnd.ms-excel': ['.xls'],
}

const FILE_EXTENSION_TO_SOURCE_TYPE: Record<string, SourceType> = {
  '.csv': 'csv',
  '.xlsx': 'excel',
  '.xls': 'excel',
}

// =============================================================================
// Icons
// =============================================================================

const CloseIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
)

const UploadIcon = () => (
  <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.5}
      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
    />
  </svg>
)

const FileIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
    />
  </svg>
)

// =============================================================================
// Component
// =============================================================================

export function SupplierAddModal({ isOpen, onClose, onSuccess }: SupplierAddModalProps) {
  const { t } = useTranslation()

  // Form state
  const [name, setName] = useState('')
  const [sourceType, setSourceType] = useState<SourceType>('google_sheets')
  const [sourceUrl, setSourceUrl] = useState('')
  const [isActive, setIsActive] = useState(true)
  const [notes, setNotes] = useState('')

  // File upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)

  // Mutations
  const createSupplier = useCreateSupplier()
  const uploadFile = useUploadSupplierFile()

  // Form validation
  const isValid = name.trim().length > 0

  // Reset form
  const resetForm = useCallback(() => {
    setName('')
    setSourceType('google_sheets')
    setSourceUrl('')
    setIsActive(true)
    setNotes('')
    setSelectedFile(null)
    setFileError(null)
  }, [])

  // Handle close
  const handleClose = useCallback(() => {
    resetForm()
    onClose()
  }, [onClose, resetForm])

  // Dropzone callbacks
  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
    setFileError(null)

    if (rejectedFiles.length > 0) {
      const rejection = rejectedFiles[0]
      const errorCode = rejection.errors[0]?.code
      if (errorCode === 'file-invalid-type') {
        setFileError(t('suppliers.modal.invalidFileType'))
      } else if (errorCode === 'file-too-large') {
        setFileError(t('suppliers.modal.fileTooLarge'))
      } else {
        setFileError(rejection.errors[0]?.message || t('suppliers.modal.uploadError'))
      }
      return
    }

    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0]
      setSelectedFile(file)

      // Auto-detect source type from file extension
      const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
      const detectedType = FILE_EXTENSION_TO_SOURCE_TYPE[ext]
      if (detectedType) {
        setSourceType(detectedType)
      }
    }
  }, [t])

  const { getRootProps, getInputProps, isDragActive, isDragAccept, isDragReject } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024, // 50MB
  })

  // Remove selected file
  const handleRemoveFile = useCallback(() => {
    setSelectedFile(null)
    setFileError(null)
  }, [])

  // Handle submit
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!isValid) return

    try {
      // Create supplier
      const supplierData: CreateSupplierRequest = {
        name: name.trim(),
        source_type: sourceType,
        source_url: sourceUrl.trim() || undefined,
        is_active: isActive,
        notes: notes.trim() || undefined,
      }

      const result = await createSupplier.mutateAsync(supplierData)

      // If file is selected, upload it
      if (selectedFile && result.supplier?.id) {
        await uploadFile.mutateAsync({
          supplierId: result.supplier.id,
          file: selectedFile,
        })
      }

      // Success
      handleClose()
      onSuccess?.()
    } catch (error) {
      // Error is handled by mutation state
      console.error('Failed to create supplier:', error)
    }
  }

  if (!isOpen) return null

  const isSubmitting = createSupplier.isPending || uploadFile.isPending
  const error = createSupplier.error || uploadFile.error

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={handleClose} />

      {/* Modal */}
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold text-slate-900">{t('suppliers.modal.title')}</h2>
          <button
            onClick={handleClose}
            className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
            aria-label={t('common.close')}
          >
            <CloseIcon />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Supplier Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-slate-700 mb-1.5">
              {t('suppliers.modal.name')} <span className="text-danger">*</span>
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('suppliers.modal.namePlaceholder')}
              className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors"
              required
              autoFocus
            />
          </div>

          {/* Source Type */}
          <div>
            <label htmlFor="sourceType" className="block text-sm font-medium text-slate-700 mb-1.5">
              {t('suppliers.modal.sourceType')}
            </label>
            <select
              id="sourceType"
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value as SourceType)}
              className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors bg-white"
            >
              <option value="google_sheets">{t('suppliers.sourceTypes.google_sheets')}</option>
              <option value="csv">{t('suppliers.sourceTypes.csv')}</option>
              <option value="excel">{t('suppliers.sourceTypes.excel')}</option>
            </select>
          </div>

          {/* Source URL */}
          <div>
            <label htmlFor="sourceUrl" className="block text-sm font-medium text-slate-700 mb-1.5">
              {t('suppliers.modal.sourceUrl')}
            </label>
            <input
              id="sourceUrl"
              type="url"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder={t('suppliers.modal.sourceUrlPlaceholder')}
              className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors"
            />
            <p className="mt-1 text-xs text-slate-500">{t('suppliers.modal.sourceUrlHint')}</p>
          </div>

          {/* File Upload Dropzone */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              {t('suppliers.modal.uploadFile')}
            </label>
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                isDragAccept
                  ? 'border-emerald-400 bg-emerald-50'
                  : isDragReject
                  ? 'border-danger bg-danger/5'
                  : isDragActive
                  ? 'border-primary bg-primary/5'
                  : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
              }`}
            >
              <input {...getInputProps()} />
              {selectedFile ? (
                <div className="flex items-center justify-center gap-3">
                  <FileIcon />
                  <div className="text-left">
                    <p className="text-sm font-medium text-slate-900">{selectedFile.name}</p>
                    <p className="text-xs text-slate-500">
                      {(selectedFile.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRemoveFile()
                    }}
                    className="p-1 text-slate-400 hover:text-danger rounded-lg hover:bg-slate-100"
                    aria-label={t('common.remove')}
                  >
                    <CloseIcon />
                  </button>
                </div>
              ) : (
                <div className="text-slate-500">
                  <UploadIcon />
                  <p className="mt-2 text-sm">{t('suppliers.modal.dropzoneText')}</p>
                  <p className="mt-1 text-xs text-slate-400">{t('suppliers.modal.dropzoneHint')}</p>
                </div>
              )}
            </div>
            {fileError && <p className="mt-1.5 text-xs text-danger">{fileError}</p>}
          </div>

          {/* Active Toggle */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              role="switch"
              aria-checked={isActive}
              onClick={() => setIsActive(!isActive)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                isActive ? 'bg-primary' : 'bg-slate-200'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  isActive ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
            <span className="text-sm text-slate-700">{t('suppliers.modal.activeLabel')}</span>
          </div>

          {/* Notes */}
          <div>
            <label htmlFor="notes" className="block text-sm font-medium text-slate-700 mb-1.5">
              {t('suppliers.modal.notes')}
            </label>
            <textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t('suppliers.modal.notesPlaceholder')}
              rows={2}
              className="w-full px-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors resize-none"
            />
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 bg-danger/10 border border-danger/20 rounded-lg">
              <p className="text-sm text-danger">{error.message}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              disabled={isSubmitting}
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={!isValid || isSubmitting}
              className={`px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors ${
                isValid && !isSubmitting
                  ? 'bg-primary hover:bg-primary/90'
                  : 'bg-slate-300 cursor-not-allowed'
              }`}
            >
              {isSubmitting ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  {t('common.saving')}
                </span>
              ) : (
                t('suppliers.modal.create')
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

