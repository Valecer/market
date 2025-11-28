#!/usr/bin/env bun
/**
 * Performance benchmarking script for admin endpoints
 * 
 * Tests admin endpoints with various loads to verify
 * p95 response times meet the target of < 1000ms.
 * 
 * Usage:
 *   bun run scripts/benchmark-admin.ts [--url=<url>] [--requests=<n>] [--concurrency=<c>] [--token=<jwt>]
 * 
 * Options:
 *   --url         Base URL of the API (default: http://localhost:3000)
 *   --requests    Total number of requests (default: 500)
 *   --concurrency Concurrent requests (default: 20)
 *   --token       JWT token for authentication (required)
 *   --username    Username for login (default: admin)
 *   --password    Password for login (default: admin123)
 */

interface BenchmarkResult {
  endpoint: string
  totalRequests: number
  successfulRequests: number
  failedRequests: number
  totalDurationMs: number
  requestsPerSecond: number
  responseTimes: {
    min: number
    max: number
    avg: number
    p50: number
    p90: number
    p95: number
    p99: number
  }
  statusCodes: Record<number, number>
  errors: string[]
}

interface RequestResult {
  durationMs: number
  statusCode: number
  success: boolean
  error?: string
}

async function makeRequest(url: string, token: string): Promise<RequestResult> {
  const start = performance.now()
  
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`,
        'User-Agent': 'Benchmark/1.0',
      },
    })
    
    const durationMs = performance.now() - start
    
    // Consume the body to ensure full request completion
    await response.text()
    
    return {
      durationMs,
      statusCode: response.status,
      success: response.status >= 200 && response.status < 400,
    }
  } catch (error) {
    const durationMs = performance.now() - start
    return {
      durationMs,
      statusCode: 0,
      success: false,
      error: error instanceof Error ? error.message : String(error),
    }
  }
}

async function login(baseUrl: string, username: string, password: string): Promise<string | null> {
  try {
    const response = await fetch(`${baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
    })
    
    if (!response.ok) {
      console.error(`Login failed: ${response.status}`)
      return null
    }
    
    const data = await response.json() as { token: string }
    return data.token
  } catch (error) {
    console.error('Login error:', error)
    return null
  }
}

function percentile(sortedArray: number[], p: number): number {
  if (sortedArray.length === 0) return 0
  const index = Math.ceil((p / 100) * sortedArray.length) - 1
  return sortedArray[Math.max(0, index)]
}

async function runEndpointBenchmark(
  baseUrl: string,
  endpoint: string,
  token: string,
  totalRequests: number,
  concurrency: number
): Promise<BenchmarkResult> {
  const results: RequestResult[] = []
  const errors: string[] = []
  const statusCodes: Record<number, number> = {}
  
  const url = `${baseUrl}${endpoint}`
  
  console.log(`\nBenchmarking: ${endpoint}`)
  console.log('-'.repeat(40))
  
  const startTime = performance.now()
  
  // Run with concurrency limit
  let completed = 0
  for (let i = 0; i < totalRequests; i += concurrency) {
    const batchSize = Math.min(concurrency, totalRequests - i)
    const batchResults = await Promise.all(
      Array(batchSize).fill(null).map(() => makeRequest(url, token))
    )
    
    results.push(...batchResults)
    
    // Track status codes and errors
    for (const result of batchResults) {
      statusCodes[result.statusCode] = (statusCodes[result.statusCode] || 0) + 1
      if (result.error) {
        errors.push(result.error)
      }
    }
    
    completed += batchSize
    const progress = Math.round((completed / totalRequests) * 100)
    process.stdout.write(`\rProgress: ${progress}% (${completed}/${totalRequests})`)
  }
  
  const totalDurationMs = performance.now() - startTime
  
  console.log('')
  
  // Calculate statistics
  const durations = results.map(r => r.durationMs).sort((a, b) => a - b)
  const successfulRequests = results.filter(r => r.success).length
  const failedRequests = results.filter(r => !r.success).length
  
  const min = Math.min(...durations)
  const max = Math.max(...durations)
  const avg = durations.reduce((sum, d) => sum + d, 0) / durations.length
  
  return {
    endpoint,
    totalRequests,
    successfulRequests,
    failedRequests,
    totalDurationMs,
    requestsPerSecond: (totalRequests / totalDurationMs) * 1000,
    responseTimes: {
      min: Math.round(min * 100) / 100,
      max: Math.round(max * 100) / 100,
      avg: Math.round(avg * 100) / 100,
      p50: Math.round(percentile(durations, 50) * 100) / 100,
      p90: Math.round(percentile(durations, 90) * 100) / 100,
      p95: Math.round(percentile(durations, 95) * 100) / 100,
      p99: Math.round(percentile(durations, 99) * 100) / 100,
    },
    statusCodes,
    errors: [...new Set(errors)].slice(0, 10),
  }
}

