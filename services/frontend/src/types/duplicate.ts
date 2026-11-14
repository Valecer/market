/**
 * Duplicate Types for Frontend
 *
 * TypeScript interfaces for duplicate management workflow.
 * Matches the Bun API response schemas.
 *
 * @see /specs/011-pipeline-stabilization/spec.md
 */

/**
 * Product summary for duplicate comparison
 */
export interface ProductSummary {
  id: string
  name: string
  category: string
  price: number
  supplierCount: number
}

/**
 * Duplicate status
 */
export type DuplicateStatus = 'pending' | 'merged' | 'dismissed'

/**
 * Potential duplicate item for admin review
 */
export interface PotentialDuplicate {
  id: string
  product1: ProductSummary
  product2: ProductSummary
  similarityScore: number
  detectionReason: string
  status: DuplicateStatus
  createdAt: string
}

/**
 * Response for duplicate list
 */
export interface DuplicateListResponse {
  duplicates: PotentialDuplicate[]
  total: number
}

/**
 * Response for duplicate stats
 */
export interface DuplicateStatsResponse {
  total: number
  pending: number
  merged: number
  dismissed: number
}

/**
 * Query params for duplicate list
 */
export interface DuplicateListQuery {
  status?: DuplicateStatus
  limit?: number
  offset?: number
}

/**
 * Request to merge duplicates
 */
export interface MergeDuplicateRequest {
  keepProductId: string
  archiveProductId: string
}

/**
 * Response after merge
 */
export interface MergeDuplicateResponse {
  success: boolean
  mergedProduct: {
    id: string
    name: string
    supplierItemCount: number
  }
}

/**
 * Response after dismiss
 */
export interface DismissDuplicateResponse {
  success: boolean
}
