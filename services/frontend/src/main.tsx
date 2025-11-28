import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Theme } from '@radix-ui/themes'
import '@radix-ui/themes/styles.css'
import './index.css'
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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Theme accentColor="blue" grayColor="slate" radius="medium" scaling="100%">
        <App />
      </Theme>
    </QueryClientProvider>
  </StrictMode>
)
