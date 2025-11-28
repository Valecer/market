/**
 * Filter Types for Catalog and Admin Views
 *
 * These types define the shape of filter objects used throughout the application.
 * They correspond to the query parameters accepted by the backend API.
 */

/**
 * Public catalog filters (no authentication required)
 */
export interface CatalogFilters {
  /** Category UUID to filter by */
  category_id?: string
  /** Minimum price (inclusive) */
  min_price?: number
  /** Maximum price (inclusive) */
  max_price?: number
  /** Search query for product name or SKU */
  search?: string
  /** Page number (1-indexed) */
  page?: number
  /** Items per page */
  limit?: number
}

/**
 * Admin product filters (sales view)
 */
export interface AdminProductFilters {
  /** Product status */
  status?: 'draft' | 'active' | 'archived'
  /** Minimum margin percentage */
  min_margin?: number
  /** Maximum margin percentage */
  max_margin?: number
  /** Filter by supplier UUID */
  supplier_id?: string
  /** Page number */
  page?: number
  /** Items per page */
  limit?: number
}

/**
 * Procurement view filters
 */
export interface ProcurementFilters {
  /** Filter by supplier UUID */
  supplier_id?: string
  /** Search query */
  search?: string
  /** Show only unmatched items */
  unmatched_only?: boolean
  /** Page number */
  page?: number
  /** Items per page */
  limit?: number
}

