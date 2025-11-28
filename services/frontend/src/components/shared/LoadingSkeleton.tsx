/**
 * LoadingSkeleton Components
 *
 * Skeleton loading states for different content types.
 * Uses CSS animations for smooth pulse effect.
 *
 * Design System: Tailwind CSS with custom animations
 * Accessibility: Uses aria-busy for screen readers
 */

import { cn } from '@/lib/utils'

interface SkeletonProps {
  className?: string
}

/**
 * Base skeleton element with pulse animation
 */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-slate-200', className)}
      aria-hidden="true"
    />
  )
}

/**
 * Product card skeleton for catalog loading
 */
export function ProductCardSkeleton() {
  return (
    <div
      className="bg-white rounded-xl shadow-md overflow-hidden border border-border"
      aria-busy="true"
      aria-label="Loading product"
    >
      {/* Image placeholder */}
      <Skeleton className="h-48 w-full rounded-none" />

      <div className="p-4 space-y-3">
        {/* Category badge */}
        <Skeleton className="h-5 w-20 rounded-full" />

        {/* Title */}
        <Skeleton className="h-5 w-3/4" />

        {/* SKU */}
        <Skeleton className="h-4 w-1/3" />

        {/* Price and supplier count */}
        <div className="flex items-center justify-between pt-2">
          <Skeleton className="h-7 w-24" />
          <Skeleton className="h-5 w-16" />
        </div>
      </div>
    </div>
  )
}

/**
 * Product grid skeleton for catalog loading
 */
export function ProductGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6"
      role="status"
      aria-label="Loading products"
    >
      {Array.from({ length: count }).map((_, i) => (
        <ProductCardSkeleton key={i} />
      ))}
      <span className="sr-only">Loading products...</span>
    </div>
  )
}

/**
 * Filter bar skeleton
 */
export function FilterBarSkeleton() {
  return (
    <div
      className="flex flex-col sm:flex-row gap-4 p-4 bg-white rounded-lg shadow-sm border border-border"
      aria-busy="true"
    >
      {/* Search input */}
      <Skeleton className="h-10 flex-1 max-w-md" />

      {/* Category dropdown */}
      <Skeleton className="h-10 w-40" />

      {/* Price range */}
      <div className="flex gap-2 items-center">
        <Skeleton className="h-10 w-24" />
        <span className="text-slate-400">—</span>
        <Skeleton className="h-10 w-24" />
      </div>
    </div>
  )
}

/**
 * Table row skeleton for admin views
 */
export function TableRowSkeleton({ columns = 5 }: { columns?: number }) {
  return (
    <tr className="border-b border-border">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="p-4">
          <Skeleton className="h-5 w-full" />
        </td>
      ))}
    </tr>
  )
}

/**
 * Table skeleton for admin views
 */
export function TableSkeleton({
  rows = 5,
  columns = 5,
}: {
  rows?: number
  columns?: number
}) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-border overflow-hidden">
      <table className="w-full" aria-busy="true">
        <thead className="bg-slate-50">
          <tr>
            {Array.from({ length: columns }).map((_, i) => (
              <th key={i} className="p-4 text-left">
                <Skeleton className="h-4 w-20" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <TableRowSkeleton key={i} columns={columns} />
          ))}
        </tbody>
      </table>
      <span className="sr-only">Loading table data...</span>
    </div>
  )
}

/**
 * Product detail page skeleton
 */
export function ProductDetailSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading product details">
      {/* Back button */}
      <Skeleton className="h-9 w-24" />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Image */}
        <Skeleton className="h-80 lg:h-96 rounded-xl" />

        {/* Details */}
        <div className="space-y-4">
          <Skeleton className="h-6 w-24 rounded-full" />
          <Skeleton className="h-8 w-3/4" />
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-10 w-32" />

          <div className="pt-4 space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-4/6" />
          </div>

          <div className="pt-6">
            <Skeleton className="h-12 w-40" />
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Generic loading skeleton with customizable height
 * Alias for Skeleton with default styles
 */
export function LoadingSkeleton({ className }: SkeletonProps) {
  return <Skeleton className={className} />
}

