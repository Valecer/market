import { userRepository } from '../db/repositories/user.repository'
import { generateJWTPayload, calculateExpirationTime } from '../utils/jwt-utils'
import type { LoginRequest, LoginResponse } from '../types/auth.types'
import type { User } from '../db/schema/types'

/**
 * Authentication Service
 * 
 * Handles business logic for user authentication including:
 * - Credential validation
 * - Password verification
 * - JWT token generation
 */

export class AuthService {
  /**
   * Authenticate user with username and password
   * 
   * @param credentials - Login credentials (username, password)
   * @param jwt - JWT plugin instance for token signing
   * @returns LoginResponse with token and user info, or null if authentication fails
   */
  static async login(
    credentials: LoginRequest,
    jwt: { sign: (payload: any) => Promise<string> }
  ): Promise<LoginResponse | null> {
    // Find user by username
    const user = await userRepository.findByUsername(credentials.username)

    if (!user) {
      // Return null instead of throwing to allow controller to handle error formatting
      return null
    }

    // Verify password using Bun.password.verify
    const isPasswordValid = await Bun.password.verify(
      credentials.password,
      user.passwordHash
    )

    if (!isPasswordValid) {
      return null
    }

    // Generate JWT payload
    const payload = generateJWTPayload(user.id, user.role)

    // Sign JWT token
    const token = await jwt.sign(payload)

    // Calculate expiration time
    const expirationHours = Number(process.env.JWT_EXPIRATION_HOURS) || 24
    const expiresAt = calculateExpirationTime(expirationHours)

    // Return login response
    return {
      token,
      expires_at: expiresAt,
      user: {
        id: user.id,
        username: user.username,
        role: user.role,
      },
    }
  }
}

