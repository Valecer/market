import { pgTable, varchar, index, foreignKey, unique, uuid, timestamp, check, jsonb, numeric, text, integer, pgEnum } from "drizzle-orm/pg-core"
import { sql } from "drizzle-orm"

export const productStatus = pgEnum("product_status", ['draft', 'active', 'archived'])
export const userRole = pgEnum("user_role", ['sales', 'procurement', 'admin'])


export const alembicVersion = pgTable("alembic_version", {
	versionNum: varchar("version_num", { length: 32 }).primaryKey().notNull(),
});

export const categories = pgTable("categories", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	name: varchar({ length: 255 }).notNull(),
	parentId: uuid("parent_id"),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_categories_parent").using("btree", table.parentId.asc().nullsLast().op("uuid_ops")),
	foreignKey({
			columns: [table.parentId],
			foreignColumns: [table.id],
			name: "categories_parent_id_fkey"
		}).onDelete("cascade"),
	unique("uq_category_name_parent").on(table.name, table.parentId),
]);

export const products = pgTable("products", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	internalSku: varchar("internal_sku", { length: 100 }).notNull(),
	name: varchar({ length: 500 }).notNull(),
	categoryId: uuid("category_id"),
	status: productStatus().default('draft').notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_products_category").using("btree", table.categoryId.asc().nullsLast().op("uuid_ops")),
	index("idx_products_name").using("btree", table.name.asc().nullsLast().op("varchar_pattern_ops")),
	index("idx_products_sku").using("btree", table.internalSku.asc().nullsLast().op("text_ops")),
	index("idx_products_status").using("btree", table.status.asc().nullsLast().op("enum_ops")),
	foreignKey({
			columns: [table.categoryId],
			foreignColumns: [categories.id],
			name: "products_category_id_fkey"
		}).onDelete("set null"),
	unique("products_internal_sku_key").on(table.internalSku),
]);

export const suppliers = pgTable("suppliers", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	name: varchar({ length: 255 }).notNull(),
	sourceType: varchar("source_type", { length: 50 }).notNull(),
	contactEmail: varchar("contact_email", { length: 255 }),
	metadata: jsonb().default({}).notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_suppliers_name").using("btree", table.name.asc().nullsLast().op("text_ops")),
	index("idx_suppliers_source_type").using("btree", table.sourceType.asc().nullsLast().op("text_ops")),
	check("check_source_type", sql`(source_type)::text = ANY ((ARRAY['google_sheets'::character varying, 'csv'::character varying, 'excel'::character varying])::text[])`),
]);

export const supplierItems = pgTable("supplier_items", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	supplierId: uuid("supplier_id").notNull(),
	productId: uuid("product_id"),
	supplierSku: varchar("supplier_sku", { length: 255 }).notNull(),
	name: varchar({ length: 500 }).notNull(),
	currentPrice: numeric("current_price", { precision: 10, scale:  2 }).notNull(),
	characteristics: jsonb().default({}).notNull(),
	lastIngestedAt: timestamp("last_ingested_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_supplier_items_characteristics").using("gin", table.characteristics.asc().nullsLast().op("jsonb_ops")),
	index("idx_supplier_items_last_ingested").using("btree", table.lastIngestedAt.desc().nullsFirst().op("timestamptz_ops")),
	index("idx_supplier_items_price").using("btree", table.currentPrice.asc().nullsLast().op("numeric_ops")),
	index("idx_supplier_items_product").using("btree", table.productId.asc().nullsLast().op("uuid_ops")),
	index("idx_supplier_items_supplier").using("btree", table.supplierId.asc().nullsLast().op("uuid_ops")),
	foreignKey({
			columns: [table.supplierId],
			foreignColumns: [suppliers.id],
			name: "supplier_items_supplier_id_fkey"
		}).onDelete("cascade"),
	foreignKey({
			columns: [table.productId],
			foreignColumns: [products.id],
			name: "supplier_items_product_id_fkey"
		}).onDelete("set null"),
	unique("unique_supplier_sku").on(table.supplierId, table.supplierSku),
	check("check_positive_price", sql`current_price >= (0)::numeric`),
]);

export const priceHistory = pgTable("price_history", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	supplierItemId: uuid("supplier_item_id").notNull(),
	price: numeric({ precision: 10, scale:  2 }).notNull(),
	recordedAt: timestamp("recorded_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_price_history_item").using("btree", table.supplierItemId.asc().nullsLast().op("uuid_ops")),
	index("idx_price_history_item_recorded").using("btree", table.supplierItemId.asc().nullsLast().op("timestamptz_ops"), table.recordedAt.desc().nullsFirst().op("timestamptz_ops")),
	index("idx_price_history_recorded").using("btree", table.recordedAt.desc().nullsFirst().op("timestamptz_ops")),
	foreignKey({
			columns: [table.supplierItemId],
			foreignColumns: [supplierItems.id],
			name: "price_history_supplier_item_id_fkey"
		}).onDelete("cascade"),
	check("check_positive_price", sql`price >= (0)::numeric`),
]);

export const parsingLogs = pgTable("parsing_logs", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	taskId: varchar("task_id", { length: 255 }).notNull(),
	supplierId: uuid("supplier_id"),
	errorType: varchar("error_type", { length: 100 }).notNull(),
	errorMessage: text("error_message").notNull(),
	rowNumber: integer("row_number"),
	rowData: jsonb("row_data"),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_parsing_logs_created").using("btree", table.createdAt.desc().nullsFirst().op("timestamptz_ops")),
	index("idx_parsing_logs_error_type").using("btree", table.errorType.asc().nullsLast().op("text_ops")),
	index("idx_parsing_logs_supplier").using("btree", table.supplierId.asc().nullsLast().op("uuid_ops")),
	index("idx_parsing_logs_task").using("btree", table.taskId.asc().nullsLast().op("text_ops")),
	foreignKey({
			columns: [table.supplierId],
			foreignColumns: [suppliers.id],
			name: "parsing_logs_supplier_id_fkey"
		}).onDelete("set null"),
]);

export const users = pgTable("users", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	username: varchar({ length: 255 }).notNull(),
	passwordHash: varchar("password_hash", { length: 255 }).notNull(),
	role: userRole().notNull(),
	createdAt: timestamp("created_at", { mode: 'string' }).default(sql`CURRENT_TIMESTAMP`),
	updatedAt: timestamp("updated_at", { mode: 'string' }).default(sql`CURRENT_TIMESTAMP`),
}, (table) => [
	index("idx_users_username").using("btree", table.username.asc().nullsLast().op("text_ops")),
	unique("users_username_key").on(table.username),
]);
