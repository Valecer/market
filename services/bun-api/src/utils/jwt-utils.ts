import type { JWTPayload } from '../types/auth.types'

/**
 * JWT Utility Functions
 * 
 * Helper functions for JWT token generation and validation
 */

/**
 * Generate JWT payload for a user
 * 
 * @param userId - User UUID
 * @param role - User role (sales, procurement, admin)
 * @param expirationHours - Token expiration in hours (default: 24)
 * @returns JWT payload object
 */
export function generateJWTPayload(
  userId: string,
  role: 'sales' | 'procurement' | 'admin',
  expirationHours: number = Number(process.env.JWT_EXPIRATION_HOURS) || 24
): JWTPayload {
  const now = Math.floor(Date.now() / 1000) // Current time in seconds
  const exp = now + expirationHours * 3600 // Add hours in seconds

  return {
    sub: userId,
    role,
    exp,
    iss: process.env.JWT_ISSUER || 'marketbel-api',
  }
}

/**
 * Calculate token expiration timestamp
 * 
 * @param expirationHours - Token expiration in hours
 * @returns ISO 8601 timestamp string
 */
export function calculateExpirationTime(expirationHours: number = 24): string {
  const expirationMs = expirationHours * 3600 * 1000
  return new Date(Date.now() + expirationMs).toISOString()
}

