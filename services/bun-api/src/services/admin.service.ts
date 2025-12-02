import { db } from '../db/client'
import { productRepository, type IProductRepository } from '../db/repositories/product.repository'
import { supplierItemRepository, type ISupplierItemRepository } from '../db/repositories/supplier-item.repository'
import { categoryRepository, type ICategoryRepository } from '../db/repositories/category.repository'
import { supplierRepository, type ISupplierRepository } from '../db/repositories/supplier.repository'
import { queueService, RedisUnavailableError } from './queue.service'
import { eq } from 'drizzle-orm'
import { products } from '../db/schema/schema'
import type { AdminQuery, AdminProductsResponse, MatchRequest, MatchResponse, AdminProduct, CreateProductRequest, CreateProductResponse, SyncRequest, SyncResponse, UnmatchedQuery, UnmatchedResponse } from '../types/admin.types'
import type { ParseTaskMessage, ParserType } from '../types/queue.types'
import { createErrorResponse } from '../types/errors'
import { generateInternalSku } from '../utils/sku-generator'

/**
 * Admin Service
 * 
 * Handles business logic for admin operations
 */
export class AdminService {
  constructor(
    private readonly productRepo: IProductRepository = productRepository,
    private readonly supplierItemRepo: ISupplierItemRepository = supplierItemRepository,
    private readonly categoryRepo: ICategoryRepository = categoryRepository,
    private readonly supplierRepo: ISupplierRepository = supplierRepository
  ) {}

