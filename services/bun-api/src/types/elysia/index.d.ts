import type { JWTPayload } from '../auth.types'
import type { Cookie } from 'elysia'

declare module 'elysia' {
  interface Context {
    user: JWTPayload | null
    jwt?: {
      sign: (payload: object) => Promise<string> | string
      verify: (token: string) => Promise<JWTPayload | null> | JWTPayload | null
    }
    cookie: Record<string, Cookie<unknown>>
  }
}

export {}
