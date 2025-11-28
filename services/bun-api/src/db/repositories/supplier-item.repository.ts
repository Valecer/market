import { eq, isNull, and, ilike, or, count } from 'drizzle-orm'
import { db } from '../client'
import { supplierItems, suppliers } from '../schema/schema'
import type { SupplierItem } from '../schema/types'

/**
 * Unmatched supplier item query parameters
 */
export interface UnmatchedQuery {
  supplier_id?: string
  search?: string
  page?: number
  limit?: number
}

/**
 * Unmatched supplier item with supplier details
 */
export interface UnmatchedSupplierItem {
  id: string
  supplier_id: string
  supplier_name: string
  supplier_sku: string
  name: string
  current_price: string
  characteristics: Record<string, unknown>
  last_ingested_at: string
}

/**
 * Supplier Item Repository Interface
 * 
 * Defines the contract for supplier item data access operations
 */
export interface ISupplierItemRepository {
  /**
   * Find a supplier item by ID
   * @param id - The supplier item UUID
   * @returns The supplier item if found, null otherwise
   */
  findById(id: string): Promise<SupplierItem | null>

  /**
   * Update the product_id for a supplier item
   * @param id - The supplier item UUID
   * @param productId - The product UUID to link (or null to unlink)
   * @param tx - Optional transaction context (same type as db)
   * @returns The updated supplier item
   */
  updateProductId(
    id: string,
    productId: string | null,
    tx?: typeof db
  ): Promise<SupplierItem>

  /**
   * Find all unmatched supplier items (where product_id IS NULL)
   * @param query - Query parameters for filtering and pagination
   * @returns Array of unmatched supplier items with supplier details
   */
  findUnmatched(query: UnmatchedQuery): Promise<UnmatchedSupplierItem[]>

  /**
   * Count all unmatched supplier items
   * @param query - Query parameters for filtering (excluding pagination)
   * @returns Total count of unmatched supplier items
   */
  countUnmatched(query: Omit<UnmatchedQuery, 'page' | 'limit'>): Promise<number>
}

/**
 * Supplier Item Repository Implementation
 * 
 * Implements supplier item data access using Drizzle ORM
 */
export class SupplierItemRepository implements ISupplierItemRepository {
  async findById(id: string): Promise<SupplierItem | null> {
    const result = await db
      .select()
      .from(supplierItems)
      .where(eq(supplierItems.id, id))
      .limit(1)

    return result[0] || null
  }

  async updateProductId(
    id: string,
    productId: string | null,
    tx: typeof db = db
  ): Promise<SupplierItem> {
    const result = await tx
      .update(supplierItems)
      .set({
        productId: productId,
        updatedAt: new Date().toISOString(),
      })
      .where(eq(supplierItems.id, id))
      .returning()

    if (!result[0]) {
      throw new Error(`Supplier item with id ${id} not found`)
    }

    return result[0]
  }

  async findUnmatched(query: UnmatchedQuery): Promise<UnmatchedSupplierItem[]> {
    const { supplier_id, search, page = 1, limit = 50 } = query
    const offset = (page - 1) * limit

    // Build conditions
    const conditions = [isNull(supplierItems.productId)]
    
    if (supplier_id) {
      conditions.push(eq(supplierItems.supplierId, supplier_id))
    }
    
    if (search) {
      const searchPattern = `%${search}%`
      conditions.push(
        or(
          ilike(supplierItems.supplierSku, searchPattern),
          ilike(supplierItems.name, searchPattern)
        )!
      )
    }

    const result = await db
      .select({
        id: supplierItems.id,
        supplier_id: supplierItems.supplierId,
        supplier_name: suppliers.name,
        supplier_sku: supplierItems.supplierSku,
        name: supplierItems.name,
        current_price: supplierItems.currentPrice,
        characteristics: supplierItems.characteristics,
        last_ingested_at: supplierItems.lastIngestedAt,
      })
      .from(supplierItems)
      .leftJoin(suppliers, eq(supplierItems.supplierId, suppliers.id))
      .where(and(...conditions))
      .orderBy(supplierItems.lastIngestedAt)
      .limit(limit)
      .offset(offset)

    return result.map((item) => ({
      id: item.id,
      supplier_id: item.supplier_id,
      supplier_name: item.supplier_name || '',
      supplier_sku: item.supplier_sku,
      name: item.name,
      current_price: parseFloat(item.current_price || '0').toFixed(2),
      characteristics: (item.characteristics as Record<string, unknown>) || {},
      last_ingested_at: item.last_ingested_at,
    }))
  }

  async countUnmatched(query: Omit<UnmatchedQuery, 'page' | 'limit'>): Promise<number> {
    const { supplier_id, search } = query

    // Build conditions
    const conditions = [isNull(supplierItems.productId)]
    
    if (supplier_id) {
      conditions.push(eq(supplierItems.supplierId, supplier_id))
    }
    
    if (search) {
      const searchPattern = `%${search}%`
      conditions.push(
        or(
          ilike(supplierItems.supplierSku, searchPattern),
          ilike(supplierItems.name, searchPattern)
        )!
      )
    }

    const result = await db
      .select({ count: count() })
      .from(supplierItems)
      .where(and(...conditions))

    return result[0]?.count || 0
  }
}

// Export singleton instance
export const supplierItemRepository = new SupplierItemRepository()

