/**
 * JobPhaseIndicator Component
 *
 * Displays multi-phase progress indicator for ML ingestion jobs.
 * Shows phase-specific icons, colors, and progress information.
 *
 * Phases: Downloading → Analyzing → Matching → Complete/Failed
 *
 * Design System: Tailwind CSS v4.1
 * Accessibility: WCAG 2.1 Level AA
 * i18n: All text content uses useTranslation
 */

import { useTranslation } from 'react-i18next'
import type { IngestionJob, JobPhase } from '@/types/ingestion'

// =============================================================================
// Types
// =============================================================================

interface JobPhaseIndicatorProps {
  job: IngestionJob
  compact?: boolean
}

// =============================================================================
// Constants
// =============================================================================

const PHASES: JobPhase[] = ['downloading', 'analyzing', 'matching', 'complete']

const PHASE_CONFIG: Record<
  JobPhase,
  {
    icon: React.FC<{ className?: string }>
    color: string
    bgColor: string
    textColor: string
    borderColor: string
  }
> = {
  downloading: {
    icon: DownloadIcon,
    color: 'bg-blue-500',
    bgColor: 'bg-blue-50',
    textColor: 'text-blue-700',
    borderColor: 'border-blue-200',
  },
  analyzing: {
    icon: AnalyzeIcon,
    color: 'bg-amber-500',
    bgColor: 'bg-amber-50',
    textColor: 'text-amber-700',
    borderColor: 'border-amber-200',
  },
  matching: {
    icon: MatchIcon,
    color: 'bg-violet-500',
    bgColor: 'bg-violet-50',
    textColor: 'text-violet-700',
    borderColor: 'border-violet-200',
  },
  complete: {
    icon: CheckIcon,
    color: 'bg-emerald-500',
    bgColor: 'bg-emerald-50',
    textColor: 'text-emerald-700',
    borderColor: 'border-emerald-200',
  },
  failed: {
    icon: ErrorIcon,
    color: 'bg-rose-500',
    bgColor: 'bg-rose-50',
    textColor: 'text-rose-700',
    borderColor: 'border-rose-200',
  },
}

// =============================================================================
// Icons
// =============================================================================

function DownloadIcon({ className = '' }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"
      />
    </svg>
  )
}

function AnalyzeIcon({ className = '' }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
      />
    </svg>
  )
}

function MatchIcon({ className = '' }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
      />
    </svg>
  )
}

function CheckIcon({ className = '' }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  )
}

function ErrorIcon({ className = '' }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  )
}

