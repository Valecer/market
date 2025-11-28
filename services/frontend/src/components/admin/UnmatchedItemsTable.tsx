/**
 * UnmatchedItemsTable Component
 *
 * TanStack Table implementation for displaying unmatched supplier items.
 * Features sortable columns, multi-select, and "Link to Product" functionality.
 *
 * Design System: Tailwind CSS with clean, professional table styling
 * Accessibility: Semantic HTML table, keyboard navigation, checkbox selection
 */

import { useMemo, useState, useCallback } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type RowSelectionState,
} from '@tanstack/react-table'
import type { UnmatchedSupplierItem } from '@/hooks/useUnmatchedItems'

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

const LinkIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
  </svg>
)

const CheckIcon = () => (
  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 12 12">
    <path d="M10.28 2.28L3.989 8.575 1.695 6.28A1 1 0 00.28 7.695l3 3a1 1 0 001.414 0l7-7A1 1 0 0010.28 2.28z" />
  </svg>
)

// =============================================================================
// Types
// =============================================================================

interface UnmatchedItemsTableProps {
  /** Unmatched supplier items to display */
  items: UnmatchedSupplierItem[]
  /** Loading state */
  isLoading?: boolean
  /** Callback when "Link to Product" is clicked (single item) */
  onLinkClick?: (item: UnmatchedSupplierItem) => void
  /** Callback when "Link Selected" is clicked (multiple items) */
  onLinkSelectedClick?: (items: UnmatchedSupplierItem[]) => void
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Format currency display
 */
function formatCurrency(value: string | number): string {
  const numValue = typeof value === 'string' ? parseFloat(value) : value
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(numValue)
}

/**
 * Format date for display
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

// =============================================================================
// Component
// =============================================================================

export function UnmatchedItemsTable({ 
  items, 
  isLoading = false, 
  onLinkClick,
  onLinkSelectedClick,
}: UnmatchedItemsTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})

  // Get selected items
  const selectedItems = useMemo(() => {
    return Object.keys(rowSelection)
      .filter((key) => rowSelection[key])
      .map((key) => items[parseInt(key)])
      .filter(Boolean)
  }, [rowSelection, items])

  const handleLinkSelected = useCallback(() => {
    if (selectedItems.length > 0 && onLinkSelectedClick) {
      onLinkSelectedClick(selectedItems)
    }
  }, [selectedItems, onLinkSelectedClick])

  const clearSelection = useCallback(() => {
    setRowSelection({})
  }, [])

  // Define columns with sorting and selection
  const columns = useMemo<ColumnDef<UnmatchedSupplierItem>[]>(
    () => [
      {
        id: 'select',
        header: ({ table }) => (
          <div className="flex items-center justify-center">
            <input
              type="checkbox"
              checked={table.getIsAllPageRowsSelected()}
              ref={(el) => {
                if (el) {
                  el.indeterminate = table.getIsSomePageRowsSelected()
                }
              }}
              onChange={table.getToggleAllPageRowsSelectedHandler()}
              className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary/50 cursor-pointer"
              aria-label="Select all items"
            />
          </div>
        ),
        cell: ({ row }) => (
          <div className="flex items-center justify-center">
            <input
              type="checkbox"
              checked={row.getIsSelected()}
              disabled={!row.getCanSelect()}
              onChange={row.getToggleSelectedHandler()}
              onClick={(e) => e.stopPropagation()}
              className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary/50 cursor-pointer disabled:opacity-50"
              aria-label={`Select ${row.original.name}`}
            />
          </div>
        ),
        enableSorting: false,
        size: 40,
      },
      {
        accessorKey: 'name',
        header: 'Item Name',
        cell: ({ row }) => (
          <div className="flex flex-col">
            <span className="font-medium text-slate-900">{row.original.name}</span>
            <span className="text-xs text-slate-500 mt-0.5 font-mono">
              {row.original.supplier_sku}
            </span>
          </div>
        ),
        enableSorting: true,
      },
      {
        accessorKey: 'supplier_name',
        header: 'Supplier',
        cell: ({ row }) => (
          <span className="text-slate-700">{row.original.supplier_name}</span>
        ),
        enableSorting: true,
      },
      {
        accessorKey: 'current_price',
        header: 'Price',
        cell: ({ row }) => (
          <span className="font-medium text-slate-900">
            {formatCurrency(row.original.current_price)}
          </span>
        ),
        enableSorting: true,
      },
      {
        accessorKey: 'last_ingested_at',
        header: 'Last Synced',
        cell: ({ row }) => (
          <span className="text-sm text-slate-500">
            {formatDate(row.original.last_ingested_at)}
          </span>
        ),
        enableSorting: true,
      },
      {
        id: 'actions',
        header: '',
        cell: ({ row }) => (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onLinkClick?.(row.original)
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-primary bg-primary/5 hover:bg-primary/10 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50"
            aria-label={`Link ${row.original.name} to a product`}
          >
            <LinkIcon />
            Link to Product
          </button>
        ),
        enableSorting: false,
      },
    ],
    [onLinkClick]
  )

  // Initialize TanStack Table with row selection
  const table = useReactTable({
    data: items,
    columns,
    state: { sorting, rowSelection },
    onSortingChange: setSorting,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    enableRowSelection: true,
  })

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-slate-50">
              <tr>
                {['', 'Item Name', 'Supplier', 'Price', 'Last Synced', ''].map((header, i) => (
                  <th key={i} className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-border">
              {Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-5 bg-slate-100 rounded animate-pulse" style={{ width: j === 0 ? '16px' : `${60 + Math.random() * 40}%` }} />
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
  if (items.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-border p-8 text-center">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-50 mb-4">
          <svg className="w-6 h-6 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h3 className="text-lg font-medium text-slate-900 mb-1">All items matched!</h3>
        <p className="text-slate-500">All supplier items have been linked to products.</p>
      </div>
    )
  }

  return (
    <div className="relative">
      {/* Floating selection action bar */}
      {selectedItems.length > 0 && (
        <div className="sticky top-0 z-10 mb-3 flex items-center justify-between gap-4 px-4 py-3 bg-primary text-white rounded-lg shadow-lg animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-6 h-6 bg-white/20 rounded-full">
              <CheckIcon />
            </div>
            <span className="font-medium">
              {selectedItems.length} item{selectedItems.length !== 1 ? 's' : ''} selected
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={clearSelection}
              className="px-3 py-1.5 text-sm font-medium text-white/80 hover:text-white hover:bg-white/10 rounded-md transition-colors"
            >
              Clear
            </button>
            <button
              type="button"
              onClick={handleLinkSelected}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium bg-white text-primary hover:bg-white/90 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-white/50"
            >
              <LinkIcon />
              Link Selected to Product
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg border border-border overflow-hidden shadow-sm">
        <div className="px-4 py-3 bg-slate-50 border-b border-border flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">
            Unmatched Items
            <span className="ml-2 text-xs font-normal text-slate-500">
              ({items.length} item{items.length !== 1 ? 's' : ''})
            </span>
          </h3>
          {items.length > 0 && (
            <span className="text-xs text-slate-500">
              Select items to link multiple at once
            </span>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-white">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      className={`px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider ${
                        header.column.getCanSort() ? 'cursor-pointer select-none hover:bg-slate-50 transition-colors group' : ''
                      } ${header.id === 'select' ? 'w-10' : ''}`}
                      onClick={header.column.getCanSort() ? header.column.getToggleSortingHandler() : undefined}
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
                  className={`transition-colors ${
                    row.getIsSelected() 
                      ? 'bg-primary/5 hover:bg-primary/10' 
                      : 'hover:bg-slate-50/50'
                  }`}
                  onClick={() => row.toggleSelected()}
                  style={{ cursor: 'pointer' }}
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
    </div>
  )
}

