#!/usr/bin/env bun

/**
 * Script to generate bcrypt password hashes for seeding users table
 * Usage: bun run scripts/hash-password.ts <password>
 */

const password = Bun.argv[2]

if (!password) {
  console.error('Usage: bun run scripts/hash-password.ts <password>')
  console.error('Example: bun run scripts/hash-password.ts mypassword123')
  process.exit(1)
}

const hash = await Bun.password.hash(password, {
  algorithm: 'bcrypt',
  cost: 10,
})

console.log(`Password: ${password}`)
console.log(`Hash: ${hash}`)
console.log('\nCopy the hash above and use it in the seed script or migration.')

