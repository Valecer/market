/**
 * Select Component
 *
 * Reusable dropdown select with label, error state, and helper text.
 * Follows constitution principles: Single Responsibility, Design System Consistency.
 *
 * Design System: Tailwind CSS + Custom theme variables
 * Accessibility: Labels, ARIA attributes, keyboard navigation
 */

import {
  forwardRef,
  useId,
  type SelectHTMLAttributes,
  type ReactNode,
} from 'react'

interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  /** Label text displayed above the select */
  label?: string
  /** Error message - triggers error styling when present */
  error?: string
  /** Helper text displayed below the select */
  helperText?: string
  /** Select size variant */
  size?: 'sm' | 'md' | 'lg'
  /** Placeholder option text */
  placeholder?: string
  /** Options to display */
  options?: SelectOption[]
  /** Full width select */
  fullWidth?: boolean
  /** Children (alternative to options prop) */
  children?: ReactNode
}

const sizeStyles = {
  sm: {
    select: 'h-8 text-sm pl-3 pr-8',
    label: 'text-xs',
    helper: 'text-xs',
  },
  md: {
    select: 'h-10 text-sm pl-3 pr-10',
    label: 'text-sm',
    helper: 'text-sm',
  },
  lg: {
    select: 'h-12 text-base pl-4 pr-10',
    label: 'text-base',
    helper: 'text-sm',
  },
}

/**
 * Select component with label, error, and helper text support.
 *
 * @example
 * // Basic select with options
 * <Select
 *   label="Country"
 *   placeholder="Select a country"
 *   options={[
 *     { value: 'us', label: 'United States' },
 *     { value: 'uk', label: 'United Kingdom' },
 *   ]}
 * />
 *
 * @example
 * // Select with error
 * <Select label="Category" error="Please select a category" options={categories} />
 *
 * @example
 * // Select with children
 * <Select label="Status">
 *   <option value="active">Active</option>
 *   <option value="inactive">Inactive</option>
 * </Select>
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      label,
      error,
      helperText,
      size = 'md',
      placeholder,
      options,
      fullWidth = false,
      disabled,
      className = '',
      id: providedId,
      'aria-describedby': ariaDescribedBy,
      children,
      ...props
    },
    ref
  ) => {
    const generatedId = useId()
    const id = providedId || generatedId
    const errorId = `${id}-error`
    const helperId = `${id}-helper`
    const styles = sizeStyles[size]

    const hasError = Boolean(error)
    const showHelperText = helperText && !hasError

    // Build aria-describedby
    const describedByIds = [
      ariaDescribedBy,
      hasError ? errorId : null,
      showHelperText ? helperId : null,
    ]
      .filter(Boolean)
      .join(' ') || undefined

    return (
      <div className={`flex flex-col gap-1.5 ${fullWidth ? 'w-full' : ''}`}>
        {/* Label */}
        {label && (
          <label
            htmlFor={id}
            className={`
              font-medium text-slate-700
              dark:text-slate-300
              ${styles.label}
              ${disabled ? 'opacity-50' : ''}
            `.trim().replace(/\s+/g, ' ')}
          >
            {label}
          </label>
        )}

        {/* Select wrapper */}
        <div className="relative">
          {/* Select element */}
          <select
            ref={ref}
            id={id}
            disabled={disabled}
            aria-invalid={hasError}
            aria-describedby={describedByIds}
            className={`
              w-full
              appearance-none
              rounded-lg
              border
              bg-white
              text-slate-900
              cursor-pointer
              transition-all duration-200
              focus:outline-none focus:ring-2 focus:ring-offset-0
              disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400
              dark:bg-slate-900 dark:text-white
              ${hasError
                ? 'border-danger focus:border-danger focus:ring-danger/20'
                : 'border-border hover:border-slate-400 focus:border-primary focus:ring-primary/20'
              }
              ${styles.select}
              ${className}
            `.trim().replace(/\s+/g, ' ')}
            {...props}
          >
            {/* Placeholder option */}
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}

            {/* Options from prop */}
            {options?.map((option) => (
              <option
                key={option.value}
                value={option.value}
                disabled={option.disabled}
              >
                {option.label}
              </option>
            ))}

            {/* Children options */}
            {children}
          </select>

          {/* Dropdown arrow */}
          <span
            className={`
              absolute right-0 top-0 bottom-0 flex items-center justify-center
              pointer-events-none
              ${size === 'lg' ? 'pr-3.5' : 'pr-3'}
              ${disabled ? 'text-slate-300' : 'text-slate-500'}
            `.trim().replace(/\s+/g, ' ')}
            aria-hidden="true"
          >
            <svg
              className={`${size === 'lg' ? 'h-5 w-5' : 'h-4 w-4'}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </span>
        </div>

        {/* Error message */}
        {hasError && (
          <p
            id={errorId}
            role="alert"
            aria-live="polite"
            className={`
              flex items-center gap-1.5
              text-danger
              ${styles.helper}
            `.trim().replace(/\s+/g, ' ')}
          >
            <svg
              className="h-4 w-4 shrink-0"
              fill="currentColor"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
            {error}
          </p>
        )}

        {/* Helper text */}
        {showHelperText && (
          <p
            id={helperId}
            className={`
              text-muted
              ${styles.helper}
            `.trim().replace(/\s+/g, ' ')}
          >
            {helperText}
          </p>
        )}
      </div>
    )
  }
)

Select.displayName = 'Select'

export type { SelectProps, SelectOption }

