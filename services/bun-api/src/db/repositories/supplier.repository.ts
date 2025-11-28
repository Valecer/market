import { db } from '../client'
import { suppliers } from '../schema/schema'
import { eq } from 'drizzle-orm'
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
 * Repository interface for supplier data access
 */
export interface ISupplierRepository {
  findById(id: string): Promise<Supplier | null>
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
}

// Export singleton instance
export const supplierRepository = new SupplierRepository()

