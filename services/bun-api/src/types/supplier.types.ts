/**
 * Supplier Types
 *
 * TypeBox schemas and types for supplier management endpoints.
 * Enables creating suppliers directly without master sheet.
 */

import { Type, Static } from '@sinclair/typebox'

// =============================================================================
// Enums
// =============================================================================

/**
 * Supported source types for supplier data
 */
export const SourceTypeEnum = Type.Union([
  Type.Literal('google_sheets'),
  Type.Literal('csv'),
  Type.Literal('excel'),
])

// =============================================================================
// Request Schemas
// =============================================================================

/**
 * POST /api/v1/admin/suppliers request body
 * Extended in Phase 8 with use_ml_processing flag
 */
export const CreateSupplierRequestSchema = Type.Object({
  name: Type.String({
    minLength: 1,
    maxLength: 255,
    description: 'Supplier display name',
  }),
  source_type: SourceTypeEnum,
  source_url: Type.Optional(
    Type.String({
      format: 'uri',
      description: 'URL to supplier price list (Google Sheets, CSV, etc.)',
    })
  ),
  contact_email: Type.Optional(
    Type.String({
      format: 'email',
      description: 'Supplier contact email',
    })
  ),
  is_active: Type.Optional(
    Type.Boolean({
      default: true,
      description: 'Whether supplier is active for sync',
    })
  ),
  use_ml_processing: Type.Optional(
    Type.Boolean({
      default: true,
      description: 'Whether to use ML pipeline for processing (Phase 8)',
    })
  ),
  notes: Type.Optional(
    Type.String({
      maxLength: 1000,
      description: 'Additional notes about the supplier',
    })
  ),
})

/**
 * PUT /api/v1/admin/suppliers/:id request body
 */
export const UpdateSupplierRequestSchema = Type.Partial(CreateSupplierRequestSchema)

/**
 * POST /api/v1/admin/suppliers/:id/upload request
 * File is handled via multipart form-data
 */
export const UploadSupplierFileRequestSchema = Type.Object({
  file: Type.Any({
    description: 'Price list file (CSV, XLSX)',
  }),
  sheet_name: Type.Optional(
    Type.String({
      description: 'Sheet name for Excel files (defaults to first sheet)',
    })
  ),
  header_row: Type.Optional(
    Type.Number({
      minimum: 1,
      default: 1,
      description: 'Row number containing column headers',
    })
  ),
  data_start_row: Type.Optional(
    Type.Number({
      minimum: 1,
      default: 2,
      description: 'Row number where data starts',
    })
  ),
})

// =============================================================================
// Response Schemas
// =============================================================================

/**
 * Supplier entity response
 * Extended in Phase 8 with use_ml_processing flag
 */
export const SupplierResponseSchema = Type.Object({
  id: Type.String({ format: 'uuid' }),
  name: Type.String(),
  source_type: SourceTypeEnum,
  source_url: Type.Union([Type.String(), Type.Null()]),
  contact_email: Type.Union([Type.String(), Type.Null()]),
  is_active: Type.Boolean(),
  use_ml_processing: Type.Boolean({ description: 'Whether ML processing is enabled' }),
  notes: Type.Union([Type.String(), Type.Null()]),
  items_count: Type.Number({ minimum: 0 }),
  created_at: Type.String(),
  updated_at: Type.String(),
})

/**
 * POST /api/v1/admin/suppliers success response (201)
 */
export const CreateSupplierResponseSchema = Type.Object({
  supplier: SupplierResponseSchema,
  message: Type.String(),
})

/**
 * DELETE /api/v1/admin/suppliers/:id success response
 */
export const DeleteSupplierResponseSchema = Type.Object({
  id: Type.String({ format: 'uuid' }),
  message: Type.String(),
})

/**
 * POST /api/v1/admin/suppliers/:id/upload success response
 */
export const UploadSupplierFileResponseSchema = Type.Object({
  task_id: Type.String({
    description: 'Background task ID for tracking parse progress',
  }),
  file_name: Type.String({
    description: 'Original uploaded file name',
  }),
  detected_format: SourceTypeEnum,
  status: Type.Literal('queued'),
  message: Type.String(),
})

/**
 * GET /api/v1/admin/suppliers response
 */
export const SuppliersListResponseSchema = Type.Object({
  suppliers: Type.Array(SupplierResponseSchema),
  total: Type.Number({ minimum: 0 }),
})

// =============================================================================
// Type Exports
// =============================================================================

export type SourceType = Static<typeof SourceTypeEnum>
export type CreateSupplierRequest = Static<typeof CreateSupplierRequestSchema>
export type UpdateSupplierRequest = Static<typeof UpdateSupplierRequestSchema>
export type SupplierResponse = Static<typeof SupplierResponseSchema>
export type CreateSupplierResponse = Static<typeof CreateSupplierResponseSchema>
export type DeleteSupplierResponse = Static<typeof DeleteSupplierResponseSchema>
export type UploadSupplierFileResponse = Static<typeof UploadSupplierFileResponseSchema>
export type SuppliersListResponse = Static<typeof SuppliersListResponseSchema>

