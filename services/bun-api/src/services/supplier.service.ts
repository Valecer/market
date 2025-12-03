/**
 * Supplier Service
 *
 * Business logic for supplier management.
 * Handles CRUD operations and file upload processing.
 */

import Redis from 'ioredis'
import { supplierRepository, type CreateSupplierInput, type UpdateSupplierInput } from '../db/repositories/supplier.repository'
import { productRepository } from '../db/repositories/product.repository'
import type {
  SupplierResponse,
  CreateSupplierResponse,
  DeleteSupplierResponse,
  UploadSupplierFileResponse,
  SuppliersListResponse,
  SourceType,
} from '../types/supplier.types'
import { mkdir, writeFile, unlink } from 'node:fs/promises'
import { join } from 'node:path'

// =============================================================================
// Constants
// =============================================================================

const PARSE_TRIGGERS_KEY = 'parse:triggers'
const UPLOADS_DIR = process.env.UPLOADS_DIR || '/shared/uploads'

/**
 * Map file extensions to source types
 */
const EXTENSION_TO_SOURCE_TYPE: Record<string, SourceType> = {
  '.csv': 'csv',
  '.xlsx': 'excel',
  '.xls': 'excel',
}

// =============================================================================
// Supplier Service
// =============================================================================

class SupplierService {
  private redis: Redis | null = null
  private redisUrl: string

  constructor(redisUrl?: string) {
    this.redisUrl = redisUrl || process.env.REDIS_URL || 'redis://localhost:6379'
  }

  /**
   * Get or create Redis connection (lazy initialization)
   */
  private async getRedis(): Promise<Redis> {
    if (this.redis && this.redis.status === 'ready') {
      return this.redis
    }

    this.redis = new Redis(this.redisUrl, {
      maxRetriesPerRequest: 1,
      retryStrategy: (times) => {
        if (times > 1) return null
        return 100
      },
      lazyConnect: true,
      connectTimeout: 5000,
    })

    try {
      await this.redis.connect()
      return this.redis
    } catch (error) {
      this.redis = null
      const err = new Error('Redis service is temporarily unavailable') as Error & { code: string }
      err.code = 'REDIS_UNAVAILABLE'
      throw err
    }
  }

  /**
   * Transform repository supplier to API response format
   */
  private transformToResponse(supplier: any, itemsCount: number = 0): SupplierResponse {
    const metadata = supplier.metadata || {}
    return {
      id: supplier.id,
      name: supplier.name,
      source_type: supplier.sourceType as SourceType,
      source_url: metadata.source_url || null,
      contact_email: supplier.contactEmail,
      is_active: metadata.is_active ?? true,
      use_ml_processing: metadata.use_ml_processing ?? true,
      notes: metadata.notes || null,
      items_count: itemsCount,
      created_at: supplier.createdAt,
      updated_at: supplier.updatedAt,
    }
  }

  /**
   * Get all suppliers with item counts
   */
  async getSuppliers(): Promise<SuppliersListResponse> {
    const suppliers = await supplierRepository.findAllWithItemCounts()
    
    return {
      suppliers: suppliers.map((s) => ({
        id: s.id,
        name: s.name,
        source_type: (s.sourceType || 'csv') as SourceType,
        source_url: (s.metadata as any)?.source_url || null,
        contact_email: null, // Not in WithItemCount type
        is_active: (s.metadata as any)?.is_active ?? true,
        use_ml_processing: (s.metadata as any)?.use_ml_processing ?? true,
        notes: (s.metadata as any)?.notes || null,
        items_count: s.itemsCount,
        created_at: s.updatedAt?.toISOString() || new Date().toISOString(),
        updated_at: s.updatedAt?.toISOString() || new Date().toISOString(),
      })),
      total: suppliers.length,
    }
  }

  /**
   * Get a single supplier by ID
   */
  async getSupplierById(id: string): Promise<SupplierResponse | null> {
    const supplier = await supplierRepository.findById(id)
    if (!supplier) {
      return null
    }

    // Get item count
    const allSuppliers = await supplierRepository.findAllWithItemCounts()
    const withCount = allSuppliers.find((s) => s.id === id)
    const itemsCount = withCount?.itemsCount || 0

    return this.transformToResponse(supplier, itemsCount)
  }

