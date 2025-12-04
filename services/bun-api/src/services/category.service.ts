/**
 * Category Service
 *
 * Handles business logic for category governance workflow.
 * Supports admin review of auto-created categories from Semantic ETL.
 *
 * @see /specs/009-semantic-etl/spec.md - FR-6: Hybrid Category Governance
 */

import { db } from '../db/client'
import { categories, products, suppliers } from '../db/schema/schema'
import { eq, sql, and, or } from 'drizzle-orm'
import type {
  CategoryReviewQuery,
  CategoryReviewResponse,
  CategoryReviewItem,
  CategoryApprovalRequest,
  CategoryApprovalResponse,
  BulkCategoryApprovalRequest,
  BulkCategoryApprovalResponse,
  CategoryReviewCountResponse,
  CategoryUpdateRequest,
  CategoryUpdateResponse,
  CategoryDeleteResponse,
} from '../types/category.types'

/**
 * Category Service Interface
 *
 * Defines the contract for category governance operations
 */
export interface ICategoryService {
  /**
   * Get paginated list of categories for admin review
   */
  getCategoriesForReview(query: CategoryReviewQuery): Promise<CategoryReviewResponse>

  /**
   * Get count of categories needing review (for badge)
   */
  getReviewCount(): Promise<CategoryReviewCountResponse>

  /**
   * Approve or merge a category
   */
  processApproval(request: CategoryApprovalRequest): Promise<CategoryApprovalResponse>

  /**
   * Bulk approve multiple categories
   */
  bulkApprove(request: BulkCategoryApprovalRequest): Promise<BulkCategoryApprovalResponse>

  /**
   * Update a category name
   */
  updateCategory(categoryId: string, request: CategoryUpdateRequest): Promise<CategoryUpdateResponse>

  /**
   * Delete a category
   */
  deleteCategory(categoryId: string): Promise<CategoryDeleteResponse>
}

/**
 * Category Service Implementation
 *
 * Implements category governance using Drizzle ORM
 */
