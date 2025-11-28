/**
 * Hooks Index
 *
 * Central export for all custom React hooks.
 */

export { useAuth } from './useAuth'
export { useCart } from './useCart'
export { useCatalog, type CatalogResponse, type CatalogFilters } from './useCatalog'
export { useCategories, type Category } from './useCategories'
export { useAdminProducts, type AdminProductsResponse } from './useAdminProducts'
export { useAdminProduct } from './useAdminProduct'

// Phase 6: Procurement hooks
export { useUnmatchedItems, type UnmatchedSupplierItem, type UnmatchedItemsResponse } from './useUnmatchedItems'
export { useMatchSupplier, type MatchParams, type MatchResponse, type MatchAction } from './useMatchSupplier'
export { useProductSearch, type ProductSearchResult } from './useProductSearch'

