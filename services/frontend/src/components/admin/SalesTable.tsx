/**
 * SalesTable Component
 *
 * TanStack Table implementation for the sales internal catalog.
 * Displays products with columns: name, SKU, selling price, cost price, margin%, category, status.
 * Features sortable columns and clickable rows for navigation to product detail.
 *
 * Design System: Tailwind CSS with clean, professional table styling
 * Accessibility: Semantic HTML table, keyboard navigation for sorting
 */

import { useMemo, useState } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import type { AdminProduct } from '@/lib/api-client'

// =============================================================================
// Icons
// =============================================================================

const SortAscIcon = () => (
  <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
  </svg>
)

const SortDescIcon = () => (
  <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
  </svg>
)

const SortNoneIcon = () => (
  <svg className="w-4 h-4 ml-1 opacity-0 group-hover:opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
  </svg>
)

// =============================================================================
// Types
// =============================================================================

interface SalesTableProps {
  /** Products with pricing data */
  products: AdminProduct[]
  /** Loading state */
  isLoading?: boolean
  /** Callback when row is clicked */
  onRowClick?: (product: AdminProduct) => void
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Get the lowest price from supplier items
 */
function getLowestPrice(product: AdminProduct): number {
  if (!product.supplier_items || product.supplier_items.length === 0) {
    return 0
  }
  const prices = product.supplier_items.map(item => parseFloat(item.current_price))
  return Math.min(...prices)
}

/**
 * Format currency display
 */
function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value)
}

/**
 * Format margin percentage with color coding
 */
function formatMargin(margin: number | null): { text: string; className: string } {
  if (margin === null) {
    return { text: '—', className: 'text-slate-400' }
  }
  
  const text = `${margin.toFixed(1)}%`
  
  if (margin < 10) {
    return { text, className: 'text-danger font-medium' }
  } else if (margin < 20) {
    return { text, className: 'text-amber-600 font-medium' }
  } else {
    return { text, className: 'text-success font-medium' }
  }
}

/**
 * Get status badge styling
 */
function getStatusBadge(status: AdminProduct['status']): { text: string; className: string } {
  switch (status) {
    case 'active':
      return { 
        text: 'Active', 
        className: 'bg-success/10 text-success border-success/20' 
      }
    case 'draft':
      return { 
        text: 'Draft', 
        className: 'bg-slate-100 text-slate-600 border-slate-200' 
      }
    case 'archived':
      return { 
        text: 'Archived', 
        className: 'bg-slate-100 text-slate-400 border-slate-200' 
      }
    default:
      return { 
        text: status, 
        className: 'bg-slate-100 text-slate-500 border-slate-200' 
      }
  }
}

// =============================================================================
// Component
// =============================================================================

export function SalesTable({ products, isLoading = false, onRowClick }: SalesTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])

  // Define columns with sorting
  const columns = useMemo<ColumnDef<AdminProduct>[]>(
    () => [
      {
        accessorKey: 'name',
        header: 'Product Name',
        cell: ({ row }) => (
          <div className="flex flex-col">
            <span className="font-medium text-slate-900">{row.original.name}</span>
            <span className="text-xs text-slate-500 mt-0.5">
              {row.original.supplier_items?.length || 0} supplier{row.original.supplier_items?.length !== 1 ? 's' : ''}
            </span>
          </div>
        ),
        enableSorting: true,
      },
      {
        accessorKey: 'internal_sku',
        header: 'SKU',
        cell: ({ row }) => (
          <span className="font-mono text-sm text-slate-600">
            {row.original.internal_sku}
          </span>
        ),
        enableSorting: true,
      },
      {
        id: 'selling_price',
        header: 'Selling Price',
        accessorFn: (row) => getLowestPrice(row),
        cell: ({ row }) => {
          const price = getLowestPrice(row.original)
          return (
            <span className="font-medium text-slate-900">
              {price > 0 ? formatCurrency(price) : '—'}
            </span>
          )
        },
        enableSorting: true,
      },
      {
        id: 'cost_price',
        header: 'Cost Price',
        accessorFn: (row) => getLowestPrice(row),
        cell: ({ row }) => {
          const price = getLowestPrice(row.original)
          return (
            <span className="text-slate-600">
              {price > 0 ? formatCurrency(price) : '—'}
            </span>
          )
        },
        enableSorting: true,
      },
      {
        accessorKey: 'margin_percentage',
        header: 'Margin',
        cell: ({ row }) => {
          const { text, className } = formatMargin(row.original.margin_percentage)
          return <span className={className}>{text}</span>
        },
        enableSorting: true,
      },
      {
        accessorKey: 'category_id',
        header: 'Category',
        cell: ({ row }) => (
          <span className="text-slate-600 text-sm">
            {row.original.category_id || '—'}
          </span>
        ),
        enableSorting: true,
      },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => {
          const { text, className } = getStatusBadge(row.original.status)
          return (
            <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium border ${className}`}>
              {text}
            </span>
          )
        },
        enableSorting: true,
      },
    ],
    []
  )

  // Initialize TanStack Table
  const table = useReactTable({
    data: products,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-slate-50">
              <tr>
                {['Product Name', 'SKU', 'Selling Price', 'Cost Price', 'Margin', 'Category', 'Status'].map((header) => (
                  <th key={header} className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-border">
              {Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 7 }).map((_, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-5 bg-slate-100 rounded animate-pulse" style={{ width: `${60 + Math.random() * 40}%` }} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  // Empty state
  if (products.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-border p-8 text-center">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-slate-100 mb-4">
          <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
        </div>
        <h3 className="text-lg font-medium text-slate-900 mb-1">No products found</h3>
        <p className="text-slate-500">Try adjusting your filters or search criteria.</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg border border-border overflow-hidden shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-border">
          <thead className="bg-slate-50">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className={`px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider ${
                      header.column.getCanSort() ? 'cursor-pointer select-none hover:bg-slate-100 transition-colors group' : ''
                    }`}
                    onClick={header.column.getToggleSortingHandler()}
                    aria-sort={
                      header.column.getIsSorted() === 'asc'
                        ? 'ascending'
                        : header.column.getIsSorted() === 'desc'
                        ? 'descending'
                        : 'none'
                    }
                  >
                    <div className="flex items-center">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getCanSort() && (
                        <>
                          {header.column.getIsSorted() === 'asc' ? (
                            <SortAscIcon />
                          ) : header.column.getIsSorted() === 'desc' ? (
                            <SortDescIcon />
                          ) : (
                            <SortNoneIcon />
                          )}
                        </>
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white divide-y divide-border">
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className={`hover:bg-slate-50 transition-colors ${onRowClick ? 'cursor-pointer' : ''}`}
                onClick={() => onRowClick?.(row.original)}
                tabIndex={onRowClick ? 0 : undefined}
                onKeyDown={(e) => {
                  if (onRowClick && (e.key === 'Enter' || e.key === ' ')) {
                    e.preventDefault()
                    onRowClick(row.original)
                  }
                }}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-3 whitespace-nowrap">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

