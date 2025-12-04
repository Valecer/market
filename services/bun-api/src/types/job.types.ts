/**
 * Job Types for Semantic ETL Pipeline
 *
 * Extended job phases and status tracking for Phase 9.
 * Adds semantic ETL phases: extracting, normalizing, completed_with_errors
 *
 * @see /specs/009-semantic-etl/data-model.md
 */

import { Type, type Static } from '@sinclair/typebox'

// =============================================================================
// Job Phase Enum (Extended for Semantic ETL)
// =============================================================================

/**
 * Job processing phases for multi-phase status display
 *
 * Phase 8 phases: downloading, analyzing, matching, complete, failed
 * Phase 9 additions: pending, extracting, normalizing, completed_with_errors
 */
export const SemanticJobPhaseEnum = Type.Union([
  Type.Literal('pending'),
  Type.Literal('downloading'),
  Type.Literal('analyzing'),
  Type.Literal('extracting'),
  Type.Literal('normalizing'),
  Type.Literal('complete'),
  Type.Literal('completed_with_errors'),
  Type.Literal('failed'),
])

export type SemanticJobPhase = Static<typeof SemanticJobPhaseEnum>

// =============================================================================
// Job Phase Metadata
// =============================================================================

/**
 * Metadata for displaying job phases in UI
 */
export interface JobPhaseMetadata {
  phase: SemanticJobPhase
  displayName: string
  color: 'blue' | 'yellow' | 'green' | 'red' | 'gray' | 'orange'
  icon: string
  description: string
}

/**
 * Configuration for all job phases
 */
export const JOB_PHASE_CONFIG: Record<SemanticJobPhase, JobPhaseMetadata> = {
  pending: {
    phase: 'pending',
    displayName: 'Pending',
    color: 'gray',
    icon: 'clock',
    description: 'Job is queued for processing',
  },
  downloading: {
    phase: 'downloading',
    displayName: 'Downloading',
    color: 'blue',
    icon: 'download',
    description: 'Downloading file from source',
  },
  analyzing: {
    phase: 'analyzing',
    displayName: 'Analyzing Structure',
    color: 'blue',
    icon: 'magnifying-glass',
    description: 'Identifying sheets and data structure',
  },
  extracting: {
    phase: 'extracting',
    displayName: 'Extracting Products',
    color: 'blue',
    icon: 'archive',
    description: 'Extracting product data with LLM',
  },
  normalizing: {
    phase: 'normalizing',
    displayName: 'Matching Categories',
    color: 'blue',
    icon: 'component-1',
    description: 'Normalizing categories and deduplicating',
  },
  complete: {
    phase: 'complete',
    displayName: 'Complete',
    color: 'green',
    icon: 'check-circle',
    description: 'Job completed successfully',
  },
  completed_with_errors: {
    phase: 'completed_with_errors',
    displayName: 'Completed with Errors',
    color: 'orange',
    icon: 'exclamation-triangle',
    description: 'Job completed but some rows failed extraction',
  },
  failed: {
    phase: 'failed',
    displayName: 'Failed',
    color: 'red',
    icon: 'cross-circle',
    description: 'Job failed to complete',
  },
}

// =============================================================================
// Job Status Schemas (TypeBox)
// =============================================================================

/**
 * Extraction progress during extracting phase
 */
export const ExtractionProgressSchema = Type.Object({
  chunks_processed: Type.Number({
    minimum: 0,
    description: 'Number of chunks processed',
  }),
  chunks_total: Type.Number({
    minimum: 0,
    description: 'Total chunks to process',
  }),
  rows_processed: Type.Number({
    minimum: 0,
    description: 'Number of rows processed',
  }),
  rows_total: Type.Number({
    minimum: 0,
    description: 'Total rows to process',
  }),
  products_extracted: Type.Number({
    minimum: 0,
    description: 'Products extracted so far',
  }),
  errors_count: Type.Number({
    minimum: 0,
    description: 'Extraction errors encountered',
  }),
  percentage: Type.Number({
    minimum: 0,
    maximum: 100,
    description: 'Extraction percentage',
  }),
})

export type ExtractionProgress = Static<typeof ExtractionProgressSchema>

/**
 * Category normalization progress during normalizing phase
 */
export const NormalizationProgressSchema = Type.Object({
  categories_processed: Type.Number({
    minimum: 0,
    description: 'Categories processed so far',
  }),
  categories_total: Type.Number({
    minimum: 0,
    description: 'Total categories to process',
  }),
  matched_count: Type.Number({
    minimum: 0,
    description: 'Categories matched to existing',
  }),
  created_count: Type.Number({
    minimum: 0,
    description: 'New categories created',
  }),
  review_queue_count: Type.Number({
    minimum: 0,
    description: 'Categories added to review queue',
  }),
  percentage: Type.Number({
    minimum: 0,
    maximum: 100,
    description: 'Normalization percentage',
  }),
})

