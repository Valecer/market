import { eq, and, like, gte, lte, sql, asc, count } from 'drizzle-orm'
import { db } from '../client'
import { products, supplierItems } from '../schema/schema'
import type { CatalogQuery, CatalogProduct } from '../../types/catalog.types'

/**
 * Product Repository Interface
 * 
 * Defines the contract for product data access operations
 */
export interface IProductRepository {
  /**
   * Find active products with filters, aggregations, and pagination
   * @param filters - Query filters (category, price range, search, pagination)
   * @returns Array of catalog products with aggregated data
   */
  findActive(filters: CatalogQuery): Promise<CatalogProduct[]>

  /**
   * Get total count of active products matching filters
   * @param filters - Query filters (category, price range, search)
   * @returns Total count of matching products
   */
  countActive(filters: Omit<CatalogQuery, 'page' | 'limit'>): Promise<number>
}

/**
 * Product Repository Implementation
 * 
 * Implements product data access using Drizzle ORM
 */
export class ProductRepository implements IProductRepository {
  async findActive(filters: CatalogQuery): Promise<CatalogProduct[]> {
    const { category_id, min_price, max_price, search, page = 1, limit = 50 } = filters
    const offset = (page - 1) * limit

    // Build WHERE conditions
    const conditions = [eq(products.status, 'active')]

    if (category_id) {
      conditions.push(eq(products.categoryId, category_id))
    }

    if (search) {
      conditions.push(like(products.name, `%${search}%`))
    }

    // Build HAVING conditions for price filters (after aggregation)
    const havingConditions: ReturnType<typeof sql>[] = []
    
    if (min_price !== undefined) {
      havingConditions.push(
        sql`COALESCE(MIN(${supplierItems.currentPrice})::numeric, 0) >= ${min_price}`
      )
    }
    
    if (max_price !== undefined) {
      havingConditions.push(
        sql`COALESCE(MAX(${supplierItems.currentPrice})::numeric, 0) <= ${max_price}`
      )
    }

    // Build query with aggregations
    let query = db
      .select({
        id: products.id,
        internal_sku: products.internalSku,
        name: products.name,
        category_id: products.categoryId,
        min_price: sql<string>`COALESCE(MIN(${supplierItems.currentPrice})::text, '0.00')`,
        max_price: sql<string>`COALESCE(MAX(${supplierItems.currentPrice})::text, '0.00')`,
        supplier_count: sql<number>`COUNT(DISTINCT ${supplierItems.supplierId})`,
      })
      .from(products)
      .leftJoin(supplierItems, eq(products.id, supplierItems.productId))
      .where(and(...conditions))
      .groupBy(products.id, products.internalSku, products.name, products.categoryId)

    // Apply HAVING clause if price filters exist
    if (havingConditions.length > 0) {
      // Combine SQL fragments - Drizzle's having accepts SQL fragments
      const havingClause = havingConditions.length === 1
        ? havingConditions[0]
        : sql`${havingConditions[0]} AND ${havingConditions[1]}`
      
      query = query.having(havingClause) as typeof query
    }

    // Apply sorting and pagination
    const result = await query
      .orderBy(asc(products.name))
      .limit(limit)
      .offset(offset)

    // Format prices to ensure 2 decimal places
    return result.map((row) => ({
      ...row,
      min_price: parseFloat(row.min_price || '0').toFixed(2),
      max_price: parseFloat(row.max_price || '0').toFixed(2),
    }))
  }

  async countActive(filters: Omit<CatalogQuery, 'page' | 'limit'>): Promise<number> {
    const { category_id, min_price, max_price, search } = filters

    // Build WHERE conditions
    const conditions = [eq(products.status, 'active')]

    if (category_id) {
      conditions.push(eq(products.categoryId, category_id))
    }

    if (search) {
      conditions.push(like(products.name, `%${search}%`))
    }

    // Build HAVING conditions for price filters
    const havingConditions: ReturnType<typeof sql>[] = []
    
    if (min_price !== undefined) {
      havingConditions.push(
        sql`COALESCE(MIN(${supplierItems.currentPrice})::numeric, 0) >= ${min_price}`
      )
    }
    
    if (max_price !== undefined) {
      havingConditions.push(
        sql`COALESCE(MAX(${supplierItems.currentPrice})::numeric, 0) <= ${max_price}`
      )
    }

    // If we have price filters, we need to use a subquery with HAVING
    // Otherwise, we can use a simpler count query
    if (havingConditions.length > 0) {
      // Count distinct products that match HAVING conditions
      let subqueryBuilder = db
        .select({
          productId: products.id,
        })
        .from(products)
        .leftJoin(supplierItems, eq(products.id, supplierItems.productId))
        .where(and(...conditions))
        .groupBy(products.id)
      
      // Apply HAVING clause
      if (havingConditions.length > 0) {
        const havingClause = havingConditions.length === 1
          ? havingConditions[0]
          : sql`${havingConditions[0]} AND ${havingConditions[1]}`
        
        subqueryBuilder = subqueryBuilder.having(havingClause) as typeof subqueryBuilder
      }
      
      const subquery = subqueryBuilder.as('filtered_products')

      const countResult = await db
        .select({
          count: sql<number>`COUNT(*)::int`,
        })
        .from(subquery)

      return Number(countResult[0]?.count) || 0
    } else {
      // Simple count without HAVING - no need for GROUP BY
      const countResult = await db
        .select({
          count: sql<number>`COUNT(DISTINCT ${products.id})::int`,
        })
        .from(products)
        .leftJoin(supplierItems, eq(products.id, supplierItems.productId))
        .where(and(...conditions))

      return Number(countResult[0]?.count) || 0
    }
  }
}

// Export singleton instance
export const productRepository = new ProductRepository()

