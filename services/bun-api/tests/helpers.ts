import { Elysia } from 'elysia'
import { jwt } from '@elysiajs/jwt'
import { errorHandler } from '../src/middleware/error-handler'
import { authController } from '../src/controllers/auth'
import { catalogController } from '../src/controllers/catalog'
import { adminController } from '../src/controllers/admin'

/**
 * Test Helpers
 * 
 * Shared utilities for all endpoint tests
 */

// Type helper for JSON responses
export type ErrorResponse = {
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
}

/**
 * JWT secret for testing
 */
export const TEST_JWT_SECRET = 'test-secret-key-for-jwt-signing'

/**
 * Create a test app with JWT and error handler
 * Base configuration for all test apps
 */
export function createBaseTestApp() {
  return new Elysia()
    .use(errorHandler)
    .use(
      jwt({
        name: 'jwt',
        secret: TEST_JWT_SECRET,
        exp: '24h',
      })
    )
}

/**
 * Create a test app with auth controller
 * Used for authentication endpoint tests
 */
export function createAuthTestApp() {
  return createBaseTestApp().use(authController)
}

/**
 * Create a test app with catalog controller
 * Used for catalog endpoint tests
 */
export function createCatalogTestApp() {
  return createBaseTestApp().use(catalogController)
}

/**
 * Create a test app with admin and auth controllers
 * Used for admin endpoint tests
 */
export function createAdminTestApp() {
  return createBaseTestApp()
    .use(authController) // Need auth controller for login endpoint
    .use(adminController)
}

/**
 * Generate a JWT token for testing
 * @param app - Test app instance (must have auth controller)
 * @param username - Username to login with
 * @param password - Password to login with
 * @returns JWT token or null if login fails
 */
export async function generateTestToken(
  app: ReturnType<typeof createAuthTestApp> | ReturnType<typeof createAdminTestApp>,
  username: string = 'admin',
  password: string = 'admin123',
  retries: number = 3
): Promise<string | null> {
  // Retry logic to handle potential race conditions after user creation
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      // First, try to login to get a token
      const loginResponse = await app.handle(
        new Request('http://localhost/api/v1/auth/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ username, password }),
        })
      )

      const responseText = await loginResponse.text()

      if (loginResponse.status === 200) {
        try {
          const data = JSON.parse(responseText) as { token: string }
          if (!data.token) {
            if (attempt < retries) {
              await new Promise((resolve) => setTimeout(resolve, 100 * attempt))
              continue
            }
            return null
          }
          return data.token
        } catch (e) {
          if (attempt < retries) {
            await new Promise((resolve) => setTimeout(resolve, 100 * attempt))
            continue
          }
          return null
        }
      } else {
        // If 401 and we have retries left, wait and retry (might be a timing issue)
        if (loginResponse.status === 401 && attempt < retries) {
          await new Promise((resolve) => setTimeout(resolve, 100 * attempt))
          continue
        }
      }
    } catch (error) {
      // If login fails, retry if attempts remain
      if (attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, 100 * attempt))
        continue
      }
    }
  }
  return null
}

/**
 * Verify token works by making a test request
 * @param app - Test app instance
 * @param token - JWT token to verify
 * @returns true if token is valid, false otherwise
 */
export async function verifyToken(
  app: ReturnType<typeof createAdminTestApp>,
  token: string
): Promise<boolean> {
  try {
    const testResponse = await app.handle(
      new Request('http://localhost/api/v1/admin/products?page=1&limit=1', {
        method: 'GET',
        headers: { Authorization: `Bearer ${token}` },
      })
    )

    return testResponse.status === 200
  } catch (error) {
    return false
  }
}

/**
 * Setup authentication tokens for all roles
 * @param app - Test app instance (must have auth controller)
 * @returns Object with tokens for admin, procurement, and sales roles
 */
export async function setupAuthTokens(
  app: ReturnType<typeof createAuthTestApp> | ReturnType<typeof createAdminTestApp>
): Promise<{
  adminToken: string | null
  procurementToken: string | null
  salesToken: string | null
}> {
  const adminToken = await generateTestToken(app, 'admin', 'admin123')
  const procurementToken = await generateTestToken(app, 'procurement', 'procurement123')
  const salesToken = await generateTestToken(app, 'sales', 'sales123')

  return {
    adminToken,
    procurementToken,
    salesToken,
  }
}

