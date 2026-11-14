/**
 * Duplicate Service
 *
 * Business logic for managing potential duplicate products.
 * Handles listing, merging, and dismissing duplicate pairs.
 *
 * Phase 11: Pipeline Stabilization - US2 Auto-Creation + Duplicate Detection
 *
 * Tasks: T070-T073
 */

import { db } from '../db/client'
import { eq, and, sql } from 'drizzle-orm'
import { potentialDuplicates, products, supplierItems, categories } from '../db/schema/schema'
import type {
  PotentialDuplicate,
  ProductSummary,
  MergeDuplicateRequest,
  DuplicateStats,
  PotentialDuplicateStatus,
} from '../types/duplicate.types'

export interface DuplicateListQuery {
  status?: PotentialDuplicateStatus
  limit?: number
  offset?: number
}

export interface DuplicateListResponse {
  duplicates: PotentialDuplicate[]
  total: number
}

export interface MergeResponse {
  success: boolean
  mergedProduct: {
    id: string
    name: string
    supplierItemCount: number
  }
}

export interface DismissResponse {
  success: boolean
}

/**
 * Duplicate Service
 *
 * Methods:
 * - list(): Get paginated duplicates with product details
 * - merge(): Merge two products into one
 * - dismiss(): Mark a duplicate as false positive
 * - getStats(): Get duplicate queue statistics
 */
export class DuplicateService {
  /**
   * T071: List potential duplicates with product details
   *
   * @param query - Filter/pagination options
   * @returns Paginated duplicate list with full product details
   */
  async list(query: DuplicateListQuery = {}): Promise<DuplicateListResponse> {
    const { status = 'pending', limit = 50, offset = 0 } = query

    // Get total count for the status filter
    const countResult = await db
      .select({ count: sql<number>`COUNT(*)::int` })
      .from(potentialDuplicates)
      .where(eq(potentialDuplicates.status, status))

    const total = countResult[0]?.count || 0

    // Get duplicates with product details via subqueries
    const rows = await db
      .select({
        id: potentialDuplicates.id,
        productId1: potentialDuplicates.productId1,
        productId2: potentialDuplicates.productId2,
        similarityScore: potentialDuplicates.similarityScore,
        detectionReason: potentialDuplicates.detectionReason,
        status: potentialDuplicates.status,
        createdAt: potentialDuplicates.createdAt,
      })
      .from(potentialDuplicates)
      .where(eq(potentialDuplicates.status, status))
      .orderBy(sql`${potentialDuplicates.createdAt} DESC`)
      .limit(limit)
      .offset(offset)

    // Fetch product details for each duplicate
    const duplicates: PotentialDuplicate[] = await Promise.all(
      rows.map(async (row) => {
        const [product1, product2] = await Promise.all([
          this.getProductSummary(row.productId1),
          this.getProductSummary(row.productId2),
        ])

        return {
          id: row.id,
          product1,
          product2,
          similarityScore: parseFloat(row.similarityScore || '0'),
          detectionReason: row.detectionReason,
          status: row.status as PotentialDuplicateStatus,
          createdAt: new Date(row.createdAt),
        }
      })
    )

    return { duplicates, total }
  }

  /**
   * T072: Merge duplicate products
   *
   * Reassigns all supplier_items from archived product to kept product,
   * archives the duplicate, and marks the record as merged.
   *
   * @param duplicateId - Potential duplicate record ID
   * @param keepProductId - Product ID to keep
   * @param archiveProductId - Product ID to archive
   * @returns Merge result with updated product info
   */
  async merge(
    duplicateId: string,
    keepProductId: string,
    archiveProductId: string
  ): Promise<MergeResponse> {
    // Validate the duplicate record exists and is pending
    const duplicate = await db
      .select()
      .from(potentialDuplicates)
      .where(eq(potentialDuplicates.id, duplicateId))
      .limit(1)

    if (!duplicate[0]) {
      const error = new Error(`Duplicate record with id ${duplicateId} not found`)
      ;(error as any).code = 'NOT_FOUND'
      throw error
    }

    if (duplicate[0].status !== 'pending') {
      const error = new Error(`Duplicate record is already ${duplicate[0].status}`)
      ;(error as any).code = 'VALIDATION_ERROR'
      throw error
    }

    // Validate the product IDs match the duplicate record
    const validIds = [duplicate[0].productId1, duplicate[0].productId2]
    if (!validIds.includes(keepProductId) || !validIds.includes(archiveProductId)) {
      const error = new Error('Product IDs must match the duplicate record')
      ;(error as any).code = 'VALIDATION_ERROR'
      throw error
    }

    if (keepProductId === archiveProductId) {
      const error = new Error('Cannot merge a product with itself')
      ;(error as any).code = 'VALIDATION_ERROR'
      throw error
    }

    // Execute merge in transaction
    return await db.transaction(async (tx) => {
      // 1. Reassign supplier_items from archived to kept product
      await tx
        .update(supplierItems)
        .set({
          productId: keepProductId,
          updatedAt: sql`NOW()`,
        })
        .where(eq(supplierItems.productId, archiveProductId))

      // 2. Archive the duplicate product
      await tx
        .update(products)
        .set({
          status: 'archived',
          updatedAt: sql`NOW()`,
        })
        .where(eq(products.id, archiveProductId))

      // 3. Update duplicate record status
      await tx
        .update(potentialDuplicates)
        .set({
          status: 'merged',
          reviewedAt: sql`NOW()`,
          // Note: reviewedBy should be set from the JWT user context
        })
        .where(eq(potentialDuplicates.id, duplicateId))

      // 4. Get updated product info
      const keptProduct = await tx
        .select({
          id: products.id,
          name: products.name,
        })
        .from(products)
        .where(eq(products.id, keepProductId))
        .limit(1)

      // 5. Count supplier items for merged product
      const countResult = await tx
        .select({ count: sql<number>`COUNT(*)::int` })
        .from(supplierItems)
        .where(eq(supplierItems.productId, keepProductId))

      return {
        success: true,
        mergedProduct: {
          id: keptProduct[0]?.id || keepProductId,
          name: keptProduct[0]?.name || '',
          supplierItemCount: countResult[0]?.count || 0,
        },
      }
    })
  }

