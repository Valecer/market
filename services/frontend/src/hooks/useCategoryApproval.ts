/**
 * useCategoryApproval Hook
 *
 * Mutation hooks for approving, merging, updating, and deleting categories.
 * Uses TanStack Query mutations with optimistic updates.
 *
 * @see /specs/009-semantic-etl/spec.md - FR-6: Hybrid Category Governance
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import type {
  CategoryApprovalRequest,
  CategoryApprovalResponse,
  BulkCategoryApprovalRequest,
  BulkCategoryApprovalResponse,
  CategoryUpdateRequest,
  CategoryUpdateResponse,
  CategoryDeleteResponse,
} from '@/types/category'
import { useAuth } from './useAuth'
import { categoryQueryKeys } from './useCategoriesReview'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3000'

/**
 * Approve or merge a single category
 */
async function approveCategory(
  request: CategoryApprovalRequest,
  token: string | null
): Promise<CategoryApprovalResponse> {
  const url = `${API_BASE}/api/v1/admin/categories/approve`

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Operation failed' }))
    throw new Error(error.error?.message || error.message || 'Operation failed')
  }

  return response.json()
}

/**
 * Bulk approve multiple categories
 */
async function bulkApproveCategories(
  request: BulkCategoryApprovalRequest,
  token: string | null
): Promise<BulkCategoryApprovalResponse> {
  const url = `${API_BASE}/api/v1/admin/categories/approve/bulk`

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Bulk approval failed' }))
    throw new Error(error.error?.message || error.message || 'Bulk approval failed')
  }

  return response.json()
}

/**
 * Hook for approving or merging a single category
 *
 * @returns TanStack Mutation for category approval/merge
 */
export function useCategoryApproval() {
  const { state } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: CategoryApprovalRequest) => approveCategory(request, state.token),
    onSuccess: () => {
      // Invalidate all category review queries to refresh the list
      queryClient.invalidateQueries({ queryKey: categoryQueryKeys.all })
    },
  })
}

/**
 * Hook for bulk approving multiple categories
 *
 * @returns TanStack Mutation for bulk category approval
 */
export function useBulkCategoryApproval() {
  const { state } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: BulkCategoryApprovalRequest) => bulkApproveCategories(request, state.token),
    onSuccess: () => {
      // Invalidate all category review queries to refresh the list
      queryClient.invalidateQueries({ queryKey: categoryQueryKeys.all })
    },
  })
}

/**
 * Update a category name
 */
async function updateCategory(
  categoryId: string,
  request: CategoryUpdateRequest,
  token: string | null
): Promise<CategoryUpdateResponse> {
  const url = `${API_BASE}/api/v1/admin/categories/${categoryId}`

  const response = await fetch(url, {
    method: 'PATCH',
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Update failed' }))
    throw new Error(error.error?.message || error.message || 'Update failed')
  }

  return response.json()
}

/**
 * Delete a category
 */
async function deleteCategory(
  categoryId: string,
  token: string | null
): Promise<CategoryDeleteResponse> {
  const url = `${API_BASE}/api/v1/admin/categories/${categoryId}`

  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Delete failed' }))
    throw new Error(error.error?.message || error.message || 'Delete failed')
  }

  return response.json()
}

/**
 * Hook for updating a category name
 *
 * @returns TanStack Mutation for category update
 */
export function useCategoryUpdate() {
  const { state } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ categoryId, name }: { categoryId: string; name: string }) =>
      updateCategory(categoryId, { name }, state.token),
    onSuccess: () => {
      // Invalidate all category review queries to refresh the list
      queryClient.invalidateQueries({ queryKey: categoryQueryKeys.all })
    },
  })
}

/**
 * Hook for deleting a category
 *
 * @returns TanStack Mutation for category deletion
 */
export function useCategoryDelete() {
  const { state } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (categoryId: string) => deleteCategory(categoryId, state.token),
    onSuccess: () => {
      // Invalidate all category review queries to refresh the list
      queryClient.invalidateQueries({ queryKey: categoryQueryKeys.all })
    },
  })
}

