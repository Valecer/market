/**
 * ErrorState Component
 *
 * Displays user-friendly error messages with retry functionality.
 * Supports different error types and custom messages.
 *
 * Design System: Tailwind CSS with danger color theme
 * Accessibility: Uses role="alert" for screen readers
 */

import { cn } from '@/lib/utils'

interface ErrorStateProps {
  /** Error message to display */
  message?: string
  /** Title for the error (default: "Something went wrong") */
  title?: string
  /** Callback for retry button */
  onRetry?: () => void
  /** Additional CSS classes */
  className?: string
  /** Show as inline (smaller) or full section */
  variant?: 'inline' | 'section'
}

/**
 * Error state component with retry functionality
 */
export function ErrorState({
  message = 'An unexpected error occurred. Please try again.',
  title = 'Something went wrong',
  onRetry,
  className,
  variant = 'section',
}: ErrorStateProps) {
  if (variant === 'inline') {
    return (
      <div
        role="alert"
        className={cn(
          'flex items-center gap-3 p-4 bg-danger/10 border border-danger/20 rounded-lg',
          className
        )}
      >
        <svg
          className="w-5 h-5 text-danger flex-shrink-0"
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
        <span className="text-sm text-danger flex-1">{message}</span>
        {onRetry && (
          <button
            onClick={onRetry}
            className="text-sm font-medium text-danger hover:text-danger/80 underline underline-offset-2"
          >
            Retry
          </button>
        )}
      </div>
    )
  }

  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center justify-center p-8 bg-white rounded-xl shadow-md border border-border',
        className
      )}
    >
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-danger/10 mb-4">
        <svg
          className="w-8 h-8 text-danger"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
      </div>

      <h2 className="text-xl font-semibold text-slate-900 mb-2">{title}</h2>

      <p className="text-slate-500 text-center max-w-md mb-6">{message}</p>

      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-white font-medium rounded-lg hover:bg-primary/90 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
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
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          Try Again
        </button>
      )}
    </div>
  )
}

/**
 * Empty state component (when no data matches filters)
 */
export function EmptyState({
  title = 'No results found',
  message = 'Try adjusting your filters or search terms.',
  icon,
  className,
}: {
  title?: string
  message?: string
  icon?: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center p-12 bg-white rounded-xl shadow-md border border-border',
        className
      )}
    >
      {icon || (
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-100 mb-4">
          <svg
            className="w-8 h-8 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
            />
          </svg>
        </div>
      )}

      <h3 className="text-lg font-semibold text-slate-900 mb-2">{title}</h3>
      <p className="text-slate-500 text-center max-w-sm">{message}</p>
    </div>
  )
}