export class CategoryService implements ICategoryService {
  /**
   * Get paginated list of categories for admin review
   *
   * Includes:
   * - Parent category name (self-join)
   * - Supplier name (join)
   * - Product count (aggregate)
   */
  async getCategoriesForReview(query: CategoryReviewQuery): Promise<CategoryReviewResponse> {
    const {
      supplier_id,
      needs_review,
      search,
      page = 1,
      limit = 50,
      sort_by = 'created_at',
      sort_order = 'desc',
    } = query

    const offset = (page - 1) * limit

    // Build where conditions dynamically
    const conditions: string[] = []

    // Filter by needs_review (optional - undefined returns all)
    if (needs_review !== undefined) {
      conditions.push(`c.needs_review = ${needs_review}`)
    }

    // Filter by supplier_id if provided
    if (supplier_id) {
      conditions.push(`c.supplier_id = '${supplier_id}'::uuid`)
    }

    // Search by name (case-insensitive)
    if (search && search.trim()) {
      const escapedSearch = search.trim().replace(/'/g, "''")
      conditions.push(`c.name ILIKE '%${escapedSearch}%'`)
    }

    // Only show active categories
    conditions.push(`c.is_active = true`)

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''

    // Build ORDER BY clause
    let orderByClause = ''
    if (sort_by === 'name') {
      orderByClause = sort_order === 'asc' ? 'ORDER BY c.name ASC' : 'ORDER BY c.name DESC'
    } else if (sort_by === 'product_count') {
      orderByClause =
        sort_order === 'asc' ? 'ORDER BY product_count ASC' : 'ORDER BY product_count DESC'
    } else {
      // default: created_at
      orderByClause =
        sort_order === 'asc' ? 'ORDER BY c.created_at ASC' : 'ORDER BY c.created_at DESC'
    }

    // Execute the main query with all joins
    const dataResult = await db.execute<CategoryReviewItem>(sql.raw(`
      SELECT
        c.id::text as id,
        c.name,
        c.parent_id::text as parent_id,
        pc.name as parent_name,
        c.needs_review,
        c.is_active,
        c.supplier_id::text as supplier_id,
        s.name as supplier_name,
        COALESCE(prod_count.cnt, 0)::integer as product_count,
        c.created_at::text as created_at,
        c.updated_at::text as updated_at
      FROM categories c
      LEFT JOIN categories pc ON c.parent_id = pc.id
      LEFT JOIN suppliers s ON c.supplier_id = s.id
      LEFT JOIN (
        SELECT category_id, COUNT(*)::integer as cnt
        FROM products
        WHERE category_id IS NOT NULL
        GROUP BY category_id
      ) prod_count ON prod_count.category_id = c.id
      ${whereClause}
      ${orderByClause}
      LIMIT ${limit}
      OFFSET ${offset}
    `))

    // Get total count
    const countResult = await db.execute<{ total: number }>(sql.raw(`
      SELECT COUNT(*)::integer as total
      FROM categories c
      ${whereClause}
    `))

    const total_count = countResult.rows[0]?.total ?? 0

    return {
      total_count,
      page,
      limit,
      data: dataResult.rows as CategoryReviewItem[],
    }
  }

  /**
   * Get count of categories needing review (for badge)
   *
   * Only counts active categories where needs_review = true
   */
  async getReviewCount(): Promise<CategoryReviewCountResponse> {
    const result = await db.execute<{ count: number }>(sql`
      SELECT COUNT(*)::integer as count
      FROM categories
      WHERE needs_review = true
        AND is_active = true
    `)

    return {
      count: result.rows[0]?.count ?? 0,
    }
  }

  /**
   * Approve or merge a category
   *
   * For 'approve': Sets needs_review=false
   * For 'merge': Transfers all products to target category, then deletes source
   */
  async processApproval(request: CategoryApprovalRequest): Promise<CategoryApprovalResponse> {
    const { category_id, action, merge_with_id } = request

    // Validate category exists
    const [category] = await db
      .select()
      .from(categories)
      .where(eq(categories.id, category_id))
      .limit(1)

    if (!category) {
      const error = new Error(`Category with id ${category_id} not found`)
      ;(error as any).code = 'NOT_FOUND'
      throw error
    }

    if (action === 'approve') {
      // Set needs_review = false
      await db
        .update(categories)
        .set({
          needsReview: false,
          updatedAt: sql`NOW()`,
        })
        .where(eq(categories.id, category_id))

      return {
        success: true,
        message: `Category "${category.name}" approved`,
        category_id,
        action: 'approve',
        affected_products: 0,
      }
    }

    // Action is 'merge'
    if (!merge_with_id) {
      const error = new Error('merge_with_id is required for merge action')
      ;(error as any).code = 'VALIDATION_ERROR'
      throw error
    }

    // Validate target category exists
    const [targetCategory] = await db
      .select()
      .from(categories)
      .where(eq(categories.id, merge_with_id))
      .limit(1)

    if (!targetCategory) {
      const error = new Error(`Target category with id ${merge_with_id} not found`)
      ;(error as any).code = 'NOT_FOUND'
      throw error
    }

    // Cannot merge to self
    if (category_id === merge_with_id) {
      const error = new Error('Cannot merge category with itself')
      ;(error as any).code = 'VALIDATION_ERROR'
      throw error
    }

    // Execute merge in transaction
    return await db.transaction(async (tx) => {
      // 1. Update all products from source to target category
      const updateResult = await tx.execute(sql`
        UPDATE products
        SET category_id = ${merge_with_id}::uuid, updated_at = NOW()
        WHERE category_id = ${category_id}::uuid
      `)

      const affected_products = updateResult.rowCount ?? 0

      // 2. Update any child categories to point to target
      await tx.execute(sql`
        UPDATE categories
        SET parent_id = ${merge_with_id}::uuid, updated_at = NOW()
        WHERE parent_id = ${category_id}::uuid
      `)

      // 3. Delete the source category (soft delete - set is_active = false)
      // Or hard delete if you prefer:
      await tx.execute(sql`
        DELETE FROM categories
        WHERE id = ${category_id}::uuid
      `)

      return {
        success: true,
        message: `Category "${category.name}" merged into "${targetCategory.name}" (${affected_products} products transferred)`,
        category_id,
        action: 'merge' as const,
        affected_products,
      }
    })
  }

  /**
   * Bulk approve multiple categories
   *
   * Sets needs_review = false for all specified categories
   */
  async bulkApprove(request: BulkCategoryApprovalRequest): Promise<BulkCategoryApprovalResponse> {
    const { category_ids } = request

    if (category_ids.length === 0) {
      return {
        success: true,
        approved_count: 0,
        message: 'No categories to approve',
      }
    }

    // Build placeholders for IN clause
    const placeholders = category_ids.map((id) => `'${id}'::uuid`).join(', ')

    // Update all categories in bulk
    const result = await db.execute(sql.raw(`
      UPDATE categories
      SET needs_review = false, updated_at = NOW()
      WHERE id IN (${placeholders})
        AND needs_review = true
    `))

    const approved_count = result.rowCount ?? 0

    return {
      success: true,
      approved_count,
      message: `${approved_count} categories approved`,
    }
  }

  /**
   * Update a category name
   *
   * @param categoryId - UUID of the category to update
   * @param request - Update request with new name
   */
  async updateCategory(categoryId: string, request: CategoryUpdateRequest): Promise<CategoryUpdateResponse> {
    const { name } = request

    // Validate category exists
    const [category] = await db
      .select()
      .from(categories)
      .where(eq(categories.id, categoryId))
      .limit(1)

    if (!category) {
      const error = new Error(`Category with id ${categoryId} not found`)
      ;(error as any).code = 'NOT_FOUND'
      throw error
    }

    // Check for duplicate name in same parent
    const [duplicate] = await db
      .select()
      .from(categories)
      .where(
        and(
          eq(categories.name, name),
          category.parentId
            ? eq(categories.parentId, category.parentId)
            : sql`parent_id IS NULL`
        )
      )
      .limit(1)

    if (duplicate && duplicate.id !== categoryId) {
      const error = new Error(`Category "${name}" already exists at this level`)
      ;(error as any).code = 'DUPLICATE'
      throw error
    }

    // Update the category
    await db
      .update(categories)
      .set({
        name,
        updatedAt: sql`NOW()`,
      })
      .where(eq(categories.id, categoryId))

    // Get the updated category with all joins
    const dataResult = await db.execute<CategoryReviewItem>(sql.raw(`
      SELECT
        c.id::text as id,
        c.name,
        c.parent_id::text as parent_id,
        pc.name as parent_name,
        c.needs_review,
        c.is_active,
        c.supplier_id::text as supplier_id,
        s.name as supplier_name,
        COALESCE(prod_count.cnt, 0)::integer as product_count,
        c.created_at::text as created_at,
        c.updated_at::text as updated_at
      FROM categories c
      LEFT JOIN categories pc ON c.parent_id = pc.id
      LEFT JOIN suppliers s ON c.supplier_id = s.id
      LEFT JOIN (
        SELECT category_id, COUNT(*)::integer as cnt
        FROM products
        WHERE category_id IS NOT NULL
        GROUP BY category_id
      ) prod_count ON prod_count.category_id = c.id
      WHERE c.id = '${categoryId}'::uuid
    `))

    return {
      success: true,
      message: `Category renamed to "${name}"`,
      category: dataResult.rows[0] as CategoryReviewItem,
    }
  }

  /**
   * Delete a category
   *
   * Reassigns products to parent category (or null if root).
   * Also reassigns child categories to parent.
   *
   * @param categoryId - UUID of the category to delete
   */
  async deleteCategory(categoryId: string): Promise<CategoryDeleteResponse> {
    // Validate category exists
    const [category] = await db
      .select()
      .from(categories)
      .where(eq(categories.id, categoryId))
      .limit(1)

    if (!category) {
      const error = new Error(`Category with id ${categoryId} not found`)
      ;(error as any).code = 'NOT_FOUND'
      throw error
    }

    // Execute deletion in transaction
    return await db.transaction(async (tx) => {
      // 1. Reassign products to parent category (or null)
      const parentId = category.parentId
      const updateProductsResult = await tx.execute(sql.raw(`
        UPDATE products
        SET category_id = ${parentId ? `'${parentId}'::uuid` : 'NULL'}, updated_at = NOW()
        WHERE category_id = '${categoryId}'::uuid
      `))

      const reassigned_products = updateProductsResult.rowCount ?? 0

      // 2. Reassign child categories to parent
      await tx.execute(sql.raw(`
        UPDATE categories
        SET parent_id = ${parentId ? `'${parentId}'::uuid` : 'NULL'}, updated_at = NOW()
        WHERE parent_id = '${categoryId}'::uuid
      `))

      // 3. Delete the category
      await tx.execute(sql.raw(`
        DELETE FROM categories
        WHERE id = '${categoryId}'::uuid
      `))

      return {
        success: true,
        message: `Category "${category.name}" deleted (${reassigned_products} products reassigned)`,
        category_id: categoryId,
        reassigned_products,
      }
    })
  }
}

// Export singleton instance
export const categoryService = new CategoryService()
