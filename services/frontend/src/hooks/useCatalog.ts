/**
 * useCatalog Hook
 *
 * TanStack Query hook for fetching the public product catalog.
 * Supports filtering by category, price range, search, and pagination.
 *
 * @example
 * const { data, isLoading, error } = useCatalog({
 *   search: 'laptop',
 *   min_price: 100,
 *   page: 1
 * })
 */

import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { apiClient, type CatalogFilters, type CatalogProduct } from '@/lib/api-client'
import { queryKeys } from '@/lib/query-keys'

export interface CatalogResponse {
  total_count: number
  page: number
  limit: number
  data: CatalogProduct[]
}

/**
 * Fetch catalog products with optional filters
 */
async function fetchCatalog(filters: CatalogFilters): Promise<CatalogResponse> {
  const { data, error } = await apiClient.GET('/api/v1/catalog/', {
    params: {
      query: {
        category_id: filters.category_id,
        min_price: filters.min_price,
        max_price: filters.max_price,
        search: filters.search,
        page: filters.page ?? 1,
        limit: filters.limit ?? 12,
      },
    },
  })

  if (error) {
    throw new Error(error.error?.message || 'Failed to fetch catalog')
  }

  return data as CatalogResponse
}

/**
 * Hook for fetching the public product catalog
 *
 * Features:
 * - Automatic caching (5 minute staleTime)
 * - Background refetching on window focus
 * - Keeps previous data while fetching new page (smooth pagination)
 * - Query key includes filters for proper cache separation
 */
export function useCatalog(filters: CatalogFilters = {}) {
  return useQuery({
    queryKey: queryKeys.catalog.list(filters),
    queryFn: () => fetchCatalog(filters),
    placeholderData: keepPreviousData, // Keep previous data during pagination
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Type export for components that need the response type
 */
export type { CatalogProduct, CatalogFilters }

