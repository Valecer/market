/**
 * SupplierStatusTable Component
 *
 * Sortable table displaying all suppliers with their sync status.
 * Shows: Name, Source Type, Last Sync, Status (color-coded), Items Count.
 * Inactive suppliers are visually distinguished.
 *
 * Design System: Tailwind CSS v4.1
 * Accessibility: WCAG 2.1 Level AA
 * i18n: All text content uses useTranslation
 *
 * @see /specs/006-admin-sync-scheduler/spec.md
 */

import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import type { SupplierStatusTableProps, SupplierStatus, SupplierSyncStatus } from '@/types/ingestion'

// =============================================================================
// Types
// =============================================================================

type SortField = 'name' | 'source_type' | 'last_sync_at' | 'status' | 'items_count'
type SortDirection = 'asc' | 'desc'

// =============================================================================
// Constants
// =============================================================================

/**
 * Status badge configuration
 */
const STATUS_CONFIG: Record<
  SupplierSyncStatus,
  { bgColor: string; textColor: string; dotColor: string }
> = {
  success: {
    bgColor: 'bg-emerald-100',
    textColor: 'text-emerald-800',
    dotColor: 'bg-emerald-500',
  },
  error: {
    bgColor: 'bg-red-100',
    textColor: 'text-red-800',
    dotColor: 'bg-red-500',
  },
  pending: {
    bgColor: 'bg-amber-100',
    textColor: 'text-amber-800',
    dotColor: 'bg-amber-500',
  },
  inactive: {
    bgColor: 'bg-slate-100',
    textColor: 'text-slate-500',
    dotColor: 'bg-slate-400',
  },
}

// =============================================================================
// Icons
// =============================================================================

const SortIcon = ({ direction }: { direction: SortDirection | null }) => (
  <svg
    className={`w-4 h-4 transition-transform ${direction === 'desc' ? 'rotate-180' : ''}`}
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
    aria-hidden="true"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M7 11l5-5m0 0l5 5m-5-5v12"
    />
  </svg>
)

const DatabaseIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    stroke="currentColor"
    viewBox="0 0 24 24"
    aria-hidden="true"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"
    />
  </svg>
)

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Format timestamp for display
 */
function formatTimestamp(isoString: string | null): string {
  if (!isoString) return '—'
  try {
    const date = new Date(isoString)
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return '—'
  }
}

/**
 * Sort comparison function
 */
function compareSuppliers(
  a: SupplierStatus,
  b: SupplierStatus,
  field: SortField,
  direction: SortDirection
): number {
  let comparison = 0

  switch (field) {
    case 'name':
      comparison = a.name.localeCompare(b.name)
      break
    case 'source_type':
      comparison = a.source_type.localeCompare(b.source_type)
      break
    case 'last_sync_at':
      const dateA = a.last_sync_at ? new Date(a.last_sync_at).getTime() : 0
      const dateB = b.last_sync_at ? new Date(b.last_sync_at).getTime() : 0
      comparison = dateA - dateB
      break
    case 'status':
      const statusOrder = { error: 0, pending: 1, success: 2, inactive: 3 }
      comparison = statusOrder[a.status] - statusOrder[b.status]
      break
    case 'items_count':
      comparison = a.items_count - b.items_count
      break
  }

  return direction === 'asc' ? comparison : -comparison
}

// =============================================================================
// Header Component
// =============================================================================

interface SortableHeaderProps {
  label: string
  field: SortField
  currentSort: SortField
  direction: SortDirection
  onSort: (field: SortField) => void
  align?: 'left' | 'right'
}

