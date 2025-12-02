/**
 * useCreateProduct Hook
 *
 * Creates a new product with optional supplier item linkage.
 * Supports the "split SKU" workflow where a supplier item can be
 * linked during product creation.
 *
 * i18n: Error messages should be handled by the calling component
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { queryKeys } from '@/lib/query-keys'

// =============================================================================
// Types
// =============================================================================

export interface CreateProductRequest {
  /** Product name (required) */
  name: string
  /** Internal SKU (auto-generated if not provided) */
  internal_sku?: string
  /** Category UUID */
  category_id?: string
  /** Product status (defaults to 'draft') */
  status?: 'draft' | 'active'
  /** Supplier item to link during creation */
  supplier_item_id?: string
}

export interface CreateProductResponse {
  id: string
  internal_sku: string
  name: string
  category_id: string | null
  status: 'draft' | 'active'
  supplier_items: Array<{
    id: string
    supplier_id: string
    supplier_name: string
    supplier_sku: string
    current_price: string
    characteristics: Record<string, unknown>
    last_ingested_at: string
  }>
  created_at: string
}

interface UseCreateProductOptions {
  /** Callback on successful creation */
  onSuccess?: (data: CreateProductResponse) => void
  /** Callback on error */
  onError?: (error: Error) => void
}

// =============================================================================
// Hook
// =============================================================================

/**
 * Hook to create a new product with optional supplier item linkage
 * 
 * @example
 * ```tsx
 * const { createProduct, isCreating } = useCreateProduct({
 *   onSuccess: (product) => {
 *     toast.success(`Created ${product.name}`)
 *   },
 * })
 * 
 * // Create product and link supplier item
 * await createProduct({
 *   name: 'New Product',
 *   supplier_item_id: 'uuid-of-supplier-item',
 * })
 * ```
 */
export function useCreateProduct(options: UseCreateProductOptions = {}) {
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: async (request: CreateProductRequest): Promise<CreateProductResponse> => {
      const { data, error } = await apiClient.POST('/api/v1/admin/products', {
        body: request,
      })

      if (error) {
        const errorMessage = (error as { error?: { message?: string } })?.error?.message 
          || 'Failed to create product'
        throw new Error(errorMessage)
      }

      if (!data) {
        throw new Error('No data returned from API')
      }

      // Type assertion - API response matches CreateProductResponse structure
      return data as unknown as CreateProductResponse
    },
    onSuccess: (data) => {
      // Invalidate related queries to refresh data
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.products.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.suppliers.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.catalog.all })
      
      options.onSuccess?.(data)
    },
    onError: (error: Error) => {
      options.onError?.(error)
    },
  })

  return {
    /** Create a new product */
    createProduct: mutation.mutateAsync,
    /** Whether creation is in progress */
    isCreating: mutation.isPending,
    /** Whether creation failed */
    isError: mutation.isError,
    /** Error from last creation attempt */
    error: mutation.error,
    /** Reset mutation state */
    reset: mutation.reset,
  }
}

