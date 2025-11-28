import { Elysia } from 'elysia'

/**
 * Enhanced request logging middleware with:
 * - Request ID propagation for distributed tracing
 * - Structured JSON logging
 * - Response time tracking
 * - Error context logging with stack traces for 5xx errors
 */

// Generate a unique request ID
function generateRequestId(): string {
  return `req_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 11)}`
}

// Extended request type with our custom properties
interface RequestWithMetadata extends Request {
  _startTime?: number
  _requestId?: string
}

export interface LogEntry {
  timestamp: string
  requestId: string
  level: 'info' | 'warn' | 'error' | 'debug'
  method: string
  path: string
  status?: number
  duration?: string
  durationMs?: number
  userAgent?: string
  ip?: string
  query?: Record<string, string>
  error?: {
    message: string
    stack?: string
    code?: string
  }
  context?: Record<string, unknown>
}

// Structured log formatter
function formatLog(entry: LogEntry): string {
  return JSON.stringify(entry)
}

// Log to console with appropriate method
function log(entry: LogEntry): void {
  const output = formatLog(entry)
  
  switch (entry.level) {
    case 'error':
      console.error(output)
      break
    case 'warn':
      console.warn(output)
      break
    case 'debug':
      console.debug(output)
      break
    default:
      console.log(output)
  }
}

export const logger = new Elysia({ name: 'logger' })
  .derive(({ request, headers }) => {
    // Generate or extract request ID (support for incoming request IDs from load balancers)
    const incomingRequestId = headers['x-request-id'] as string | undefined
    const requestId = incomingRequestId || generateRequestId()
    
    // Store start time and request ID on request
    const req = request as RequestWithMetadata
    req._startTime = Date.now()
    req._requestId = requestId
    
    return {
      requestId,
      startTime: req._startTime,
    }
  })
  .onAfterHandle(({ request, requestId, startTime, set, headers }) => {
    const duration = Date.now() - (startTime || Date.now())
    const url = new URL(request.url)
    const status = typeof set.status === 'number' ? set.status : 200
    
    // Determine log level based on status code
    const level: LogEntry['level'] = status >= 500 ? 'error' : status >= 400 ? 'warn' : 'info'
    
    const logEntry: LogEntry = {
      timestamp: new Date().toISOString(),
      requestId: requestId || 'unknown',
      level,
      method: request.method,
      path: url.pathname,
      status,
      duration: `${duration}ms`,
      durationMs: duration,
      userAgent: headers['user-agent'] as string | undefined,
      ip: headers['x-forwarded-for'] as string || headers['x-real-ip'] as string || 'unknown',
    }
    
    // Add query params if present (exclude sensitive data)
    if (url.search) {
      const params = Object.fromEntries(url.searchParams)
      // Exclude sensitive params
      delete params.password
      delete params.token
      delete params.secret
      if (Object.keys(params).length > 0) {
        logEntry.query = params
      }
    }
    
    log(logEntry)
    
    // Add request ID to response headers for client-side correlation
    if (typeof set.headers === 'object' && set.headers !== null) {
      (set.headers as Record<string, string>)['X-Request-ID'] = requestId || 'unknown'
    }
  })
  .onError(({ request, error, set, requestId, startTime, headers }) => {
    const duration = Date.now() - (startTime || Date.now())
    const url = new URL(request.url)
    const status = typeof set.status === 'number' ? set.status : 500
    
    // Type guard for Error
    const isError = error instanceof Error
    const errorMessage = isError ? error.message : String(error)
    const errorStack = isError ? error.stack : undefined
    const errorCode = (error as any).code as string | undefined
    
    // Always log at error level for onError handler
    const logEntry: LogEntry = {
      timestamp: new Date().toISOString(),
      requestId: requestId || 'unknown',
      level: 'error',
      method: request.method,
      path: url.pathname,
      status,
      duration: `${duration}ms`,
      durationMs: duration,
      userAgent: headers['user-agent'] as string | undefined,
      ip: headers['x-forwarded-for'] as string || headers['x-real-ip'] as string || 'unknown',
      error: {
        message: errorMessage,
        code: errorCode,
      },
    }
    
    // Include stack trace for 5xx errors (server errors)
    // This helps with debugging while not exposing internal details for client errors
    if (status >= 500 && errorStack) {
      logEntry.error!.stack = errorStack
    }
    
    // Add additional context for debugging
    if (status >= 500) {
      logEntry.context = {
        errorType: isError ? error.constructor.name : 'Unknown',
        nodeEnv: process.env.NODE_ENV || 'development',
      }
    }
    
    log(logEntry)
    
    // Add request ID to response headers for client-side correlation
    if (typeof set.headers === 'object' && set.headers !== null) {
      (set.headers as Record<string, string>)['X-Request-ID'] = requestId || 'unknown'
    }
  })

// Export types for use in other modules
export type { LogEntry as StructuredLogEntry }
