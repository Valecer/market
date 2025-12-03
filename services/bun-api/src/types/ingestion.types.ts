/**
 * Ingestion Types
 *
 * TypeBox schemas and types for the Admin Control Panel & Master Sync Scheduler feature.
 * Used for API request/response validation and type inference.
 *
 * @see /specs/006-admin-sync-scheduler/plan/data-model.md
 * @see /specs/008-ml-ingestion-integration/plan/data-model.md
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

/**
 * Job processing phases for multi-phase status display (Phase 8)
 */
export const JobPhaseEnum = Type.Union([
  Type.Literal('downloading'),
  Type.Literal('analyzing'),
  Type.Literal('matching'),
  Type.Literal('complete'),
  Type.Literal('failed'),
])

/**
 * Job status from ML service
 */
export const JobStatusEnum = Type.Union([
  Type.Literal('pending'),
  Type.Literal('processing'),
  Type.Literal('completed'),
  Type.Literal('failed'),
])

/**
 * Supported file types for ML processing
 */
export const FileTypeEnum = Type.Union([
  Type.Literal('excel'),
  Type.Literal('csv'),
  Type.Literal('pdf'),
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
 * Extended in Phase 8 with use_ml_processing flag
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
  use_ml_processing: Type.Boolean({
    description: 'Whether ML processing is enabled for this supplier',
    default: true,
  }),
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

// =============================================================================
// ML Job Schemas (Phase 8)
// =============================================================================

/**
 * Download progress for downloading phase
 */
export const DownloadProgressSchema = Type.Object({
  bytes_downloaded: Type.Number({ minimum: 0, description: 'Bytes downloaded so far' }),
  bytes_total: Type.Union([Type.Number({ minimum: 0 }), Type.Null()], {
    description: 'Total bytes to download (null if unknown)',
  }),
  percentage: Type.Number({ minimum: 0, maximum: 100, description: 'Download percentage' }),
})

/**
 * Analysis progress for analyzing/matching phases
 */
export const AnalysisProgressSchema = Type.Object({
  items_processed: Type.Number({ minimum: 0, description: 'Items processed so far' }),
  items_total: Type.Number({ minimum: 0, description: 'Total items to process' }),
  matches_found: Type.Number({ minimum: 0, description: 'Successful product matches' }),
  review_queue: Type.Number({ minimum: 0, description: 'Items in review queue' }),
  errors: Type.Number({ minimum: 0, description: 'Processing errors' }),
  percentage: Type.Number({ minimum: 0, maximum: 100, description: 'Analysis percentage' }),
})

/**
 * Ingestion job with multi-phase status tracking
 */
export const IngestionJobSchema = Type.Object({
  job_id: Type.String({ format: 'uuid', description: 'Job UUID' }),
  supplier_id: Type.String({ format: 'uuid', description: 'Associated supplier UUID' }),
  supplier_name: Type.String({ description: 'Supplier name for display' }),
  phase: JobPhaseEnum,
  status: JobStatusEnum,
  download_progress: Type.Union([DownloadProgressSchema, Type.Null()], {
    description: 'Download progress (null if not in download phase)',
  }),
  analysis_progress: Type.Union([AnalysisProgressSchema, Type.Null()], {
    description: 'Analysis progress (null if not in analysis phase)',
  }),
  file_type: FileTypeEnum,
  error: Type.Union([Type.String(), Type.Null()], {
    description: 'Primary error message if failed',
  }),
  error_details: Type.Array(Type.String(), {
    description: 'Detailed error messages',
  }),
  can_retry: Type.Boolean({
    description: 'Whether the job can be retried',
  }),
  retry_count: Type.Number({
    minimum: 0,
    description: 'Number of retry attempts',
  }),
  max_retries: Type.Number({
    minimum: 0,
    description: 'Maximum retry attempts allowed',
  }),
  created_at: Type.String({ description: 'Job creation timestamp (ISO 8601)' }),
  started_at: Type.Union([Type.String(), Type.Null()], {
    description: 'Processing start timestamp (ISO 8601)',
  }),
  completed_at: Type.Union([Type.String(), Type.Null()], {
    description: 'Processing completion timestamp (ISO 8601)',
  }),
})

/**
 * POST /api/v1/admin/jobs/:id/retry request
 */
export const RetryJobParamsSchema = Type.Object({
  id: Type.String({ format: 'uuid', description: 'Job UUID to retry' }),
})

/**
 * POST /api/v1/admin/jobs/:id/retry success response (202)
 */
export const RetryJobResponseSchema = Type.Object({
  job_id: Type.String({ format: 'uuid', description: 'Job UUID' }),
  status: Type.Literal('retrying', { description: 'Job is being retried' }),
  message: Type.String({ description: 'Human-readable confirmation' }),
  retry_count: Type.Number({ description: 'Current retry count' }),
})

/**
 * GET /api/v1/admin/ingestion/status success response (200)
 * Extended in Phase 8 with jobs array and current_phase
 */
export const IngestionStatusResponseSchema = Type.Object({
  sync_state: SyncStateEnum,
  current_phase: Type.Union([JobPhaseEnum, Type.Null()], {
    description: 'Current phase of active job (null if idle)',
  }),
  progress: Type.Union([SyncProgressSchema, Type.Null()], {
    description: 'Progress when processing_suppliers, null otherwise',
  }),
  last_sync_at: Type.Union([Type.String(), Type.Null()], {
    description: 'Timestamp of last completed sync (ISO 8601)',
  }),
  next_scheduled_at: Type.String({
    description: 'Timestamp of next scheduled automatic sync (ISO 8601)',
  }),
  jobs: Type.Array(IngestionJobSchema, {
    description: 'Active and recent ingestion jobs',
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
export type JobPhase = Static<typeof JobPhaseEnum>
export type JobStatus = Static<typeof JobStatusEnum>
export type FileType = Static<typeof FileTypeEnum>
export type SyncProgress = Static<typeof SyncProgressSchema>
export type SupplierStatus = Static<typeof SupplierStatusSchema>
export type ParsingLogEntry = Static<typeof ParsingLogEntrySchema>
export type TriggerSyncResponse = Static<typeof TriggerSyncResponseSchema>
export type DownloadProgress = Static<typeof DownloadProgressSchema>
export type AnalysisProgress = Static<typeof AnalysisProgressSchema>
export type IngestionJob = Static<typeof IngestionJobSchema>
export type RetryJobParams = Static<typeof RetryJobParamsSchema>
export type RetryJobResponse = Static<typeof RetryJobResponseSchema>
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

