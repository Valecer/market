/**
 * useAdminProduct Hook
 *
 * TanStack Query hook for fetching a single admin product with full details.
 * Includes supplier items, pricing data, and margin calculations.
 *
 * Note: Uses the admin products endpoint with filtering since there's no
 * dedicated single-product admin endpoint.
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient, type AdminProduct } from '@/lib/api-client'
import { queryKeys } from '@/lib/query-keys'

/**
 * Fetch a single admin product by ID
 * Since there's no dedicated endpoint, we fetch the list and filter
 */
async function fetchAdminProduct(id: string): Promise<AdminProduct> {
  const { data, error } = await apiClient.GET('/api/v1/admin/products', {
    params: {
      query: {
        page: 1,
        limit: 100,
      },
    },
  })

  if (error) {
    throw new Error(error.error?.message || 'Failed to fetch product')
  }

  // Find the product in the results
  const product = data?.data?.find((p: AdminProduct) => p.id === id)

  if (!product) {
    throw new Error('Product not found')
  }

  return product
}

/**
 * Hook for fetching a single admin product with full details
 *
 * Features:
 * - Fetches product with supplier items and margin data
 * - Requires authentication (sales or admin role)
 * - Query disabled when no id provided
 * - 5 minute cache time
 */
export function useAdminProduct(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.admin.products.detail(id ?? ''),
    queryFn: () => fetchAdminProduct(id!),
    enabled: !!id,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

export type { AdminProduct }

