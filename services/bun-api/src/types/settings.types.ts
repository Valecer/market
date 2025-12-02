/**
 * Settings Types
 *
 * TypeBox schemas and types for admin settings management.
 * Used for master sheet URL configuration and other admin settings.
 */

import { Type, Static } from '@sinclair/typebox'

// =============================================================================
// Request Schemas
// =============================================================================

/**
 * PUT /api/v1/admin/settings/master-sheet-url request body
 */
export const UpdateMasterSheetUrlRequestSchema = Type.Object({
  url: Type.String({
    format: 'uri',
    description: 'Google Sheets URL for the master supplier configuration sheet',
    examples: ['https://docs.google.com/spreadsheets/d/1abc123/edit'],
  }),
  sheet_name: Type.Optional(
    Type.String({
      minLength: 1,
      maxLength: 100,
      description: 'Name of the worksheet tab to parse (default: "Suppliers")',
      examples: ['Suppliers', 'Sheet1'],
    })
  ),
})

// =============================================================================
// Response Schemas
// =============================================================================

/**
 * GET /api/v1/admin/settings/master-sheet-url response
 */
export const MasterSheetUrlResponseSchema = Type.Object({
  url: Type.Union([Type.String(), Type.Null()], {
    description: 'Current master sheet URL or null if not configured',
  }),
  sheet_name: Type.String({
    description: 'Name of the worksheet tab to parse',
    default: 'Suppliers',
  }),
  configured: Type.Boolean({
    description: 'Whether a master sheet URL is configured',
  }),
  last_updated_at: Type.Union([Type.String(), Type.Null()], {
    description: 'ISO timestamp of last URL update',
  }),
})

/**
 * PUT /api/v1/admin/settings/master-sheet-url success response
 */
export const UpdateMasterSheetUrlResponseSchema = Type.Object({
  url: Type.String({
    description: 'Updated master sheet URL',
  }),
  sheet_name: Type.String({
    description: 'Updated worksheet tab name',
  }),
  message: Type.String({
    description: 'Confirmation message',
  }),
})

// =============================================================================
// Type Exports
// =============================================================================

export type UpdateMasterSheetUrlRequest = Static<typeof UpdateMasterSheetUrlRequestSchema>
export type MasterSheetUrlResponse = Static<typeof MasterSheetUrlResponseSchema>
export type UpdateMasterSheetUrlResponse = Static<typeof UpdateMasterSheetUrlResponseSchema>

