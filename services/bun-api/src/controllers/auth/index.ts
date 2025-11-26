import { Elysia, t } from 'elysia'
import { AuthService } from '../../services/auth.service'
import { LoginRequestSchema, LoginResponseSchema } from '../../types/auth.types'
import { createErrorResponse } from '../../types/errors'

/**
 * Authentication Controller
 * 
 * Handles HTTP requests for authentication endpoints.
 * No business logic - delegates to AuthService.
 */

export const authController = new Elysia({ prefix: '/api/v1/auth' })
  .post(
    '/login',
    async ({ body, jwt, set }) => {
      try {
        // Call auth service to authenticate
        const loginResponse = await AuthService.login(body, jwt)

        if (!loginResponse) {
          set.status = 401
          return createErrorResponse(
            'UNAUTHORIZED',
            'Invalid username or password'
          )
        }

        // Return successful login response
        set.status = 200
        return loginResponse
      } catch (error) {
        // Re-throw to be caught by error handler middleware
        throw error
      }
    },
    {
      body: LoginRequestSchema,
      error({ code, error, set }) {
        // Handle validation errors - convert 422 to 400 to match API contract
        if (code === 'VALIDATION') {
          set.status = 400
          return createErrorResponse(
            'VALIDATION_ERROR',
            'Invalid request parameters',
            {
              issue: error.message,
            }
          )
        }
      },
      response: {
        200: LoginResponseSchema,
        401: t.Object({
          error: t.Object({
            code: t.Literal('UNAUTHORIZED'),
            message: t.String(),
          }),
        }),
        400: t.Object({
          error: t.Object({
            code: t.Literal('VALIDATION_ERROR'),
            message: t.String(),
            details: t.Optional(t.Object({})),
          }),
        }),
      },
      detail: {
        tags: ['auth'],
        summary: 'Authenticate user and receive JWT token',
        description:
          'Validates username and password credentials. Returns a JWT token on success that can be used for authenticated requests.',
        examples: [
          {
            description: 'Successful login',
            value: {
              request: {
                username: 'admin',
                password: 'admin123',
              },
              response: {
                token:
                  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJyb2xlIjoiYWRtaW4iLCJleHAiOjE3MzI2MjM2MDAsImlzcyI6Im1hcmtldGJlbC1hcGkifQ.signature',
                expires_at: '2025-11-27T10:30:00Z',
                user: {
                  id: '550e8400-e29b-41d4-a716-446655440000',
                  username: 'admin',
                  role: 'admin',
                },
              },
            },
          },
        ],
      },
    }
  )

