import { productRepository, type IProductRepository } from '../db/repositories/product.repository'
import type { AdminQuery, AdminProductsResponse } from '../types/admin.types'

/**
 * Admin Service
 * 
 * Handles business logic for admin operations
 */
export class AdminService {
  constructor(private readonly productRepo: IProductRepository = productRepository) {}

  /**
   * Get paginated admin products with filters
   * @param query - Query parameters (status, margin, supplier_id, pagination)
   * @returns Paginated admin products response
   */
  async getAdminProducts(query: AdminQuery): Promise<AdminProductsResponse> {
    const { page = 1, limit = 50 } = query

    // Fetch products and total count in parallel
    const [data, total_count] = await Promise.all([
      this.productRepo.findAll(query),
      this.productRepo.countAll({
        status: query.status,
        min_margin: query.min_margin,
        max_margin: query.max_margin,
        supplier_id: query.supplier_id,
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
export const adminService = new AdminService()

