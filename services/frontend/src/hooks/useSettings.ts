/**
 * useSettings Hook
 *
 * Hook for managing admin settings (master sheet URL).
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/lib/query-keys'
import type { MasterSheetUrlResponse, UpdateMasterSheetUrlRequest } from '@/types/settings'

const API_URL = import.meta.env.VITE_API_URL || ''

/**
 * Fetch helper with auth token
 */
async function fetchWithAuth<T>(url: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('jwt_token')
  const response = await fetch(`${API_URL}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options?.headers,
    },
  })

  if (!response.ok) {
    // Handle JSON parsing errors (e.g., DecompressionStream not available in Safari)
    let errorData: { error?: { message?: string } } = {}
    try {
      const text = await response.text()
      errorData = JSON.parse(text)
    } catch {
      // If JSON parsing fails, use status text
      throw new Error(`Request failed: ${response.statusText || response.status}`)
    }
    throw new Error(errorData.error?.message || 'Request failed')
  }

  return response.json()
}

// =============================================================================
// Query Hook
// =============================================================================

/**
 * Hook to fetch master sheet URL configuration
 */
export function useMasterSheetUrl(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.settings.masterSheetUrl,
    queryFn: async () => {
      return fetchWithAuth<MasterSheetUrlResponse>('/api/v1/admin/settings/master-sheet-url')
    },
    enabled: options?.enabled ?? true,
    staleTime: 30 * 1000, // 30 seconds
  })
}

// =============================================================================
// Mutation Hook
// =============================================================================

/**
 * Hook to update master sheet URL
 */
export function useUpdateMasterSheetUrl() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: UpdateMasterSheetUrlRequest) => {
      return fetchWithAuth<{ url: string; message: string }>(
        '/api/v1/admin/settings/master-sheet-url',
        {
          method: 'PUT',
          body: JSON.stringify(data),
        }
      )
    },
    onSuccess: () => {
      // Invalidate settings query to refetch
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.masterSheetUrl })
    },
  })
}

