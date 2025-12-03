import { db } from '../client'
import { suppliers, supplierItems } from '../schema/schema'
import { eq, sql, count } from 'drizzle-orm'
import type { PostgresJsTransaction } from 'drizzle-orm/postgres-js'

/**
 * Supplier Repository
 * 
 * Handles database access for supplier entities.
 * Supports full CRUD operations for direct supplier management.
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
 * Supplier with item count for ingestion status
 */
export interface SupplierWithItemCount {
  id: string
  name: string
  sourceType: string | null
  metadata: Record<string, unknown> | null
  updatedAt: Date | null
  itemsCount: number
}

/**
 * Input for creating a new supplier
 */
export interface CreateSupplierInput {
  name: string
  sourceType: string
  contactEmail?: string | null
  sourceUrl?: string | null
  isActive?: boolean
  useMlProcessing?: boolean
  notes?: string | null
}

/**
 * Input for updating an existing supplier
 */
export interface UpdateSupplierInput {
  name?: string
  sourceType?: string
  contactEmail?: string | null
  sourceUrl?: string | null
  isActive?: boolean
  useMlProcessing?: boolean
  notes?: string | null
}

/**
 * Repository interface for supplier data access
 */
export interface ISupplierRepository {
  findById(id: string): Promise<Supplier | null>
  findByName(name: string): Promise<Supplier | null>
  findAllWithItemCounts(): Promise<SupplierWithItemCount[]>
  create(input: CreateSupplierInput): Promise<Supplier>
  update(id: string, input: UpdateSupplierInput): Promise<Supplier | null>
  delete(id: string): Promise<boolean>
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

  /**
   * Find a supplier by name (case-insensitive)
   * @param name - Supplier name
   * @returns Supplier entity or null if not found
   */
  async findByName(name: string): Promise<Supplier | null> {
    const result = await db
      .select()
      .from(suppliers)
      .where(sql`LOWER(${suppliers.name}) = LOWER(${name})`)
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

  /**
   * Find all suppliers with their item counts
   * Used by ingestion service for status display
   * @returns Array of suppliers with item counts
   */
  async findAllWithItemCounts(): Promise<SupplierWithItemCount[]> {
    // Use raw SQL for reliable item counting
    // (Drizzle ORM subqueries can have type inference issues)
    const result = await db.execute(sql`
      SELECT 
        s.id,
        s.name,
        s.source_type,
        s.metadata,
        s.updated_at,
        COALESCE((
          SELECT COUNT(*)::integer 
          FROM supplier_items si 
          WHERE si.supplier_id = s.id
        ), 0) as items_count
      FROM suppliers s
      ORDER BY s.name
    `)

    return (result.rows as any[]).map((row) => ({
      id: row.id,
      name: row.name,
      sourceType: row.source_type,
      metadata: row.metadata as Record<string, unknown> | null,
      updatedAt: row.updated_at ? new Date(row.updated_at) : null,
      itemsCount: Number(row.items_count) || 0,
    }))
  }

  /**
   * Create a new supplier
   * @param input - Supplier creation input
   * @returns Created supplier entity
   */
  async create(input: CreateSupplierInput): Promise<Supplier> {
    const metadata = {
      source_url: input.sourceUrl || null,
      is_active: input.isActive ?? true,
      use_ml_processing: input.useMlProcessing ?? true,
      notes: input.notes || null,
    }

    const result = await db
      .insert(suppliers)
      .values({
        name: input.name,
        sourceType: input.sourceType,
        contactEmail: input.contactEmail || null,
        metadata,
      })
      .returning()

    const created = result[0]
    return {
      id: created.id,
      name: created.name,
      sourceType: created.sourceType,
      contactEmail: created.contactEmail,
      metadata: created.metadata as Record<string, any>,
      createdAt: created.createdAt,
      updatedAt: created.updatedAt,
    }
  }

  /**
   * Update an existing supplier
   * @param id - Supplier UUID
   * @param input - Fields to update
   * @returns Updated supplier or null if not found
   */
  async update(id: string, input: UpdateSupplierInput): Promise<Supplier | null> {
    // First fetch existing supplier to merge metadata
    const existing = await this.findById(id)
    if (!existing) {
      return null
    }

    // Merge metadata updates
    const existingMeta = existing.metadata || {}
    const metadata = {
      ...existingMeta,
      ...(input.sourceUrl !== undefined && { source_url: input.sourceUrl }),
      ...(input.isActive !== undefined && { is_active: input.isActive }),
      ...(input.useMlProcessing !== undefined && { use_ml_processing: input.useMlProcessing }),
      ...(input.notes !== undefined && { notes: input.notes }),
    }

    // Build update values
    const updateValues: Record<string, any> = {
      metadata,
      updatedAt: new Date().toISOString(),
    }

    if (input.name !== undefined) {
      updateValues.name = input.name
    }
    if (input.sourceType !== undefined) {
      updateValues.sourceType = input.sourceType
    }
    if (input.contactEmail !== undefined) {
      updateValues.contactEmail = input.contactEmail
    }

    const result = await db
      .update(suppliers)
      .set(updateValues)
      .where(eq(suppliers.id, id))
      .returning()

    if (!result[0]) {
      return null
    }

    const updated = result[0]
    return {
      id: updated.id,
      name: updated.name,
      sourceType: updated.sourceType,
      contactEmail: updated.contactEmail,
      metadata: updated.metadata as Record<string, any>,
      createdAt: updated.createdAt,
      updatedAt: updated.updatedAt,
    }
  }

  /**
   * Delete a supplier by ID
   * Note: This will cascade delete supplier_items due to FK constraint
   * @param id - Supplier UUID
   * @returns true if deleted, false if not found
   */
  async delete(id: string): Promise<boolean> {
    const result = await db
      .delete(suppliers)
      .where(eq(suppliers.id, id))
      .returning({ id: suppliers.id })

    return result.length > 0
  }
}

// Export singleton instance
export const supplierRepository = new SupplierRepository()

