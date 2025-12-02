/**
 * API Client for Marketbel Backend
 *
 * Uses openapi-fetch for type-safe API calls with auto-generated types.
 * Includes JWT token injection and automatic 401 redirect handling.
 */

import createClient from 'openapi-fetch'
import type { paths } from '@/types/api'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000'

/**
 * Type-safe API client instance
 * Use this for all API calls to ensure type safety
 */
export const apiClient = createClient<paths>({
  baseUrl: API_URL
})

/**
 * Middleware: Auto-inject JWT token on all requests
 */
apiClient.use({
  onRequest: ({ request }) => {
    const token = localStorage.getItem('jwt_token')
    if (token) {
      request.headers.set('Authorization', `Bearer ${token}`)
    }
    return request
  }
})

/**
 * Middleware: Handle 401 responses by redirecting to login
 */
apiClient.use({
  onResponse: ({ response }) => {
    if (response.status === 401) {
      // Clear stored auth data
      localStorage.removeItem('jwt_token')
      localStorage.removeItem('user')

      // Don't redirect if already on login page
      if (!window.location.pathname.includes('/login')) {
        // Redirect to login with expired parameter
        window.location.href = '/login?expired=true'
      }
    }
    return response
  }
})

// =============================================================================
// Type Helpers - Extract useful types from the generated API types
// =============================================================================

/** Catalog product from GET /api/v1/catalog/ */
export type CatalogProduct = NonNullable<
  paths['/api/v1/catalog/']['get']['responses']['200']['content']['application/json']['data']
>[number]

/** Admin product from GET /api/v1/admin/products */
export type AdminProduct = NonNullable<
  paths['/api/v1/admin/products']['get']['responses']['200']['content']['application/json']['data']
>[number]

/** Supplier item nested in admin product */
export type SupplierItem = AdminProduct['supplier_items'][number]

/** Login response from POST /api/v1/auth/login */
export type LoginResponse =
  paths['/api/v1/auth/login']['post']['responses']['200']['content']['application/json']

/** User from login response */
export type User = LoginResponse['user']

/** User role */
export type UserRole = User['role']

/** Product status */
export type ProductStatus = 'draft' | 'active' | 'archived'

/** Catalog query filters */
export type CatalogFilters = {
  category_id?: string
  min_price?: number
  max_price?: number
  search?: string
  page?: number
  limit?: number
}

/** Admin products query filters */
export type AdminProductFilters = {
  status?: ProductStatus
  min_margin?: number
  max_margin?: number
  supplier_id?: string
  page?: number
  limit?: number
}

// =============================================================================
// API Error Types
// =============================================================================

export type ApiErrorCode =
  | 'VALIDATION_ERROR'
  | 'UNAUTHORIZED'
  | 'FORBIDDEN'
  | 'NOT_FOUND'
  | 'CONFLICT'
  | 'RATE_LIMIT_EXCEEDED'
  | 'INTERNAL_ERROR'
  | 'REDIS_UNAVAILABLE'

export interface ApiError {
  error: {
    code: ApiErrorCode
    message: string
    details?: Record<string, unknown>
  }
}

/**
 * Check if a response error is an API error
 */
export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'error' in error &&
    typeof (error as ApiError).error === 'object' &&
    'code' in (error as ApiError).error &&
    'message' in (error as ApiError).error
  )
}

/**
 * Extract error message from API error or fallback to generic message
 */
export function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    return error.error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'An unexpected error occurred'
}