function printResult(result: BenchmarkResult, target: number) {
  console.log(`\n  Requests:     ${result.successfulRequests}/${result.totalRequests} successful`)
  console.log(`  RPS:          ${result.requestsPerSecond.toFixed(2)}`)
  console.log(`  p50:          ${result.responseTimes.p50}ms`)
  console.log(`  p95:          ${result.responseTimes.p95}ms`)
  console.log(`  p99:          ${result.responseTimes.p99}ms`)
  
  const pass = result.responseTimes.p95 < target
  console.log(`  Target:       < ${target}ms - ${pass ? '✅ PASS' : '❌ FAIL'}`)
  
  return pass
}

// Parse command line arguments
function parseArgs(): {
  url: string
  requests: number
  concurrency: number
  token?: string
  username: string
  password: string
} {
  const args = process.argv.slice(2)
  let url = 'http://localhost:3000'
  let requests = 500
  let concurrency = 20
  let token: string | undefined
  let username = 'admin'
  let password = 'admin123'
  
  for (const arg of args) {
    if (arg.startsWith('--url=')) {
      url = arg.slice(6)
    } else if (arg.startsWith('--requests=')) {
      requests = parseInt(arg.slice(11), 10)
    } else if (arg.startsWith('--concurrency=')) {
      concurrency = parseInt(arg.slice(14), 10)
    } else if (arg.startsWith('--token=')) {
      token = arg.slice(8)
    } else if (arg.startsWith('--username=')) {
      username = arg.slice(11)
    } else if (arg.startsWith('--password=')) {
      password = arg.slice(11)
    }
  }
  
  return { url, requests, concurrency, token, username, password }
}

// Main execution
async function main() {
  const { url, requests, concurrency, token: providedToken, username, password } = parseArgs()
  
  console.log('\n📊 Admin Endpoints Benchmark')
  console.log('='.repeat(50))
  console.log(`Base URL: ${url}`)
  console.log(`Total Requests per endpoint: ${requests}`)
  console.log(`Concurrency: ${concurrency}`)
  console.log('='.repeat(50))
  
  // Get auth token
  let token = providedToken
  if (!token) {
    console.log('\nAuthenticating...')
    token = await login(url, username, password)
    if (!token) {
      console.error('\n❌ Failed to authenticate. Provide --token or valid credentials.')
      process.exit(1)
    }
    console.log('✅ Authenticated successfully')
  }
  
  // Admin endpoints to benchmark
  const endpoints = [
    { path: '/api/v1/admin/products', target: 1000 },
    { path: '/api/v1/admin/products?page=1&limit=50', target: 1000 },
    { path: '/api/v1/admin/products?status=active', target: 1000 },
  ]
  
  const results: BenchmarkResult[] = []
  let allPassed = true
  
  for (const { path, target } of endpoints) {
    const result = await runEndpointBenchmark(url, path, token, requests, concurrency)
    results.push(result)
    
    const passed = printResult(result, target)
    if (!passed) allPassed = false
  }
  
  // Summary
  console.log('\n\n📈 Summary')
  console.log('='.repeat(50))
  console.log('\n| Endpoint | p95 | Target | Status |')
  console.log('|----------|-----|--------|--------|')
  
  for (const result of results) {
    const target = 1000
    const status = result.responseTimes.p95 < target ? '✅' : '❌'
    console.log(`| ${result.endpoint.substring(0, 35).padEnd(35)} | ${result.responseTimes.p95.toString().padStart(3)}ms | <${target}ms | ${status} |`)
  }
  
  console.log('\n' + '='.repeat(50))
  console.log(`Overall: ${allPassed ? '✅ All targets met' : '❌ Some targets not met'}`)
  
  process.exit(allPassed ? 0 : 1)
}

main().catch(error => {
  console.error('Benchmark failed:', error)
  process.exit(1)
})

