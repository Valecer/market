import { eq } from 'drizzle-orm'
import { db } from '../client'
import { users } from '../schema/schema'
import type { User, NewUser } from '../schema/types'

/**
 * User Repository Interface
 * 
 * Defines the contract for user data access operations
 */
export interface IUserRepository {
  /**
   * Find a user by username
   * @param username - The username to search for
   * @returns The user if found, null otherwise
   */
  findByUsername(username: string): Promise<User | null>

  /**
   * Find a user by ID
   * @param id - The user UUID
   * @returns The user if found, null otherwise
   */
  findById(id: string): Promise<User | null>
}

/**
 * User Repository Implementation
 * 
 * Implements user data access using Drizzle ORM
 */
export class UserRepository implements IUserRepository {
  async findByUsername(username: string): Promise<User | null> {
    const result = await db
      .select()
      .from(users)
      .where(eq(users.username, username))
      .limit(1)

    return result[0] || null
  }

  async findById(id: string): Promise<User | null> {
    const result = await db
      .select()
      .from(users)
      .where(eq(users.id, id))
      .limit(1)

    return result[0] || null
  }
}

// Export singleton instance
export const userRepository = new UserRepository()

