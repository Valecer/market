/**
 * Hooks Index
 *
 * Central export for all custom React hooks.
 */

export { useAuth } from './useAuth'
export { useCart } from './useCart'
export { useCatalog, type CatalogResponse, type CatalogFilters } from './useCatalog'
export { useCategories, type Category } from './useCategories'
export { 
  useAdminProducts, 
  useUpdateProductStatus, 
  useBulkUpdateProductStatus, 
  type AdminProductsResponse,
  type UpdateProductStatusParams,
  type UpdateProductStatusResponse,
  type BulkUpdateStatusParams,
  type BulkUpdateStatusResponse,
} from './useAdminProducts'
export { useAdminProduct } from './useAdminProduct'

// Phase 6: Procurement hooks
export { useUnmatchedItems, type UnmatchedSupplierItem, type UnmatchedItemsResponse } from './useUnmatchedItems'
export { useMatchSupplier, type MatchParams, type MatchResponse, type MatchAction } from './useMatchSupplier'
export { useProductSearch, type ProductSearchResult } from './useProductSearch'
export { useCreateProduct, type CreateProductRequest, type CreateProductResponse } from './useCreateProduct'

// Phase 6: Ingestion hooks
export { useIngestionStatus, type IngestionStatus } from './useIngestionStatus'
export { useTriggerSync, type TriggerSyncResponse } from './useTriggerSync'

// Phase 8: Retry failed jobs
export { useRetryJob } from './useRetryJob'

// Phase 7: Settings and Supplier Management hooks
export { useMasterSheetUrl, useUpdateMasterSheetUrl } from './useSettings'
export {
  useSuppliers,
  useSupplier,
  useCreateSupplier,
  useUpdateSupplier,
  useDeleteSupplier,
  useUploadSupplierFile,
} from './useSuppliers'

