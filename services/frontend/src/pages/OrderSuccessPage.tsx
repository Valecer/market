/**
 * OrderSuccessPage
 *
 * Success page shown after mock checkout completion.
 * Displays confirmation message and order summary.
 */

import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'

export function OrderSuccessPage() {
  // Generate a mock order number on mount
  const [orderNumber] = useState(() => {
    const timestamp = Date.now().toString(36).toUpperCase()
    const random = Math.random().toString(36).substring(2, 6).toUpperCase()
    return `ORD-${timestamp}-${random}`
  })

  // Confetti effect on mount (simple CSS animation)
  const [showConfetti, setShowConfetti] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => setShowConfetti(false), 3000)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center relative overflow-hidden">
      {/* Simple confetti effect */}
      {showConfetti && (
        <div className="absolute inset-0 pointer-events-none">
          {[...Array(20)].map((_, i) => (
            <div
              key={i}
              className="absolute animate-confetti"
              style={{
                left: `${Math.random() * 100}%`,
                animationDelay: `${Math.random() * 0.5}s`,
                backgroundColor: ['#2563eb', '#7c3aed', '#059669', '#d97706', '#dc2626'][i % 5],
                width: '10px',
                height: '10px',
                borderRadius: Math.random() > 0.5 ? '50%' : '0',
              }}
            />
          ))}
        </div>
      )}

      <div className="max-w-md mx-auto px-4 py-16 text-center">
        {/* Success Icon */}
        <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-success/10 mb-6">
          <svg
            className="w-12 h-12 text-success"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>

        {/* Title */}
        <h1 className="text-3xl font-bold text-slate-900 mb-3">
          Order Placed Successfully!
        </h1>

        {/* Subtitle */}
        <p className="text-slate-500 mb-8">
          Thank you for your order. This is a mock checkout, so no actual payment was processed.
        </p>

        {/* Order Number */}
        <div className="bg-white rounded-lg border border-border shadow-sm p-6 mb-8">
          <p className="text-sm text-slate-500 mb-1">Order Number</p>
          <p className="text-xl font-mono font-semibold text-slate-900">{orderNumber}</p>
        </div>

        {/* Info Box */}
        <div className="bg-primary/5 rounded-lg border border-primary/20 p-4 mb-8">
          <div className="flex items-start gap-3 text-left">
            <svg
              className="w-5 h-5 text-primary flex-shrink-0 mt-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div className="text-sm">
              <p className="font-medium text-primary mb-1">Demo Mode</p>
              <p className="text-slate-600">
                This is a demonstration of the checkout flow. In a real application, 
                you would receive an email confirmation and order tracking information.
              </p>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="space-y-3">
          <Link
            to="/"
            className="block w-full py-3 px-4 bg-primary text-white font-medium rounded-lg hover:bg-primary/90 transition-colors"
          >
            Continue Shopping
          </Link>
          <Link
            to="/cart"
            className="block w-full py-3 px-4 text-slate-600 font-medium border border-border rounded-lg hover:bg-slate-50 transition-colors"
          >
            View Cart
          </Link>
        </div>
      </div>

      {/* CSS for confetti animation */}
      <style>{`
        @keyframes confetti-fall {
          0% {
            transform: translateY(-100vh) rotate(0deg);
            opacity: 1;
          }
          100% {
            transform: translateY(100vh) rotate(720deg);
            opacity: 0;
          }
        }
        .animate-confetti {
          animation: confetti-fall 3s ease-out forwards;
        }
      `}</style>
    </div>
  )
}

