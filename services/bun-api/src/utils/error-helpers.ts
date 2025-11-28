/**
 * Error Helpers
 * 
 * Shared utilities for handling errors consistently across controllers.
 * Follows DRY principle by centralizing error handling logic.
 */

/** UUID validation regex */
export const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** Validate UUID format */
export const isValidUUID = (value: string): boolean => UUID_REGEX.test(value)

/** Parse optional number from query param */
export const parseNum = (v: unknown): number | undefined => {
  if (v === undefined || v === null || v === '') return undefined
  const n = typeof v === 'string' ? parseFloat(v) : Number(v)
  return isNaN(n) ? undefined : n
}

/** Parse optional integer from query param */
export const parseInt = (v: unknown): number | undefined => {
  if (v === undefined || v === null || v === '') return undefined
  const n = typeof v === 'string' ? globalThis.parseInt(v, 10) : Math.floor(Number(v))
  return isNaN(n) ? undefined : n
}
