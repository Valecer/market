/**
 * useCategoriesReview Hook
 *
 * Hook for fetching categories that need admin review.
 * Uses TanStack Query for server state management.
 *
 * @see /specs/009-semantic-etl/spec.md - FR-6: Hybrid Category Governance
 */

import { useQuery } from '@tanstack/react-query'
import type {
  CategoryReviewQuery,
  CategoryReviewResponse,
  CategoryReviewCountResponse,
  CategoryMergeSuggestionsResponse,
} from '@/types/category'
import { useAuth } from './useAuth'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3000'

/**
 * Query key factory for category review queries
 */
export const categoryQueryKeys = {
  all: ['categories'] as const,
  review: (query: CategoryReviewQuery) => ['categories', 'review', query] as const,
  reviewCount: () => ['categories', 'review', 'count'] as const,
  mergeSuggestions: (categoryId: string) => ['categories', 'merge-suggestions', categoryId] as const,
}

/**
 * Fetch categories for review from the API
 */
async function fetchCategoriesForReview(
  query: CategoryReviewQuery,
  token: string | null
): Promise<CategoryReviewResponse> {
  const params = new URLSearchParams()

  if (query.supplier_id) params.set('supplier_id', query.supplier_id)
  if (query.needs_review !== undefined) params.set('needs_review', String(query.needs_review))
  if (query.search) params.set('search', query.search)
  if (query.page) params.set('page', String(query.page))
  if (query.limit) params.set('limit', String(query.limit))
  if (query.sort_by) params.set('sort_by', query.sort_by)
  if (query.sort_order) params.set('sort_order', query.sort_order)

  const url = `${API_BASE}/api/v1/admin/categories/review?${params.toString()}`

  const response = await fetch(url, {
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to load categories' }))
    throw new Error(error.error?.message || error.message || 'Failed to load categories')
  }

  return response.json()
}

/**
 * Fetch count of categories needing review
 */
async function fetchReviewCount(token: string | null): Promise<CategoryReviewCountResponse> {
  const url = `${API_BASE}/api/v1/admin/categories/review/count`

  const response = await fetch(url, {
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to load count' }))
    throw new Error(error.error?.message || error.message || 'Failed to load count')
  }

  return response.json()
}

/**
 * Hook for fetching categories needing review
 *
 * @param query - Filter and pagination options
 * @returns TanStack Query result with category data
 */
export function useCategoriesReview(query: CategoryReviewQuery = {}) {
  const { state, user } = useAuth()
  const isAdmin = user?.role === 'admin'

  return useQuery({
    queryKey: categoryQueryKeys.review(query),
    queryFn: () => fetchCategoriesForReview(query, state.token),
    enabled: !!state.token && isAdmin,
    staleTime: 30 * 1000, // 30 seconds
    refetchOnWindowFocus: true,
  })
}

/**
 * Hook for fetching count of categories needing review
 *
 * Used for navigation badge. Polls every 60 seconds.
 */
export function useCategoryReviewCount() {
  const { state, user } = useAuth()
  const isAdmin = user?.role === 'admin'

  return useQuery({
    queryKey: categoryQueryKeys.reviewCount(),
    queryFn: () => fetchReviewCount(state.token),
    enabled: !!state.token && isAdmin,
    staleTime: 60 * 1000, // 60 seconds
    refetchInterval: 60 * 1000, // Poll every minute
  })
}

/**
 * Fetch merge suggestions for a category
 */
async function fetchMergeSuggestions(
  categoryId: string,
  token: string | null
): Promise<CategoryMergeSuggestionsResponse> {
  const url = `${API_BASE}/api/v1/admin/categories/review/${categoryId}/suggestions`

  const response = await fetch(url, {
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to load suggestions' }))
    throw new Error(error.error?.message || error.message || 'Failed to load suggestions')
  }

  return response.json()
}

/**
 * Hook for fetching merge suggestions for a category
 *
 * @param categoryId - ID of the category to get suggestions for
 * @returns TanStack Query result with merge suggestions
 */
export function useCategoryMergeSuggestions(categoryId: string | null) {
  const { state, user } = useAuth()
  const isAdmin = user?.role === 'admin'

  return useQuery({
    queryKey: categoryQueryKeys.mergeSuggestions(categoryId || ''),
    queryFn: () => fetchMergeSuggestions(categoryId!, state.token),
    enabled: !!state.token && isAdmin && !!categoryId,
    staleTime: 30 * 1000, // 30 seconds
  })
}