function SortableHeader({
  label,
  field,
  currentSort,
  direction,
  onSort,
  align = 'left',
}: SortableHeaderProps) {
  const isActive = currentSort === field

  return (
    <th
      className={`px-4 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider cursor-pointer hover:bg-slate-100 transition-colors select-none ${
        align === 'right' ? 'text-right' : 'text-left'
      }`}
      onClick={() => onSort(field)}
      role="columnheader"
      aria-sort={isActive ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <div
        className={`flex items-center gap-1 ${align === 'right' ? 'justify-end' : ''}`}
      >
        {label}
        <span className={isActive ? 'text-primary' : 'text-slate-300'}>
          <SortIcon direction={isActive ? direction : null} />
        </span>
      </div>
    </th>
  )
}

// =============================================================================
// Status Badge Component
// =============================================================================

interface StatusBadgeProps {
  status: SupplierSyncStatus
  label: string
}

function StatusBadge({ status, label }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status]

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.bgColor} ${config.textColor}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dotColor}`} />
      {label}
    </span>
  )
}

// =============================================================================
// Main Component
// =============================================================================

/**
 * SupplierStatusTable - Sortable supplier sync status table
 */
export function SupplierStatusTable({ suppliers, isLoading }: SupplierStatusTableProps) {
  const { t } = useTranslation()

  // Sort state
  const [sortField, setSortField] = useState<SortField>('name')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')

  // Handle sort click
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  // Sorted suppliers
  const sortedSuppliers = useMemo(() => {
    return [...suppliers].sort((a, b) => compareSuppliers(a, b, sortField, sortDirection))
  }, [suppliers, sortField, sortDirection])

  return (
    <div className="bg-white rounded-xl shadow-md border border-border overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border bg-slate-50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg text-primary">
            <DatabaseIcon />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              {t('ingestion.suppliers', 'Suppliers')}
            </h3>
            <p className="text-sm text-slate-500">
              {t('suppliers.count', { count: suppliers.length })}
            </p>
          </div>
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
        </div>
      ) : suppliers.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center px-4">
          <div className="p-3 bg-slate-100 rounded-full mb-3">
            <DatabaseIcon />
          </div>
          <p className="text-slate-500 text-sm">{t('suppliers.noSuppliers')}</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-slate-50">
              <tr>
                <SortableHeader
                  label={t('common.name')}
                  field="name"
                  currentSort={sortField}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <SortableHeader
                  label={t('ingestion.sourceType')}
                  field="source_type"
                  currentSort={sortField}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <SortableHeader
                  label={t('ingestion.lastSync')}
                  field="last_sync_at"
                  currentSort={sortField}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <SortableHeader
                  label={t('ingestion.status')}
                  field="status"
                  currentSort={sortField}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <SortableHeader
                  label={t('ingestion.itemsCount')}
                  field="items_count"
                  currentSort={sortField}
                  direction={sortDirection}
                  onSort={handleSort}
                  align="right"
                />
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-white">
              {sortedSuppliers.map((supplier) => (
                <tr
                  key={supplier.id}
                  className={`transition-colors ${
                    supplier.status === 'inactive'
                      ? 'bg-slate-50/50 opacity-60'
                      : supplier.status === 'error'
                      ? 'bg-red-50/30 hover:bg-red-50/50'
                      : 'hover:bg-slate-50'
                  }`}
                >
                  {/* Name */}
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span
                      className={`text-sm font-medium ${
                        supplier.status === 'inactive'
                          ? 'text-slate-400 line-through'
                          : 'text-slate-900'
                      }`}
                    >
                      {supplier.name}
                    </span>
                  </td>

                  {/* Source Type */}
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-slate-500">
                    {t(`suppliers.sourceTypes.${supplier.source_type}`, supplier.source_type)}
                  </td>

                  {/* Last Sync */}
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-slate-500">
                    {formatTimestamp(supplier.last_sync_at)}
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3 whitespace-nowrap">
                    <StatusBadge
                      status={supplier.status}
                      label={t(`ingestion.supplierStatus.${supplier.status}`)}
                    />
                  </td>

                  {/* Items Count */}
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-slate-600 text-right font-medium">
                    {supplier.items_count.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

