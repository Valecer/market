import { eq, and, like, gte, lte, sql, asc, count, inArray } from 'drizzle-orm'
import { db } from '../client'
import { products, supplierItems, suppliers } from '../schema/schema'
import type { CatalogQuery, CatalogProduct } from '../../types/catalog.types'
import type { AdminQuery, AdminProduct, SupplierItemDetail } from '../../types/admin.types'

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

  /**
   * Find all products (all statuses) with supplier details for admin view
   * @param filters - Query filters (status, margin, supplier_id, pagination)
   * @returns Array of admin products with supplier item details
   */
  findAll(filters: AdminQuery): Promise<AdminProduct[]>

  /**
   * Get total count of products matching admin filters
   * @param filters - Query filters (status, margin, supplier_id)
   * @returns Total count of matching products
   */
  countAll(filters: Omit<AdminQuery, 'page' | 'limit'>): Promise<number>

  /**
   * Find a product by ID with all supplier items
   * @param id - The product UUID
   * @returns The product with supplier items if found, null otherwise
   */
  findByIdWithSuppliers(id: string): Promise<AdminProduct | null>
}

/**
 * Product Repository Implementation
 * 
 * Implements product data access using Drizzle ORM
 */
export class ProductRepository implements IProductRepository {
  async findActive(filters: CatalogQuery): Promise<CatalogProduct[]> {
    const { category_id, min_price, max_price, search, page = 1, limit = 50 } = filters
    const pageNum = Number(page)
    const limitNum = Number(limit)
    const offset = (pageNum - 1) * limitNum

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
      .limit(limitNum)
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

  async findAll(filters: AdminQuery): Promise<AdminProduct[]> {
    const { status, min_margin, max_margin, supplier_id, page = 1, limit = 50 } = filters
    const offset = (page - 1) * limit

    // Build WHERE conditions for products
    const productConditions = []
    if (status) {
      productConditions.push(eq(products.status, status))
    }

    // If supplier_id filter is specified, we need to get product IDs that have items from that supplier
    let filteredProductIds: string[] | undefined
    if (supplier_id) {
      const productsWithSupplier = await db
        .selectDistinct({ id: products.id })
        .from(products)
        .leftJoin(supplierItems, eq(products.id, supplierItems.productId))
        .where(
          and(
            productConditions.length > 0 ? and(...productConditions) : undefined,
            eq(supplierItems.supplierId, supplier_id)
          )
        )
      
      filteredProductIds = productsWithSupplier.map((p) => p.id)
      
      if (filteredProductIds.length === 0) {
        return []
      }
      
      // Add product ID filter
      productConditions.push(inArray(products.id, filteredProductIds))
    }

    // Get products matching filters
    const productQuery = db
      .select({
        id: products.id,
        internal_sku: products.internalSku,
        name: products.name,
        category_id: products.categoryId,
        status: products.status,
      })
      .from(products)
      .where(productConditions.length > 0 ? and(...productConditions) : undefined)
      .orderBy(asc(products.name))
      .limit(Number(limit))
      .offset(Number(offset))

    const productRows = await productQuery

    if (productRows.length === 0) {
      return []
    }

    const productIds = productRows.map((p) => p.id)

    // Now fetch supplier items for these products
    const supplierItemConditions = [inArray(supplierItems.productId, productIds)]
    
    if (supplier_id) {
      supplierItemConditions.push(eq(supplierItems.supplierId, supplier_id))
    }

    // Fetch supplier items with supplier details
    const supplierItemRows = await db
      .select({
        id: supplierItems.id,
        supplier_id: supplierItems.supplierId,
        supplier_name: suppliers.name,
        supplier_sku: supplierItems.supplierSku,
        current_price: supplierItems.currentPrice,
        characteristics: supplierItems.characteristics,
        last_ingested_at: supplierItems.lastIngestedAt,
        product_id: supplierItems.productId,
      })
      .from(supplierItems)
      .leftJoin(suppliers, eq(supplierItems.supplierId, suppliers.id))
      .where(and(...supplierItemConditions))

    // Group supplier items by product
    const supplierItemsByProduct = new Map<string, SupplierItemDetail[]>()
    for (const item of supplierItemRows) {
      if (!item.product_id) continue
      
      const productId = item.product_id
      if (!supplierItemsByProduct.has(productId)) {
        supplierItemsByProduct.set(productId, [])
      }

      const price = parseFloat(item.current_price || '0').toFixed(2)
      supplierItemsByProduct.get(productId)!.push({
        id: item.id,
        supplier_id: item.supplier_id,
        supplier_name: item.supplier_name || '',
        supplier_sku: item.supplier_sku,
        current_price: price,
        characteristics: (item.characteristics as Record<string, any>) || {},
        last_ingested_at: item.last_ingested_at,
      })
    }

    // Build result with margin calculation
    const result: AdminProduct[] = []
    for (const product of productRows) {
      const items = supplierItemsByProduct.get(product.id) || []
      
      // Calculate margin percentage
      // Formula: (target - min_price) / target * 100
      // Note: target_price field doesn't exist in products table yet
      // TODO: When target_price is added to products table, implement margin calculation:
      // const targetPrice = product.target_price
      // if (targetPrice && items.length > 0) {
      //   const minPrice = Math.min(...items.map(i => parseFloat(i.current_price)))
      //   margin_percentage = targetPrice > 0 ? ((targetPrice - minPrice) / targetPrice) * 100 : null
      // }
      let margin_percentage: number | null = null

      // Apply margin filters if specified
      // Note: Margin filtering is currently disabled because target_price doesn't exist
      // When target_price is added, uncomment the following:
      // if (min_margin !== undefined && margin_percentage !== null && margin_percentage < min_margin) {
      //   continue
      // }
      // if (max_margin !== undefined && margin_percentage !== null && margin_percentage > max_margin) {
      //   continue
      // }

      // Filter by supplier_id if specified (already done in query, but double-check items)
      if (supplier_id && items.length === 0) {
        continue
      }

      result.push({
        id: product.id,
        internal_sku: product.internal_sku,
        name: product.name,
        category_id: product.category_id,
        status: product.status as 'draft' | 'active' | 'archived',
        supplier_items: items,
        margin_percentage,
      })
    }

    return result
  }

  async countAll(filters: Omit<AdminQuery, 'page' | 'limit'>): Promise<number> {
    const { status, min_margin, max_margin, supplier_id } = filters

    // Build WHERE conditions for products
    const productConditions = []
    if (status) {
      productConditions.push(eq(products.status, status))
    }

    // If we have margin or supplier filters, we need to join with supplier_items
    if (min_margin !== undefined || max_margin !== undefined || supplier_id) {
      // Build conditions for supplier items
      const supplierItemConditions = []
      if (supplier_id) {
        supplierItemConditions.push(eq(supplierItems.supplierId, supplier_id))
      }

      // Count distinct products that have matching supplier items
      // Note: Margin filtering would require target_price field which doesn't exist yet
      const countResult = await db
        .select({
          count: sql<number>`COUNT(DISTINCT ${products.id})::int`,
        })
        .from(products)
        .leftJoin(supplierItems, eq(products.id, supplierItems.productId))
        .where(
          and(
            productConditions.length > 0 ? and(...productConditions) : undefined,
            supplierItemConditions.length > 0 ? and(...supplierItemConditions) : undefined,
          )
        )

      return Number(countResult[0]?.count) || 0
    } else {
      // Simple count without joins
      const countResult = await db
        .select({
          count: sql<number>`COUNT(*)::int`,
        })
        .from(products)
        .where(productConditions.length > 0 ? and(...productConditions) : undefined)

      return Number(countResult[0]?.count) || 0
    }
  }

  async findByIdWithSuppliers(id: string): Promise<AdminProduct | null> {
    // Fetch product
    const productResult = await db
      .select({
        id: products.id,
        internal_sku: products.internalSku,
        name: products.name,
        category_id: products.categoryId,
        status: products.status,
      })
      .from(products)
      .where(eq(products.id, id))
      .limit(1)

    if (!productResult[0]) {
      return null
    }

    const product = productResult[0]

    // Fetch supplier items for this product
    const supplierItemRows = await db
      .select({
        id: supplierItems.id,
        supplier_id: supplierItems.supplierId,
        supplier_name: suppliers.name,
        supplier_sku: supplierItems.supplierSku,
        current_price: supplierItems.currentPrice,
        characteristics: supplierItems.characteristics,
        last_ingested_at: supplierItems.lastIngestedAt,
      })
      .from(supplierItems)
      .leftJoin(suppliers, eq(supplierItems.supplierId, suppliers.id))
      .where(eq(supplierItems.productId, id))

    // Map supplier items to SupplierItemDetail format
    const supplier_items: SupplierItemDetail[] = supplierItemRows.map((item) => {
      const price = parseFloat(item.current_price || '0').toFixed(2)
      return {
        id: item.id,
        supplier_id: item.supplier_id,
        supplier_name: item.supplier_name || '',
        supplier_sku: item.supplier_sku,
        current_price: price,
        characteristics: (item.characteristics as Record<string, any>) || {},
        last_ingested_at: item.last_ingested_at,
      }
    })

    // Calculate margin percentage (currently null as target_price doesn't exist)
    let margin_percentage: number | null = null

    return {
      id: product.id,
      internal_sku: product.internal_sku,
      name: product.name,
      category_id: product.category_id,
      status: product.status as 'draft' | 'active' | 'archived',
      supplier_items,
      margin_percentage,
    }
  }
}

// Export singleton instance
export const productRepository = new ProductRepository()