  /**
   * Get unmatched supplier items (not linked to any product)
   * @param query - Query parameters (supplier_id, search, pagination)
   * @returns Paginated unmatched supplier items response
   */
  async getUnmatchedItems(query: UnmatchedQuery): Promise<UnmatchedResponse> {
    const { page = 1, limit = 50 } = query

    // Fetch unmatched items and total count in parallel
    const [data, total_count] = await Promise.all([
      this.supplierItemRepo.findUnmatched(query),
      this.supplierItemRepo.countUnmatched({
        supplier_id: query.supplier_id,
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
    try {
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

      // Fetch all supplier items for this product within the transaction
      const { supplierItems, suppliers } = await import('../db/schema/schema')
      const supplierItemRows = await tx
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
        .where(eq(supplierItems.productId, productId))

      // Map supplier items to SupplierItemDetail format
      const supplier_items = supplierItemRows.map((item) => {
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
      const margin_percentage: number | null = null

      // Construct response from product and supplier items
      return {
        product: {
          id: product[0].id,
          internal_sku: product[0].internalSku,
          name: product[0].name,
          category_id: product[0].categoryId,
          status: product[0].status as 'draft' | 'active' | 'archived',
          supplier_items,
          margin_percentage,
        },
      }
      })
    } catch (error: any) {
      // Check if error already has our custom code property
      if ((error as any).code && typeof (error as any).code === 'string' && 
          ['VALIDATION_ERROR', 'NOT_FOUND', 'CONFLICT', 'INTERNAL_ERROR'].includes((error as any).code)) {
        throw error // Re-throw with preserved code
      }

      // Handle PostgreSQL error codes
      if (error?.code) {
        // Handle unique constraint violations
        if (error.code === '23505') {
          const validationError = new Error(error.detail || 'Database constraint violation')
          ;(validationError as any).code = 'VALIDATION_ERROR'
          throw validationError
        }
        // Handle foreign key violations
        if (error.code === '23503') {
          const validationError = new Error(error.detail || 'Invalid reference: product or supplier item not found')
          ;(validationError as any).code = 'VALIDATION_ERROR'
          throw validationError
        }
        // Handle other database errors
        if (error.code.startsWith('23') || error.code.startsWith('42')) {
          const validationError = new Error(error.message || 'Database constraint violation')
          ;(validationError as any).code = 'VALIDATION_ERROR'
          throw validationError
        }
      }

      // Handle connection errors
      if (error?.message && (
        error.message.includes('connection') ||
        error.message.includes('timeout') ||
        error.message.includes('ECONNREFUSED')
      )) {
        const dbError = new Error('Database connection error')
        ;(dbError as any).code = 'INTERNAL_ERROR'
        throw dbError
      }

      // If we get here, it's an unexpected error - wrap it
      const unexpectedError = new Error(error?.message || 'An unexpected error occurred')
      ;(unexpectedError as any).code = 'INTERNAL_ERROR'
      ;(unexpectedError as any).originalError = error
      throw unexpectedError
    }
  }

  /**
   * Create a new product with optional supplier item linkage
   * @param request - Create product request (name, optional SKU, category, status, supplier_item_id)
   * @returns Created product with supplier items
   * @throws Error with appropriate message for error handler to catch
   */
  async createProduct(request: CreateProductRequest): Promise<CreateProductResponse> {
    // Execute in transaction to ensure atomicity
    try {
      return await db.transaction(async (tx) => {
        // T127: Validate name required (1-500 chars) - already validated by TypeBox schema
        const { name, internal_sku, category_id, status, supplier_item_id } = request

        // T128: Validate internal_sku uniqueness if provided
        let finalSku = internal_sku
        if (finalSku) {
          const existingProduct = await this.productRepo.findBySku(finalSku)
          if (existingProduct) {
            const error = new Error(`Product with internal_sku '${finalSku}' already exists`)
            ;(error as any).code = 'VALIDATION_ERROR'
            throw error
          }
        } else {
          // T131: Auto-generate internal_sku if not provided
          finalSku = generateInternalSku()
          // Ensure generated SKU is unique (retry if collision - very unlikely)
          let attempts = 0
          while (await this.productRepo.findBySku(finalSku)) {
            if (attempts++ > 10) {
              const error = new Error('Failed to generate unique SKU after multiple attempts')
              ;(error as any).code = 'INTERNAL_ERROR'
              throw error
            }
            finalSku = generateInternalSku()
          }
        }

        // T129: Validate category_id exists if provided
        if (category_id) {
          const category = await this.categoryRepo.findById(category_id)
          if (!category) {
            const error = new Error(`Category with id ${category_id} not found`)
            ;(error as any).code = 'VALIDATION_ERROR'
            throw error
          }
        }

        // T130: Validate supplier_item_id exists and not linked if provided
        if (supplier_item_id) {
          const supplierItem = await this.supplierItemRepo.findById(supplier_item_id)
          if (!supplierItem) {
            const error = new Error(`Supplier item with id ${supplier_item_id} not found`)
            ;(error as any).code = 'VALIDATION_ERROR'
            throw error
          }
          if (supplierItem.productId !== null) {
            const error = new Error(`Supplier item is already linked to product ${supplierItem.productId}`)
            ;(error as any).code = 'VALIDATION_ERROR'
            throw error
          }
        }

        // T132: Create product with default status='draft' if not provided
        const productStatus = status || 'draft'

        // T123: Create product
        const newProduct = await this.productRepo.create(
          {
            internalSku: finalSku,
            name,
            categoryId: category_id || null,
            status: productStatus,
          },
          tx
        )

        // T133: Link supplier item in same transaction if supplier_item_id provided
        let linkedSupplierItem: any = null
        if (supplier_item_id) {
          await this.supplierItemRepo.updateProductId(supplier_item_id, newProduct.id, tx)
          // Fetch the linked supplier item to include in response
          linkedSupplierItem = await this.supplierItemRepo.findById(supplier_item_id)
        }

        // Construct response from the data we have (avoid querying outside transaction)
        const supplier_items = linkedSupplierItem
          ? [
              {
                id: linkedSupplierItem.id,
                supplier_id: linkedSupplierItem.supplierId,
                supplier_name: '', // Will be populated by findByIdWithSuppliers if needed, but for creation we can leave empty
                supplier_sku: linkedSupplierItem.supplierSku,
                current_price: parseFloat(linkedSupplierItem.currentPrice || '0').toFixed(2),
                characteristics: (linkedSupplierItem.characteristics as Record<string, any>) || {},
                last_ingested_at: linkedSupplierItem.lastIngestedAt,
              },
            ]
          : []

        // If we need supplier name, fetch it (but this is optional for creation response)
        if (linkedSupplierItem) {
          const { suppliers } = await import('../db/schema/schema')
          const { eq } = await import('drizzle-orm')
          const supplierResult = await tx
            .select({ name: suppliers.name })
            .from(suppliers)
            .where(eq(suppliers.id, linkedSupplierItem.supplierId))
            .limit(1)
          
          if (supplierResult[0] && supplier_items[0]) {
            supplier_items[0].supplier_name = supplierResult[0].name || ''
          }
        }

        // Map to CreateProductResponse format
        return {
          id: newProduct.id,
          internal_sku: newProduct.internalSku,
          name: newProduct.name,
          category_id: newProduct.categoryId,
          status: newProduct.status as 'draft' | 'active',
          supplier_items,
          created_at: new Date().toISOString(),
        }
      })
    } catch (error: any) {
      // Check if error already has our custom code property (from validation above)
      if ((error as any).code && typeof (error as any).code === 'string' && 
          ['VALIDATION_ERROR', 'NOT_FOUND', 'CONFLICT', 'INTERNAL_ERROR'].includes((error as any).code)) {
        throw error // Re-throw with preserved code
      }

      // Handle PostgreSQL error codes
      if (error?.code) {
        // Handle unique constraint violations
        if (error.code === '23505') { // PostgreSQL unique violation
          const validationError = new Error(error.detail || 'Product with this SKU already exists')
          ;(validationError as any).code = 'VALIDATION_ERROR'
          throw validationError
        }
        // Handle foreign key violations
        if (error.code === '23503') { // PostgreSQL foreign key violation
          const validationError = new Error(error.detail || 'Invalid reference: category or supplier item not found')
          ;(validationError as any).code = 'VALIDATION_ERROR'
          throw validationError
        }
        // Handle other database errors
        if (error.code.startsWith('23') || error.code.startsWith('42')) { // SQL state errors
          const validationError = new Error(error.message || 'Database constraint violation')
          ;(validationError as any).code = 'VALIDATION_ERROR'
          throw validationError
        }
      }

      // Handle connection errors
      if (error?.message && (
        error.message.includes('connection') ||
        error.message.includes('timeout') ||
        error.message.includes('ECONNREFUSED')
      )) {
        const dbError = new Error('Database connection error')
        ;(dbError as any).code = 'INTERNAL_ERROR'
        throw dbError
      }

      // If we get here, it's an unexpected error - wrap it
      const unexpectedError = new Error(error?.message || 'An unexpected error occurred')
      ;(unexpectedError as any).code = 'INTERNAL_ERROR'
      ;(unexpectedError as any).originalError = error
      throw unexpectedError
    }
  }

  /**
   * Trigger a data sync for a supplier
   * Enqueues a parse task to Redis for the Python worker to process
   * @param request - Sync request containing supplier_id
   * @returns Sync response with task_id and enqueue timestamp
   * @throws Error with appropriate code for error handler to catch
   */
  async triggerSync(request: SyncRequest): Promise<SyncResponse> {
    const { supplier_id } = request

    // T155: Validate supplier exists
    const supplier = await this.supplierRepo.findById(supplier_id)
    if (!supplier) {
      const error = new Error(`Supplier with id ${supplier_id} not found`)
      ;(error as any).code = 'NOT_FOUND'
      throw error
    }

    // T156: Construct task message with all required fields
    const taskId = crypto.randomUUID()
    const enqueuedAt = new Date().toISOString()

    // Validate parser_type is a valid value
    const validParserTypes = ['google_sheets', 'csv', 'excel'] as const
    const parserType = validParserTypes.includes(supplier.sourceType as ParserType)
      ? (supplier.sourceType as ParserType)
      : 'csv' // Default fallback

    const message: ParseTaskMessage = {
      task_id: taskId,
      parser_type: parserType,
      supplier_name: supplier.name,
      source_config: supplier.metadata || {},
      retry_count: 0,
      max_retries: 3,
      enqueued_at: enqueuedAt,
    }

    // T151-T153: Enqueue to Redis with error handling
    try {
      await queueService.enqueueParseTask(message)
    } catch (error) {
      if (error instanceof RedisUnavailableError) {
        const redisError = new Error('Queue service is temporarily unavailable')
        ;(redisError as any).code = 'REDIS_UNAVAILABLE'
        throw redisError
      }
      throw error
    }

    return {
      task_id: taskId,
      supplier_id,
      status: 'queued',
      enqueued_at: enqueuedAt,
    }
  }

  /**
   * Update product status
   * @param productId - Product UUID
   * @param status - New status (draft, active, archived)
   * @returns Updated product info
   */
  async updateProductStatus(
    productId: string,
    status: 'draft' | 'active' | 'archived'
  ): Promise<{
    id: string
    internal_sku: string
    name: string
    status: 'draft' | 'active' | 'archived'
    updated_at: string
    message: string
  }> {
    // Find product using findByIdWithSuppliers (existing method)
    const product = await this.productRepo.findByIdWithSuppliers(productId)
    if (!product) {
      const error = new Error(`Product with id ${productId} not found`)
      ;(error as any).code = 'NOT_FOUND'
      throw error
    }

    // Update status
    await this.productRepo.updateStatus(productId, status)

    return {
      id: productId,
      internal_sku: product.internal_sku,
      name: product.name,
      status,
      updated_at: new Date().toISOString(),
      message: `Product status updated to ${status}`,
    }
  }

  /**
   * Bulk update product statuses
   * @param productIds - Array of product UUIDs
   * @param status - New status for all products
   * @returns Count of updated products
   */
  async bulkUpdateProductStatus(
    productIds: string[],
    status: 'draft' | 'active' | 'archived'
  ): Promise<{
    updated_count: number
    status: 'draft' | 'active' | 'archived'
    message: string
  }> {
    const updatedCount = await this.productRepo.bulkUpdateStatus(productIds, status)

    return {
      updated_count: updatedCount,
      status,
      message: `${updatedCount} products updated to ${status} status`,
    }
  }
}

// Export singleton instance
export const adminService = new AdminService()

