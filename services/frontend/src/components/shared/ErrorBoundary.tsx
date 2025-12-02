/**
 * ErrorBoundary Component
 *
 * React error boundary with fallback UI and error recovery.
 * Follows constitution principles: Single Responsibility, KISS.
 *
 * Design System: Tailwind CSS + Custom theme variables
 * Accessibility: Error announcements, focus management
 *
 * Based on: react-error-boundary best practices
 */

import { Component, type ErrorInfo, type ReactNode } from 'react'

interface FallbackProps {
  /** The error that was caught */
  error: Error
  /** Function to reset the error boundary and retry rendering */
  resetErrorBoundary: () => void
}

interface ErrorBoundaryProps {
  /** Child components to render */
  children: ReactNode
  /** Custom fallback component */
  FallbackComponent?: React.ComponentType<FallbackProps>
  /** Simple fallback element (alternative to FallbackComponent) */
  fallback?: ReactNode
  /** Callback when error is caught */
  onError?: (error: Error, errorInfo: ErrorInfo) => void
  /** Callback when error boundary is reset */
  onReset?: () => void
  /** Keys that, when changed, will reset the error boundary */
  resetKeys?: unknown[]
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

/**
 * Default fallback component displayed when an error occurs.
 */
function DefaultFallback({ error, resetErrorBoundary }: FallbackProps) {
  return (
    <div
      role="alert"
      className="min-h-[200px] flex items-center justify-center p-8"
    >
      <div className="max-w-md w-full bg-white dark:bg-slate-900 rounded-xl shadow-lg border border-border p-6 text-center">
        {/* Error icon */}
        <div className="mx-auto w-16 h-16 flex items-center justify-center rounded-full bg-danger/10 mb-4">
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

        {/* Error title */}
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
          Something went wrong
        </h2>

        {/* Error message */}
        <p className="text-sm text-muted mb-4">
          An unexpected error occurred. Please try again.
        </p>

        {/* Error details (development only) */}
        {import.meta.env.DEV && (
          <details className="mb-4 text-left">
            <summary className="text-sm text-muted cursor-pointer hover:text-slate-700 dark:hover:text-slate-300">
              Error details
            </summary>
            <pre className="mt-2 p-3 bg-slate-100 dark:bg-slate-800 rounded-lg text-xs text-danger overflow-auto max-h-32">
              {error.message}
              {error.stack && `\n\n${error.stack}`}
            </pre>
          </details>
        )}

        {/* Retry button */}
        <button
          onClick={resetErrorBoundary}
          className="inline-flex items-center justify-center gap-2 h-10 px-4 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 active:bg-primary/80 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:ring-offset-2 transition-colors"
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
      </div>
    </div>
  )
}

/**
 * Error boundary component that catches JavaScript errors in child components.
 *
 * @example
 * // Basic usage
 * <ErrorBoundary>
 *   <MyComponent />
 * </ErrorBoundary>
 *
 * @example
 * // With custom fallback
 * <ErrorBoundary fallback={<div>Something went wrong</div>}>
 *   <MyComponent />
 * </ErrorBoundary>
 *
 * @example
 * // With fallback component and reset keys
 * <ErrorBoundary
 *   FallbackComponent={CustomErrorFallback}
 *   onError={(error) => logError(error)}
 *   resetKeys={[userId]}
 * >
 *   <UserProfile userId={userId} />
 * </ErrorBoundary>
 */
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error to console in development
    if (import.meta.env.DEV) {
      console.error('ErrorBoundary caught an error:', error, errorInfo)
    }

    // Call onError callback if provided
    this.props.onError?.(error, errorInfo)
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps): void {
    // Reset error boundary when resetKeys change
    if (this.state.hasError && this.props.resetKeys) {
      const hasResetKeyChanged = this.props.resetKeys.some(
        (key, index) => key !== prevProps.resetKeys?.[index]
      )
      if (hasResetKeyChanged) {
        this.resetErrorBoundary()
      }
    }
  }

  resetErrorBoundary = (): void => {
    this.props.onReset?.()
    this.setState({ hasError: false, error: null })
  }

  render(): ReactNode {
    const { hasError, error } = this.state
    const { children, FallbackComponent, fallback } = this.props

    if (hasError && error) {
      // Priority: FallbackComponent > fallback > DefaultFallback
      if (FallbackComponent) {
        return (
          <FallbackComponent
            error={error}
            resetErrorBoundary={this.resetErrorBoundary}
          />
        )
      }

      if (fallback) {
        return fallback
      }

      return (
        <DefaultFallback
          error={error}
          resetErrorBoundary={this.resetErrorBoundary}
        />
      )
    }

    return children
  }
}

export type { ErrorBoundaryProps, FallbackProps }

