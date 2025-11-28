import { Elysia } from 'elysia'
import { createErrorResponse } from '../types/errors'
import type { ErrorCode } from '../types/errors'

/**
 * Global error handler middleware
 * 
 * Catches all errors and formats them into consistent error responses
 * following the standard error response format.
 */

export const errorHandler = new Elysia({ name: 'error-handler' })
  .onError(({ code, error, set }) => {
    // Type guard: check if error is an Error instance
    const isError = error instanceof Error
    const errorMessage = isError ? error.message : String(error)
    const errorStack = isError ? error.stack : undefined

    // Check for custom error code on error object first (set by service layer)
    // This takes precedence over Elysia's built-in error codes
    const customErrorCode = (error as any).code as string | undefined

    // Log error for debugging
    console.error('Error caught by error handler:', {
      code,
      errorCode: customErrorCode,
      error: errorMessage,
      stack: errorStack,
    })

    // Handle validation errors
    // Priority: custom error code > Elysia code > message check
    if (customErrorCode === 'VALIDATION_ERROR' || code === 'VALIDATION') {
      set.status = 400
      return createErrorResponse(
        'VALIDATION_ERROR',
        errorMessage || 'Invalid request parameters',
        {
          issue: errorMessage,
        }
      )
    }

    // Handle not found errors
    if (customErrorCode === 'NOT_FOUND' || code === 'NOT_FOUND') {
      set.status = 404
      return createErrorResponse('NOT_FOUND', errorMessage || 'Resource not found')
    }

    // Handle conflict errors
    if (customErrorCode === 'CONFLICT' || (isError && errorMessage.includes('Conflict'))) {
      set.status = 409
      return createErrorResponse('CONFLICT', errorMessage || 'Conflict')
    }

    // Handle unauthorized errors
    if (customErrorCode === 'UNAUTHORIZED' || (isError && errorMessage.includes('Unauthorized'))) {
      set.status = 401
      return createErrorResponse('UNAUTHORIZED', errorMessage || 'Unauthorized')
    }

    // Handle forbidden errors
    if (customErrorCode === 'FORBIDDEN' || (isError && errorMessage.includes('Forbidden'))) {
      set.status = 403
      return createErrorResponse('FORBIDDEN', errorMessage || 'Forbidden')
    }

    // Handle rate limit errors
    if (customErrorCode === 'RATE_LIMIT' || customErrorCode === 'RATE_LIMIT_EXCEEDED' || (isError && errorMessage.includes('Rate limit'))) {
      set.status = 429
      return createErrorResponse('RATE_LIMIT_EXCEEDED', errorMessage || 'Rate limit exceeded')
    }

    // Handle internal errors (from service layer)
    if (customErrorCode === 'INTERNAL_ERROR') {
      set.status = 500
      return createErrorResponse(
        'INTERNAL_ERROR',
        process.env.NODE_ENV === 'production'
          ? 'Internal server error'
          : errorMessage || 'An unexpected error occurred'
      )
    }

    // Handle Redis unavailable errors
    if (isError && (errorMessage.includes('Redis') || errorMessage.includes('redis'))) {
      set.status = 503
      return createErrorResponse('REDIS_UNAVAILABLE', 'Redis service unavailable')
    }

    // Handle parse errors (from Elysia)
    if (code === 'PARSE') {
      set.status = 400
      return createErrorResponse('VALIDATION_ERROR', 'Could not parse request body', {
        issue: errorMessage,
      })
    }

    // Default to 500 for unknown errors
    set.status = 500
    return createErrorResponse(
      'INTERNAL_ERROR',
      process.env.NODE_ENV === 'production'
        ? 'Internal server error'
        : errorMessage || 'An unexpected error occurred'
    )
  })