  /**
   * Create a new supplier
   * If source_url is provided and is_active is true, triggers a sync
   */
  async createSupplier(input: {
    name: string
    source_type: SourceType
    source_url?: string
    contact_email?: string
    is_active?: boolean
    use_ml_processing?: boolean
    notes?: string
  }): Promise<CreateSupplierResponse> {
    // Check for duplicate name
    const existing = await supplierRepository.findByName(input.name)
    if (existing) {
      const error = new Error(`Supplier with name "${input.name}" already exists`) as Error & { code: string }
      error.code = 'CONFLICT'
      throw error
    }

    const createInput: CreateSupplierInput = {
      name: input.name,
      sourceType: input.source_type,
      contactEmail: input.contact_email,
      sourceUrl: input.source_url,
      isActive: input.is_active ?? true,
      useMlProcessing: input.use_ml_processing ?? true,
      notes: input.notes,
    }

    const supplier = await supplierRepository.create(createInput)

    // If source_url is provided and active, trigger a sync to process this supplier
    let syncTriggered = false
    if (input.source_url && (input.is_active ?? true)) {
      try {
        const redis = await this.getRedis()
        const timestamp = Date.now()
        const taskId = `sync-supplier-${supplier.id.slice(0, 8)}-${timestamp}`
        
        // Set sync trigger for the worker to pick up
        await redis.set(
          'sync:trigger',
          JSON.stringify({
            task_id: taskId,
            triggered_by: 'supplier_created',
            triggered_at: new Date().toISOString(),
            supplier_id: supplier.id,
          }),
          'EX',
          300 // 5 minute expiry
        )
        syncTriggered = true
      } catch (error) {
        // Log error but don't fail supplier creation
        console.error('Failed to trigger sync after supplier creation:', error)
      }
    }

    return {
      supplier: this.transformToResponse(supplier, 0),
      message: syncTriggered
        ? `Supplier "${supplier.name}" created. Sync triggered automatically.`
        : `Supplier "${supplier.name}" created successfully`,
    }
  }

  /**
   * Update an existing supplier
   */
  async updateSupplier(
    id: string,
    input: {
      name?: string
      source_type?: SourceType
      source_url?: string
      contact_email?: string
      is_active?: boolean
      use_ml_processing?: boolean
      notes?: string
    }
  ): Promise<SupplierResponse | null> {
    // Check if supplier exists
    const existing = await supplierRepository.findById(id)
    if (!existing) {
      return null
    }

    // If name is being changed, check for duplicates
    if (input.name && input.name.toLowerCase() !== existing.name.toLowerCase()) {
      const duplicate = await supplierRepository.findByName(input.name)
      if (duplicate && duplicate.id !== id) {
        const error = new Error(`Supplier with name "${input.name}" already exists`) as Error & { code: string }
        error.code = 'CONFLICT'
        throw error
      }
    }

    const updateInput: UpdateSupplierInput = {
      name: input.name,
      sourceType: input.source_type,
      contactEmail: input.contact_email,
      sourceUrl: input.source_url,
      isActive: input.is_active,
      useMlProcessing: input.use_ml_processing,
      notes: input.notes,
    }

    const updated = await supplierRepository.update(id, updateInput)
    if (!updated) {
      return null
    }

    // Get item count
    const allSuppliers = await supplierRepository.findAllWithItemCounts()
    const withCount = allSuppliers.find((s) => s.id === id)
    const itemsCount = withCount?.itemsCount || 0

    return this.transformToResponse(updated, itemsCount)
  }