  /**
   * T073: Dismiss duplicate (mark as false positive)
   *
   * @param duplicateId - Potential duplicate record ID
   * @returns Success response
   */
  async dismiss(duplicateId: string): Promise<DismissResponse> {
    // Validate the duplicate record exists and is pending
    const duplicate = await db
      .select()
      .from(potentialDuplicates)
      .where(eq(potentialDuplicates.id, duplicateId))
      .limit(1)

    if (!duplicate[0]) {
      const error = new Error(`Duplicate record with id ${duplicateId} not found`)
      ;(error as any).code = 'NOT_FOUND'
      throw error
    }

    if (duplicate[0].status !== 'pending') {
      const error = new Error(`Duplicate record is already ${duplicate[0].status}`)
      ;(error as any).code = 'VALIDATION_ERROR'
      throw error
    }

    // Update status to dismissed
    await db
      .update(potentialDuplicates)
      .set({
        status: 'dismissed',
        reviewedAt: sql`NOW()`,
      })
      .where(eq(potentialDuplicates.id, duplicateId))

    return { success: true }
  }

  /**
   * Get statistics about the duplicate queue
   *
   * @returns Counts by status
   */
  async getStats(): Promise<DuplicateStats> {
    const results = await db
      .select({
        status: potentialDuplicates.status,
        count: sql<number>`COUNT(*)::int`,
      })
      .from(potentialDuplicates)
      .groupBy(potentialDuplicates.status)

    const stats: DuplicateStats = {
      total: 0,
      pending: 0,
      merged: 0,
      dismissed: 0,
    }

    for (const row of results) {
      stats.total += row.count
      if (row.status === 'pending') stats.pending = row.count
      if (row.status === 'merged') stats.merged = row.count
      if (row.status === 'dismissed') stats.dismissed = row.count
    }

    return stats
  }

  /**
   * Get product summary with supplier count
   *
   * @param productId - Product UUID
   * @returns ProductSummary object
   */
  private async getProductSummary(productId: string): Promise<ProductSummary> {
    // Get product with category
    const productResult = await db
      .select({
        id: products.id,
        name: products.name,
        categoryId: products.categoryId,
      })
      .from(products)
      .where(eq(products.id, productId))
      .limit(1)

    const product = productResult[0]

    if (!product) {
      return {
        id: productId,
        name: '[Deleted Product]',
        category: 'Unknown',
        price: 0,
        supplierCount: 0,
      }
    }

    // Get category name
    let categoryName = 'Uncategorized'
    if (product.categoryId) {
      const categoryResult = await db
        .select({ name: categories.name })
        .from(categories)
        .where(eq(categories.id, product.categoryId))
        .limit(1)
      categoryName = categoryResult[0]?.name || 'Unknown'
    }

    // Get supplier count and min price
    const supplierResult = await db
      .select({
        count: sql<number>`COUNT(*)::int`,
        minPrice: sql<string>`COALESCE(MIN(current_price), 0)`,
      })
      .from(supplierItems)
      .where(eq(supplierItems.productId, productId))

    return {
      id: product.id,
      name: product.name,
      category: categoryName,
      price: parseFloat(supplierResult[0]?.minPrice || '0'),
      supplierCount: supplierResult[0]?.count || 0,
    }
  }
}

// Export singleton instance
export const duplicateService = new DuplicateService()
