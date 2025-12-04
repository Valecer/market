/**
 * Category Types for Frontend
 *
 * TypeScript interfaces for category governance workflow.
 * Matches the Bun API response schemas.
 *
 * @see /specs/009-semantic-etl/data-model.md
 */

/**
 * Category item for admin review workflow
 */
export interface CategoryReviewItem {
  id: string
  name: string
  parent_id: string | null
  parent_name: string | null
  needs_review: boolean
  is_active: boolean
  supplier_id: string | null
  supplier_name: string | null
  product_count: number
  created_at: string
  updated_at: string
}

/**
 * Paginated response for category review list
 */
export interface CategoryReviewResponse {
  total_count: number
  page: number
  limit: number
  data: CategoryReviewItem[]
}

/**
 * Response for pending review count (for badge)
 */
export interface CategoryReviewCountResponse {
  count: number
}

/**
 * Request to approve or merge a category
 */
export interface CategoryApprovalRequest {
  category_id: string
  action: 'approve' | 'merge'
  merge_with_id?: string
}

/**
 * Response after approving or merging a category
 */
export interface CategoryApprovalResponse {
  success: boolean
  message: string
  category_id: string
  action: 'approve' | 'merge'
  affected_products: number
}

/**
 * Request to approve multiple categories at once
 */
export interface BulkCategoryApprovalRequest {
  category_ids: string[]
}

/**
 * Response for bulk category approval
 */
export interface BulkCategoryApprovalResponse {
  success: boolean
  approved_count: number
  message: string
}

/**
 * Query parameters for listing categories needing review
 */
export interface CategoryReviewQuery {
  supplier_id?: string
  needs_review?: boolean
  search?: string
  page?: number
  limit?: number
  sort_by?: 'created_at' | 'name' | 'product_count'
  sort_order?: 'asc' | 'desc'
}

/**
 * Category suggestion for merge operation
 */
export interface CategoryMatchSuggestion {
  id: string
  name: string
  similarity_score: number
  product_count: number
}

/**
 * Response for merge suggestions endpoint
 */
export interface CategoryMergeSuggestionsResponse {
  category_id: string
  category_name: string
  suggestions: CategoryMatchSuggestion[]
}

/**
 * Request to update a category name
 */
export interface CategoryUpdateRequest {
  name: string
}

/**
 * Response after updating a category
 */
export interface CategoryUpdateResponse {
  success: boolean
  message: string
  category: CategoryReviewItem
}

/**
 * Response after deleting a category
 */
export interface CategoryDeleteResponse {
  success: boolean
  message: string
  category_id: string
  reassigned_products: number
}

