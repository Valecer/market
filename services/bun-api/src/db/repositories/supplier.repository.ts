import { db } from '../client'
import { suppliers, supplierItems } from '../schema/schema'
import { eq, sql, count } from 'drizzle-orm'
import type { PostgresJsTransaction } from 'drizzle-orm/postgres-js'

/**
 * Supplier Repository
 * 
 * Handles database access for supplier entities
 */

/**
 * Supplier entity type
 */
export interface Supplier {
  id: string
  name: string
  sourceType: string
  contactEmail: string | null
  metadata: Record<string, any>
  createdAt: string
  updatedAt: string
}

/**
 * Supplier with item count for ingestion status
 */
export interface SupplierWithItemCount {
  id: string
  name: string
  sourceType: string | null
  metadata: Record<string, unknown> | null
  updatedAt: Date | null
  itemsCount: number
}

/**
 * Repository interface for supplier data access
 */
export interface ISupplierRepository {
  findById(id: string): Promise<Supplier | null>
  findAllWithItemCounts(): Promise<SupplierWithItemCount[]>
}

class SupplierRepository implements ISupplierRepository {
  /**
   * Find a supplier by ID
   * @param id - Supplier UUID
   * @returns Supplier entity or null if not found
   */
  async findById(id: string): Promise<Supplier | null> {
    const result = await db
      .select()
      .from(suppliers)
      .where(eq(suppliers.id, id))
      .limit(1)

    if (!result[0]) {
      return null
    }

    return {
      id: result[0].id,
      name: result[0].name,
      sourceType: result[0].sourceType,
      contactEmail: result[0].contactEmail,
      metadata: result[0].metadata as Record<string, any>,
      createdAt: result[0].createdAt,
      updatedAt: result[0].updatedAt,
    }
  }

  /**
   * Find all suppliers with their item counts
   * Used by ingestion service for status display
   * @returns Array of suppliers with item counts
   */
  async findAllWithItemCounts(): Promise<SupplierWithItemCount[]> {
    // Use a subquery to count items per supplier
    const result = await db
      .select({
        id: suppliers.id,
        name: suppliers.name,
        sourceType: suppliers.sourceType,
        metadata: suppliers.metadata,
        updatedAt: suppliers.updatedAt,
        itemsCount: sql<number>`(
          SELECT COUNT(*)::integer FROM supplier_items 
          WHERE supplier_items.supplier_id = ${suppliers.id}
        )`.as('items_count'),
      })
      .from(suppliers)
      .orderBy(suppliers.name)

    return result.map((row) => ({
      id: row.id,
      name: row.name,
      sourceType: row.sourceType,
      metadata: row.metadata as Record<string, unknown> | null,
      updatedAt: row.updatedAt ? new Date(row.updatedAt) : null,
      itemsCount: row.itemsCount || 0,
    }))
  }
}

// Export singleton instance
export const supplierRepository = new SupplierRepository()

