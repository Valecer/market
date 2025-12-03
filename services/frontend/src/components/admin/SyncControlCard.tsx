/**
 * SyncControlCard Component
 *
 * Admin control panel card for triggering and monitoring sync operations.
 * Displays current sync state, progress, and timestamps.
 *
 * Design System: Tailwind CSS v4.1
 * Accessibility: WCAG 2.1 Level AA
 * i18n: All text content uses useTranslation
 */

import { useTranslation } from 'react-i18next'
import type { SyncControlCardProps } from '@/types/ingestion'
import { JobPhaseIndicator } from './JobPhaseIndicator'

// Status indicator colors and styles
const STATUS_CONFIG = {
  idle: {
    bgColor: 'bg-emerald-500',
    pulseColor: 'bg-emerald-400',
    textColor: 'text-emerald-700',
    bgLight: 'bg-emerald-50',
    pulse: false,
  },
  syncing_master: {
    bgColor: 'bg-amber-500',
    pulseColor: 'bg-amber-400',
    textColor: 'text-amber-700',
    bgLight: 'bg-amber-50',
    pulse: true,
  },
  processing_suppliers: {
    bgColor: 'bg-blue-500',
    pulseColor: 'bg-blue-400',
    textColor: 'text-blue-700',
    bgLight: 'bg-blue-50',
    pulse: true,
  },
} as const

// Icons
const SyncIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
    aria-hidden="true"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
    />
  </svg>
)

const ClockIcon = () => (
  <svg
    className="w-4 h-4"
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
    aria-hidden="true"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
    />
  </svg>
)

/**
 * Format a timestamp for display
 */
function formatTimestamp(isoString: string | null): string {
  if (!isoString) return '—'
  try {
    const date = new Date(isoString)
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return '—'
  }
}

/**
 * Calculate relative time for display
 */
function getRelativeTime(isoString: string | null): string {
  if (!isoString) return ''
  try {
    const date = new Date(isoString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 1) return 'just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return `${diffDays}d ago`
  } catch {
    return ''
  }
}

/**
 * SyncControlCard - Main sync control UI component
 */
export function SyncControlCard({
  syncState,
  progress,
  lastSyncAt,
  nextScheduledAt,
  jobs,
  onSyncNow,
  isSyncing,
  isLoading = false,
  error = null,
}: SyncControlCardProps) {
  const { t } = useTranslation()
  const statusConfig = STATUS_CONFIG[syncState]
  const progressPercent = progress ? Math.round((progress.current / progress.total) * 100) : 0

  // Filter active jobs (processing or recently completed)
  const activeJobs = jobs.filter(
    (job) => job.status === 'processing' || job.status === 'pending'
  )
  const recentJobs = jobs.filter(
    (job) => job.status === 'completed' || job.status === 'failed'
  ).slice(0, 3)

  return (
    <div className="bg-white rounded-xl shadow-md border border-border overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border bg-slate-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <SyncIcon />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900">
                {t('ingestion.syncControl')}
              </h3>
              <p className="text-sm text-slate-500">
                {t('ingestion.syncControlDescription')}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Status Section */}
      <div className="px-6 py-5">
        {/* Current Status */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            {/* Status Indicator */}
            <div className="relative flex items-center justify-center">
              <span
                className={`relative flex h-3 w-3 ${statusConfig.pulse ? 'animate-pulse' : ''}`}
              >
                {statusConfig.pulse && (
                  <span
                    className={`absolute inline-flex h-full w-full rounded-full ${statusConfig.pulseColor} opacity-75 animate-ping`}
                  />
                )}
                <span
                  className={`relative inline-flex rounded-full h-3 w-3 ${statusConfig.bgColor}`}
                />
              </span>
            </div>

            {/* Status Text */}
            <div>
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusConfig.bgLight} ${statusConfig.textColor}`}
              >
                {t(`ingestion.state.${syncState}`)}
              </span>
            </div>
          </div>

          {/* Sync Now Button */}
          <button
            onClick={onSyncNow}
            disabled={isSyncing || isLoading}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all
              ${
                isSyncing || isLoading
                  ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                  : 'bg-primary text-white hover:bg-primary/90 active:scale-95 shadow-sm'
              }
            `}
            aria-busy={isSyncing}
            aria-disabled={isSyncing || isLoading}
          >
            {isSyncing ? (
              <>
                <svg
                  className="animate-spin h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
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
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                {t('ingestion.syncing')}
              </>
            ) : (
              <>
                <SyncIcon />
                {t('ingestion.syncNow')}
              </>
            )}
          </button>
        </div>

        {/* Progress Bar (visible during processing_suppliers) */}
        {syncState === 'processing_suppliers' && progress && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-slate-600">
                {t('ingestion.processingSuppliers')}
              </span>
              <span className="text-sm font-medium text-slate-900">
                {progress.current} / {progress.total}
              </span>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${progressPercent}%` }}
                role="progressbar"
                aria-valuenow={progressPercent}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {progressPercent}% {t('common.complete')}
            </p>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-3 bg-danger/10 border border-danger/20 rounded-lg">
            <p className="text-sm text-danger font-medium">{error}</p>
          </div>
        )}

        {/* Active Jobs (Phase 8) */}
        {activeJobs.length > 0 && (
          <div className="mb-6 space-y-3">
            <h4 className="text-sm font-medium text-slate-700">
              {t('ingestion.activeJobs')}
            </h4>
            {activeJobs.map((job) => (
              <JobPhaseIndicator key={job.job_id} job={job} />
            ))}
          </div>
        )}

        {/* Recent Jobs (Phase 8) */}
        {recentJobs.length > 0 && activeJobs.length === 0 && (
          <div className="mb-6 space-y-2">
            <h4 className="text-sm font-medium text-slate-700">
              {t('ingestion.recentJobs')}
            </h4>
            {recentJobs.map((job) => (
              <JobPhaseIndicator key={job.job_id} job={job} compact />
            ))}
          </div>
        )}

        {/* Timestamps */}
        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border">
          {/* Last Sync */}
          <div className="flex items-start gap-3">
            <div className="p-2 bg-slate-100 rounded-lg">
              <ClockIcon />
            </div>
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">
                {t('ingestion.lastSync')}
              </p>
              <p className="text-sm font-semibold text-slate-900">
                {formatTimestamp(lastSyncAt)}
              </p>
              {lastSyncAt && (
                <p className="text-xs text-slate-400">{getRelativeTime(lastSyncAt)}</p>
              )}
            </div>
          </div>

          {/* Next Scheduled */}
          <div className="flex items-start gap-3">
            <div className="p-2 bg-slate-100 rounded-lg">
              <ClockIcon />
            </div>
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">
                {t('ingestion.nextScheduled')}
              </p>
              <p className="text-sm font-semibold text-slate-900">
                {formatTimestamp(nextScheduledAt)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Loading Overlay */}
      {isLoading && (
        <div className="absolute inset-0 bg-white/50 flex items-center justify-center">
          <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
        </div>
      )}
    </div>
  )
}

