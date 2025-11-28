import { Type, Static } from '@sinclair/typebox'

/**
 * Queue-related TypeBox schemas
 * 
 * Based on queue-messages.json contract for Redis queue communication
 * between Bun API and Python worker
 */

/**
 * Parser type enum matching supplier.source_type
 */
export const ParserTypeSchema = Type.Union([
  Type.Literal('google_sheets'),
  Type.Literal('csv'),
  Type.Literal('excel'),
])

export type ParserType = Static<typeof ParserTypeSchema>

/**
 * Source configuration schema (parser-specific configuration from suppliers.metadata)
 */
export const SourceConfigSchema = Type.Object({
  spreadsheet_url: Type.Optional(Type.String({ format: 'uri' })),
  sheet_name: Type.Optional(Type.String()),
  file_path: Type.Optional(Type.String()),
  column_mapping: Type.Optional(
    Type.Record(Type.String(), Type.String())
  ),
}, { additionalProperties: true })

export type SourceConfig = Static<typeof SourceConfigSchema>

/**
 * Parse task message schema
 * 
 * This schema matches the Phase 1 Python worker expectations (Pydantic model)
 * Must be serialized with JSON.stringify() before LPUSH to Redis
 */
export const ParseTaskMessageSchema = Type.Object({
  task_id: Type.String({ format: 'uuid' }),
  parser_type: ParserTypeSchema,
  supplier_name: Type.String({ maxLength: 255 }),
  source_config: SourceConfigSchema,
  retry_count: Type.Integer({ minimum: 0, default: 0 }),
  max_retries: Type.Integer({ minimum: 0, default: 3 }),
  enqueued_at: Type.String({ format: 'date-time' }),
})

export type ParseTaskMessage = Static<typeof ParseTaskMessageSchema>

