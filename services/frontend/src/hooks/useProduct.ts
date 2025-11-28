/**
 * useProduct Hook
 *
 * TanStack Query hook for fetching a single product's admin details.
 * Used in ProductDetailPage and admin views.
 *
 * Note: The API currently doesn't have a public /catalog/:id endpoint,
 * so this hook fetches from the admin endpoint for authorized users,
 * or uses the catalog list data for public users.
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient, type AdminProduct } from '@/lib/api-client'
import { queryKeys } from '@/lib/query-keys'

/**
 * Fetch a single admin product with supplier items
 */
async function fetchAdminProduct(id: string): Promise<AdminProduct> {
  // Note: This endpoint requires authentication
  // For public product detail, we'll use the catalog list data
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
 * Hook for fetching admin product details
 *
 * Features:
 * - Fetches product with supplier items and margin data
 * - Requires authentication (sales or admin role)
 * - Query disabled when no id provided
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

