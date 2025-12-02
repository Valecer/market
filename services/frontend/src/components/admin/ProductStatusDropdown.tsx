/**
 * ProductStatusDropdown Component
 *
 * Dropdown for changing product status (draft, active, archived).
 * Used in SalesTable for inline status updates.
 *
 * Design System: Tailwind CSS with clean dropdown styling
 * Accessibility: Keyboard navigation, proper ARIA attributes
 * i18n: All text content is translatable
 */

import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import type { ProductStatus } from '@/lib/api-client'

// =============================================================================
// Icons
// =============================================================================

const ChevronDownIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
  </svg>
)

const CheckIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
)

const LoadingSpinner = () => (
  <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
  </svg>
)

// =============================================================================
// Types
// =============================================================================

interface ProductStatusDropdownProps {
  currentStatus: ProductStatus
  productId: string
  onStatusChange: (productId: string, newStatus: ProductStatus) => Promise<void>
  disabled?: boolean
  size?: 'sm' | 'md'
}

interface StatusOption {
  value: ProductStatus
  labelKey: string
  colorClass: string
  bgClass: string
}

// =============================================================================
// Constants
// =============================================================================

const STATUS_OPTIONS: StatusOption[] = [
  {
    value: 'draft',
    labelKey: 'admin.status.draft',
    colorClass: 'text-slate-600',
    bgClass: 'bg-slate-100 hover:bg-slate-200',
  },
  {
    value: 'active',
    labelKey: 'admin.status.active',
    colorClass: 'text-emerald-700',
    bgClass: 'bg-emerald-100 hover:bg-emerald-200',
  },
  {
    value: 'archived',
    labelKey: 'admin.status.archived',
    colorClass: 'text-slate-500',
    bgClass: 'bg-slate-100 hover:bg-slate-200',
  },
]

// =============================================================================
// Component
// =============================================================================

export function ProductStatusDropdown({
  currentStatus,
  productId,
  onStatusChange,
  disabled = false,
  size = 'sm',
}: ProductStatusDropdownProps) {
  const { t } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Handle keyboard navigation
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (!isOpen) return

      if (event.key === 'Escape') {
        setIsOpen(false)
        buttonRef.current?.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen])

  const currentOption = STATUS_OPTIONS.find(opt => opt.value === currentStatus) ?? STATUS_OPTIONS[0]

  const handleStatusSelect = async (status: ProductStatus) => {
    if (status === currentStatus) {
      setIsOpen(false)
      return
    }

    setIsLoading(true)
    try {
      await onStatusChange(productId, status)
    } finally {
      setIsLoading(false)
      setIsOpen(false)
    }
  }

  const sizeClasses = size === 'sm' 
    ? 'px-2 py-1 text-xs' 
    : 'px-3 py-1.5 text-sm'

  return (
    <div ref={dropdownRef} className="relative inline-block">
      <button
        ref={buttonRef}
        onClick={(e) => {
          e.stopPropagation() // Prevent row click
          if (!disabled && !isLoading) setIsOpen(!isOpen)
        }}
        disabled={disabled || isLoading}
        className={`
          inline-flex items-center gap-1.5 rounded-full font-medium border transition-colors
          ${sizeClasses}
          ${currentOption.bgClass}
          ${currentOption.colorClass}
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          focus:outline-none focus:ring-2 focus:ring-primary/50
        `}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        {isLoading ? (
          <LoadingSpinner />
        ) : (
          <>
            {t(currentOption.labelKey)}
            <ChevronDownIcon />
          </>
        )}
      </button>

      {isOpen && (
        <div
          className="absolute z-50 mt-1 w-32 rounded-md bg-white shadow-lg border border-border py-1"
          role="listbox"
          style={{ right: 0 }}
        >
          {STATUS_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={(e) => {
                e.stopPropagation()
                handleStatusSelect(option.value)
              }}
              className={`
                w-full px-3 py-2 text-left text-sm flex items-center justify-between
                hover:bg-slate-50 transition-colors
                ${option.value === currentStatus ? option.colorClass : 'text-slate-700'}
              `}
              role="option"
              aria-selected={option.value === currentStatus}
            >
              {t(option.labelKey)}
              {option.value === currentStatus && <CheckIcon />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}



