/**
 * App Component
 *
 * Root application component.
 * Wraps the RouterProvider with AuthProvider and CartProvider.
 */

import { RouterProvider } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import { CartProvider } from '@/contexts/CartContext'
import { router } from '@/routes'

function App() {
  return (
    <AuthProvider>
      <CartProvider>
        <RouterProvider router={router} />
      </CartProvider>
    </AuthProvider>
  )
}

export default App
