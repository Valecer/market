import { productRepository, type IProductRepository, ProductRepository } from '../db/repositories/product.repository'
import type { CatalogQuery, CatalogResponse, CatalogProductDetail } from '../types/catalog.types'

/**
 * Catalog Service
 * 
 * Handles business logic for catalog operations
 */
export class CatalogService {
  constructor(private readonly productRepo: ProductRepository = productRepository) {}

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

    const pageNum = Number(page)
    const limitNum = Number(limit)

    return {
      total_count,
      page: pageNum,
      limit: limitNum,
      data,
    }
  }

  /**
   * Get a single product by ID with variants
   * Phase 10: Product Variants
   * @param id - Product UUID
   * @returns Product detail with variants or null
   */
  async getProductById(id: string): Promise<CatalogProductDetail | null> {
    return this.productRepo.findByIdWithVariants(id)
  }
}

// Export singleton instance
export const catalogService = new CatalogService()

