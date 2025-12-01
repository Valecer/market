/**
 * useTriggerSync Hook
 *
 * TanStack Query mutation hook for triggering the master sync pipeline.
 * Handles the POST /api/v1/admin/ingestion/sync request.
 *
 * @example
 * const { mutate, isPending, error } = useTriggerSync()
 * mutate() // Triggers sync
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient, getErrorMessage } from '@/lib/api-client'
import { queryKeys } from '@/lib/query-keys'
import type { TriggerSyncResponse, SyncInProgressError } from '@/types/ingestion'

/**
 * Trigger master sync pipeline via API
 */
async function triggerSync(): Promise<TriggerSyncResponse> {
  const { data, error, response } = await apiClient.POST('/api/v1/admin/ingestion/sync', {})

  if (error) {
    // Handle SYNC_IN_PROGRESS error specifically
    if (response?.status === 409) {
      const syncError = error as unknown as SyncInProgressError
      throw new Error(
        syncError.error?.message || 'A sync operation is already in progress'
      )
    }
    throw new Error(getErrorMessage(error))
  }

  return data as TriggerSyncResponse
}

/**
 * Hook for triggering the master sync pipeline
 *
 * Features:
 * - Optimistic UI update (status changes immediately)
 * - Automatic status refetch on success
 * - Error handling with user-friendly messages
 */
export function useTriggerSync() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: triggerSync,
    onMutate: async () => {
      // Cancel any outgoing refetches to avoid race conditions
      await queryClient.cancelQueries({ queryKey: queryKeys.ingestion.all })

      // Snapshot the previous value
      const previousStatus = queryClient.getQueryData(queryKeys.ingestion.status())

      // Optimistically update to syncing state
      queryClient.setQueryData(queryKeys.ingestion.status(), (old: unknown) => {
        if (old && typeof old === 'object' && 'sync_state' in old) {
          return {
            ...old,
            sync_state: 'syncing_master',
            progress: null,
          }
        }
        return old
      })

      return { previousStatus }
    },
    onError: (_err, _variables, context) => {
      // Rollback to previous state on error
      if (context?.previousStatus) {
        queryClient.setQueryData(queryKeys.ingestion.status(), context.previousStatus)
      }
    },
    onSettled: () => {
      // Refetch status after sync trigger (success or error)
      queryClient.invalidateQueries({ queryKey: queryKeys.ingestion.all })
    },
  })
}

export type { TriggerSyncResponse }

