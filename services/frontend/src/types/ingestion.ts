/**
 * Ingestion Types
 *
 * TypeScript types for the Admin Control Panel & Master Sync Scheduler feature.
 *
 * @see /specs/006-admin-sync-scheduler/plan/data-model.md
 * @see /specs/008-ml-ingestion-integration/plan/data-model.md
 */

// =============================================================================
// Enums / Union Types
// =============================================================================

/**
 * Sync pipeline states
 * - idle: No sync operation running
 * - syncing_master: Reading and parsing the Master Google Sheet
 * - processing_suppliers: Enqueuing parse tasks for active suppliers
 */
export type SyncState = 'idle' | 'syncing_master' | 'processing_suppliers'

/**
 * Individual supplier sync status
 * Derived from most recent parsing_log entry
 */
export type SupplierSyncStatus = 'success' | 'error' | 'pending' | 'inactive'

/**
 * Job processing phases for multi-phase status display (Phase 8)
 * - downloading: File is being fetched from source
 * - analyzing: ML service is parsing the file
 * - matching: ML service is matching items to products
 * - complete: Processing finished successfully
 * - failed: Processing failed (may be retryable)
 */
export type JobPhase = 'downloading' | 'analyzing' | 'matching' | 'complete' | 'failed'

/**
 * Job status from ML service
 */
export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed'

/**
 * Supported file types for ML processing
 */
export type FileType = 'excel' | 'csv' | 'pdf'

// =============================================================================
// Data Types
// =============================================================================

/**
 * Sync progress during processing_suppliers state
 */
export interface SyncProgress {
  current: number
  total: number
}

// =============================================================================
// ML Job Progress Types (Phase 8)
// =============================================================================

/**
 * Download progress for downloading phase
 */
export interface DownloadProgress {
  bytes_downloaded: number
  bytes_total: number | null
  percentage: number
}

/**
 * Analysis progress for analyzing/matching phases
 */
export interface AnalysisProgress {
  items_processed: number
  items_total: number
  matches_found: number
  review_queue: number
  errors: number
  percentage: number
}

/**
 * Ingestion job with multi-phase status tracking
 */
export interface IngestionJob {
  job_id: string
  supplier_id: string
  supplier_name: string
  phase: JobPhase
  status: JobStatus
  download_progress: DownloadProgress | null
  analysis_progress: AnalysisProgress | null
  file_type: FileType
  error: string | null
  error_details: string[]
  can_retry: boolean
  retry_count: number
  max_retries: number
  created_at: string
  started_at: string | null
  completed_at: string | null
}

/**
 * Supplier status in the ingestion status response
 * Extended in Phase 8 with use_ml_processing flag
 */
export interface SupplierStatus {
  id: string
  name: string
  source_type: string
  last_sync_at: string | null
  status: SupplierSyncStatus
  items_count: number
  use_ml_processing: boolean
}

/**
 * Parsing log entry for the live log viewer
 */
export interface ParsingLogEntry {
  id: string
  task_id: string
  supplier_id: string | null
  supplier_name: string | null
  error_type: string
  error_message: string
  row_number: number | null
  created_at: string
}

/**
 * Full ingestion status response from API
 * Extended in Phase 8 with jobs array and current_phase
 */
export interface IngestionStatus {
  sync_state: SyncState
  current_phase: JobPhase | null
  progress: SyncProgress | null
  last_sync_at: string | null
  next_scheduled_at: string
  jobs: IngestionJob[]
  suppliers: SupplierStatus[]
  recent_logs: ParsingLogEntry[]
}

/**
 * Trigger sync response from API
 */
export interface TriggerSyncResponse {
  task_id: string
  status: 'queued'
  message: string
}

/**
 * Sync already running error response
 */
export interface SyncInProgressError {
  error: {
    code: 'SYNC_IN_PROGRESS'
    message: string
    current_task_id: string
  }
}

// =============================================================================
// Component Props
// =============================================================================

/**
 * Props for SyncControlCard component
 * Extended in Phase 8 with jobs array and retry functionality
 */
export interface SyncControlCardProps {
  syncState: SyncState
  progress: SyncProgress | null
  lastSyncAt: string | null
  nextScheduledAt: string
  jobs: IngestionJob[]
  onSyncNow: () => void
  onRetryJob?: (jobId: string) => void
  isSyncing: boolean
  isRetrying?: boolean
  isLoading?: boolean
  error?: string | null
}

/**
 * Props for LiveLogViewer component (Phase 5)
 */
export interface LiveLogViewerProps {
  logs: ParsingLogEntry[]
  isLoading: boolean
}

/**
 * Props for SupplierStatusTable component (Phase 5)
 */
export interface SupplierStatusTableProps {
  suppliers: SupplierStatus[]
  isLoading: boolean
  onDeleteSupplier?: (id: string, name: string) => void
  isDeletingSupplier?: boolean
}

