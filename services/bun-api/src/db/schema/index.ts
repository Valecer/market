/**
 * Drizzle ORM Schema
 * 
 * Exports all database schemas:
 * - Phase 1 tables (introspected from existing database)
 * - Phase 2 tables (users - managed locally, also introspected)
 */

// All tables (Phase 1 + Phase 2) - introspected from database
export * from './schema'
export * from './relations'

// TypeScript type definitions inferred from schemas
export * from './types'
