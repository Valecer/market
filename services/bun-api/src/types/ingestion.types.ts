/**
 * Ingestion Types
 *
 * TypeBox schemas and types for the Admin Control Panel & Master Sync Scheduler feature.
 * Used for API request/response validation and type inference.
 *
 * @see /specs/006-admin-sync-scheduler/plan/data-model.md
 */

import { Type, Static } from '@sinclair/typebox'

// =============================================================================
// Enums
// =============================================================================

/**
 * Sync pipeline states
 * - idle: No sync operation running
 * - syncing_master: Reading and parsing the Master Google Sheet
 * - processing_suppliers: Enqueuing parse tasks for active suppliers
 */
export const SyncStateEnum = Type.Union([
  Type.Literal('idle'),
  Type.Literal('syncing_master'),
  Type.Literal('processing_suppliers'),
])

/**
 * Individual supplier sync status
 * Derived from most recent parsing_log entry
 */
export const SupplierSyncStatusEnum = Type.Union([
  Type.Literal('success'),
  Type.Literal('error'),
  Type.Literal('pending'),
  Type.Literal('inactive'),
])

// =============================================================================
// Request Schemas
// =============================================================================

/**
 * POST /api/v1/admin/ingestion/sync request
 * No body required - triggers global sync
 */
export const TriggerSyncRequestSchema = Type.Object({})

/**
 * GET /api/v1/admin/ingestion/status query params
 */
export const IngestionStatusQuerySchema = Type.Object({
  log_limit: Type.Optional(
    Type.Number({
      minimum: 1,
      maximum: 100,
      default: 50,
      description: 'Maximum number of recent logs to return',
    })
  ),
})

// =============================================================================
// Response Schemas
// =============================================================================

/**
 * Sync progress during processing_suppliers state
 */
export const SyncProgressSchema = Type.Object({
  current: Type.Number({ description: 'Number of suppliers processed' }),
  total: Type.Number({ description: 'Total suppliers to process' }),
})

/**
 * Supplier status in the ingestion status response
 */
export const SupplierStatusSchema = Type.Object({
  id: Type.String({ format: 'uuid', description: 'Supplier UUID' }),
  name: Type.String({ description: 'Supplier display name' }),
  source_type: Type.String({ description: 'Data source format (google_sheets, csv, excel)' }),
  last_sync_at: Type.Union([Type.String(), Type.Null()], {
    description: 'Last successful sync timestamp (ISO 8601)',
  }),
  status: SupplierSyncStatusEnum,
  items_count: Type.Number({ minimum: 0, description: 'Number of supplier items in database' }),
})

/**
 * Parsing log entry for the live log viewer
 */
export const ParsingLogEntrySchema = Type.Object({
  id: Type.String({ format: 'uuid', description: 'Log entry UUID' }),
  task_id: Type.String({ description: 'Task that generated this log' }),
  supplier_id: Type.Union([Type.String({ format: 'uuid' }), Type.Null()], {
    description: 'Associated supplier ID',
  }),
  supplier_name: Type.Union([Type.String(), Type.Null()], {
    description: 'Supplier name (joined from suppliers table)',
  }),
  error_type: Type.String({
    description: 'Log level/category (INFO, WARNING, ERROR, ValidationError, ParserError)',
  }),
  error_message: Type.String({ description: 'Log message content' }),
  row_number: Type.Union([Type.Number({ minimum: 1 }), Type.Null()], {
    description: 'Source row number if applicable',
  }),
  created_at: Type.String({ description: 'Log entry timestamp (ISO 8601)' }),
})

/**
 * POST /api/v1/admin/ingestion/sync success response (202)
 */
export const TriggerSyncResponseSchema = Type.Object({
  task_id: Type.String({ description: 'Unique identifier for tracking the sync job' }),
  status: Type.Literal('queued', { description: "Always 'queued' on success" }),
  message: Type.String({ description: 'Human-readable confirmation' }),
})

/**
 * GET /api/v1/admin/ingestion/status success response (200)
 */
export const IngestionStatusResponseSchema = Type.Object({
  sync_state: SyncStateEnum,
  progress: Type.Union([SyncProgressSchema, Type.Null()], {
    description: 'Progress when processing_suppliers, null otherwise',
  }),
  last_sync_at: Type.Union([Type.String(), Type.Null()], {
    description: 'Timestamp of last completed sync (ISO 8601)',
  }),
  next_scheduled_at: Type.String({
    description: 'Timestamp of next scheduled automatic sync (ISO 8601)',
  }),
  suppliers: Type.Array(SupplierStatusSchema, {
    description: 'List of all suppliers with sync status',
  }),
  recent_logs: Type.Array(ParsingLogEntrySchema, {
    description: 'Recent parsing log entries',
  }),
})

/**
 * POST /api/v1/admin/ingestion/sync conflict response (409)
 * Returned when sync is already in progress
 */
export const SyncAlreadyRunningResponseSchema = Type.Object({
  error: Type.Object({
    code: Type.Literal('SYNC_IN_PROGRESS'),
    message: Type.String({ description: 'Human-readable error message' }),
    current_task_id: Type.String({ description: 'Task ID of the running sync' }),
  }),
})

// =============================================================================
// Type Exports
// =============================================================================

export type SyncState = Static<typeof SyncStateEnum>
export type SupplierSyncStatus = Static<typeof SupplierSyncStatusEnum>
export type SyncProgress = Static<typeof SyncProgressSchema>
export type SupplierStatus = Static<typeof SupplierStatusSchema>
export type ParsingLogEntry = Static<typeof ParsingLogEntrySchema>
export type TriggerSyncResponse = Static<typeof TriggerSyncResponseSchema>
export type IngestionStatusResponse = Static<typeof IngestionStatusResponseSchema>
export type IngestionStatusQuery = Static<typeof IngestionStatusQuerySchema>
export type SyncAlreadyRunningResponse = Static<typeof SyncAlreadyRunningResponseSchema>

// =============================================================================
// Queue Message Types
// =============================================================================

/**
 * Message format for trigger_master_sync_task
 * Published to Redis queue for Python worker consumption
 */
export interface TriggerMasterSyncMessage {
  task_id: string
  triggered_by: 'manual' | 'scheduled'
  triggered_at: string
  master_sheet_url?: string
}

