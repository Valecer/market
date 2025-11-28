/**
 * Input Component
 *
 * Reusable text input with label, error state, and helper text.
 * Follows constitution principles: Single Responsibility, Design System Consistency.
 *
 * Design System: Tailwind CSS + Custom theme variables
 * Accessibility: Labels, ARIA attributes, error announcements
 */

import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
} from 'react'

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  /** Label text displayed above the input */
  label?: string
  /** Error message - triggers error styling when present */
  error?: string
  /** Helper text displayed below the input */
  helperText?: string
  /** Input size variant */
  size?: 'sm' | 'md' | 'lg'
  /** Icon to display at the start of input */
  startIcon?: ReactNode
  /** Icon to display at the end of input */
  endIcon?: ReactNode
  /** Full width input */
  fullWidth?: boolean
}

const sizeStyles = {
  sm: {
    input: 'h-8 text-sm px-3',
    label: 'text-xs',
    helper: 'text-xs',
    iconWrapper: 'px-2.5',
  },
  md: {
    input: 'h-10 text-sm px-3',
    label: 'text-sm',
    helper: 'text-sm',
    iconWrapper: 'px-3',
  },
  lg: {
    input: 'h-12 text-base px-4',
    label: 'text-base',
    helper: 'text-sm',
    iconWrapper: 'px-3.5',
  },
}

/**
 * Input component with label, error, and helper text support.
 *
 * @example
 * // Basic input with label
 * <Input label="Email" type="email" placeholder="Enter your email" />
 *
 * @example
 * // Input with error
 * <Input label="Password" type="password" error="Password is required" />
 *
 * @example
 * // Input with helper text
 * <Input label="Username" helperText="Must be at least 3 characters" />
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      helperText,
      size = 'md',
      startIcon,
      endIcon,
      fullWidth = false,
      disabled,
      className = '',
      id: providedId,
      'aria-describedby': ariaDescribedBy,
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

        {/* Input wrapper */}
        <div className="relative">
          {/* Start icon */}
          {startIcon && (
            <span
              className={`
                absolute left-0 top-0 bottom-0 flex items-center justify-center
                text-slate-400 pointer-events-none
                ${styles.iconWrapper}
              `.trim().replace(/\s+/g, ' ')}
              aria-hidden="true"
            >
              {startIcon}
            </span>
          )}

          {/* Input element */}
          <input
            ref={ref}
            id={id}
            disabled={disabled}
            aria-invalid={hasError}
            aria-describedby={describedByIds}
            className={`
              w-full
              rounded-lg
              border
              bg-white
              text-slate-900
              placeholder:text-slate-400
              transition-all duration-200
              focus:outline-none focus:ring-2 focus:ring-offset-0
              disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400
              dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500
              ${hasError
                ? 'border-danger focus:border-danger focus:ring-danger/20'
                : 'border-border hover:border-slate-400 focus:border-primary focus:ring-primary/20'
              }
              ${startIcon ? 'pl-10' : ''}
              ${endIcon ? 'pr-10' : ''}
              ${styles.input}
              ${className}
            `.trim().replace(/\s+/g, ' ')}
            {...props}
          />

          {/* End icon */}
          {endIcon && (
            <span
              className={`
                absolute right-0 top-0 bottom-0 flex items-center justify-center
                text-slate-400 pointer-events-none
                ${styles.iconWrapper}
              `.trim().replace(/\s+/g, ' ')}
              aria-hidden="true"
            >
              {endIcon}
            </span>
          )}
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

Input.displayName = 'Input'

export type { InputProps }

