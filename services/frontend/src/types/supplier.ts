/**
 * Supplier Types
 *
 * TypeScript types for supplier management.
 */

// =============================================================================
// Enums
// =============================================================================

/**
 * Supported source types for supplier data
 */
export type SourceType = 'google_sheets' | 'csv' | 'excel'

// =============================================================================
// Entity Types
// =============================================================================

/**
 * Supplier entity
 */
export interface Supplier {
  id: string
  name: string
  source_type: SourceType
  source_url: string | null
  contact_email: string | null
  is_active: boolean
  notes: string | null
  items_count: number
  created_at: string
  updated_at: string
}

// =============================================================================
// Request Types
// =============================================================================

/**
 * POST /api/v1/admin/suppliers request
 */
export interface CreateSupplierRequest {
  name: string
  source_type: SourceType
  source_url?: string
  contact_email?: string
  is_active?: boolean
  notes?: string
}

/**
 * PUT /api/v1/admin/suppliers/:id request
 */
export interface UpdateSupplierRequest {
  name?: string
  source_type?: SourceType
  source_url?: string
  contact_email?: string
  is_active?: boolean
  notes?: string
}

/**
 * POST /api/v1/admin/suppliers/:id/upload request options
 */
export interface UploadSupplierFileOptions {
  sheet_name?: string
  header_row?: number
  data_start_row?: number
}

// =============================================================================
// Response Types
// =============================================================================

/**
 * POST /api/v1/admin/suppliers response
 */
export interface CreateSupplierResponse {
  supplier: Supplier
  message: string
}

/**
 * DELETE /api/v1/admin/suppliers/:id response
 */
export interface DeleteSupplierResponse {
  id: string
  message: string
}

/**
 * POST /api/v1/admin/suppliers/:id/upload response
 */
export interface UploadSupplierFileResponse {
  task_id: string
  file_name: string
  detected_format: SourceType
  status: 'queued'
  message: string
}

/**
 * GET /api/v1/admin/suppliers response
 */
export interface SuppliersListResponse {
  suppliers: Supplier[]
  total: number
}

