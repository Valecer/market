import { eq, isNull } from 'drizzle-orm'
import { db } from '../client'
import { supplierItems } from '../schema/schema'
import type { SupplierItem } from '../schema/types'

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
}

// Export singleton instance
export const supplierItemRepository = new SupplierItemRepository()

