import { StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Theme } from '@radix-ui/themes'
import { ErrorBoundary } from '@/components/shared/ErrorBoundary'
import { ToastProvider } from '@/components/shared/Toast'
import '@radix-ui/themes/styles.css'
import './index.css'
// Initialize i18n before App renders
import './i18n'
import App from './App'

/**
 * TanStack Query Client configuration
 * - staleTime: 5 minutes before data is considered stale
 * - gcTime: 10 minutes before unused data is garbage collected
 * - retry: 1 automatic retry on failure
 * - refetchOnWindowFocus: automatically refetch when window regains focus
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes
      retry: 1,
      refetchOnWindowFocus: true
    }
  }
})

/**
 * Loading fallback for i18n Suspense
 * Shows while translations are loading
 */
function LoadingFallback() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-50">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        <span className="text-sm text-slate-500">Loading...</span>
      </div>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary
      onError={(error, errorInfo) => {
        // Log to console in development, could send to error tracking service
        console.error('Application error:', error)
        console.error('Component stack:', errorInfo.componentStack)
      }}
      onReset={() => {
        // Clear any cached data that might be causing issues
        queryClient.clear()
      }}
    >
      <QueryClientProvider client={queryClient}>
        <Suspense fallback={<LoadingFallback />}>
        <Theme accentColor="blue" grayColor="slate" radius="medium" scaling="100%">
          <ToastProvider>
            <App />
          </ToastProvider>
        </Theme>
        </Suspense>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>
)
