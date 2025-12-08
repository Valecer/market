/**
 * useProduct Hook
 *
 * TanStack Query hook for fetching a single product with variants.
 * Phase 10: Product Variants
 *
 * @example
 * const { data: product, isLoading, error } = useProduct(productId)
 */

import { useQuery } from '@tanstack/react-query'
import type { CatalogProductDetail } from '@/lib/api-client'
import { queryKeys } from '@/lib/query-keys'

/**
 * Fetch a single product by ID with variants
 */
async function fetchProduct(id: string): Promise<CatalogProductDetail> {
  const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:3000'}/api/v1/catalog/${id}`)

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Product not found')
    }
    throw new Error('Failed to fetch product')
  }

  return response.json()
}

/**
 * Hook for fetching a single product with variants
 *
 * Features:
 * - Automatic caching (5 minute staleTime)
 * - Background refetching on window focus
 * - Returns null-safe loading/error states
 */
export function useProduct(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.catalog.detail(id ?? ''),
    queryFn: () => fetchProduct(id!),
    enabled: !!id,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

export type { CatalogProductDetail }

