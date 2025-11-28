import { Elysia } from 'elysia'

/**
 * Response compression middleware
 * 
 * Enables gzip/deflate compression for responses larger than threshold.
 * Uses Bun's native compression when available.
 * 
 * Note: In production, this is typically handled by a reverse proxy (nginx/cloudflare),
 * but this provides compression for direct API access during development.
 */

const COMPRESSION_THRESHOLD = 1024 // 1KB minimum size to compress
const COMPRESSIBLE_TYPES = [
  'application/json',
  'text/plain',
  'text/html',
  'text/css',
  'application/javascript',
  'text/javascript',
  'application/xml',
  'text/xml',
]

export const compression = new Elysia({ name: 'compression' })
  .onAfterHandle(async ({ request, set, response }) => {
    // Skip if no response body
    if (!response) return response
    
    // Get accepted encodings from client
    const acceptEncoding = request.headers.get('accept-encoding') || ''
    const supportsGzip = acceptEncoding.includes('gzip')
    const supportsDeflate = acceptEncoding.includes('deflate')
    
    // Skip if client doesn't support compression
    if (!supportsGzip && !supportsDeflate) return response
    
    // Get content type
    const contentType = typeof set.headers === 'object' && set.headers !== null
      ? (set.headers as Record<string, string>)['content-type'] || 'application/json'
      : 'application/json'
    
    // Skip if content type is not compressible
    const isCompressible = COMPRESSIBLE_TYPES.some(type => contentType.includes(type))
    if (!isCompressible) return response
    
    // Convert response to string to check size
    let body: string
    if (typeof response === 'string') {
      body = response
    } else if (typeof response === 'object') {
      body = JSON.stringify(response)
    } else {
      return response
    }
    
    // Skip if body is too small
    if (body.length < COMPRESSION_THRESHOLD) return response
    
    // Use Bun's built-in compression
    try {
      const encoder = new TextEncoder()
      const data = encoder.encode(body)
      
      if (supportsGzip) {
        const compressed = Bun.gzipSync(data)
        set.headers = {
          ...set.headers,
          'content-encoding': 'gzip',
          'vary': 'accept-encoding',
        }
        return new Response(compressed, {
          headers: {
            'content-type': contentType,
            'content-encoding': 'gzip',
            'vary': 'accept-encoding',
          },
        })
      } else if (supportsDeflate) {
        const compressed = Bun.deflateSync(data)
        set.headers = {
          ...set.headers,
          'content-encoding': 'deflate',
          'vary': 'accept-encoding',
        }
        return new Response(compressed, {
          headers: {
            'content-type': contentType,
            'content-encoding': 'deflate',
            'vary': 'accept-encoding',
          },
        })
      }
    } catch (error) {
      // If compression fails, return original response
      console.error('Compression failed:', error)
    }
    
    return response
  })