function SpinnerIcon({ className = '' }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className}`}
      fill="none"
      viewBox="0 0 24 24"
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
  )
}

// =============================================================================
// Helper Functions
// =============================================================================

function getPhaseIndex(phase: JobPhase): number {
  if (phase === 'failed') return -1
  return PHASES.indexOf(phase)
}

function getProgressPercent(job: IngestionJob): number {
  if (job.phase === 'downloading' && job.download_progress) {
    return job.download_progress.percentage
  }
  if ((job.phase === 'analyzing' || job.phase === 'matching') && job.analysis_progress) {
    return job.analysis_progress.percentage
  }
  if (job.phase === 'complete') return 100
  return 0
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// =============================================================================
// Component
// =============================================================================

export function JobPhaseIndicator({ job, compact = false }: JobPhaseIndicatorProps) {
  const { t } = useTranslation()
  const config = PHASE_CONFIG[job.phase]
  const Icon = config.icon
  const currentPhaseIndex = getPhaseIndex(job.phase)
  const isActive = job.status === 'processing' || job.status === 'pending'
  const progressPercent = getProgressPercent(job)

  if (compact) {
    // Compact version - just icon and badge
    return (
      <div className="flex items-center gap-2">
        <div
          className={`flex items-center justify-center w-8 h-8 rounded-full ${config.bgColor} ${config.textColor}`}
        >
          {isActive && job.phase !== 'complete' ? (
            <SpinnerIcon className="w-4 h-4" />
          ) : (
            <Icon className="w-4 h-4" />
          )}
        </div>
        <span
          className={`px-2 py-0.5 rounded-full text-xs font-medium ${config.bgColor} ${config.textColor}`}
        >
          {t(`ingestion.phase.${job.phase}`)}
        </span>
      </div>
    )
  }

  // Full version with progress bar and details
  return (
    <div
      className={`rounded-lg border ${config.borderColor} ${config.bgColor} p-4`}
      role="region"
      aria-label={t('ingestion.jobProgress')}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div
            className={`flex items-center justify-center w-10 h-10 rounded-full ${config.color} text-white`}
          >
            {isActive && job.phase !== 'complete' && job.phase !== 'failed' ? (
              <SpinnerIcon className="w-5 h-5" />
            ) : (
              <Icon className="w-5 h-5" />
            )}
          </div>
          <div>
            <p className={`font-semibold ${config.textColor}`}>
              {t(`ingestion.phase.${job.phase}`)}
            </p>
            <p className="text-sm text-slate-600">{job.supplier_name}</p>
          </div>
        </div>

        {/* Progress percentage */}
        {isActive && (
          <span className={`text-2xl font-bold ${config.textColor}`}>
            {progressPercent}%
          </span>
        )}
      </div>

      {/* Phase Progress Steps */}
      <div className="flex items-center gap-1 mb-3">
        {PHASES.map((phase, index) => {
          const isCompleted = job.phase === 'complete' || (currentPhaseIndex >= 0 && index < currentPhaseIndex)
          const isCurrent = phase === job.phase && job.phase !== 'complete'
          const PhaseIcon = PHASE_CONFIG[phase].icon

          return (
            <div key={phase} className="flex items-center flex-1">
              {/* Step circle */}
              <div
                className={`relative flex items-center justify-center w-6 h-6 rounded-full shrink-0 transition-colors ${
                  isCompleted
                    ? 'bg-emerald-500 text-white'
                    : isCurrent
                    ? `${config.color} text-white`
                    : 'bg-slate-200 text-slate-400'
                }`}
              >
                {isCompleted ? (
                  <CheckIcon className="w-3.5 h-3.5" />
                ) : (
                  <PhaseIcon className="w-3.5 h-3.5" />
                )}
                {isCurrent && isActive && (
                  <span className="absolute inset-0 rounded-full animate-ping opacity-30 bg-current" />
                )}
              </div>

              {/* Connector line */}
              {index < PHASES.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-1 transition-colors ${
                    isCompleted ? 'bg-emerald-500' : 'bg-slate-200'
                  }`}
                />
              )}
            </div>
          )
        })}
      </div>

      {/* Progress bar */}
      {isActive && (
        <div className="mb-3">
          <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
            <div
              className={`h-2 rounded-full transition-all duration-300 ease-out ${config.color}`}
              style={{ width: `${progressPercent}%` }}
              role="progressbar"
              aria-valuenow={progressPercent}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
        </div>
      )}

      {/* Progress details */}
      <div className="text-sm text-slate-600 space-y-1">
        {job.phase === 'downloading' && job.download_progress && (
          <p>
            {formatBytes(job.download_progress.bytes_downloaded)}
            {job.download_progress.bytes_total && (
              <> / {formatBytes(job.download_progress.bytes_total)}</>
            )}
          </p>
        )}

        {(job.phase === 'analyzing' || job.phase === 'matching') && job.analysis_progress && (
          <>
            <p>
              {t('ingestion.itemsProcessed', {
                processed: job.analysis_progress.items_processed,
                total: job.analysis_progress.items_total,
              })}
            </p>
            {job.analysis_progress.matches_found > 0 && (
              <p className="text-emerald-600">
                ✓ {t('ingestion.matchesFound', { count: job.analysis_progress.matches_found })}
              </p>
            )}
            {job.analysis_progress.review_queue > 0 && (
              <p className="text-amber-600">
                ⏳ {t('ingestion.inReviewQueue', { count: job.analysis_progress.review_queue })}
              </p>
            )}
            {job.analysis_progress.errors > 0 && (
              <p className="text-rose-600">
                ⚠ {t('ingestion.processingErrors', { count: job.analysis_progress.errors })}
              </p>
            )}
          </>
        )}

        {job.phase === 'complete' && job.analysis_progress && (
          <div className="flex items-center gap-4">
            <span className="text-emerald-600">
              ✓ {job.analysis_progress.items_processed} {t('ingestion.itemsProcessedTotal')}
            </span>
            {job.analysis_progress.matches_found > 0 && (
              <span>{job.analysis_progress.matches_found} {t('ingestion.matched')}</span>
            )}
            {job.analysis_progress.review_queue > 0 && (
              <span className="text-amber-600">
                {job.analysis_progress.review_queue} {t('ingestion.inReview')}
              </span>
            )}
          </div>
        )}

        {job.phase === 'failed' && job.error && (
          <div className="p-2 bg-rose-100 rounded border border-rose-200">
            <p className="text-rose-700 font-medium">{job.error}</p>
            {job.retry_count > 0 && (
              <p className="text-rose-600 text-xs mt-1">
                {t('ingestion.retryAttempt', {
                  current: job.retry_count,
                  max: job.max_retries,
                })}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// Also export individual icons for reuse
export { DownloadIcon, AnalyzeIcon, MatchIcon, CheckIcon, ErrorIcon, SpinnerIcon }

