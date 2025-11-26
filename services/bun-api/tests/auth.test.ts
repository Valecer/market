import { describe, test, expect, beforeAll, afterAll } from 'bun:test'
import { Elysia } from 'elysia'
import { jwt } from '@elysiajs/jwt'
import { authController } from '../src/controllers/auth'
import { errorHandler } from '../src/middleware/error-handler'

/**
 * Authentication Endpoint Tests
 * 
 * Tests for T049-T054: Login flow scenarios
 */

// Create a test app with auth controller
const createTestApp = () => {
  return new Elysia()
    .use(errorHandler)
    .use(
      jwt({
        name: 'jwt',
        secret: 'test-secret-key-for-jwt-signing',
        exp: '24h',
      })
    )
    .use(authController)
}

describe('Authentication - Login Endpoint', () => {
  let app: ReturnType<typeof createTestApp>
  let server: any

  beforeAll(() => {
    app = createTestApp()
  })

  afterAll(() => {
    if (server) {
      server.stop()
    }
  })

  describe('T049: Valid credentials return token with 200', () => {
    test('POST /api/v1/auth/login with valid credentials', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: 'admin',
            password: 'admin123',
          }),
        })
      )

      expect(response.status).toBe(200)

      const data = await response.json()
      expect(data).toHaveProperty('token')
      expect(data).toHaveProperty('expires_at')
      expect(data).toHaveProperty('user')
      expect(data.user).toHaveProperty('id')
      expect(data.user).toHaveProperty('username')
      expect(data.user).toHaveProperty('role')
      expect(typeof data.token).toBe('string')
      expect(data.token.length).toBeGreaterThan(0)
    })
  })

  describe('T050: Invalid username returns 401', () => {
    test('POST /api/v1/auth/login with invalid username', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: 'nonexistent',
            password: 'admin123',
          }),
        })
      )

      expect(response.status).toBe(401)

      const data = await response.json()
      expect(data).toHaveProperty('error')
      expect(data.error).toHaveProperty('code')
      expect(data.error.code).toBe('UNAUTHORIZED')
      expect(data.error.message).toContain('Invalid username or password')
    })
  })

  describe('T051: Invalid password returns 401', () => {
    test('POST /api/v1/auth/login with invalid password', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: 'admin',
            password: 'wrongpassword',
          }),
        })
      )

      expect(response.status).toBe(401)

      const data = await response.json()
      expect(data).toHaveProperty('error')
      expect(data.error).toHaveProperty('code')
      expect(data.error.code).toBe('UNAUTHORIZED')
      expect(data.error.message).toContain('Invalid username or password')
    })
  })

  describe('T052: Missing fields return 400', () => {
    test('POST /api/v1/auth/login with missing username', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            password: 'admin123',
          }),
        })
      )

      expect(response.status).toBe(400)

      const data = await response.json()
      expect(data).toHaveProperty('error')
      expect(data.error).toHaveProperty('code')
      expect(data.error.code).toBe('VALIDATION_ERROR')
    })

    test('POST /api/v1/auth/login with missing password', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: 'admin',
          }),
        })
      )

      expect(response.status).toBe(400)

      const data = await response.json()
      expect(data).toHaveProperty('error')
      expect(data.error).toHaveProperty('code')
      expect(data.error.code).toBe('VALIDATION_ERROR')
    })

    test('POST /api/v1/auth/login with empty body', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        })
      )

      expect(response.status).toBe(400)

      const data = await response.json()
      expect(data).toHaveProperty('error')
      expect(data.error).toHaveProperty('code')
      expect(data.error.code).toBe('VALIDATION_ERROR')
    })
  })

  describe('T053: JWT payload structure matches specification', () => {
    test('JWT token contains correct payload structure', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: 'admin',
            password: 'admin123',
          }),
        })
      )

      expect(response.status).toBe(200)

      const data = await response.json()
      const token = data.token

      // Decode JWT token (without verification for structure check)
      const parts = token.split('.')
      expect(parts.length).toBe(3) // header.payload.signature

      // Decode payload (base64url)
      const payload = JSON.parse(
        Buffer.from(parts[1], 'base64url').toString('utf-8')
      )

      // Verify payload structure matches JWTPayload specification
      expect(payload).toHaveProperty('sub')
      expect(payload).toHaveProperty('role')
      expect(payload).toHaveProperty('exp')
      expect(payload).toHaveProperty('iss')

      // Verify types
      expect(typeof payload.sub).toBe('string')
      expect(typeof payload.role).toBe('string')
      expect(['sales', 'procurement', 'admin']).toContain(payload.role)
      expect(typeof payload.exp).toBe('number')
      expect(typeof payload.iss).toBe('string')
      expect(payload.iss).toBe(process.env.JWT_ISSUER || 'marketbel-api')

      // Verify user in response matches payload
      expect(data.user.id).toBe(payload.sub)
      expect(data.user.role).toBe(payload.role)
    })
  })

  describe('T054: Token expiration after configured hours', () => {
    test('JWT token exp claim is set correctly', async () => {
      const expirationHours = 24
      const now = Math.floor(Date.now() / 1000)
      const expectedExp = now + expirationHours * 3600
      const tolerance = 60 // 1 minute tolerance

      const response = await app.handle(
        new Request('http://localhost/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: 'admin',
            password: 'admin123',
          }),
        })
      )

      expect(response.status).toBe(200)

      const data = await response.json()
      const token = data.token

      // Decode JWT payload
      const parts = token.split('.')
      const payload = JSON.parse(
        Buffer.from(parts[1], 'base64url').toString('utf-8')
      )

      // Verify exp is approximately correct (within tolerance)
      expect(Math.abs(payload.exp - expectedExp)).toBeLessThan(tolerance)

      // Verify expires_at in response is ISO 8601 format
      expect(data.expires_at).toMatch(
        /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z$/
      )

      // Verify expires_at matches exp timestamp (within tolerance)
      const expiresAtMs = new Date(data.expires_at).getTime()
      const expMs = payload.exp * 1000
      expect(Math.abs(expiresAtMs - expMs)).toBeLessThan(tolerance * 1000)
    })
  })
})

