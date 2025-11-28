import { eq } from 'drizzle-orm'
import { db } from '../client'
import { categories } from '../schema/schema'
import type { Category } from '../schema/types'

/**
 * Category Repository Interface
 * 
 * Defines the contract for category data access operations
 */
export interface ICategoryRepository {
  /**
   * Find a category by ID
   * @param id - The category UUID
   * @returns The category if found, null otherwise
   */
  findById(id: string): Promise<Category | null>
}

/**
 * Category Repository Implementation
 * 
 * Implements category data access using Drizzle ORM
 */
export class CategoryRepository implements ICategoryRepository {
  async findById(id: string): Promise<Category | null> {
    const result = await db
      .select()
      .from(categories)
      .where(eq(categories.id, id))
      .limit(1)

    return result[0] || null
  }
}

// Export singleton instance
export const categoryRepository = new CategoryRepository()

