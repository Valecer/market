/**
 * TypeScript type definitions for Drizzle ORM schemas
 * 
 * These types are inferred from the Drizzle schema definitions
 * and provide type safety throughout the application.
 */

import type {
  products,
  supplierItems,
  suppliers,
  categories,
  users,
  priceHistory,
  parsingLogs,
} from './schema'

// Product types
export type Product = typeof products.$inferSelect
export type NewProduct = typeof products.$inferInsert

// Supplier Item types
export type SupplierItem = typeof supplierItems.$inferSelect
export type NewSupplierItem = typeof supplierItems.$inferInsert

// Supplier types
export type Supplier = typeof suppliers.$inferSelect
export type NewSupplier = typeof suppliers.$inferInsert

// Category types
export type Category = typeof categories.$inferSelect
export type NewCategory = typeof categories.$inferInsert

// User types
export type User = typeof users.$inferSelect
export type NewUser = typeof users.$inferInsert

// Price History types
export type PriceHistory = typeof priceHistory.$inferSelect
export type NewPriceHistory = typeof priceHistory.$inferInsert

// Parsing Log types
export type ParsingLog = typeof parsingLogs.$inferSelect
export type NewParsingLog = typeof parsingLogs.$inferInsert

// Product status enum
export type ProductStatus = 'draft' | 'active' | 'archived'

// User role enum
export type UserRole = 'sales' | 'procurement' | 'admin'

