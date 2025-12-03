import { Elysia, t } from 'elysia'
import { adminService } from '../../services/admin.service'
import { ingestionService } from '../../services/ingestion.service'
import { settingsService } from '../../services/settings.service'
import { supplierService } from '../../services/supplier.service'
import {
  AdminProductsResponseSchema,
  MatchRequestSchema,
  MatchResponseSchema,
  CreateProductRequestSchema,
  CreateProductResponseSchema,
  SyncRequestSchema,
  SyncResponseSchema,
  UnmatchedResponseSchema,
  UpdateProductStatusRequestSchema,
  UpdateProductStatusResponseSchema,
  BulkUpdateProductStatusRequestSchema,
  BulkUpdateProductStatusResponseSchema,
} from '../../types/admin.types'
import {
  TriggerSyncResponseSchema,
  IngestionStatusResponseSchema,
  SyncAlreadyRunningResponseSchema,
  RetryJobResponseSchema,
} from '../../types/ingestion.types'
import { jobService } from '../../services/job.service'
import {
  MasterSheetUrlResponseSchema,
  UpdateMasterSheetUrlRequestSchema,
  UpdateMasterSheetUrlResponseSchema,
} from '../../types/settings.types'
import {
  CreateSupplierRequestSchema,
  CreateSupplierResponseSchema,
  UpdateSupplierRequestSchema,
  SupplierResponseSchema,
  DeleteSupplierResponseSchema,
  SuppliersListResponseSchema,
  UploadSupplierFileResponseSchema,
} from '../../types/supplier.types'
import { createErrorResponse } from '../../types/errors'
import { authMiddleware } from '../../middleware/auth'
import { rateLimiter } from '../../middleware/rate-limiter'
import { isValidUUID, parseNum } from '../../utils/error-helpers'

/**
 * Admin Controller
 * 
 * Handles HTTP requests for admin operations.
 * Requires authentication and appropriate role permissions.
 * 
 * Uses functional plugin pattern to ensure JWT plugin from parent app is accessible
 * via authMiddleware. See CLAUDE.md for explanation of Elysia plugin scoping.
 */

// =============================================================================
// Reusable Response Schemas (DRY)
// =============================================================================

const ErrorSchemas = {
  validation: t.Object({
    error: t.Object({
      code: t.Literal('VALIDATION_ERROR'),
      message: t.String(),
      details: t.Optional(t.Object({})),
    }),
  }),
  unauthorized: t.Object({
    error: t.Object({
      code: t.Literal('UNAUTHORIZED'),
      message: t.String(),
    }),
  }),
  forbidden: t.Object({
    error: t.Object({
      code: t.Literal('FORBIDDEN'),
      message: t.String(),
    }),
  }),
  notFound: t.Object({
    error: t.Object({
      code: t.Literal('NOT_FOUND'),
      message: t.String(),
    }),
  }),
  conflict: t.Object({
    error: t.Object({
      code: t.Literal('CONFLICT'),
      message: t.String(),
    }),
  }),
  rateLimited: t.Object({
    error: t.Object({
      code: t.Literal('RATE_LIMIT_EXCEEDED'),
      message: t.String(),
      details: t.Optional(t.Object({})),
    }),
  }),
  internal: t.Object({
    error: t.Object({
      code: t.Literal('INTERNAL_ERROR'),
      message: t.String(),
    }),
  }),
  redisUnavailable: t.Object({
    error: t.Object({
      code: t.Literal('REDIS_UNAVAILABLE'),
      message: t.String(),
    }),
  }),
}

// =============================================================================
// Controller
// =============================================================================

