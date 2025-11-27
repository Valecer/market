import { db } from '../db/client'
import { productRepository, type IProductRepository } from '../db/repositories/product.repository'
import { supplierItemRepository, type ISupplierItemRepository } from '../db/repositories/supplier-item.repository'
import { eq } from 'drizzle-orm'
import { products } from '../db/schema/schema'
import type { AdminQuery, AdminProductsResponse, MatchRequest, MatchResponse, AdminProduct } from '../types/admin.types'
import { createErrorResponse } from '../types/errors'

/**
 * Admin Service
 * 
 * Handles business logic for admin operations
 */
export class AdminService {
  constructor(
    private readonly productRepo: IProductRepository = productRepository,
    private readonly supplierItemRepo: ISupplierItemRepository = supplierItemRepository
  ) {}

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

  /**
   * Match or unmatch a supplier item to a product
   * @param productId - The product UUID
   * @param request - Match request (action: link/unlink, supplier_item_id)
   * @returns Updated product with supplier items
   * @throws Error with appropriate message for error handler to catch
   */
  async matchProduct(productId: string, request: MatchRequest): Promise<MatchResponse> {
    const { action, supplier_item_id } = request

    // Execute in transaction to ensure atomicity
    return await db.transaction(async (tx) => {
      // Validate product exists and not archived
      const product = await tx
        .select()
        .from(products)
        .where(eq(products.id, productId))
        .limit(1)

      if (!product[0]) {
        const error = new Error(`Product with id ${productId} not found`)
        ;(error as any).code = 'NOT_FOUND'
        throw error
      }

      if (product[0].status === 'archived') {
        const error = new Error('Cannot link supplier items to archived products')
        ;(error as any).code = 'VALIDATION_ERROR'
        throw error
      }

      // Validate supplier item exists
      const supplierItem = await this.supplierItemRepo.findById(supplier_item_id)
      if (!supplierItem) {
        const error = new Error(`Supplier item with id ${supplier_item_id} not found`)
        ;(error as any).code = 'NOT_FOUND'
        throw error
      }

      if (action === 'link') {
        // Validate supplier item is not already linked
        if (supplierItem.productId !== null) {
          // Check if it's linked to a different product
          if (supplierItem.productId !== productId) {
            const error = new Error(
              `Supplier item is already linked to a different product (${supplierItem.productId})`
            )
            ;(error as any).code = 'CONFLICT'
            throw error
          }
          // Already linked to this product - return current state
        } else {
          // Link the supplier item to the product
          await this.supplierItemRepo.updateProductId(supplier_item_id, productId, tx)
        }
      } else if (action === 'unlink') {
        // Validate supplier item is linked to this product
        if (supplierItem.productId !== productId) {
          const error = new Error(`Supplier item is not linked to product ${productId}`)
          ;(error as any).code = 'VALIDATION_ERROR'
          throw error
        }

        // Unlink the supplier item (set product_id to NULL)
        await this.supplierItemRepo.updateProductId(supplier_item_id, null, tx)
      }

      // Fetch updated product with supplier items
      const updatedProduct = await this.productRepo.findByIdWithSuppliers(productId)
      if (!updatedProduct) {
        const error = new Error(`Product with id ${productId} not found after update`)
        ;(error as any).code = 'NOT_FOUND'
        throw error
      }

      return {
        product: updatedProduct,
      }
    })
  }
}

// Export singleton instance
export const adminService = new AdminService()

