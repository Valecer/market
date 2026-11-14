/**
 * Duplicate Detection Types
 *
 * Shared interfaces for potential duplicate handling in admin flows.
 * Mirrors Phase 2 Type Safety definitions in specs/011-pipeline-stabilization/plan.md.
 *
 * Phase 11: Pipeline Stabilization - US2 Auto-Creation + Duplicate Detection
 */

import { Type } from '@sinclair/typebox'
import type { Static } from '@sinclair/typebox'

// =============================================================================
// Type Definitions
// =============================================================================

export type PotentialDuplicateStatus = 'pending' | 'merged' | 'dismissed'

export interface ProductSummary {
  id: string
  name: string
  category: string
  price: number
  supplierCount: number
}

export interface PotentialDuplicate {
  id: string
  product1: ProductSummary
  product2: ProductSummary
  similarityScore: number
  detectionReason: string
  status: PotentialDuplicateStatus
  createdAt: Date
}

export interface MergeDuplicateRequest {
  keepProductId: string
  archiveProductId: string
}

export interface DuplicateStats {
  total: number
  pending: number
  merged: number
  dismissed: number
}

// =============================================================================
// TypeBox Schemas for Request/Response Validation
// =============================================================================

export const DuplicateStatusSchema = Type.Union([
  Type.Literal('pending'),
  Type.Literal('merged'),
  Type.Literal('dismissed'),
])

export const ProductSummarySchema = Type.Object({
  id: Type.String({ format: 'uuid', description: 'Product UUID' }),
  name: Type.String({ description: 'Product name' }),
  category: Type.String({ description: 'Full category path' }),
  price: Type.Number({ description: 'Current price' }),
  supplierCount: Type.Integer({ minimum: 0, description: 'Number of linked supplier items' }),
})

export const PotentialDuplicateSchema = Type.Object({
  id: Type.String({ format: 'uuid', description: 'Duplicate record UUID' }),
  product1: ProductSummarySchema,
  product2: ProductSummarySchema,
  similarityScore: Type.Number({ minimum: 0, maximum: 100, description: 'Name similarity (0-100)' }),
  detectionReason: Type.String({ description: 'Why the pair was flagged' }),
  status: DuplicateStatusSchema,
  createdAt: Type.String({ format: 'date-time', description: 'Detection timestamp' }),
})

// GET /admin/duplicates response
export const DuplicateListResponseSchema = Type.Object({
  duplicates: Type.Array(PotentialDuplicateSchema),
  total: Type.Integer({ minimum: 0, description: 'Total count matching filter' }),
})

export type DuplicateListResponse = Static<typeof DuplicateListResponseSchema>

// PATCH /admin/duplicates/:id/merge request
export const MergeDuplicateRequestSchema = Type.Object({
  keepProductId: Type.String({
    format: 'uuid',
    description: 'Product ID to keep',
  }),
  archiveProductId: Type.String({
    format: 'uuid',
    description: 'Product ID to archive',
  }),
})

export type MergeDuplicateRequestBody = Static<typeof MergeDuplicateRequestSchema>

// PATCH /admin/duplicates/:id/merge response
export const MergeDuplicateResponseSchema = Type.Object({
  success: Type.Boolean(),
  mergedProduct: Type.Object({
    id: Type.String({ format: 'uuid' }),
    name: Type.String(),
    supplierItemCount: Type.Integer({ minimum: 0 }),
  }),
})

export type MergeDuplicateResponse = Static<typeof MergeDuplicateResponseSchema>

// PATCH /admin/duplicates/:id/dismiss response
export const DismissDuplicateResponseSchema = Type.Object({
  success: Type.Boolean(),
})

export type DismissDuplicateResponse = Static<typeof DismissDuplicateResponseSchema>

// GET /admin/duplicates/stats response
export const DuplicateStatsResponseSchema = Type.Object({
  total: Type.Integer({ minimum: 0 }),
  pending: Type.Integer({ minimum: 0 }),
  merged: Type.Integer({ minimum: 0 }),
  dismissed: Type.Integer({ minimum: 0 }),
})

export type DuplicateStatsResponse = Static<typeof DuplicateStatsResponseSchema>
