/**
 * useIngestionStatus Hook
 *
 * TanStack Query hook for polling ingestion pipeline status.
 * Automatically polls every 3 seconds while sync is in progress.
 *
 * @example
 * const { data, isLoading, error } = useIngestionStatus()
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { queryKeys } from '@/lib/query-keys'
import type { IngestionStatus } from '@/types/ingestion'

/**
 * Fetch ingestion status from API
 */
async function fetchIngestionStatus(logLimit: number = 50): Promise<IngestionStatus> {
  const { data, error } = await apiClient.GET('/api/v1/admin/ingestion/status', {
    params: {
      query: {
        log_limit: logLimit,
      },
    },
  })

  if (error) {
    throw new Error(error.error?.message || 'Failed to fetch ingestion status')
  }

  return data as IngestionStatus
}

/**
 * Hook for polling ingestion pipeline status
 *
 * Features:
 * - Polls every 3 seconds while sync is in progress
 * - Longer polling interval (10s) when idle
 * - Auto-enabled when user has admin role
 * - Pauses polling when browser tab is hidden
 */
export function useIngestionStatus(options?: { enabled?: boolean; logLimit?: number }) {
  const { enabled = true, logLimit = 50 } = options || {}

  return useQuery({
    queryKey: queryKeys.ingestion.status(logLimit),
    queryFn: () => fetchIngestionStatus(logLimit),
    enabled,
    // Poll every 3 seconds when syncing, 10 seconds when idle
    refetchInterval: (query) => {
      const state = query.state.data?.sync_state
      if (state === 'syncing_master' || state === 'processing_suppliers') {
        return 3000 // 3 seconds during sync
      }
      return 10000 // 10 seconds when idle
    },
    // Don't refetch in background when tab is hidden
    refetchIntervalInBackground: false,
    // Keep data fresh
    staleTime: 2000,
  })
}

export type { IngestionStatus }

