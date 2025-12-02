/**
 * Settings Types
 *
 * TypeScript types for admin settings management.
 */

// =============================================================================
// Response Types
// =============================================================================

/**
 * GET /api/v1/admin/settings/master-sheet-url response
 */
export interface MasterSheetUrlResponse {
  url: string | null
  sheet_name: string
  configured: boolean
  last_updated_at: string | null
}

/**
 * PUT /api/v1/admin/settings/master-sheet-url response
 */
export interface UpdateMasterSheetUrlResponse {
  url: string
  sheet_name: string
  message: string
}

// =============================================================================
// Request Types
// =============================================================================

/**
 * PUT /api/v1/admin/settings/master-sheet-url request
 */
export interface UpdateMasterSheetUrlRequest {
  url: string
  sheet_name?: string
}

