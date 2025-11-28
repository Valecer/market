import { Type, Static } from '@sinclair/typebox'

/**
 * Authentication-related TypeBox schemas
 * 
 * Based on auth-api.json contract
 */

export const LoginRequestSchema = Type.Object({
  username: Type.String({ minLength: 3, maxLength: 255 }),
  password: Type.String({ minLength: 8, maxLength: 255 }),
})

export type LoginRequest = Static<typeof LoginRequestSchema>

export const UserRoleSchema = Type.Union([
  Type.Literal('sales'),
  Type.Literal('procurement'),
  Type.Literal('admin'),
])

export type UserRole = Static<typeof UserRoleSchema>

export const UserSchema = Type.Object({
  id: Type.String({ format: 'uuid' }),
  username: Type.String(),
  role: UserRoleSchema,
})

export type User = Static<typeof UserSchema>

export const LoginResponseSchema = Type.Object({
  token: Type.String(),
  expires_at: Type.String({ format: 'date-time' }),
  user: UserSchema,
})

export type LoginResponse = Static<typeof LoginResponseSchema>

export const JWTPayloadSchema = Type.Object({
  sub: Type.String({ format: 'uuid' }), // User ID
  role: UserRoleSchema,
  exp: Type.Number(), // Expiration timestamp (Unix)
  iss: Type.String(), // Issuer
})

export type JWTPayload = Static<typeof JWTPayloadSchema>