export type NormalizationProgress = Static<typeof NormalizationProgressSchema>

/**
 * Semantic ETL job status response
 */
export const SemanticJobStatusSchema = Type.Object({
  job_id: Type.String({
    format: 'uuid',
    description: 'Job UUID',
  }),
  supplier_id: Type.String({
    format: 'uuid',
    description: 'Associated supplier UUID',
  }),
  supplier_name: Type.String({
    description: 'Supplier name for display',
  }),
  phase: SemanticJobPhaseEnum,
  progress_percent: Type.Number({
    minimum: 0,
    maximum: 100,
    description: 'Overall progress percentage',
  }),
  // Phase-specific progress
  extraction_progress: Type.Union([ExtractionProgressSchema, Type.Null()], {
    description: 'Extraction progress (null if not in extracting phase)',
  }),
  normalization_progress: Type.Union([NormalizationProgressSchema, Type.Null()], {
    description: 'Normalization progress (null if not in normalizing phase)',
  }),
  // Result metrics
  total_rows: Type.Union([Type.Number({ minimum: 0 }), Type.Null()], {
    description: 'Total rows in source file',
  }),
  successful_extractions: Type.Union([Type.Number({ minimum: 0 }), Type.Null()], {
    description: 'Successfully extracted products',
  }),
  failed_extractions: Type.Union([Type.Number({ minimum: 0 }), Type.Null()], {
    description: 'Rows that failed extraction',
  }),
  duplicates_removed: Type.Union([Type.Number({ minimum: 0 }), Type.Null()], {
    description: 'Duplicate products removed',
  }),
  categories_matched: Type.Union([Type.Number({ minimum: 0 }), Type.Null()], {
    description: 'Categories matched to existing',
  }),
  categories_created: Type.Union([Type.Number({ minimum: 0 }), Type.Null()], {
    description: 'New categories created',
  }),
  // Error handling
  error_message: Type.Union([Type.String(), Type.Null()], {
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
  // Timestamps
  created_at: Type.String({
    description: 'Job creation timestamp (ISO 8601)',
  }),
  started_at: Type.Union([Type.String(), Type.Null()], {
    description: 'Processing start timestamp (ISO 8601)',
  }),
  completed_at: Type.Union([Type.String(), Type.Null()], {
    description: 'Processing completion timestamp (ISO 8601)',
  }),
})

export type SemanticJobStatus = Static<typeof SemanticJobStatusSchema>

// =============================================================================
// Extraction Summary
// =============================================================================

/**
 * Summary of extraction results for API responses
 */
export const ExtractionSummarySchema = Type.Object({
  total_rows: Type.Number({
    minimum: 0,
    description: 'Total rows processed',
  }),
  successful_extractions: Type.Number({
    minimum: 0,
    description: 'Successfully extracted products',
  }),
  failed_extractions: Type.Number({
    minimum: 0,
    description: 'Rows that failed extraction',
  }),
  duplicates_removed: Type.Number({
    minimum: 0,
    description: 'Duplicate products removed',
  }),
  success_rate: Type.Number({
    minimum: 0,
    maximum: 100,
    description: 'Extraction success rate percentage',
  }),
  status: Type.Union([
    Type.Literal('success'),
    Type.Literal('completed_with_errors'),
    Type.Literal('failed'),
  ], {
    description: 'Final status based on success rate',
  }),
})

export type ExtractionSummary = Static<typeof ExtractionSummarySchema>

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Calculate overall progress percentage from phase and sub-progress
 */
export function calculateOverallProgress(
  phase: SemanticJobPhase,
  extractionProgress?: ExtractionProgress | null,
  normalizationProgress?: NormalizationProgress | null
): number {
  switch (phase) {
    case 'pending':
      return 0
    case 'downloading':
      return 5 // Fixed progress for downloading
    case 'analyzing':
      return 15 // Fixed progress for analyzing
    case 'extracting':
      if (extractionProgress) {
        // Extraction is 15-75% of overall progress
        return 15 + (extractionProgress.percentage * 0.6)
      }
      return 20
    case 'normalizing':
      if (normalizationProgress) {
        // Normalization is 75-95% of overall progress
        return 75 + (normalizationProgress.percentage * 0.2)
      }
      return 80
    case 'complete':
    case 'completed_with_errors':
      return 100
    case 'failed':
      return 0 // Reset on failure
    default:
      return 0
  }
}

/**
 * Determine final status based on extraction metrics
 */
export function determineJobStatus(
  successfulExtractions: number,
  totalRows: number
): 'success' | 'completed_with_errors' | 'failed' {
  if (totalRows === 0) return 'failed'
  
  const successRate = (successfulExtractions / totalRows) * 100
  
  if (successRate === 100) return 'success'
  if (successRate >= 80) return 'completed_with_errors'
  return 'failed'
}

