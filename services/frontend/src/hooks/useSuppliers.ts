/**
 * useSuppliers Hooks
 *
 * Hooks for supplier management including CRUD and file upload.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/lib/query-keys'
import type {
  Supplier,
  CreateSupplierRequest,
  CreateSupplierResponse,
  UpdateSupplierRequest,
  DeleteSupplierResponse,
  SuppliersListResponse,
  UploadSupplierFileResponse,
  UploadSupplierFileOptions,
} from '@/types/supplier'

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
// Query Hooks
// =============================================================================

/**
 * Hook to fetch all suppliers
 */
export function useSuppliers(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.suppliers.list,
    queryFn: async () => {
      return fetchWithAuth<SuppliersListResponse>('/api/v1/admin/suppliers')
    },
    enabled: options?.enabled ?? true,
    staleTime: 30 * 1000, // 30 seconds
  })
}

/**
 * Hook to fetch a single supplier by ID
 */
export function useSupplier(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.suppliers.detail(id),
    queryFn: async () => {
      return fetchWithAuth<Supplier>(`/api/v1/admin/suppliers/${id}`)
    },
    enabled: options?.enabled ?? !!id,
    staleTime: 30 * 1000,
  })
}

// =============================================================================
// Mutation Hooks
// =============================================================================

/**
 * Hook to create a new supplier
 */
export function useCreateSupplier() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: CreateSupplierRequest) => {
      return fetchWithAuth<CreateSupplierResponse>('/api/v1/admin/suppliers', {
        method: 'POST',
        body: JSON.stringify(data),
      })
    },
    onSuccess: () => {
      // Invalidate suppliers list
      queryClient.invalidateQueries({ queryKey: queryKeys.suppliers.list })
      // Also invalidate ingestion status to refresh supplier list there
      queryClient.invalidateQueries({ queryKey: queryKeys.ingestion.all })
    },
  })
}

/**
 * Hook to update a supplier
 */
export function useUpdateSupplier() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: UpdateSupplierRequest }) => {
      return fetchWithAuth<Supplier>(`/api/v1/admin/suppliers/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      })
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.suppliers.list })
      queryClient.invalidateQueries({ queryKey: queryKeys.suppliers.detail(variables.id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.ingestion.all })
    },
  })
}

/**
 * Hook to delete a supplier
 */
export function useDeleteSupplier() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (id: string) => {
      return fetchWithAuth<DeleteSupplierResponse>(`/api/v1/admin/suppliers/${id}`, {
        method: 'DELETE',
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.suppliers.list })
      queryClient.invalidateQueries({ queryKey: queryKeys.ingestion.all })
    },
  })
}

/**
 * Hook to upload a file for a supplier
 */
export function useUploadSupplierFile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      supplierId,
      file,
      options,
    }: {
      supplierId: string
      file: File
      options?: UploadSupplierFileOptions
    }) => {
      const formData = new FormData()
      formData.append('file', file)
      if (options?.sheet_name) {
        formData.append('sheet_name', options.sheet_name)
      }
      if (options?.header_row) {
        formData.append('header_row', options.header_row.toString())
      }
      if (options?.data_start_row) {
        formData.append('data_start_row', options.data_start_row.toString())
      }

      const token = localStorage.getItem('jwt_token')
      const response = await fetch(`${API_URL}/api/v1/admin/suppliers/${supplierId}/upload`, {
        method: 'POST',
        headers: {
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error?.message || 'Failed to upload file')
      }

      return response.json() as Promise<UploadSupplierFileResponse>
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.suppliers.list })
      queryClient.invalidateQueries({ queryKey: queryKeys.suppliers.detail(variables.supplierId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.ingestion.all })
    },
  })
}

