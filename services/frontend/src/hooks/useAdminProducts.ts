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

import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { apiClient, type AdminProduct, type AdminProductFilters, type ProductStatus } from '@/lib/api-client'
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

// =============================================================================
// Product Status Mutations
// =============================================================================

export interface UpdateProductStatusParams {
  productId: string
  status: ProductStatus
}

export interface UpdateProductStatusResponse {
  id: string
  internal_sku: string
  name: string
  status: ProductStatus
  updated_at: string
  message: string
}

export interface BulkUpdateStatusParams {
  productIds: string[]
  status: ProductStatus
}

export interface BulkUpdateStatusResponse {
  updated_count: number
  status: ProductStatus
  message: string
}

/**
 * Get auth token from localStorage
 */
function getAuthToken(): string | null {
  // Token is stored directly as 'jwt_token' (not in a JSON object)
  return localStorage.getItem('jwt_token')
}

/**
 * Update single product status
 * Note: Using fetch directly as these endpoints are newly added and types haven't been regenerated
 */
async function updateProductStatus(params: UpdateProductStatusParams): Promise<UpdateProductStatusResponse> {
  const token = getAuthToken()
  const response = await fetch(`/api/v1/admin/products/${params.productId}/status`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
    },
    body: JSON.stringify({ status: params.status }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.error?.message || 'Failed to update product status')
  }

  return response.json()
}

/**
 * Bulk update product statuses
 * Note: Using fetch directly as these endpoints are newly added and types haven't been regenerated
 */
async function bulkUpdateProductStatus(params: BulkUpdateStatusParams): Promise<BulkUpdateStatusResponse> {
  const token = getAuthToken()
  const response = await fetch('/api/v1/admin/products/bulk-status', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
    },
    body: JSON.stringify({
      product_ids: params.productIds,
      status: params.status,
    }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.error?.message || 'Failed to bulk update product statuses')
  }

  return response.json()
}

/**
 * Hook for updating a single product's status
 *
 * @example
 * const { mutate, isPending } = useUpdateProductStatus()
 * mutate({ productId: '...', status: 'active' })
 */
export function useUpdateProductStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: updateProductStatus,
    onSuccess: () => {
      // Invalidate admin products list to refresh data
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.products.all })
      // Also invalidate catalog since product visibility may have changed
      queryClient.invalidateQueries({ queryKey: queryKeys.catalog.all })
    },
  })
}

/**
 * Hook for bulk updating product statuses
 *
 * @example
 * const { mutate, isPending } = useBulkUpdateProductStatus()
 * mutate({ productIds: ['...', '...'], status: 'active' })
 */
export function useBulkUpdateProductStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: bulkUpdateProductStatus,
    onSuccess: () => {
      // Invalidate admin products list to refresh data
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.products.all })
      // Also invalidate catalog since product visibility may have changed
      queryClient.invalidateQueries({ queryKey: queryKeys.catalog.all })
    },
  })
}

/**
 * Type exports for components
 */
export type { AdminProduct, AdminProductFilters, ProductStatus }

