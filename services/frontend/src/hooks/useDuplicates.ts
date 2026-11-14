/**
 * useDuplicates Hook
 *
 * Hooks for fetching and managing potential duplicate products.
 * Uses TanStack Query for server state management.
 *
 * Phase 11: Pipeline Stabilization - US2 Duplicate Detection
 *
 * @see /specs/011-pipeline-stabilization/spec.md
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type {
  DuplicateListQuery,
  DuplicateListResponse,
  DuplicateStatsResponse,
  MergeDuplicateRequest,
  MergeDuplicateResponse,
  DismissDuplicateResponse,
} from '@/types/duplicate'
import { useAuth } from './useAuth'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3000'

/**
 * Query key factory for duplicate queries
 */
export const duplicateQueryKeys = {
  all: ['duplicates'] as const,
  list: (query: DuplicateListQuery) => ['duplicates', 'list', query] as const,
  stats: () => ['duplicates', 'stats'] as const,
}

/**
 * Fetch duplicates from the API
 */
async function fetchDuplicates(
  query: DuplicateListQuery,
  token: string | null
): Promise<DuplicateListResponse> {
  const params = new URLSearchParams()

  if (query.status) params.set('status', query.status)
  if (query.limit) params.set('limit', String(query.limit))
  if (query.offset !== undefined) params.set('offset', String(query.offset))

  const url = `${API_BASE}/api/v1/admin/duplicates?${params.toString()}`

  const response = await fetch(url, {
    headers: {
      Authorization: token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to load duplicates' }))
    throw new Error(error.error?.message || error.message || 'Failed to load duplicates')
  }

  return response.json()
}

/**
 * Fetch duplicate stats from the API
 */
async function fetchDuplicateStats(token: string | null): Promise<DuplicateStatsResponse> {
  const url = `${API_BASE}/api/v1/admin/duplicates/stats`

  const response = await fetch(url, {
    headers: {
      Authorization: token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to load stats' }))
    throw new Error(error.error?.message || error.message || 'Failed to load stats')
  }

  return response.json()
}

/**
 * Merge duplicate products
 */
async function mergeDuplicates(
  duplicateId: string,
  request: MergeDuplicateRequest,
  token: string | null
): Promise<MergeDuplicateResponse> {
  const url = `${API_BASE}/api/v1/admin/duplicates/${duplicateId}/merge`

  const response = await fetch(url, {
    method: 'PATCH',
    headers: {
      Authorization: token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to merge duplicates' }))
    throw new Error(error.error?.message || error.message || 'Failed to merge duplicates')
  }

  return response.json()
}

/**
 * Dismiss a duplicate (mark as false positive)
 */
async function dismissDuplicate(
  duplicateId: string,
  token: string | null
): Promise<DismissDuplicateResponse> {
  const url = `${API_BASE}/api/v1/admin/duplicates/${duplicateId}/dismiss`

  const response = await fetch(url, {
    method: 'PATCH',
    headers: {
      Authorization: token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to dismiss duplicate' }))
    throw new Error(error.error?.message || error.message || 'Failed to dismiss duplicate')
  }

  return response.json()
}

/**
 * Hook for fetching potential duplicates
 *
 * @param query - Filter and pagination options
 * @returns TanStack Query result with duplicate data
 */
export function useDuplicates(query: DuplicateListQuery = {}) {
  const { state, user } = useAuth()
  const isAdmin = user?.role === 'admin'

  return useQuery({
    queryKey: duplicateQueryKeys.list(query),
    queryFn: () => fetchDuplicates(query, state.token),
    enabled: !!state.token && isAdmin,
    staleTime: 30 * 1000, // 30 seconds
    refetchOnWindowFocus: true,
  })
}

/**
 * Hook for fetching duplicate stats
 *
 * Used for navigation badge and dashboard.
 */
export function useDuplicateStats() {
  const { state, user } = useAuth()
  const isAdmin = user?.role === 'admin'

  return useQuery({
    queryKey: duplicateQueryKeys.stats(),
    queryFn: () => fetchDuplicateStats(state.token),
    enabled: !!state.token && isAdmin,
    staleTime: 60 * 1000, // 60 seconds
    refetchInterval: 60 * 1000, // Poll every minute
  })
}

/**
 * Hook for merging duplicate products
 */
export function useMergeDuplicate() {
  const { state } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ duplicateId, request }: { duplicateId: string; request: MergeDuplicateRequest }) =>
      mergeDuplicates(duplicateId, request, state.token),
    onSuccess: () => {
      // Invalidate duplicates and stats queries
      queryClient.invalidateQueries({ queryKey: duplicateQueryKeys.all })
    },
  })
}

/**
 * Hook for dismissing a duplicate
 */
export function useDismissDuplicate() {
  const { state } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (duplicateId: string) => dismissDuplicate(duplicateId, state.token),
    onSuccess: () => {
      // Invalidate duplicates and stats queries
      queryClient.invalidateQueries({ queryKey: duplicateQueryKeys.all })
    },
  })
}
