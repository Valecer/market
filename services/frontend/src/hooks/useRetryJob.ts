/**
 * useRetryJob Hook
 *
 * TanStack Query mutation hook for retrying failed ingestion jobs.
 * Provides optimistic updates and invalidates ingestion status on success.
 *
 * @see /specs/008-ml-ingestion-integration/spec.md - User Story 3
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'

// =============================================================================
// Types
// =============================================================================

interface RetryJobResponse {
  job_id: string
  status: 'retrying'
  message: string
  retry_count: number
}

interface RetryJobError {
  error: {
    code: 'NOT_FOUND' | 'CONFLICT' | 'FORBIDDEN' | 'REDIS_UNAVAILABLE' | 'INTERNAL_ERROR'
    message: string
  }
}

interface RetryJobContext {
  previousJobId?: string
}

// =============================================================================
// Hook
// =============================================================================

/**
 * Mutation hook for retrying a failed ingestion job.
 *
 * Usage:
 * ```tsx
 * const { mutate: retryJob, isPending } = useRetryJob()
 *
 * const handleRetry = (jobId: string) => {
 *   retryJob(jobId, {
 *     onSuccess: (data) => console.log('Retry initiated:', data.message),
 *     onError: (error) => console.error('Retry failed:', error),
 *   })
 * }
 * ```
 */
export function useRetryJob() {
  const queryClient = useQueryClient()

  return useMutation<RetryJobResponse, RetryJobError, string, RetryJobContext>({
    mutationFn: async (jobId: string) => {
      const response = await api.post<RetryJobResponse>(`/admin/jobs/${jobId}/retry`)
      return response.data
    },

    onMutate: async (jobId) => {
      // Cancel any outgoing refetches to prevent overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: ['ingestion-status'] })

      return { previousJobId: jobId }
    },

    onSuccess: () => {
      // Invalidate ingestion status to refetch latest data
      queryClient.invalidateQueries({ queryKey: ['ingestion-status'] })
    },

    onError: (error, _jobId, _context) => {
      // Log error for debugging
      console.error('Failed to retry job:', error.error?.message || 'Unknown error')

      // Invalidate to restore correct state
      queryClient.invalidateQueries({ queryKey: ['ingestion-status'] })
    },
  })
}

