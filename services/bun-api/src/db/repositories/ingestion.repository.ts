/**
 * Ingestion Repository
 *
 * Data access layer for the Admin Control Panel & Master Sync Scheduler feature.
 * Handles supplier status derivation and parsing logs retrieval.
 *
 * @see /specs/006-admin-sync-scheduler/spec.md
 */

import { db } from '../client'
import { sql } from 'drizzle-orm'
import { parsingLogs, suppliers, supplierItems } from '../schema/schema'

// =============================================================================
// Types
// =============================================================================

/**
 * Supplier status derived from parsing logs
 */
export type DerivedSupplierStatus = 'success' | 'error' | 'pending' | 'inactive'

/**
 * Supplier with full status information
 */
export interface SupplierWithStatus {
  id: string
  name: string
  sourceType: string | null
  metadata: Record<string, unknown> | null
  lastSyncAt: string | null
  status: DerivedSupplierStatus
  itemsCount: number
}

/**
 * Parsing log entry with supplier name
 */
export interface ParsingLogWithSupplier {
  id: string
  taskId: string
  supplierId: string | null
  supplierName: string | null
  errorType: string
  errorMessage: string
  rowNumber: number | null
  createdAt: string
}

/**
 * Repository interface for ingestion data access
 */
export interface IIngestionRepository {
  getSuppliersWithStatus(): Promise<SupplierWithStatus[]>
  getRecentParsingLogs(limit: number): Promise<ParsingLogWithSupplier[]>
}

// =============================================================================
// Repository Implementation
// =============================================================================

class IngestionRepository implements IIngestionRepository {
  /**
   * Get all suppliers with their sync status and item counts
   *
   * Status is derived from parsing logs:
   * - error: Has ERROR-level logs in last parse session
   * - success: Has items and no recent errors
   * - pending: Never synced or currently syncing
   * - inactive: Marked inactive in metadata
   *
   * @returns Array of suppliers with derived status
   */
  async getSuppliersWithStatus(): Promise<SupplierWithStatus[]> {
    // Complex query joining suppliers, supplier_items count, and parsing_logs status
    const result = await db.execute(sql`
      WITH supplier_item_counts AS (
        SELECT 
          supplier_id,
          COUNT(*)::integer AS items_count
        FROM supplier_items
        GROUP BY supplier_id
      ),
      latest_parse_session AS (
        -- Get the most recent task_id for each supplier
        SELECT DISTINCT ON (supplier_id)
          supplier_id,
          task_id,
          created_at
        FROM parsing_logs
        WHERE supplier_id IS NOT NULL
        ORDER BY supplier_id, created_at DESC
      ),
      supplier_errors AS (
        -- Check if the latest parse session had errors
        SELECT 
          lps.supplier_id,
          CASE 
            WHEN EXISTS (
              SELECT 1 FROM parsing_logs pl
              WHERE pl.supplier_id = lps.supplier_id
                AND pl.task_id = lps.task_id
                AND pl.error_type IN ('ERROR', 'FATAL', 'PARSE_ERROR', 'VALIDATION_ERROR')
            ) THEN true
            ELSE false
          END AS has_errors,
          lps.created_at AS last_parse_at
        FROM latest_parse_session lps
      )
      SELECT 
        s.id,
        s.name,
        s.source_type,
        s.metadata,
        COALESCE(se.last_parse_at, s.updated_at) AS last_sync_at,
        COALESCE(sic.items_count, 0) AS items_count,
        CASE
          WHEN (s.metadata->>'is_active')::boolean = false THEN 'inactive'
          WHEN se.has_errors = true THEN 'error'
          WHEN sic.items_count > 0 THEN 'success'
          ELSE 'pending'
        END AS status
      FROM suppliers s
      LEFT JOIN supplier_item_counts sic ON sic.supplier_id = s.id
      LEFT JOIN supplier_errors se ON se.supplier_id = s.id
      ORDER BY s.name
    `)

    return (result.rows as any[]).map((row) => ({
      id: row.id,
      name: row.name,
      sourceType: row.source_type,
      metadata: row.metadata as Record<string, unknown> | null,
      lastSyncAt: row.last_sync_at ? new Date(row.last_sync_at).toISOString() : null,
      status: row.status as DerivedSupplierStatus,
      itemsCount: Number(row.items_count) || 0,
    }))
  }

  /**
   * Get recent parsing logs with supplier names
   *
   * Joins parsing_logs with suppliers to include supplier name for context.
   * Returns logs ordered by created_at DESC (most recent first).
   *
   * @param limit Maximum number of logs to return (default 50)
   * @returns Array of parsing log entries with supplier names
   */
  async getRecentParsingLogs(limit: number = 50): Promise<ParsingLogWithSupplier[]> {
    const result = await db.execute(sql`
      SELECT 
        pl.id,
        pl.task_id,
        pl.supplier_id,
        s.name AS supplier_name,
        pl.error_type,
        pl.error_message,
        pl.row_number,
        pl.created_at
      FROM parsing_logs pl
      LEFT JOIN suppliers s ON s.id = pl.supplier_id
      ORDER BY pl.created_at DESC
      LIMIT ${limit}
    `)

    return (result.rows as any[]).map((row) => ({
      id: row.id,
      taskId: row.task_id,
      supplierId: row.supplier_id,
      supplierName: row.supplier_name,
      errorType: row.error_type,
      errorMessage: row.error_message,
      rowNumber: row.row_number,
      createdAt: new Date(row.created_at).toISOString(),
    }))
  }

  /**
   * Derive supplier status from parsing logs
   *
   * Helper method for cases where status needs to be computed for a single supplier.
   *
   * @param supplierId The supplier UUID
   * @param isActive Whether the supplier is active
   * @param itemsCount Number of supplier items
   * @returns Derived status
   */
  async deriveSupplierStatus(
    supplierId: string,
    isActive: boolean,
    itemsCount: number
  ): Promise<DerivedSupplierStatus> {
    if (!isActive) {
      return 'inactive'
    }

    // Check for errors in the latest parse session
    const result = await db.execute(sql`
      WITH latest_task AS (
        SELECT task_id
        FROM parsing_logs
        WHERE supplier_id = ${supplierId}
        ORDER BY created_at DESC
        LIMIT 1
      )
      SELECT EXISTS (
        SELECT 1 FROM parsing_logs pl, latest_task lt
        WHERE pl.supplier_id = ${supplierId}
          AND pl.task_id = lt.task_id
          AND pl.error_type IN ('ERROR', 'FATAL', 'PARSE_ERROR', 'VALIDATION_ERROR')
      ) AS has_errors
    `)

    const hasErrors = (result.rows as any[])[0]?.has_errors ?? false

    if (hasErrors) {
      return 'error'
    }

    if (itemsCount > 0) {
      return 'success'
    }

    return 'pending'
  }
}

// Export singleton instance
export const ingestionRepository = new IngestionRepository()

