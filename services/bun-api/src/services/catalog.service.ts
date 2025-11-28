import { productRepository, type IProductRepository } from '../db/repositories/product.repository'
import type { CatalogQuery, CatalogResponse } from '../types/catalog.types'

/**
 * Catalog Service
 * 
 * Handles business logic for catalog operations
 */
export class CatalogService {
  constructor(private readonly productRepo: IProductRepository = productRepository) {}

  /**
   * Get paginated catalog products with filters
   * @param query - Query parameters (filters, pagination)
   * @returns Paginated catalog response
   */
  async getProducts(query: CatalogQuery): Promise<CatalogResponse> {
    const { page = 1, limit = 50 } = query

    // Fetch products and total count in parallel
    const [data, total_count] = await Promise.all([
      this.productRepo.findActive(query),
      this.productRepo.countActive({
        category_id: query.category_id,
        min_price: query.min_price,
        max_price: query.max_price,
        search: query.search,
      }),
    ])

    return {
      total_count,
      page,
      limit,
      data,
    }
  }
}

// Export singleton instance
export const catalogService = new CatalogService()

