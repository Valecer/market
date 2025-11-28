/**
 * useUnmatchedItems Hook
 *
 * TanStack Query hook for fetching unmatched supplier items
 * (items not linked to any internal product).
 *
 * Used in the procurement matching page to display items that need to be linked.
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { queryKeys, type ProcurementFilters } from '@/lib/query-keys'

/**
 * Unmatched supplier item type (from API response)
 */
export interface UnmatchedSupplierItem {
  id: string
  supplier_id: string
  supplier_name: string
  supplier_sku: string
  name: string
  current_price: string
  characteristics: Record<string, unknown>
  last_ingested_at: string
}

/**
 * Unmatched items response type
 */
export interface UnmatchedItemsResponse {
  total_count: number
  page: number
  limit: number
  data: UnmatchedSupplierItem[]
}

/**
 * Hook for fetching unmatched supplier items
 *
 * @param filters - Optional filters (supplier_id, search, pagination)
 * @returns TanStack Query result with unmatched items
 */
export function useUnmatchedItems(filters?: ProcurementFilters) {
  return useQuery({
    queryKey: queryKeys.admin.suppliers.unmatched(filters),
    queryFn: async (): Promise<UnmatchedItemsResponse> => {
      const { data, error } = await apiClient.GET('/api/v1/admin/suppliers/unmatched', {
        params: {
          query: {
            supplier_id: filters?.supplier_id,
            search: filters?.search,
            page: filters?.page,
            limit: filters?.limit,
          },
        },
      })

      if (error) {
        throw new Error((error as any)?.error?.message || 'Failed to fetch unmatched items')
      }

      return data as UnmatchedItemsResponse
    },
    staleTime: 2 * 60 * 1000, // 2 minutes - items can change frequently
  })
}

