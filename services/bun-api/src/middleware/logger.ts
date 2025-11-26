import { Elysia } from 'elysia'

/**
 * Request logging middleware
 * 
 * Logs all incoming requests with method, path, status code, and response time
 */

export const logger = new Elysia({ name: 'logger' })
  .onRequest(({ request }) => {
    const start = Date.now()
    // Store start time in context for response logging
    ;(request as any).startTime = start
  })
  .onAfterHandle(({ request, response, set }) => {
    const startTime = (request as any).startTime || Date.now()
    const duration = Date.now() - startTime

    const logData = {
      method: request.method,
      path: new URL(request.url).pathname,
      status: set.status || 200,
      duration: `${duration}ms`,
      timestamp: new Date().toISOString(),
    }

    // Log in structured format
    console.log(JSON.stringify(logData))

    // Log errors separately
    if (set.status && set.status >= 400) {
      console.error(JSON.stringify({
        ...logData,
        error: true,
        response: typeof response === 'object' ? JSON.stringify(response) : response,
      }))
    }
  })
  .onError(({ request, error, set }) => {
    const startTime = (request as any).startTime || Date.now()
    const duration = Date.now() - startTime

    console.error(JSON.stringify({
      method: request.method,
      path: new URL(request.url).pathname,
      status: set.status || 500,
      duration: `${duration}ms`,
      error: error.message,
      stack: error.stack,
      timestamp: new Date().toISOString(),
    }))
  })

