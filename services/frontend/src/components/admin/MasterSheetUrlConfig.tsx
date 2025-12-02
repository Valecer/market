/**
 * MasterSheetUrlConfig Component
 *
 * Allows administrators to view and update the master Google Sheet URL
 * used for supplier synchronization.
 */

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useMasterSheetUrl, useUpdateMasterSheetUrl } from '@/hooks/useSettings'

// =============================================================================
// Icons
// =============================================================================

const LinkIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
    />
  </svg>
)

const CheckIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
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

// =============================================================================
// Component
// =============================================================================

export function MasterSheetUrlConfig() {
  const { t } = useTranslation()
  const { data, isLoading, error: fetchError } = useMasterSheetUrl()
  const updateUrl = useUpdateMasterSheetUrl()

  const [isEditing, setIsEditing] = useState(false)
  const [urlValue, setUrlValue] = useState('')
  const [sheetNameValue, setSheetNameValue] = useState('Suppliers')
  const [showSuccess, setShowSuccess] = useState(false)

  // Sync URL and sheet name values with fetched data
  useEffect(() => {
    if (data?.url) {
      setUrlValue(data.url)
    }
    if (data?.sheet_name) {
      setSheetNameValue(data.sheet_name)
    }
  }, [data?.url, data?.sheet_name])

  // Handle save
  const handleSave = async () => {
    if (!urlValue.trim()) return

    try {
      await updateUrl.mutateAsync({
        url: urlValue.trim(),
        sheet_name: sheetNameValue.trim() || 'Suppliers',
      })
      setIsEditing(false)
      setShowSuccess(true)
      setTimeout(() => setShowSuccess(false), 3000)
    } catch (error) {
      // Error is handled by mutation state
    }
  }

  // Handle cancel
  const handleCancel = () => {
    setUrlValue(data?.url || '')
    setSheetNameValue(data?.sheet_name || 'Suppliers')
    setIsEditing(false)
  }

  // Validate URL format
  const isValidUrl = (url: string): boolean => {
    try {
      const parsed = new URL(url)
      return parsed.hostname.includes('docs.google.com') || parsed.hostname.includes('sheets.google')
    } catch {
      return false
    }
  }

  const isValid = urlValue.trim() && isValidUrl(urlValue)

  return (
    <div className="bg-white rounded-xl shadow-md border border-border overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border bg-slate-50">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg text-primary">
            <LinkIcon />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              {t('settings.masterSheetUrl.title')}
            </h3>
            <p className="text-sm text-slate-500">{t('settings.masterSheetUrl.description')}</p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-6 py-5">
        {isLoading ? (
          <div className="flex items-center gap-2 text-slate-500">
            <div className="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
            <span className="text-sm">{t('common.loading')}</span>
          </div>
        ) : fetchError ? (
          <div className="p-3 bg-danger/10 border border-danger/20 rounded-lg">
            <p className="text-sm text-danger">{t('settings.masterSheetUrl.fetchError')}</p>
          </div>
        ) : isEditing ? (
          <div className="space-y-4">
            {/* URL Input */}
            <div>
              <label htmlFor="masterSheetUrl" className="block text-sm font-medium text-slate-700 mb-1.5">
                {t('settings.masterSheetUrl.label')}
              </label>
              <input
                id="masterSheetUrl"
                type="url"
                value={urlValue}
                onChange={(e) => setUrlValue(e.target.value)}
                placeholder={t('settings.masterSheetUrl.placeholder')}
                className={`w-full px-3 py-2.5 border rounded-lg text-sm focus:outline-none focus:ring-2 transition-colors ${
                  urlValue && !isValid
                    ? 'border-danger focus:ring-danger/20 focus:border-danger'
                    : 'border-border focus:ring-primary/20 focus:border-primary'
                }`}
                autoFocus
              />
              {urlValue && !isValid && (
                <p className="mt-1.5 text-xs text-danger">
                  {t('settings.masterSheetUrl.invalidUrl')}
                </p>
              )}
            </div>

            {/* Sheet Name Input */}
            <div>
              <label htmlFor="masterSheetName" className="block text-sm font-medium text-slate-700 mb-1.5">
                {t('settings.masterSheetUrl.sheetNameLabel')}
              </label>
              <input
                id="masterSheetName"
                type="text"
                value={sheetNameValue}
                onChange={(e) => setSheetNameValue(e.target.value)}
                placeholder={t('settings.masterSheetUrl.sheetNamePlaceholder')}
                className="w-full px-3 py-2.5 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors"
              />
              <p className="mt-1.5 text-xs text-slate-500">
                {t('settings.masterSheetUrl.sheetNameHint')}
              </p>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleSave}
                disabled={!isValid || updateUrl.isPending}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  isValid && !updateUrl.isPending
                    ? 'bg-primary text-white hover:bg-primary/90'
                    : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                }`}
              >
                {updateUrl.isPending ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    {t('common.saving')}
                  </>
                ) : (
                  <>
                    <CheckIcon />
                    {t('common.save')}
                  </>
                )}
              </button>
              <button
                onClick={handleCancel}
                disabled={updateUrl.isPending}
                className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              >
                {t('common.cancel')}
              </button>
            </div>

            {/* Error */}
            {updateUrl.error && (
              <div className="p-3 bg-danger/10 border border-danger/20 rounded-lg">
                <p className="text-sm text-danger">{updateUrl.error.message}</p>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              {data?.configured ? (
                <>
                  <p className="text-sm text-slate-900 truncate font-mono bg-slate-50 px-3 py-2 rounded-lg border border-border">
                    {data.url}
                  </p>
                  {data.sheet_name && (
                    <p className="mt-2 text-sm text-slate-700">
                      <span className="font-medium">{t('settings.masterSheetUrl.sheetNameLabel')}:</span>{' '}
                      <span className="font-mono bg-slate-50 px-2 py-1 rounded border border-border">
                        {data.sheet_name}
                      </span>
                    </p>
                  )}
                  {data.last_updated_at && (
                    <p className="mt-1.5 text-xs text-slate-500">
                      {t('settings.masterSheetUrl.lastUpdated')}{' '}
                      {new Date(data.last_updated_at).toLocaleString()}
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-slate-500 italic">
                  {t('settings.masterSheetUrl.notConfigured')}
                </p>
              )}
            </div>

            <button
              onClick={() => setIsEditing(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-primary bg-primary/10 hover:bg-primary/20 rounded-lg transition-colors"
            >
              <EditIcon />
              {data?.configured ? t('common.edit') : t('common.configure')}
            </button>
          </div>
        )}

        {/* Success Message */}
        {showSuccess && (
          <div className="mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center gap-2">
            <CheckIcon />
            <p className="text-sm text-emerald-700">{t('settings.masterSheetUrl.saveSuccess')}</p>
          </div>
        )}
      </div>
    </div>
  )
}

