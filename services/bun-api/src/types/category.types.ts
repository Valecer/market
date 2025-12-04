/**
 * Category Types for Semantic ETL Pipeline
 *
 * TypeBox schemas and types for category governance workflow.
 * Supports admin review of auto-created categories.
 *
 * NOTE: Uses string (UUID) for IDs to match PostgreSQL schema.
 *
 * @see /specs/009-semantic-etl/data-model.md
 */

import { Type, type Static } from '@sinclair/typebox'

// =============================================================================
// Category Review Item Schema
// =============================================================================

/**
 * Category item for admin review workflow
 *
 * Includes additional context like parent name,
 * supplier name, and product count for review UI.
 */
export const CategoryReviewItemSchema = Type.Object({
  id: Type.String({
    description: 'Category UUID',
  }),
  name: Type.String({
    description: 'Category name',
  }),
  parent_id: Type.Union([Type.String(), Type.Null()], {
    description: 'Parent category UUID (null for root)',
  }),
  parent_name: Type.Union([Type.String(), Type.Null()], {
    description: 'Parent category name (joined from categories table)',
  }),
  needs_review: Type.Boolean({
    description: 'Admin review flag',
  }),
  is_active: Type.Boolean({
    description: 'Active status',
  }),
  supplier_id: Type.Union([Type.String(), Type.Null()], {
    description: 'Original supplier UUID (for tracking)',
  }),
  supplier_name: Type.Union([Type.String(), Type.Null()], {
    description: 'Supplier name (joined from suppliers table)',
  }),
  product_count: Type.Number({
    minimum: 0,
    description: 'Number of products in this category',
  }),
  created_at: Type.String({
    description: 'Creation timestamp (ISO 8601)',
  }),
  updated_at: Type.String({
    description: 'Last update timestamp (ISO 8601)',
  }),
})

export type CategoryReviewItem = Static<typeof CategoryReviewItemSchema>

// =============================================================================
// Category Approval Request Schema
// =============================================================================

/**
 * Request to approve or merge a category
 *
 * Used by admin to resolve categories with needs_review=true.
 * - 'approve': Keep category as-is, set needs_review=false
 * - 'merge': Combine with existing category, transfer products
 */
export const CategoryApprovalRequestSchema = Type.Object({
  category_id: Type.String({
    description: 'Category UUID to approve or merge',
  }),
  action: Type.Union([Type.Literal('approve'), Type.Literal('merge')], {
    description: "Action to perform: 'approve' or 'merge'",
  }),
  merge_with_id: Type.Optional(
    Type.String({
      description: 'Target category UUID for merge (required if action=merge)',
    })
  ),
})

export type CategoryApprovalRequest = Static<typeof CategoryApprovalRequestSchema>

// =============================================================================
// Category Approval Response Schema
// =============================================================================

/**
 * Response after approving or merging a category
 */
export const CategoryApprovalResponseSchema = Type.Object({
  success: Type.Boolean({
    description: 'Operation success status',
  }),
  message: Type.String({
    description: 'Human-readable result message',
  }),
  category_id: Type.String({
    description: 'Affected category UUID',
  }),
  action: Type.Union([Type.Literal('approve'), Type.Literal('merge')], {
    description: 'Action performed',
  }),
  affected_products: Type.Number({
    minimum: 0,
    description: 'Number of products updated (for merge)',
  }),
})

export type CategoryApprovalResponse = Static<typeof CategoryApprovalResponseSchema>

// =============================================================================
// Category Review Query Schema
// =============================================================================

/**
 * Query parameters for listing categories needing review
 */
export const CategoryReviewQuerySchema = Type.Object({
  supplier_id: Type.Optional(
    Type.String({
      description: 'Filter by supplier UUID',
    })
  ),
  needs_review: Type.Optional(
    Type.Boolean({
      description: 'Filter by needs_review flag (omit for all)',
    })
  ),
  search: Type.Optional(
    Type.String({
      description: 'Search by category name',
    })
  ),
  page: Type.Optional(
    Type.Number({
      minimum: 1,
      default: 1,
      description: 'Page number',
    })
  ),
  limit: Type.Optional(
    Type.Number({
      minimum: 1,
      maximum: 200,
      default: 50,
      description: 'Items per page',
    })
  ),
  sort_by: Type.Optional(
    Type.Union(
      [
        Type.Literal('created_at'),
        Type.Literal('name'),
        Type.Literal('product_count'),
      ],
      {
        description: 'Sort field',
        default: 'created_at',
      }
    )
  ),
  sort_order: Type.Optional(
    Type.Union([Type.Literal('asc'), Type.Literal('desc')], {
      description: 'Sort order',
      default: 'desc',
    })
  ),
})

export type CategoryReviewQuery = Static<typeof CategoryReviewQuerySchema>

// =============================================================================
// Category Review Response Schema
// =============================================================================

/**
 * Paginated response for category review list
 */
export const CategoryReviewResponseSchema = Type.Object({
  total_count: Type.Number({
    minimum: 0,
    description: 'Total number of categories matching filters',
  }),
  page: Type.Number({
    minimum: 1,
    description: 'Current page number',
  }),
  limit: Type.Number({
    minimum: 1,
    description: 'Items per page',
  }),
  data: Type.Array(CategoryReviewItemSchema, {
    description: 'Array of category review items',
  }),
})

