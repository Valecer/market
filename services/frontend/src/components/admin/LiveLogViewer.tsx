/**
 * LiveLogViewer Component
 *
 * Displays a scrollable list of parsing log entries with live updates.
 * Shows timestamp, log level badge, supplier context, and message.
 * ERROR level logs are visually highlighted for quick identification.
 *
 * Design System: Tailwind CSS v4.1
 * Accessibility: WCAG 2.1 Level AA
 * i18n: All text content uses useTranslation
 *
 * @see /specs/006-admin-sync-scheduler/spec.md
 */

import { useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import type { LiveLogViewerProps, ParsingLogEntry } from '@/types/ingestion'

// =============================================================================
// Constants
// =============================================================================

/**
 * Log level configuration for visual styling
 */
const LOG_LEVEL_CONFIG: Record<
  string,
  { bgColor: string; textColor: string; label: string }
> = {
  ERROR: {
    bgColor: 'bg-red-100',
    textColor: 'text-red-700',
    label: 'ERROR',
  },
  FATAL: {
    bgColor: 'bg-red-200',
    textColor: 'text-red-800',
    label: 'FATAL',
  },
  PARSE_ERROR: {
    bgColor: 'bg-red-100',
    textColor: 'text-red-700',
    label: 'PARSE',
  },
  VALIDATION_ERROR: {
    bgColor: 'bg-amber-100',
    textColor: 'text-amber-700',
    label: 'VALID',
  },
  WARNING: {
    bgColor: 'bg-amber-100',
    textColor: 'text-amber-700',
    label: 'WARN',
  },
  INFO: {
    bgColor: 'bg-blue-100',
    textColor: 'text-blue-700',
    label: 'INFO',
  },
  SUCCESS: {
    bgColor: 'bg-emerald-100',
    textColor: 'text-emerald-700',
    label: 'OK',
  },
}

// =============================================================================
// Icons
// =============================================================================

const TerminalIcon = () => (
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
      d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
    />
  </svg>
)

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Format a timestamp for display in log entries
 */
function formatLogTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString)
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return '--:--:--'
  }
}

/**
 * Get log level configuration with fallback
 */
function getLogLevelConfig(errorType: string) {
  // Check if it's an error type
  const isError =
    errorType.includes('ERROR') ||
    errorType.includes('FATAL') ||
    errorType === 'PARSE_ERROR' ||
    errorType === 'VALIDATION_ERROR'

  return (
    LOG_LEVEL_CONFIG[errorType] ||
    (isError
      ? LOG_LEVEL_CONFIG.ERROR
      : {
          bgColor: 'bg-slate-100',
          textColor: 'text-slate-700',
          label: errorType.substring(0, 5).toUpperCase(),
        })
  )
}

/**
 * Check if log entry is an error level
 */
function isErrorLevel(errorType: string): boolean {
  return (
    errorType.includes('ERROR') ||
    errorType.includes('FATAL') ||
    errorType === 'PARSE_ERROR' ||
    errorType === 'VALIDATION_ERROR'
  )
}

// =============================================================================
// Log Entry Component
// =============================================================================

interface LogEntryProps {
  log: ParsingLogEntry
}

function LogEntry({ log }: LogEntryProps) {
  const levelConfig = getLogLevelConfig(log.error_type)
  const isError = isErrorLevel(log.error_type)

  return (
    <div
      className={`flex items-start gap-3 px-3 py-2 rounded-lg transition-colors ${
        isError
          ? 'bg-red-50/80 border-l-2 border-red-400'
          : 'hover:bg-slate-50 border-l-2 border-transparent'
      }`}
    >
      {/* Timestamp */}
      <span className="flex-shrink-0 text-xs font-mono text-slate-400 pt-0.5 w-20">
        {formatLogTimestamp(log.created_at)}
      </span>

      {/* Level Badge */}
      <span
        className={`flex-shrink-0 px-1.5 py-0.5 rounded text-xs font-semibold uppercase ${levelConfig.bgColor} ${levelConfig.textColor}`}
      >
        {levelConfig.label}
      </span>

      {/* Supplier Badge (if available) */}
      {log.supplier_name && (
        <span className="flex-shrink-0 px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600 max-w-[120px] truncate">
          {log.supplier_name}
        </span>
      )}

      {/* Message */}
      <span
        className={`flex-1 text-sm break-words ${
          isError ? 'text-red-800 font-medium' : 'text-slate-700'
        }`}
      >
        {log.error_message}
        {log.row_number !== null && (
          <span className="ml-2 text-xs text-slate-400">(row {log.row_number})</span>
        )}
      </span>
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

/**
 * LiveLogViewer - Scrollable log stream with auto-scroll
 */
export function LiveLogViewer({ logs, isLoading }: LiveLogViewerProps) {
  const { t } = useTranslation()
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to top when new logs arrive
  useEffect(() => {
    if (containerRef.current && logs.length > 0) {
      containerRef.current.scrollTop = 0
    }
  }, [logs])

  return (
    <div className="bg-white rounded-xl shadow-md border border-border overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border bg-slate-50 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-slate-200 rounded-lg text-slate-600">
            <TerminalIcon />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              {t('ingestion.logs.title', 'Parsing Logs')}
            </h3>
            <p className="text-sm text-slate-500">
              {t('ingestion.logs.subtitle', 'Recent parsing activity and errors')}
            </p>
          </div>
        </div>

        {/* Log count indicator */}
        <span className="text-xs text-slate-400 font-medium">
          {t('ingestion.logs.count', '{{count}} entries', { count: logs.length })}
        </span>
      </div>

      {/* Log Stream */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto p-4 space-y-1 min-h-[200px] max-h-[400px] bg-slate-50/50"
        role="log"
        aria-live="polite"
        aria-label={t('ingestion.logs.ariaLabel', 'Live parsing log stream')}
      >
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          </div>
        ) : logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="p-3 bg-slate-100 rounded-full mb-3">
              <TerminalIcon />
            </div>
            <p className="text-slate-500 text-sm">
              {t('ingestion.logs.empty', 'No parsing logs yet')}
            </p>
            <p className="text-slate-400 text-xs mt-1">
              {t('ingestion.logs.emptyHint', 'Logs will appear when suppliers are synced')}
            </p>
          </div>
        ) : (
          logs.map((log) => <LogEntry key={log.id} log={log} />)
        )}
      </div>

      {/* Footer with legend */}
      <div className="px-4 py-2 border-t border-border bg-slate-50/80 flex items-center gap-4 text-xs flex-shrink-0">
        <span className="text-slate-400 font-medium">
          {t('ingestion.logs.legend', 'Legend:')}
        </span>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red-400" />
          <span className="text-slate-500">Error</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-amber-400" />
          <span className="text-slate-500">Warning</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-blue-400" />
          <span className="text-slate-500">Info</span>
        </div>
      </div>
    </div>
  )
}

