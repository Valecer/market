/**
 * IngestionPage
 *
 * Admin page for the Ingestion Control Panel.
 * Allows administrators to:
 * - Configure master sheet URL
 * - Add suppliers manually with drag-and-drop file upload
 * - Trigger manual syncs and monitor pipeline status
 *
 * @see /specs/006-admin-sync-scheduler/spec.md
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useIngestionStatus, useTriggerSync, useDeleteSupplier } from '@/hooks'
import { SyncControlCard, SupplierAddModal, MasterSheetUrlConfig } from '@/components/admin'
import { useAuth } from '@/hooks/useAuth'

// =============================================================================
// Icons
// =============================================================================

const PlusIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
  </svg>
)

const TrashIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
    />
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
  const [deletingId, setDeletingId] = useState<string | null>(null)

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
  const deleteSupplier = useDeleteSupplier()

  // Handle sync button click
  const handleSyncNow = () => {
    triggerSync()
  }

  // Handle delete supplier
  const handleDeleteSupplier = async (id: string, name: string) => {
    if (!window.confirm(t('suppliers.deleteConfirm', { name }))) {
      return
    }

    setDeletingId(id)
    try {
      await deleteSupplier.mutateAsync(id)
    } finally {
      setDeletingId(null)
    }
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t('ingestion.title')}</h1>
          <p className="mt-1 text-sm text-slate-500">{t('ingestion.subtitle')}</p>
        </div>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg font-medium text-sm hover:bg-primary/90 transition-colors shadow-sm"
        >
          <PlusIcon />
          {t('suppliers.addSupplier')}
        </button>
      </div>

      {/* Master Sheet URL Configuration */}
      <MasterSheetUrlConfig />

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

      {/* Suppliers Section */}
      <div className="bg-white rounded-xl shadow-md border border-border p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-900">{t('ingestion.suppliers')}</h3>
          {status?.suppliers && (
            <span className="text-sm text-slate-500">
              {t('suppliers.count', { count: status.suppliers.length })}
            </span>
          )}
        </div>

        {isStatusLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          </div>
        ) : status?.suppliers && status.suppliers.length > 0 ? (
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
                  <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                    {t('common.actions')}
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
                      {t(`suppliers.sourceTypes.${supplier.source_type}`)}
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
                    <td className="px-4 py-3 whitespace-nowrap text-right">
                      <button
                        onClick={() => handleDeleteSupplier(supplier.id, supplier.name)}
                        disabled={deletingId === supplier.id}
                        className="p-1.5 text-slate-400 hover:text-danger hover:bg-danger/10 rounded-lg transition-colors disabled:opacity-50"
                        title={t('suppliers.delete')}
                      >
                        {deletingId === supplier.id ? (
                          <div className="w-4 h-4 border-2 border-danger/30 border-t-danger rounded-full animate-spin" />
                        ) : (
                          <TrashIcon />
                        )}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-slate-500 mb-4">{t('suppliers.noSuppliers')}</p>
            <button
              onClick={() => setIsAddModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary rounded-lg font-medium text-sm hover:bg-primary/20 transition-colors"
            >
              <PlusIcon />
              {t('suppliers.addFirst')}
            </button>
          </div>
        )}
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

