/**
 * Query Keys Factory
 *
 * Centralized query key management for TanStack Query.
 * Ensures consistent cache keys across the application.
 *
 * Usage:
 *   useQuery({ queryKey: queryKeys.catalog.list(filters), ... })
 *   queryClient.invalidateQueries({ queryKey: queryKeys.catalog.all })
 */

import type { CatalogFilters, AdminProductFilters } from '@/lib/api-client'

export interface ProcurementFilters {
  supplier_id?: string
  search?: string
  unmatched_only?: boolean
  page?: number
  limit?: number
}

export const queryKeys = {
  // =============================================================================
  // Catalog (Public)
  // =============================================================================
  catalog: {
    /** All catalog queries - use for broad invalidation */
    all: ['catalog'] as const,
    /** Catalog list with filters */
    list: (filters?: CatalogFilters) =>
      ['catalog', 'list', filters ?? {}] as const,
    /** Single product detail */
    detail: (id: string) => ['catalog', 'detail', id] as const,
    /** Categories list */
    categories: () => ['catalog', 'categories'] as const,
  },

  // =============================================================================
  // Admin Products (Sales)
  // =============================================================================
  admin: {
    products: {
      /** All admin product queries */
      all: ['admin', 'products'] as const,
      /** Admin products list with filters */
      list: (filters?: AdminProductFilters) =>
        ['admin', 'products', 'list', filters ?? {}] as const,
      /** Single admin product detail with supplier items */
      detail: (id: string) => ['admin', 'products', 'detail', id] as const,
    },
    suppliers: {
      /** All supplier queries */
      all: ['admin', 'suppliers'] as const,
      /** Unmatched supplier items with filters */
      unmatched: (filters?: ProcurementFilters) =>
        ['admin', 'suppliers', 'unmatched', filters ?? {}] as const,
      /** Single supplier detail */
      detail: (id: string) => ['admin', 'suppliers', 'detail', id] as const,
    },
  },

  // =============================================================================
  // Authentication
  // =============================================================================
  auth: {
    /** Current authenticated user */
    user: ['auth', 'user'] as const,
  },
} as const

// Type helpers for queryKey types
export type CatalogQueryKey =
  | typeof queryKeys.catalog.all
  | ReturnType<typeof queryKeys.catalog.list>
  | ReturnType<typeof queryKeys.catalog.detail>
  | ReturnType<typeof queryKeys.catalog.categories>

export type AdminProductQueryKey =
  | typeof queryKeys.admin.products.all
  | ReturnType<typeof queryKeys.admin.products.list>
  | ReturnType<typeof queryKeys.admin.products.detail>

export type AdminSupplierQueryKey =
  | typeof queryKeys.admin.suppliers.all
  | ReturnType<typeof queryKeys.admin.suppliers.unmatched>
  | ReturnType<typeof queryKeys.admin.suppliers.detail>

