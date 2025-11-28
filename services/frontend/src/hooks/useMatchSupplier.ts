/**
 * useMatchSupplier Hook
 *
 * TanStack Query mutation hook for linking/unlinking supplier items to products.
 * Implements optimistic updates for instant UI feedback.
 *
 * Used in the procurement matching page for the "Link to Product" and "Unlink" actions.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { queryKeys } from '@/lib/query-keys'
import type { UnmatchedItemsResponse } from './useUnmatchedItems'

/**
 * Match action type
 */
export type MatchAction = 'link' | 'unlink'

/**
 * Match mutation parameters
 */
export interface MatchParams {
  productId: string
  supplierItemId: string
  action: MatchAction
}

/**
 * Match response type (from API)
 */
export interface MatchResponse {
  product: {
    id: string
    internal_sku: string
    name: string
    category_id: string | null
    status: 'draft' | 'active' | 'archived'
    supplier_items: {
      id: string
      supplier_id: string
      supplier_name: string
      supplier_sku: string
      current_price: string
      characteristics: Record<string, unknown>
      last_ingested_at: string
    }[]
    margin_percentage: number | null
  }
}

/**
 * Hook for linking/unlinking supplier items to products
 *
 * Features:
 * - Optimistic updates for instant UI feedback
 * - Automatic rollback on error
 * - Cache invalidation after success
 *
 * @param options - Optional callbacks for success/error handling
 * @returns TanStack Query mutation result
 */
export function useMatchSupplier(options?: {
  onSuccess?: (data: MatchResponse, variables: MatchParams) => void
  onError?: (error: Error, variables: MatchParams) => void
}) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ productId, supplierItemId, action }: MatchParams): Promise<MatchResponse> => {
      const { data, error } = await apiClient.PATCH('/api/v1/admin/products/{id}/match', {
        params: {
          path: { id: productId },
        },
        body: {
          action,
          supplier_item_id: supplierItemId,
        },
      })

      if (error) {
        throw new Error((error as any)?.error?.message || `Failed to ${action} supplier item`)
      }

      return data as MatchResponse
    },

    // Optimistic update - remove item from unmatched list immediately when linking
    onMutate: async (variables) => {
      if (variables.action === 'link') {
        // Cancel any outgoing refetches
        await queryClient.cancelQueries({ queryKey: queryKeys.admin.suppliers.all })

        // Snapshot the previous value
        const previousUnmatched = queryClient.getQueryData<UnmatchedItemsResponse>(
          queryKeys.admin.suppliers.unmatched({})
        )

        // Optimistically remove the item from unmatched list
        if (previousUnmatched) {
          queryClient.setQueryData<UnmatchedItemsResponse>(
            queryKeys.admin.suppliers.unmatched({}),
            {
              ...previousUnmatched,
              total_count: previousUnmatched.total_count - 1,
              data: previousUnmatched.data.filter(
                (item) => item.id !== variables.supplierItemId
              ),
            }
          )
        }

        return { previousUnmatched }
      }

      return {}
    },

    // Rollback on error
    onError: (error, variables, context) => {
      if (variables.action === 'link' && context?.previousUnmatched) {
        queryClient.setQueryData(
          queryKeys.admin.suppliers.unmatched({}),
          context.previousUnmatched
        )
      }

      options?.onError?.(error as Error, variables)
    },

    // Invalidate and refetch after success
    onSuccess: (data, variables) => {
      // Invalidate unmatched items to ensure consistency
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.suppliers.all })

      // Invalidate admin products to refresh any cached product data
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.products.all })

      // Update the specific product in cache
      queryClient.setQueryData(
        queryKeys.admin.products.detail(variables.productId),
        data.product
      )

      options?.onSuccess?.(data, variables)
    },

    // Always refetch to ensure data consistency
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.suppliers.unmatched({}) })
    },
  })
}

