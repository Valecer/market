/**
 * IngestionPage
 *
 * Admin page for the Ingestion Control Panel.
 * Allows administrators to:
 * - Configure master sheet URL
 * - Add suppliers manually with drag-and-drop file upload
 * - Trigger manual syncs and monitor pipeline status
 * - View parsing logs in real-time
 * - Monitor supplier sync status
 *
 * @see /specs/006-admin-sync-scheduler/spec.md
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useIngestionStatus, useTriggerSync } from '@/hooks'
import {
  SyncControlCard,
  SupplierAddModal,
  MasterSheetUrlConfig,
  LiveLogViewer,
  SupplierStatusTable,
} from '@/components/admin'
import { useAuth } from '@/hooks/useAuth'

// =============================================================================
// Icons
// =============================================================================

const PlusIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
  </svg>
)

// =============================================================================
// Component
// =============================================================================

/**
 * IngestionPage Component
 */
export function IngestionPage() {
  const { t } = useTranslation()
  const { user } = useAuth()

  // Modal state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)

  // Fetch ingestion status with polling
  const {
    data: status,
    isLoading: isStatusLoading,
    error: statusError,
  } = useIngestionStatus({
    enabled: user?.role === 'admin', // Only poll for admin users
  })

  // Trigger sync mutation
  const {
    mutate: triggerSync,
    isPending: isTriggerPending,
    error: triggerError,
  } = useTriggerSync()

  // Delete supplier mutation available via useDeleteSupplier if needed

  // Handle sync button click
  const handleSyncNow = () => {
    triggerSync()
  }

  // Determine if sync is in progress
  const isSyncing =
    isTriggerPending ||
    status?.sync_state === 'syncing_master' ||
    status?.sync_state === 'processing_suppliers'

  // Get error message
  const errorMessage =
    triggerError?.message ||
    (statusError instanceof Error ? statusError.message : null)

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t('ingestion.title')}</h1>
          <p className="mt-1 text-sm text-slate-500">{t('ingestion.subtitle')}</p>
        </div>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-primary text-white rounded-lg font-medium text-sm hover:bg-primary/90 transition-colors shadow-sm"
        >
          <PlusIcon />
          {t('suppliers.addSupplier')}
        </button>
      </div>

      {/* Master Sheet URL Configuration */}
      <MasterSheetUrlConfig />

      {/* Control & Info Cards Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sync Control Card */}
        <SyncControlCard
          syncState={status?.sync_state || 'idle'}
          progress={status?.progress || null}
          lastSyncAt={status?.last_sync_at || null}
          nextScheduledAt={status?.next_scheduled_at || new Date().toISOString()}
          onSyncNow={handleSyncNow}
          isSyncing={isSyncing}
          isLoading={isStatusLoading}
          error={errorMessage}
        />

        {/* Info Card */}
        <div className="bg-white rounded-xl shadow-md border border-border p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-3">
            {t('ingestion.howItWorks')}
          </h3>
          <div className="space-y-4 text-sm text-slate-600">
            <div className="flex items-start gap-3">
              <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-bold">
                1
              </span>
              <p>{t('ingestion.step1')}</p>
            </div>
            <div className="flex items-start gap-3">
              <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-bold">
                2
              </span>
              <p>{t('ingestion.step2')}</p>
            </div>
            <div className="flex items-start gap-3">
              <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-bold">
                3
              </span>
              <p>{t('ingestion.step3')}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Supplier Table & Logs Row - Responsive 2-column layout */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Supplier Status Table */}
        <SupplierStatusTable
          suppliers={status?.suppliers || []}
          isLoading={isStatusLoading}
        />

        {/* Live Log Viewer */}
        <LiveLogViewer
          logs={status?.recent_logs || []}
          isLoading={isStatusLoading}
        />
      </div>

      {/* Add Supplier Modal */}
      <SupplierAddModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSuccess={() => {
          // Modal handles cleanup, status will auto-refresh via polling
        }}
      />
    </div>
  )
}
