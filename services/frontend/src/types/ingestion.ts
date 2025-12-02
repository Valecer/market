/**
 * Ingestion Types
 *
 * TypeScript types for the Admin Control Panel & Master Sync Scheduler feature.
 *
 * @see /specs/006-admin-sync-scheduler/plan/data-model.md
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

/**
 * Supplier status in the ingestion status response
 */
export interface SupplierStatus {
  id: string
  name: string
  source_type: string
  last_sync_at: string | null
  status: SupplierSyncStatus
  items_count: number
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
 */
export interface IngestionStatus {
  sync_state: SyncState
  progress: SyncProgress | null
  last_sync_at: string | null
  next_scheduled_at: string
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
 */
export interface SyncControlCardProps {
  syncState: SyncState
  progress: SyncProgress | null
  lastSyncAt: string | null
  nextScheduledAt: string
  onSyncNow: () => void
  isSyncing: boolean
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

