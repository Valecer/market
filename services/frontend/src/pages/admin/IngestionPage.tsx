/**
 * IngestionPage
 *
 * Admin page for the Ingestion Control Panel.
 * Allows administrators to trigger manual syncs and monitor pipeline status.
 *
 * User Story: US1 - Manual Sync Trigger
 * - "Sync Now" button triggers master sync pipeline
 * - Status changes to "Syncing Master Sheet" → "Processing Suppliers"
 * - Progress indicator shows current/total suppliers
 *
 * @see /specs/006-admin-sync-scheduler/spec.md
 */

import { useTranslation } from 'react-i18next'
import { useIngestionStatus, useTriggerSync } from '@/hooks'
import { SyncControlCard } from '@/components/admin'
import { useAuth } from '@/hooks/useAuth'

/**
 * IngestionPage Component
 */
export function IngestionPage() {
  const { t } = useTranslation()
  const { user } = useAuth()

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
      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          {t('ingestion.title')}
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          {t('ingestion.subtitle')}
        </p>
      </div>

      {/* Main Content Grid */}
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

        {/* Info Card - Phase 3 simplified version */}
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

      {/* Suppliers Section - Placeholder for Phase 5 */}
      {status?.suppliers && status.suppliers.length > 0 && (
        <div className="bg-white rounded-xl shadow-md border border-border p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">
            {t('ingestion.suppliers')}
          </h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                    {t('common.name')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                    {t('ingestion.sourceType')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                    {t('ingestion.status')}
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                    {t('ingestion.itemsCount')}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {status.suppliers.map((supplier) => (
                  <tr key={supplier.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-slate-900">
                      {supplier.name}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-slate-500">
                      {supplier.source_type}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          supplier.status === 'success'
                            ? 'bg-emerald-100 text-emerald-800'
                            : supplier.status === 'error'
                            ? 'bg-red-100 text-red-800'
                            : supplier.status === 'inactive'
                            ? 'bg-slate-100 text-slate-600'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {t(`ingestion.supplierStatus.${supplier.status}`)}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-slate-500 text-right">
                      {supplier.items_count.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