export const adminController = (app: Elysia) =>
  app.group('/api/v1/admin', (groupApp) =>
    groupApp
      .use(authMiddleware)
      .guard({
        beforeHandle({ user, set }) {
          if (!user) {
            set.status = 401
            return { error: { code: 'UNAUTHORIZED' as const, message: 'Unauthorized' } }
          }
          if (!['sales', 'procurement', 'admin'].includes(user.role)) {
            set.status = 403
            return { error: { code: 'FORBIDDEN' as const, message: 'Forbidden: Insufficient permissions' } }
          }
        },
      })
      // GET /products
      .get(
        '/products',
        async ({ query, set }) => {
          const adminQuery = {
            status: ['draft', 'active', 'archived'].includes(query.status as string)
              ? (query.status as 'draft' | 'active' | 'archived')
              : undefined,
            min_margin: parseNum(query.min_margin),
            max_margin: parseNum(query.max_margin),
            supplier_id: typeof query.supplier_id === 'string' ? query.supplier_id : undefined,
            page: parseNum(query.page) || 1,
            limit: parseNum(query.limit) || 50,
          }

          // Validations
          if (adminQuery.supplier_id && !isValidUUID(adminQuery.supplier_id)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'supplier_id must be a valid UUID')
          }
          if (adminQuery.min_margin !== undefined && (adminQuery.min_margin < 0 || adminQuery.min_margin > 100)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'min_margin must be between 0 and 100')
          }
          if (adminQuery.max_margin !== undefined && (adminQuery.max_margin < 0 || adminQuery.max_margin > 100)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'max_margin must be between 0 and 100')
          }
          if (adminQuery.min_margin !== undefined && adminQuery.max_margin !== undefined && adminQuery.min_margin > adminQuery.max_margin) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'min_margin must be less than or equal to max_margin')
          }
          if (adminQuery.page < 1) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'page must be greater than or equal to 1')
          }
          if (adminQuery.limit < 1 || adminQuery.limit > 200) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'limit must be between 1 and 200')
          }

          return adminService.getAdminProducts(adminQuery)
        },
        {
          query: t.Object({
            status: t.Optional(t.Any()),
            min_margin: t.Optional(t.Any()),
            max_margin: t.Optional(t.Any()),
            supplier_id: t.Optional(t.Any()),
            page: t.Optional(t.Any()),
            limit: t.Optional(t.Any()),
          }),
          error({ code, error, set }) {
            if (code === 'VALIDATION') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', 'Invalid query parameters', { issue: error.message })
            }
          },
          response: { 200: AdminProductsResponseSchema, 400: ErrorSchemas.validation, 401: ErrorSchemas.unauthorized, 500: ErrorSchemas.internal },
          detail: {
            tags: ['admin'],
            summary: 'Get paginated admin products with supplier details',
            description:
              'Returns a paginated list of products with all statuses (draft, active, archived). Includes supplier item details, margin calculations, and supports filtering by status, margin range, and supplier.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // GET /suppliers/unmatched - procurement/admin only
      .get(
        '/suppliers/unmatched',
        async ({ query, set, user }) => {
          // Additional check for procurement role
          if (!user || !['procurement', 'admin'].includes(user.role)) {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Forbidden: Procurement or admin role required.')
          }

          const unmatchedQuery = {
            supplier_id: typeof query.supplier_id === 'string' ? query.supplier_id : undefined,
            search: typeof query.search === 'string' ? query.search : undefined,
            page: parseNum(query.page) || 1,
            limit: parseNum(query.limit) || 50,
          }

          // Validations
          if (unmatchedQuery.supplier_id && !isValidUUID(unmatchedQuery.supplier_id)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'supplier_id must be a valid UUID')
          }
          if (unmatchedQuery.page < 1) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'page must be greater than or equal to 1')
          }
          if (unmatchedQuery.limit < 1 || unmatchedQuery.limit > 200) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'limit must be between 1 and 200')
          }

          return adminService.getUnmatchedItems(unmatchedQuery)
        },
        {
          query: t.Object({
            supplier_id: t.Optional(t.Any()),
            search: t.Optional(t.Any()),
            page: t.Optional(t.Any()),
            limit: t.Optional(t.Any()),
          }),
          error({ code, error, set }) {
            if (code === 'VALIDATION') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', 'Invalid query parameters', { issue: error.message })
            }
          },
          response: { 200: UnmatchedResponseSchema, 400: ErrorSchemas.validation, 401: ErrorSchemas.unauthorized, 403: ErrorSchemas.forbidden, 500: ErrorSchemas.internal },
          detail: {
            tags: ['admin'],
            summary: 'Get unmatched supplier items',
            description:
              'Returns supplier items that are not linked to any product. Supports filtering by supplier and search query. Requires procurement or admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // =============================================================================
      // Product Status Update Endpoints
      // =============================================================================
      // POST /products/bulk-status - Bulk update product statuses
      // NOTE: Must be BEFORE /products/:id routes to avoid "bulk-status" being interpreted as :id
      // Using a more specific path to avoid route conflicts
      .post(
        '/products/bulk-status',
        async ({ body, set, user }) => {
          // Sales, procurement or admin role required
          if (!user || !['sales', 'procurement', 'admin'].includes(user.role)) {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Sales, procurement or admin role required')
          }
          // Validate all UUIDs
          for (const id of body.product_ids) {
            if (!isValidUUID(id)) {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', `Invalid product ID format: ${id}`)
            }
          }
          return adminService.bulkUpdateProductStatus(body.product_ids, body.status)
        },
        {
          body: BulkUpdateProductStatusRequestSchema,
          error({ code, error, set }) {
            if (code === 'VALIDATION') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', error.message || 'Invalid request body')
            }
            const customCode = (error as any)?.code as string | undefined
            const message = error instanceof Error ? error.message : String(error)
            set.status = 500
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: {
            200: BulkUpdateProductStatusResponseSchema,
            400: ErrorSchemas.validation,
            401: ErrorSchemas.unauthorized,
            403: ErrorSchemas.forbidden,
            500: ErrorSchemas.internal,
          },
          detail: {
            tags: ['admin', 'products'],
            summary: 'Bulk update product statuses',
            description: 'Update the status of multiple products at once. Useful for activating all draft products after review. Requires sales, procurement or admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // PATCH /products/:id/match - procurement/admin only
      .group('/products/:id', (productApp) =>
        productApp
          .guard({
            beforeHandle({ user, set }) {
              if (!user) {
                set.status = 401
                return { error: { code: 'UNAUTHORIZED' as const, message: 'Unauthorized' } }
              }
              if (!['procurement', 'admin'].includes(user.role)) {
                set.status = 403
                return { error: { code: 'FORBIDDEN' as const, message: 'Forbidden: Procurement or admin role required.' } }
              }
            },
          })
          .patch(
            '/match',
            async ({ params, body, set }) => {
              if (!isValidUUID(params.id)) {
                set.status = 400
                return createErrorResponse('VALIDATION_ERROR', 'Product ID must be a valid UUID')
              }
              if (!isValidUUID(body.supplier_item_id)) {
                set.status = 400
                return createErrorResponse('VALIDATION_ERROR', 'supplier_item_id must be a valid UUID')
              }
              return adminService.matchProduct(params.id, body)
            },
            {
              body: MatchRequestSchema,
              error({ code, error, set }) {
                if (code === 'VALIDATION') {
                  set.status = 400
                  return createErrorResponse('VALIDATION_ERROR', error.message || 'Invalid request body')
                }
                const customCode = (error as any)?.code as string | undefined
                const message = error instanceof Error ? error.message : String(error)
                if (customCode === 'NOT_FOUND') { set.status = 404; return createErrorResponse('NOT_FOUND', message) }
                if (customCode === 'CONFLICT') { set.status = 409; return createErrorResponse('CONFLICT', message) }
                if (customCode === 'VALIDATION_ERROR') { set.status = 400; return createErrorResponse('VALIDATION_ERROR', message) }
                set.status = 500
                return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
              },
              response: { 200: MatchResponseSchema, 400: ErrorSchemas.validation, 401: ErrorSchemas.unauthorized, 403: ErrorSchemas.forbidden, 404: ErrorSchemas.notFound, 409: ErrorSchemas.conflict, 500: ErrorSchemas.internal },
              detail: {
                tags: ['admin'],
                summary: 'Link or unlink supplier item to product',
                description:
                  'Manually link a supplier item to a product (creating a product-supplier relationship) or unlink it (removing the relationship). Requires procurement or admin role. Operations are atomic and use database transactions.',
                security: [{ bearerAuth: [] }],
              },
            }
          )
      )
      // POST /products - procurement/admin only
      .post(
        '/products',
        async ({ body, set }) => {
          if (body.supplier_item_id && !isValidUUID(body.supplier_item_id)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'supplier_item_id must be a valid UUID')
          }
          if (body.category_id && !isValidUUID(body.category_id)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'category_id must be a valid UUID')
          }
          set.status = 201
          return adminService.createProduct(body)
        },
        {
          body: CreateProductRequestSchema,
          beforeHandle({ user, set }) {
            if (!user) {
              set.status = 401
              return { error: { code: 'UNAUTHORIZED' as const, message: 'Unauthorized' } }
            }
            if (!['procurement', 'admin'].includes(user.role)) {
              set.status = 403
              return { error: { code: 'FORBIDDEN' as const, message: 'Forbidden: Procurement or admin role required.' } }
            }
          },
          error({ code, error, set }) {
            if (code === 'VALIDATION') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', error.message || 'Invalid request body')
            }
            const customCode = (error as any)?.code as string | undefined
            const message = error instanceof Error ? error.message : String(error)
            if (customCode === 'NOT_FOUND') { set.status = 404; return createErrorResponse('NOT_FOUND', message) }
            if (customCode === 'VALIDATION_ERROR') { set.status = 400; return createErrorResponse('VALIDATION_ERROR', message) }
            set.status = 500
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: { 201: CreateProductResponseSchema, 400: ErrorSchemas.validation, 401: ErrorSchemas.unauthorized, 403: ErrorSchemas.forbidden, 500: ErrorSchemas.internal },
          detail: {
            tags: ['admin'],
            summary: 'Create a new product with optional supplier item linkage',
            description:
              'Creates a new internal product. Supports the "split SKU" workflow where a supplier item can be linked during creation. If internal_sku is not provided, one is auto-generated. Requires procurement or admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // PATCH /products/:id/status - Update single product status
      .patch(
        '/products/:id/status',
        async ({ params, body, set, user }) => {
          // Sales, procurement or admin role required
          if (!user || !['sales', 'procurement', 'admin'].includes(user.role)) {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Sales, procurement or admin role required')
          }
          if (!isValidUUID(params.id)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'Invalid product ID format')
          }
          return adminService.updateProductStatus(params.id, body.status)
        },
        {
          body: UpdateProductStatusRequestSchema,
          error({ code, error, set }) {
            if (code === 'VALIDATION') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', error.message || 'Invalid request body')
            }
            const customCode = (error as any)?.code as string | undefined
            const message = error instanceof Error ? error.message : String(error)
            if (customCode === 'NOT_FOUND') {
              set.status = 404
              return createErrorResponse('NOT_FOUND', message)
            }
            set.status = 500
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: {
            200: UpdateProductStatusResponseSchema,
            400: ErrorSchemas.validation,
            401: ErrorSchemas.unauthorized,
            403: ErrorSchemas.forbidden,
            404: ErrorSchemas.notFound,
            500: ErrorSchemas.internal,
          },
          detail: {
            tags: ['admin', 'products'],
            summary: 'Update product status',
            description: 'Update the status of a single product (draft, active, archived). Requires sales, procurement or admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // =============================================================================
      // Ingestion Control Panel Endpoints (Phase 6)
      // =============================================================================
      // GET /ingestion/status - Get current ingestion pipeline status
      .get(
        '/ingestion/status',
        async ({ query, set, user }) => {
          // Admin role required
          if (!user || user.role !== 'admin') {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Admin role required for ingestion status')
          }

          const logLimit = parseNum(query.log_limit) || 50
          if (logLimit < 1 || logLimit > 100) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'log_limit must be between 1 and 100')
          }

          return ingestionService.getStatus(logLimit)
        },
        {
          query: t.Object({
            log_limit: t.Optional(t.Any()),
          }),
          error({ code, error, set }) {
            if (code === 'VALIDATION') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', 'Invalid query parameters')
            }
            const customCode = (error as any)?.code as string | undefined
            const message = error instanceof Error ? error.message : String(error)
            if (customCode === 'REDIS_UNAVAILABLE') {
              set.status = 503
              return createErrorResponse('REDIS_UNAVAILABLE', 'Redis service is temporarily unavailable')
            }
            set.status = 500
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: {
            200: IngestionStatusResponseSchema,
            400: ErrorSchemas.validation,
            401: ErrorSchemas.unauthorized,
            403: ErrorSchemas.forbidden,
            500: ErrorSchemas.internal,
            503: ErrorSchemas.redisUnavailable,
          },
          detail: {
            tags: ['admin', 'ingestion'],
            summary: 'Get current ingestion pipeline status',
            description:
              'Returns current sync state, progress, timestamps, supplier list, and recent logs. Designed for polling at 3-5 second intervals. Requires admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // POST /ingestion/sync - Trigger master sync pipeline (admin only, rate limited)
      .use(rateLimiter({ limit: 10, windowSeconds: 60 }))
      .post(
        '/ingestion/sync',
        async ({ set, user, checkRateLimit }) => {
          // Admin role required
          if (!user || user.role !== 'admin') {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Admin role required for sync operations')
          }

          const rateLimitError = checkRateLimit()
          if (rateLimitError) return rateLimitError

          set.status = 202
          return ingestionService.triggerSync()
        },
        {
          error({ code, error, set }) {
            if (code === 'VALIDATION') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', 'Invalid request')
            }
            const customCode = (error as any)?.code as string | undefined
            const message = error instanceof Error ? error.message : String(error)

            if (customCode === 'SYNC_IN_PROGRESS') {
              set.status = 409
              return {
                error: {
                  code: 'SYNC_IN_PROGRESS' as const,
                  message: message,
                  current_task_id: (error as any)?.current_task_id || 'unknown',
                },
              }
            }
            if (customCode === 'REDIS_UNAVAILABLE') {
              set.status = 503
              return createErrorResponse('REDIS_UNAVAILABLE', 'Queue service is temporarily unavailable')
            }
            set.status = 500
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: {
            202: TriggerSyncResponseSchema,
            400: ErrorSchemas.validation,
            401: ErrorSchemas.unauthorized,
            403: ErrorSchemas.forbidden,
            409: SyncAlreadyRunningResponseSchema,
            429: ErrorSchemas.rateLimited,
            500: ErrorSchemas.internal,
            503: ErrorSchemas.redisUnavailable,
          },
          detail: {
            tags: ['admin', 'ingestion'],
            summary: 'Trigger master sync pipeline',
            description:
              'Reads Master Google Sheet, syncs suppliers, and enqueues parsing tasks for all active suppliers. Returns immediately with task_id. Rate limited to 10 requests per minute. Requires admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // =============================================================================
      // Job Management Endpoints (Phase 8)
      // =============================================================================
      // POST /jobs/:id/retry - Retry a failed job
      .post(
        '/jobs/:id/retry',
        async ({ params, set, user }) => {
          // Admin role required
          if (!user || user.role !== 'admin') {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Admin role required to retry jobs')
          }
          if (!isValidUUID(params.id)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'Job ID must be a valid UUID')
          }

          set.status = 202
          return jobService.retryJob(params.id)
        },
        {
          error({ code, error, set }) {
            if (code === 'VALIDATION') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', error.message || 'Invalid job ID')
            }
            const customCode = (error as any)?.code as string | undefined
            const message = error instanceof Error ? error.message : String(error)

            if (customCode === 'NOT_FOUND' || message.includes('not found')) {
              set.status = 404
              return createErrorResponse('NOT_FOUND', message)
            }
            if (customCode === 'INVALID_STATE' || message.includes('not in failed state')) {
              set.status = 409
              return createErrorResponse('CONFLICT', message)
            }
            if (customCode === 'MAX_RETRIES_EXCEEDED' || message.includes('Maximum retries')) {
              set.status = 409
              return createErrorResponse('CONFLICT', message)
            }
            if (customCode === 'REDIS_UNAVAILABLE') {
              set.status = 503
              return createErrorResponse('REDIS_UNAVAILABLE', 'Queue service is temporarily unavailable')
            }
            set.status = 500
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: {
            202: RetryJobResponseSchema,
            400: ErrorSchemas.validation,
            401: ErrorSchemas.unauthorized,
            403: ErrorSchemas.forbidden,
            404: ErrorSchemas.notFound,
            409: ErrorSchemas.conflict,
            500: ErrorSchemas.internal,
            503: ErrorSchemas.redisUnavailable,
          },
          detail: {
            tags: ['admin', 'jobs'],
            summary: 'Retry a failed ingestion job',
            description:
              'Enqueues a failed ingestion job for reprocessing. The job must be in a "failed" state and not have exceeded its maximum retry attempts. Requires admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // POST /sync - admin only with rate limiting (legacy single-supplier sync)
      .use(rateLimiter({ limit: 10, windowSeconds: 60 }))
      .post(
        '/sync',
        async ({ body, set, checkRateLimit }) => {
          const rateLimitError = checkRateLimit()
          if (rateLimitError) return rateLimitError

          if (!isValidUUID(body.supplier_id)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'supplier_id must be a valid UUID')
          }
          set.status = 202
          return adminService.triggerSync(body)
        },
        {
          body: SyncRequestSchema,
          beforeHandle({ user, set }) {
            if (!user) {
              set.status = 401
              return { error: { code: 'UNAUTHORIZED' as const, message: 'Unauthorized' } }
            }
            if (user.role !== 'admin') {
              set.status = 403
              return { error: { code: 'FORBIDDEN' as const, message: 'Forbidden: Admin role required for sync operations.' } }
            }
          },
          error({ code, error, set }) {
            if (code === 'VALIDATION') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', error.message || 'Invalid request body')
            }
            const customCode = (error as any)?.code as string | undefined
            const message = error instanceof Error ? error.message : String(error)
            if (customCode === 'NOT_FOUND') { set.status = 404; return createErrorResponse('NOT_FOUND', message) }
            if (customCode === 'REDIS_UNAVAILABLE') { set.status = 503; return createErrorResponse('REDIS_UNAVAILABLE', 'Queue service is temporarily unavailable') }
            set.status = 500
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: { 202: SyncResponseSchema, 400: ErrorSchemas.validation, 401: ErrorSchemas.unauthorized, 403: ErrorSchemas.forbidden, 404: ErrorSchemas.notFound, 429: ErrorSchemas.rateLimited, 500: ErrorSchemas.internal, 503: ErrorSchemas.redisUnavailable },
          detail: {
            tags: ['admin'],
            summary: 'Trigger data sync for a supplier',
            description:
              'Enqueues a background task to synchronize data from a supplier source (Google Sheets, CSV, etc.). Returns immediately with a task_id for tracking. Rate limited to 10 requests per minute per user. Requires admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // =============================================================================
      // Settings Endpoints (Admin only)
      // =============================================================================
      // GET /settings/master-sheet-url - Get current master sheet URL configuration
      .get(
        '/settings/master-sheet-url',
        async ({ set, user }) => {
          if (!user || user.role !== 'admin') {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Admin role required')
          }
          return settingsService.getMasterSheetUrl()
        },
        {
          error({ code, error, set }) {
            const customCode = (error as any)?.code as string | undefined
            const message = error instanceof Error ? error.message : String(error)
            if (customCode === 'REDIS_UNAVAILABLE') {
              set.status = 503
              return createErrorResponse('REDIS_UNAVAILABLE', 'Settings service temporarily unavailable')
            }
            set.status = 500
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: {
            200: MasterSheetUrlResponseSchema,
            401: ErrorSchemas.unauthorized,
            403: ErrorSchemas.forbidden,
            500: ErrorSchemas.internal,
            503: ErrorSchemas.redisUnavailable,
          },
          detail: {
            tags: ['admin', 'settings'],
            summary: 'Get master sheet URL configuration',
            description: 'Returns the current master Google Sheet URL used for supplier sync. Requires admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // PUT /settings/master-sheet-url - Update master sheet URL
      .put(
        '/settings/master-sheet-url',
        async ({ body, set, user }) => {
          if (!user || user.role !== 'admin') {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Admin role required')
          }
          return settingsService.updateMasterSheetUrl(body.url, body.sheet_name)
        },
        {
          body: UpdateMasterSheetUrlRequestSchema,
          error({ code, error, set }) {
            if (code === 'VALIDATION') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', 'Invalid URL format')
            }
            const customCode = (error as any)?.code as string | undefined
            const message = error instanceof Error ? error.message : String(error)
            if (customCode === 'REDIS_UNAVAILABLE') {
              set.status = 503
              return createErrorResponse('REDIS_UNAVAILABLE', 'Settings service temporarily unavailable')
            }
            set.status = 500
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: {
            200: UpdateMasterSheetUrlResponseSchema,
            400: ErrorSchemas.validation,
            401: ErrorSchemas.unauthorized,
            403: ErrorSchemas.forbidden,
            500: ErrorSchemas.internal,
            503: ErrorSchemas.redisUnavailable,
          },
          detail: {
            tags: ['admin', 'settings'],
            summary: 'Update master sheet URL',
            description: 'Sets the master Google Sheet URL for supplier sync. Requires admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // =============================================================================
      // Supplier Management Endpoints (Admin only)
      // =============================================================================
      // GET /suppliers - List all suppliers
      .get(
        '/suppliers',
        async ({ set, user }) => {
          if (!user || user.role !== 'admin') {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Admin role required')
          }
          return supplierService.getSuppliers()
        },
        {
          error({ code, error, set }) {
            set.status = 500
            const message = error instanceof Error ? error.message : String(error)
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: {
            200: SuppliersListResponseSchema,
            401: ErrorSchemas.unauthorized,
            403: ErrorSchemas.forbidden,
            500: ErrorSchemas.internal,
          },
          detail: {
            tags: ['admin', 'suppliers'],
            summary: 'List all suppliers',
            description: 'Returns all suppliers with their item counts and status. Requires admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // POST /suppliers - Create a new supplier
      .post(
        '/suppliers',
        async ({ body, set, user }) => {
          if (!user || user.role !== 'admin') {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Admin role required')
          }
          set.status = 201
          return supplierService.createSupplier(body)
        },
        {
          body: CreateSupplierRequestSchema,
          error({ code, error, set }) {
            if (code === 'VALIDATION') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', error.message || 'Invalid request body')
            }
            const customCode = (error as any)?.code as string | undefined
            const message = error instanceof Error ? error.message : String(error)
            if (customCode === 'CONFLICT') {
              set.status = 409
              return createErrorResponse('CONFLICT', message)
            }
            set.status = 500
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: {
            201: CreateSupplierResponseSchema,
            400: ErrorSchemas.validation,
            401: ErrorSchemas.unauthorized,
            403: ErrorSchemas.forbidden,
            409: ErrorSchemas.conflict,
            500: ErrorSchemas.internal,
          },
          detail: {
            tags: ['admin', 'suppliers'],
            summary: 'Create a new supplier',
            description: 'Creates a new supplier with optional source URL. Allows adding suppliers without master sheet. Requires admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // GET /suppliers/:id - Get supplier by ID
      .get(
        '/suppliers/:id',
        async ({ params, set, user }) => {
          if (!user || user.role !== 'admin') {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Admin role required')
          }
          if (!isValidUUID(params.id)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'Invalid supplier ID format')
          }
          const supplier = await supplierService.getSupplierById(params.id)
          if (!supplier) {
            set.status = 404
            return createErrorResponse('NOT_FOUND', 'Supplier not found')
          }
          return supplier
        },
        {
          error({ code, error, set }) {
            set.status = 500
            const message = error instanceof Error ? error.message : String(error)
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: {
            200: SupplierResponseSchema,
            400: ErrorSchemas.validation,
            401: ErrorSchemas.unauthorized,
            403: ErrorSchemas.forbidden,
            404: ErrorSchemas.notFound,
            500: ErrorSchemas.internal,
          },
          detail: {
            tags: ['admin', 'suppliers'],
            summary: 'Get supplier by ID',
            description: 'Returns a single supplier with full details. Requires admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // PUT /suppliers/:id - Update supplier
      .put(
        '/suppliers/:id',
        async ({ params, body, set, user }) => {
          if (!user || user.role !== 'admin') {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Admin role required')
          }
          if (!isValidUUID(params.id)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'Invalid supplier ID format')
          }
          const updated = await supplierService.updateSupplier(params.id, body)
          if (!updated) {
            set.status = 404
            return createErrorResponse('NOT_FOUND', 'Supplier not found')
          }
          return updated
        },
        {
          body: UpdateSupplierRequestSchema,
          error({ code, error, set }) {
            if (code === 'VALIDATION') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', error.message || 'Invalid request body')
            }
            const customCode = (error as any)?.code as string | undefined
            const message = error instanceof Error ? error.message : String(error)
            if (customCode === 'CONFLICT') {
              set.status = 409
              return createErrorResponse('CONFLICT', message)
            }
            set.status = 500
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: {
            200: SupplierResponseSchema,
            400: ErrorSchemas.validation,
            401: ErrorSchemas.unauthorized,
            403: ErrorSchemas.forbidden,
            404: ErrorSchemas.notFound,
            409: ErrorSchemas.conflict,
            500: ErrorSchemas.internal,
          },
          detail: {
            tags: ['admin', 'suppliers'],
            summary: 'Update supplier',
            description: 'Updates an existing supplier. Requires admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // DELETE /suppliers/:id - Delete supplier
      .delete(
        '/suppliers/:id',
        async ({ params, set, user }) => {
          if (!user || user.role !== 'admin') {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Admin role required')
          }
          if (!isValidUUID(params.id)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'Invalid supplier ID format')
          }
          const result = await supplierService.deleteSupplier(params.id)
          if (!result) {
            set.status = 404
            return createErrorResponse('NOT_FOUND', 'Supplier not found')
          }
          return result
        },
        {
          error({ code, error, set }) {
            set.status = 500
            const message = error instanceof Error ? error.message : String(error)
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: {
            200: DeleteSupplierResponseSchema,
            400: ErrorSchemas.validation,
            401: ErrorSchemas.unauthorized,
            403: ErrorSchemas.forbidden,
            404: ErrorSchemas.notFound,
            500: ErrorSchemas.internal,
          },
          detail: {
            tags: ['admin', 'suppliers'],
            summary: 'Delete supplier',
            description: 'Deletes a supplier and all associated items (cascade). Requires admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
      // POST /suppliers/:id/upload - Upload price list file for supplier
      .post(
        '/suppliers/:id/upload',
        async ({ params, body, set, user }) => {
          if (!user || user.role !== 'admin') {
            set.status = 403
            return createErrorResponse('FORBIDDEN', 'Admin role required')
          }
          if (!isValidUUID(params.id)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'Invalid supplier ID format')
          }
          
          const file = body.file as File
          if (!file || !(file instanceof File)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'No file provided')
          }

          set.status = 202
          return supplierService.uploadFile(params.id, file, {
            sheetName: body.sheet_name,
            headerRow: body.header_row,
            dataStartRow: body.data_start_row,
          })
        },
        {
          body: t.Object({
            // Accept any file type - we validate by extension in the service
            // MIME types are unreliable (browsers send different types, curl sends application/octet-stream)
            file: t.File(),
            sheet_name: t.Optional(t.String()),
            header_row: t.Optional(t.Number({ minimum: 1 })),
            data_start_row: t.Optional(t.Number({ minimum: 1 })),
          }),
          error({ code, error, set }) {
            if (code === 'VALIDATION') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', error.message || 'Invalid file or parameters')
            }
            const customCode = (error as any)?.code as string | undefined
            const message = error instanceof Error ? error.message : String(error)
            if (customCode === 'NOT_FOUND') {
              set.status = 404
              return createErrorResponse('NOT_FOUND', message)
            }
            if (customCode === 'VALIDATION_ERROR') {
              set.status = 400
              return createErrorResponse('VALIDATION_ERROR', message)
            }
            if (customCode === 'REDIS_UNAVAILABLE') {
              set.status = 503
              return createErrorResponse('REDIS_UNAVAILABLE', 'Queue service temporarily unavailable')
            }
            set.status = 500
            return createErrorResponse('INTERNAL_ERROR', process.env.NODE_ENV === 'production' ? 'Internal server error' : message)
          },
          response: {
            202: UploadSupplierFileResponseSchema,
            400: ErrorSchemas.validation,
            401: ErrorSchemas.unauthorized,
            403: ErrorSchemas.forbidden,
            404: ErrorSchemas.notFound,
            500: ErrorSchemas.internal,
            503: ErrorSchemas.redisUnavailable,
          },
          detail: {
            tags: ['admin', 'suppliers'],
            summary: 'Upload price list file',
            description: 'Uploads a CSV or Excel file for a supplier and queues it for parsing. Auto-detects format from file extension. Requires admin role.',
            security: [{ bearerAuth: [] }],
          },
        }
      )
  )
