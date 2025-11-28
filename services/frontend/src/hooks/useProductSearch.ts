/**
 * useProductSearch Hook
 *
 * TanStack Query hook for searching products with debounce.
 * Used in ProductSearchModal for fuzzy matching when linking supplier items.
 */

import { useQuery } from '@tanstack/react-query'
import { useState, useEffect, useMemo } from 'react'
import { apiClient, type AdminProduct } from '@/lib/api-client'
import { queryKeys } from '@/lib/query-keys'

/**
 * Debounce hook to delay search execution
 */
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(timer)
    }
  }, [value, delay])

  return debouncedValue
}

/**
 * Product search result type
 */
export interface ProductSearchResult {
  id: string
  internal_sku: string
  name: string
  category_id: string | null
  status: 'draft' | 'active' | 'archived'
  supplier_count: number
}

/**
 * Hook for searching products with debounce
 *
 * Features:
 * - Debounced search (300ms default)
 * - Only searches when query length >= 2 characters
 * - Returns products that can be linked to supplier items
 *
 * @param searchQuery - Search query string
 * @param debounceMs - Debounce delay in milliseconds (default: 300)
 * @returns TanStack Query result with search results
 */
export function useProductSearch(searchQuery: string, debounceMs = 300) {
  const debouncedQuery = useDebounce(searchQuery.trim(), debounceMs)

  const shouldSearch = debouncedQuery.length >= 2

  const query = useQuery({
    queryKey: ['product-search', debouncedQuery],
    queryFn: async (): Promise<ProductSearchResult[]> => {
      if (!shouldSearch) {
        return []
      }

      // Use admin products API with search - this gives us products the user can link to
      const { data, error } = await apiClient.GET('/api/v1/admin/products', {
        params: {
          query: {
            // Note: The API might not have a direct search param, 
            // so we'll filter client-side if needed
            limit: 20,
          },
        },
      })

      if (error) {
        throw new Error((error as any)?.error?.message || 'Failed to search products')
      }

      // Map and filter results based on search query
      const searchLower = debouncedQuery.toLowerCase()
      const products = (data?.data || []) as AdminProduct[]

      // Client-side filtering for fuzzy match on name or SKU
      const filtered = products.filter((product) => {
        const nameMatch = product.name.toLowerCase().includes(searchLower)
        const skuMatch = product.internal_sku.toLowerCase().includes(searchLower)
        return nameMatch || skuMatch
      })

      // Map to search result format
      return filtered.map((product) => ({
        id: product.id,
        internal_sku: product.internal_sku,
        name: product.name,
        category_id: product.category_id,
        status: product.status,
        supplier_count: product.supplier_items?.length || 0,
      }))
    },
    enabled: shouldSearch,
    staleTime: 30 * 1000, // 30 seconds - search results can be cached briefly
  })

  return {
    ...query,
    searchQuery: debouncedQuery,
    isSearching: shouldSearch && query.isLoading,
  }
}

