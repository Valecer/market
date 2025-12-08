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

import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useIngestionStatus, useTriggerSync, useDeleteSupplier } from '@/hooks'
import { useRetryJob } from '@/hooks/useRetryJob'
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

const ChevronIcon = ({ isOpen }: { isOpen: boolean }) => (
  <svg 
    className={`w-5 h-5 text-slate-500 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} 
    fill="none" 
    stroke="currentColor" 
    viewBox="0 0 24 24"
  >
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
  </svg>
)

const InfoIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
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
  
  // Collapsible "How it works" state
  const [isHowItWorksOpen, setIsHowItWorksOpen] = useState(false)

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

  // Delete supplier mutation
  const {
    mutate: deleteSupplier,
    isPending: isDeletePending,
  } = useDeleteSupplier()

  // Retry job mutation
  const {
    mutate: retryJob,
    isPending: isRetryPending,
  } = useRetryJob()

  // Handle sync button click
  const handleSyncNow = () => {
    triggerSync()
  }

  // Handle retry job
  const handleRetryJob = useCallback((jobId: string) => {
    retryJob(jobId)
  }, [retryJob])

  // Handle delete supplier
  const handleDeleteSupplier = useCallback((id: string, _name: string) => {
    deleteSupplier(id)
  }, [deleteSupplier])

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

      {/* Main Grid: Sync Control (left) | How It Works + Logs (right) */}
      {/* Left column determines row height; right column is constrained to match */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Sync Control Card - determines the row height */}
        <SyncControlCard
          syncState={status?.sync_state || 'idle'}
          progress={status?.progress || null}
          lastSyncAt={status?.last_sync_at || null}
          nextScheduledAt={status?.next_scheduled_at || new Date().toISOString()}
          jobs={status?.jobs || []}
          onSyncNow={handleSyncNow}
          onRetryJob={handleRetryJob}
          isSyncing={isSyncing}
          isRetrying={isRetryPending}
          isLoading={isStatusLoading}
          error={errorMessage}
        />

        {/* Right Column: Constrained to left column's height on desktop */}
        {/* Mobile: auto height with min-height; Desktop: match left column */}
        <div className="min-h-[400px] lg:h-0 lg:min-h-full flex flex-col gap-4 overflow-hidden">
          {/* Collapsible How It Works */}
          <div className="shrink-0 bg-white rounded-xl shadow-md border border-border overflow-hidden">
            <button
              type="button"
              onClick={() => setIsHowItWorksOpen(!isHowItWorksOpen)}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors text-left focus:outline-none focus:ring-2 focus:ring-primary/20 focus:ring-inset"
              aria-expanded={isHowItWorksOpen}
              aria-controls="how-it-works-content"
            >
              <div className="flex items-center gap-3">
                <span className="text-primary">
                  <InfoIcon />
                </span>
                <h3 className="text-lg font-semibold text-slate-900">
                  {t('ingestion.howItWorks')}
                </h3>
              </div>
              <ChevronIcon isOpen={isHowItWorksOpen} />
            </button>
            
            <div
              id="how-it-works-content"
              className={`grid transition-[grid-template-rows] duration-200 ease-in-out ${
                isHowItWorksOpen 
                  ? 'grid-rows-[1fr]' 
                  : 'grid-rows-[0fr]'
              }`}
            >
              <div className="overflow-hidden">
                <div className="px-6 pb-6 space-y-4 text-sm text-slate-600 border-t border-border pt-4">
                  <div className="flex items-start gap-3">
                    <span className="shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-bold">
                      1
                    </span>
                    <p>{t('ingestion.step1')}</p>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-bold">
                      2
                    </span>
                    <p>{t('ingestion.step2')}</p>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-bold">
                      3
                    </span>
                    <p>{t('ingestion.step3')}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Parsing Logs - fills remaining space */}
          <div className="flex-1 min-h-0">
            <LiveLogViewer
              logs={status?.recent_logs || []}
              isLoading={isStatusLoading}
            />
          </div>
        </div>
      </div>

      {/* Supplier Status Table - Full Width */}
      <SupplierStatusTable
        suppliers={status?.suppliers || []}
        isLoading={isStatusLoading}
        onDeleteSupplier={handleDeleteSupplier}
        isDeletingSupplier={isDeletePending}
      />

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
