/**
 * useAdminProducts Hook
 *
 * TanStack Query hook for fetching admin products with pricing data.
 * Supports filtering by status, margin range, supplier, and pagination.
 *
 * @example
 * const { data, isLoading, error } = useAdminProducts({
 *   status: 'active',
 *   min_margin: 10,
 *   page: 1
 * })
 */

import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { apiClient, type AdminProduct, type AdminProductFilters } from '@/lib/api-client'
import { queryKeys } from '@/lib/query-keys'

export interface AdminProductsResponse {
  total_count: number
  page: number
  limit: number
  data: AdminProduct[]
}

/**
 * Fetch admin products with optional filters
 */
async function fetchAdminProducts(filters: AdminProductFilters): Promise<AdminProductsResponse> {
  const { data, error } = await apiClient.GET('/api/v1/admin/products', {
    params: {
      query: {
        status: filters.status,
        min_margin: filters.min_margin,
        max_margin: filters.max_margin,
        supplier_id: filters.supplier_id,
        page: filters.page ?? 1,
        limit: filters.limit ?? 25,
      },
    },
  })

  if (error) {
    throw new Error(error.error?.message || 'Failed to fetch admin products')
  }

  return data as AdminProductsResponse
}

/**
 * Hook for fetching admin products with pricing data
 *
 * Features:
 * - Automatic caching (5 minute staleTime)
 * - Background refetching on window focus
 * - Keeps previous data while fetching new page (smooth pagination)
 * - Query key includes filters for proper cache separation
 * - Requires authentication (sales or admin role)
 */
export function useAdminProducts(filters: AdminProductFilters = {}) {
  return useQuery({
    queryKey: queryKeys.admin.products.list(filters),
    queryFn: () => fetchAdminProducts(filters),
    placeholderData: keepPreviousData, // Keep previous data during pagination
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Type exports for components
 */
export type { AdminProduct, AdminProductFilters }

