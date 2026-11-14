import type { JWTPayload } from './auth.types'
import type { Cookie } from 'elysia'

declare module 'elysia' {
  interface Context {
    /**
     * JWT payload injected by authMiddleware.
     * Null when authentication fails or token missing.
     */
    user: JWTPayload | null
    /**
     * JWT helper injected by @elysiajs/jwt plugin.
     * Marked optional to match runtime plugin availability.
     */
    jwt?: {
      sign: (payload: object) => Promise<string> | string
      verify: (token: string) => Promise<JWTPayload | null> | JWTPayload | null
    }
    cookie: Record<string, Cookie<unknown>>
  }
}