  /**
   * Delete a supplier and clean up orphaned products
   * 
   * When a supplier is deleted:
   * 1. All supplier_items are deleted (CASCADE)
   * 2. Products that no longer have any supplier_items are also deleted
   */
  async deleteSupplier(id: string): Promise<DeleteSupplierResponse | null> {
    const supplier = await supplierRepository.findById(id)
    if (!supplier) {
      return null
    }

    // Delete the supplier (cascades to supplier_items)
    const deleted = await supplierRepository.delete(id)
    if (!deleted) {
      return null
    }

    // Clean up orphaned products (products with no supplier_items)
    let orphanedCount = 0
    try {
      orphanedCount = await productRepository.deleteOrphaned()
    } catch (error) {
      console.error('Failed to clean up orphaned products:', error)
      // Don't fail the deletion, just log the error
    }

    const message = orphanedCount > 0
      ? `Supplier "${supplier.name}" deleted successfully. ${orphanedCount} orphaned product(s) also removed.`
      : `Supplier "${supplier.name}" deleted successfully`

    return {
      id,
      message,
    }
  }

  /**
   * Handle file upload for a supplier
   * Saves file to disk and enqueues parse task
   */
  async uploadFile(
    supplierId: string,
    file: File,
    options?: {
      sheetName?: string
      headerRow?: number
      dataStartRow?: number
    }
  ): Promise<UploadSupplierFileResponse> {
    // Verify supplier exists
    const supplier = await supplierRepository.findById(supplierId)
    if (!supplier) {
      const error = new Error(`Supplier not found`) as Error & { code: string }
      error.code = 'NOT_FOUND'
      throw error
    }

    // Detect format from file extension
    const fileName = file.name
    const ext = this.getFileExtension(fileName).toLowerCase()
    const detectedFormat = EXTENSION_TO_SOURCE_TYPE[ext]

    if (!detectedFormat) {
      const error = new Error(`Unsupported file format: ${ext}. Supported formats: .csv, .xlsx, .xls`) as Error & {
        code: string
      }
      error.code = 'VALIDATION_ERROR'
      throw error
    }

    // Create uploads directory if needed
    await mkdir(UPLOADS_DIR, { recursive: true })

    // Save file to disk
    const timestamp = Date.now()
    const safeFileName = fileName.replace(/[^a-zA-Z0-9.-]/g, '_')
    const savedFileName = `${supplierId}_${timestamp}_${safeFileName}`
    const filePath = join(UPLOADS_DIR, savedFileName)

    const arrayBuffer = await file.arrayBuffer()
    await writeFile(filePath, Buffer.from(arrayBuffer))

    // Generate task ID
    const taskId = `upload-${supplierId.slice(0, 8)}-${timestamp}`

    // Add parse trigger to Redis (Python worker polls this)
    const redis = await this.getRedis()
    
    const sourceConfig: Record<string, any> = {
      file_path: filePath,
      original_filename: fileName,
    }

    if (detectedFormat === 'excel') {
      sourceConfig.sheet_name = options?.sheetName || 'Sheet1'
    }
    sourceConfig.header_row = options?.headerRow || 1
    sourceConfig.data_start_row = options?.dataStartRow || 2

    // Use trigger mechanism - Python worker polls and enqueues using arq's native method
    const triggerData = {
      task_id: taskId,
      parser_type: detectedFormat,
      supplier_name: supplier.name,
      source_config: sourceConfig,
      created_at: new Date().toISOString(),
    }

    await redis.rpush(PARSE_TRIGGERS_KEY, JSON.stringify(triggerData))

    // Update supplier source_type if different
    if (supplier.sourceType !== detectedFormat) {
      await supplierRepository.update(supplierId, { sourceType: detectedFormat })
    }

    return {
      task_id: taskId,
      file_name: fileName,
      detected_format: detectedFormat,
      status: 'queued',
      message: `File "${fileName}" uploaded and queued for processing`,
    }
  }

  /**
   * Get file extension from filename
   */
  private getFileExtension(fileName: string): string {
    const lastDot = fileName.lastIndexOf('.')
    if (lastDot === -1) return ''
    return fileName.slice(lastDot)
  }

  /**
   * Close Redis connection gracefully
   */
  async close(): Promise<void> {
    if (this.redis) {
      await this.redis.quit()
      this.redis = null
    }
  }
}

// Export singleton instance
export const supplierService = new SupplierService()

