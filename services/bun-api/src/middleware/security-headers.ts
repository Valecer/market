import { Elysia } from 'elysia'

/**
 * Security headers middleware (Helmet-like functionality)
 * 
 * Adds various HTTP headers to help protect against common web vulnerabilities:
 * - XSS (Cross-Site Scripting)
 * - Clickjacking
 * - MIME-type sniffing
 * - Information disclosure
 * 
 * Based on OWASP security header recommendations.
 */

export interface SecurityHeadersOptions {
  /** Enable/disable Strict-Transport-Security header (default: true in production) */
  hsts?: boolean
  /** HSTS max-age in seconds (default: 31536000 = 1 year) */
  hstsMaxAge?: number
  /** Enable/disable X-Frame-Options header (default: true) */
  frameGuard?: boolean
  /** Frame options value (default: 'DENY') */
  frameOptions?: 'DENY' | 'SAMEORIGIN'
  /** Enable/disable X-Content-Type-Options header (default: true) */
  noSniff?: boolean
  /** Enable/disable X-XSS-Protection header (default: true) */
  xssFilter?: boolean
  /** Enable/disable Referrer-Policy header (default: true) */
  referrerPolicy?: boolean
  /** Referrer policy value (default: 'strict-origin-when-cross-origin') */
  referrerPolicyValue?: string
  /** Enable/disable X-Permitted-Cross-Domain-Policies header (default: true) */
  crossDomainPolicy?: boolean
  /** Enable/disable Content-Security-Policy header (default: false for API-only) */
  contentSecurityPolicy?: boolean
  /** CSP directives (default: "default-src 'self'") */
  cspDirectives?: string
  /** Enable/disable X-Download-Options header (default: true) */
  ieNoOpen?: boolean
  /** Hide X-Powered-By header (default: true) */
  hidePoweredBy?: boolean
  /** Custom headers to add */
  customHeaders?: Record<string, string>
}

const DEFAULT_OPTIONS: Required<SecurityHeadersOptions> = {
  hsts: process.env.NODE_ENV === 'production',
  hstsMaxAge: 31536000, // 1 year
  frameGuard: true,
  frameOptions: 'DENY',
  noSniff: true,
  xssFilter: true,
  referrerPolicy: true,
  referrerPolicyValue: 'strict-origin-when-cross-origin',
  crossDomainPolicy: true,
  contentSecurityPolicy: false, // Disabled by default for API-only services
  cspDirectives: "default-src 'self'",
  ieNoOpen: true,
  hidePoweredBy: true,
  customHeaders: {},
}

export const securityHeaders = (options: SecurityHeadersOptions = {}) => {
  const config = { ...DEFAULT_OPTIONS, ...options }
  
  return new Elysia({ name: 'security-headers' })
    .onBeforeHandle(({ set }) => {
      const headers: Record<string, string> = {}
      
      // HSTS - Only in production with HTTPS
      if (config.hsts) {
        headers['Strict-Transport-Security'] = `max-age=${config.hstsMaxAge}; includeSubDomains`
      }
      
      // X-Frame-Options - Prevent clickjacking
      if (config.frameGuard) {
        headers['X-Frame-Options'] = config.frameOptions
      }
      
      // X-Content-Type-Options - Prevent MIME-type sniffing
      if (config.noSniff) {
        headers['X-Content-Type-Options'] = 'nosniff'
      }
      
      // X-XSS-Protection - XSS filter (legacy browsers)
      if (config.xssFilter) {
        headers['X-XSS-Protection'] = '1; mode=block'
      }
      
      // Referrer-Policy - Control referrer information
      if (config.referrerPolicy) {
        headers['Referrer-Policy'] = config.referrerPolicyValue
      }
      
      // X-Permitted-Cross-Domain-Policies - Adobe Flash/Acrobat
      if (config.crossDomainPolicy) {
        headers['X-Permitted-Cross-Domain-Policies'] = 'none'
      }
      
      // Content-Security-Policy
      if (config.contentSecurityPolicy) {
        headers['Content-Security-Policy'] = config.cspDirectives
      }
      
      // X-Download-Options - IE specific
      if (config.ieNoOpen) {
        headers['X-Download-Options'] = 'noopen'
      }
      
      // Permissions-Policy - Control browser features (modern replacement for Feature-Policy)
      headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
      
      // Cache-Control for API responses (prevent caching of sensitive data)
      headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate'
      headers['Pragma'] = 'no-cache'
      headers['Expires'] = '0'
      
      // Add custom headers
      Object.assign(headers, config.customHeaders)
      
      // Apply all headers
      set.headers = {
        ...set.headers,
        ...headers,
      }
      
      // Remove X-Powered-By if configured
      if (config.hidePoweredBy && set.headers) {
        delete (set.headers as Record<string, string>)['X-Powered-By']
        delete (set.headers as Record<string, string>)['x-powered-by']
      }
    })
}

// Default export with sensible defaults
export const defaultSecurityHeaders = securityHeaders()

