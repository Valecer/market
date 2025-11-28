#!/usr/bin/env bun
/**
 * Performance benchmarking script for catalog endpoint
 * 
 * Tests the /api/v1/catalog endpoint with various loads to verify
 * p95 response times meet the target of < 500ms.
 * 
 * Usage:
 *   bun run scripts/benchmark-catalog.ts [--url=<url>] [--requests=<n>] [--concurrency=<c>]
 * 
 * Options:
 *   --url         Base URL of the API (default: http://localhost:3000)
 *   --requests    Total number of requests (default: 1000)
 *   --concurrency Concurrent requests (default: 50)
 */

interface BenchmarkResult {
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

async function makeRequest(url: string): Promise<RequestResult> {
  const start = performance.now()
  
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
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

function percentile(sortedArray: number[], p: number): number {
  if (sortedArray.length === 0) return 0
  const index = Math.ceil((p / 100) * sortedArray.length) - 1
  return sortedArray[Math.max(0, index)]
}

async function runBenchmark(
  baseUrl: string,
  totalRequests: number,
  concurrency: number
): Promise<BenchmarkResult> {
  const results: RequestResult[] = []
  const errors: string[] = []
  const statusCodes: Record<number, number> = {}
  
  // Test scenarios for catalog endpoint
  const scenarios = [
    '/api/v1/catalog', // No filters
    '/api/v1/catalog?page=1&limit=50', // Pagination
    '/api/v1/catalog?min_price=10&max_price=100', // Price filter
    '/api/v1/catalog?search=product', // Search filter
    '/api/v1/catalog?page=1&limit=50&min_price=0', // Combined
  ]
  
  console.log('\n📊 Catalog Endpoint Benchmark')
  console.log('='.repeat(50))
  console.log(`Base URL: ${baseUrl}`)
  console.log(`Total Requests: ${totalRequests}`)
  console.log(`Concurrency: ${concurrency}`)
  console.log('='.repeat(50))
  console.log('\nRunning benchmark...\n')
  
  const startTime = performance.now()
  
  // Process requests in batches
  let completed = 0
  const requestsToRun: string[] = []
  
  for (let i = 0; i < totalRequests; i++) {
    const scenario = scenarios[i % scenarios.length]
    requestsToRun.push(`${baseUrl}${scenario}`)
  }
  
  // Run with concurrency limit
  for (let i = 0; i < requestsToRun.length; i += concurrency) {
    const batch = requestsToRun.slice(i, i + concurrency)
    const batchResults = await Promise.all(batch.map(url => makeRequest(url)))
    
    results.push(...batchResults)
    
    // Track status codes and errors
    for (const result of batchResults) {
      statusCodes[result.statusCode] = (statusCodes[result.statusCode] || 0) + 1
      if (result.error) {
        errors.push(result.error)
      }
    }
    
    completed += batch.length
    const progress = Math.round((completed / totalRequests) * 100)
    process.stdout.write(`\rProgress: ${progress}% (${completed}/${totalRequests})`)
  }
  
  const totalDurationMs = performance.now() - startTime
  
  console.log('\n')
  
  // Calculate statistics
  const durations = results.map(r => r.durationMs).sort((a, b) => a - b)
  const successfulRequests = results.filter(r => r.success).length
  const failedRequests = results.filter(r => !r.success).length
  
  const min = Math.min(...durations)
  const max = Math.max(...durations)
  const avg = durations.reduce((sum, d) => sum + d, 0) / durations.length
  
  return {
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
    errors: [...new Set(errors)].slice(0, 10), // Unique errors, max 10
  }
}

function printResults(result: BenchmarkResult) {
  console.log('\n📈 Results')
  console.log('='.repeat(50))
  
  console.log('\nRequest Summary:')
  console.log(`  Total Requests:      ${result.totalRequests}`)
  console.log(`  Successful:          ${result.successfulRequests}`)
  console.log(`  Failed:              ${result.failedRequests}`)
  console.log(`  Total Duration:      ${Math.round(result.totalDurationMs)}ms`)
  console.log(`  Requests/Second:     ${result.requestsPerSecond.toFixed(2)}`)
  
  console.log('\nResponse Times:')
  console.log(`  Min:                 ${result.responseTimes.min}ms`)
  console.log(`  Max:                 ${result.responseTimes.max}ms`)
  console.log(`  Average:             ${result.responseTimes.avg}ms`)
  console.log(`  p50 (Median):        ${result.responseTimes.p50}ms`)
  console.log(`  p90:                 ${result.responseTimes.p90}ms`)
  console.log(`  p95:                 ${result.responseTimes.p95}ms`)
  console.log(`  p99:                 ${result.responseTimes.p99}ms`)
  
  console.log('\nStatus Codes:')
  for (const [code, count] of Object.entries(result.statusCodes)) {
    console.log(`  ${code}: ${count}`)
  }
  
  if (result.errors.length > 0) {
    console.log('\nErrors:')
    result.errors.forEach(err => console.log(`  - ${err}`))
  }
  
  // Target verification
  console.log('\n🎯 Target Verification')
  console.log('='.repeat(50))
  const p95Target = 500 // ms
  const p95Pass = result.responseTimes.p95 < p95Target
  console.log(`  p95 Target:          < ${p95Target}ms`)
  console.log(`  p95 Actual:          ${result.responseTimes.p95}ms`)
  console.log(`  Status:              ${p95Pass ? '✅ PASS' : '❌ FAIL'}`)
  
  return p95Pass
}

// Parse command line arguments
function parseArgs(): { url: string; requests: number; concurrency: number } {
  const args = process.argv.slice(2)
  let url = 'http://localhost:3000'
  let requests = 1000
  let concurrency = 50
  
  for (const arg of args) {
    if (arg.startsWith('--url=')) {
      url = arg.slice(6)
    } else if (arg.startsWith('--requests=')) {
      requests = parseInt(arg.slice(11), 10)
    } else if (arg.startsWith('--concurrency=')) {
      concurrency = parseInt(arg.slice(14), 10)
    }
  }
  
  return { url, requests, concurrency }
}

// Main execution
const { url, requests, concurrency } = parseArgs()

runBenchmark(url, requests, concurrency)
  .then(result => {
    const passed = printResults(result)
    process.exit(passed ? 0 : 1)
  })
  .catch(error => {
    console.error('Benchmark failed:', error)
    process.exit(1)
  })

