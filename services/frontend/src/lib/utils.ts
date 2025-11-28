/**
 * Utility Functions
 *
 * Common helper functions used across the application.
 */

/**
 * Combine class names conditionally
 * Simple utility without clsx dependency
 */
export function cn(...inputs: (string | undefined | null | false)[]): string {
  return inputs.filter(Boolean).join(' ')
}

/**
 * Format price as currency string
 */
export function formatPrice(price: string | number): string {
  const numPrice = typeof price === 'string' ? parseFloat(price) : price
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numPrice)
}

/**
 * Debounce function for search inputs
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    timeoutId = setTimeout(() => {
      func(...args)
    }, wait)
  }
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength - 3) + '...'
}

/**
 * Generate placeholder image URL based on product name
 */
export function getPlaceholderImage(name: string): string {
  // Use a deterministic color based on name hash
  const hash = name.split('').reduce((acc, char) => {
    return char.charCodeAt(0) + ((acc << 5) - acc)
  }, 0)

  const hue = Math.abs(hash) % 360
  // Using inline SVG data URI for placeholder
  return `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='300' viewBox='0 0 400 300'%3E%3Crect fill='hsl(${hue}, 40%25, 90%25)' width='400' height='300'/%3E%3Ctext x='200' y='150' font-family='system-ui' font-size='48' fill='hsl(${hue}, 40%25, 50%25)' text-anchor='middle' dominant-baseline='middle'%3E📦%3C/text%3E%3C/svg%3E`
}

