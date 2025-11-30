/**
 * useCategories Hook
 *
 * Hook for managing category options in filter dropdowns.
 * Since the API doesn't have a dedicated categories endpoint,
 * this extracts unique categories from catalog products.
 *
 * In a future iteration, this could fetch from a dedicated endpoint.
 */

import { useMemo } from 'react'
import { useCatalog, type CatalogProduct } from './useCatalog'

export interface Category {
  id: string
  name: string
}

/**
 * Extract unique categories from products
 * For now, uses category_id as both id and name since API doesn't return names
 */
function extractCategories(products: CatalogProduct[]): Category[] {
  const categoryMap = new Map<string, Category>()

  products.forEach((product) => {
    if (product.category_id && !categoryMap.has(product.category_id)) {
      categoryMap.set(product.category_id, {
        id: product.category_id,
        // Use truncated ID as display name until we have proper category names
        name: `Category ${product.category_id.slice(0, 8)}...`,
      })
    }
  })

  return Array.from(categoryMap.values()).sort((a, b) =>
    a.name.localeCompare(b.name)
  )
}

/**
 * Hook for getting category options
 *
 * Returns categories extracted from the catalog products.
 * This is a temporary solution until a dedicated categories API exists.
 */
export function useCategories() {
  // Fetch products to extract categories (max limit allowed by API is 200)
  const { data, isLoading, error } = useCatalog({ limit: 200 })

  const categories = useMemo(() => {
    if (!data?.data) return []
    return extractCategories(data.data)
  }, [data?.data])

  return {
    categories,
    isLoading,
    error,
  }
}