export type CategoryReviewResponse = Static<typeof CategoryReviewResponseSchema>

// =============================================================================
// Category Hierarchy Node Schema
// =============================================================================

/**
 * Category node in a hierarchical tree structure
 *
 * Used for displaying category hierarchy in UI
 */
export const CategoryHierarchyNodeSchema = Type.Recursive(
  (Self) =>
    Type.Object({
      id: Type.String({
        description: 'Category UUID',
      }),
      name: Type.String({
        description: 'Category name',
      }),
      parent_id: Type.Union([Type.String(), Type.Null()], {
        description: 'Parent category UUID',
      }),
      children: Type.Array(Self, {
        description: 'Child categories',
      }),
      needs_review: Type.Boolean({
        description: 'Admin review flag',
      }),
      is_active: Type.Boolean({
        description: 'Active status',
      }),
      product_count: Type.Number({
        minimum: 0,
        description: 'Products in this category',
      }),
    }),
  { $id: 'CategoryHierarchyNode' }
)

export type CategoryHierarchyNode = Static<typeof CategoryHierarchyNodeSchema>

// =============================================================================
// Bulk Category Actions
// =============================================================================

/**
 * Request to approve multiple categories at once
 */
export const BulkCategoryApprovalRequestSchema = Type.Object({
  category_ids: Type.Array(Type.String(), {
    minItems: 1,
    maxItems: 100,
    description: 'Array of category UUIDs to approve',
  }),
})

export type BulkCategoryApprovalRequest = Static<typeof BulkCategoryApprovalRequestSchema>

/**
 * Response for bulk category approval
 */
export const BulkCategoryApprovalResponseSchema = Type.Object({
  success: Type.Boolean({
    description: 'Operation success status',
  }),
  approved_count: Type.Number({
    minimum: 0,
    description: 'Number of categories approved',
  }),
  message: Type.String({
    description: 'Human-readable result message',
  }),
})

export type BulkCategoryApprovalResponse = Static<typeof BulkCategoryApprovalResponseSchema>

// =============================================================================
// Category Match Suggestion Schema
// =============================================================================

/**
 * Suggested match for a category (used in merge workflow)
 */
export const CategoryMatchSuggestionSchema = Type.Object({
  id: Type.String({
    description: 'Suggested category UUID',
  }),
  name: Type.String({
    description: 'Suggested category name',
  }),
  similarity_score: Type.Number({
    minimum: 0,
    maximum: 100,
    description: 'Fuzzy match similarity score',
  }),
  product_count: Type.Number({
    minimum: 0,
    description: 'Products in suggested category',
  }),
})

export type CategoryMatchSuggestion = Static<typeof CategoryMatchSuggestionSchema>

/**
 * Response with merge suggestions for a category
 */
export const CategoryMergeSuggestionsResponseSchema = Type.Object({
  category_id: Type.String({
    description: 'Source category UUID',
  }),
  category_name: Type.String({
    description: 'Source category name',
  }),
  suggestions: Type.Array(CategoryMatchSuggestionSchema, {
    description: 'Suggested categories to merge with',
  }),
})

export type CategoryMergeSuggestionsResponse = Static<typeof CategoryMergeSuggestionsResponseSchema>

// =============================================================================
// Review Count Response (for badge)
// =============================================================================

/**
 * Response for pending review count (used for badge)
 */
export const CategoryReviewCountResponseSchema = Type.Object({
  count: Type.Number({
    minimum: 0,
    description: 'Number of categories needing review',
  }),
})

export type CategoryReviewCountResponse = Static<typeof CategoryReviewCountResponseSchema>

// =============================================================================
// Category Update Request Schema
// =============================================================================

/**
 * Request to update a category name
 */
export const CategoryUpdateRequestSchema = Type.Object({
  name: Type.String({
    minLength: 1,
    maxLength: 255,
    description: 'New category name',
  }),
})

export type CategoryUpdateRequest = Static<typeof CategoryUpdateRequestSchema>

/**
 * Response after updating a category
 */
export const CategoryUpdateResponseSchema = Type.Object({
  success: Type.Boolean({
    description: 'Operation success status',
  }),
  message: Type.String({
    description: 'Human-readable result message',
  }),
  category: CategoryReviewItemSchema,
})

export type CategoryUpdateResponse = Static<typeof CategoryUpdateResponseSchema>

// =============================================================================
// Category Delete Response Schema
// =============================================================================

/**
 * Response after deleting a category
 */
export const CategoryDeleteResponseSchema = Type.Object({
  success: Type.Boolean({
    description: 'Operation success status',
  }),
  message: Type.String({
    description: 'Human-readable result message',
  }),
  category_id: Type.String({
    description: 'Deleted category UUID',
  }),
  reassigned_products: Type.Number({
    minimum: 0,
    description: 'Products reassigned to parent category (or uncategorized)',
  }),
})

export type CategoryDeleteResponse = Static<typeof CategoryDeleteResponseSchema>

