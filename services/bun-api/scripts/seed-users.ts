#!/usr/bin/env bun

/**
 * Script to seed default users in the database
 * Run after migration: bun run scripts/seed-users.ts
 */

import { drizzle } from 'drizzle-orm/node-postgres'
import { Pool } from 'pg'
import { sql } from 'drizzle-orm'

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
})

const db = drizzle(pool)

// Generate password hashes
const adminHash = await Bun.password.hash('admin123', {
  algorithm: 'bcrypt',
  cost: 10,
})
const salesHash = await Bun.password.hash('sales123', {
  algorithm: 'bcrypt',
  cost: 10,
})
const procurementHash = await Bun.password.hash('procurement123', {
  algorithm: 'bcrypt',
  cost: 10,
})

// Insert seed users (using ON CONFLICT to avoid duplicates)
await db.execute(sql`
  INSERT INTO users (username, password_hash, role)
  VALUES
    ('admin', ${adminHash}, 'admin'),
    ('sales', ${salesHash}, 'sales'),
    ('procurement', ${procurementHash}, 'procurement')
  ON CONFLICT (username) DO NOTHING
`)

console.log('✅ Seed users created successfully!')
console.log('Default credentials:')
console.log('  - admin / admin123')
console.log('  - sales / sales123')
console.log('  - procurement / procurement123')

await pool.end()

