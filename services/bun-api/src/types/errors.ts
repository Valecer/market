import { Type, Static } from '@sinclair/typebox'

/**
 * Error response schemas for consistent API error handling
 * 
 * All error responses follow the standard format:
 * {
 *   error: {
 *     code: string,
 *     message: string,
 *     details?: object
 *   }
 * }
 */

export const ErrorCodeSchema = Type.Union([
  Type.Literal('VALIDATION_ERROR'),
  Type.Literal('UNAUTHORIZED'),
  Type.Literal('FORBIDDEN'),
  Type.Literal('NOT_FOUND'),
  Type.Literal('CONFLICT'),
  Type.Literal('RATE_LIMIT_EXCEEDED'),
  Type.Literal('REDIS_UNAVAILABLE'),
  Type.Literal('INTERNAL_ERROR'),
])

export type ErrorCode = Static<typeof ErrorCodeSchema>

export const ErrorDetailsSchema = Type.Object({
  field: Type.Optional(Type.String()),
  issue: Type.Optional(Type.String()),
  value: Type.Optional(Type.Any()),
}, { additionalProperties: true })

export type ErrorDetails = Static<typeof ErrorDetailsSchema>

export const ErrorResponseSchema = Type.Object({
  error: Type.Object({
    code: ErrorCodeSchema,
    message: Type.String(),
    details: Type.Optional(ErrorDetailsSchema),
  }),
})

export type ErrorResponse = Static<typeof ErrorResponseSchema>

/**
 * Helper function to create error responses
 */
export function createErrorResponse(
  code: ErrorCode,
  message: string,
  details?: ErrorDetails
): ErrorResponse {
  return {
    error: {
      code,
      message,
      ...(details && { details }),
    },
  }
}

