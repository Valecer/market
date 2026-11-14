import { pgTable, varchar, index, foreignKey, unique, uuid, timestamp, check, jsonb, numeric, text, integer, pgEnum, boolean } from "drizzle-orm/pg-core"
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
	// Phase 9: Semantic ETL - Category Governance
	needsReview: boolean("needs_review").notNull().default(false),
	isActive: boolean("is_active").notNull().default(true),
	supplierId: uuid("supplier_id"),
	updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_categories_parent").using("btree", table.parentId.asc().nullsLast().op("uuid_ops")),
	foreignKey({
			columns: [table.parentId],
			foreignColumns: [table.id],
			name: "categories_parent_id_fkey"
		}).onDelete("cascade"),
	unique("uq_category_name_parent").on(table.name, table.parentId),
	check("chk_no_self_reference", sql`id <> parent_id`),
]);

export const products = pgTable("products", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	internalSku: varchar("internal_sku", { length: 100 }).notNull(),
	name: varchar({ length: 500 }).notNull(),
	categoryId: uuid("category_id"),
	status: productStatus().default('draft').notNull(),
	// Phase 10: Product Variants
	hasVariants: boolean("has_variants").notNull().default(false),
	variantSchema: jsonb("variant_schema"),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_products_category").using("btree", table.categoryId.asc().nullsLast().op("uuid_ops")),
	index("idx_products_name").using("btree", table.name.asc().nullsLast().op("varchar_pattern_ops")),
	index("idx_products_sku").using("btree", table.internalSku.asc().nullsLast().op("text_ops")),
	index("idx_products_status").using("btree", table.status.asc().nullsLast().op("enum_ops")),
	index("idx_products_has_variants").using("btree", table.hasVariants.asc().nullsLast()),
	foreignKey({
			columns: [table.categoryId],
			foreignColumns: [categories.id],
			name: "products_category_id_fkey"
		}).onDelete("set null"),
	unique("products_internal_sku_key").on(table.internalSku),
]);

// Phase 10: Product Variants
export const productVariants = pgTable("product_variants", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	productId: uuid("product_id").notNull(),
	variantKey: varchar("variant_key", { length: 255 }).notNull(),
	variantAttributes: jsonb("variant_attributes").default({}).notNull(),
	displayOrder: integer("display_order").default(0).notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_product_variants_product").using("btree", table.productId.asc().nullsLast().op("uuid_ops")),
	index("idx_product_variants_attributes").using("gin", table.variantAttributes.asc().nullsLast().op("jsonb_ops")),
	foreignKey({
			columns: [table.productId],
			foreignColumns: [products.id],
			name: "product_variants_product_id_fkey"
		}).onDelete("cascade"),
	unique("uq_product_variant_key").on(table.productId, table.variantKey),
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
	// Phase 10: Product Variants
	variantId: uuid("variant_id"),
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
	index("idx_supplier_items_variant").using("btree", table.variantId.asc().nullsLast().op("uuid_ops")),
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
	foreignKey({
			columns: [table.variantId],
			foreignColumns: [productVariants.id],
			name: "supplier_items_variant_id_fkey"
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

// Phase 11: Pipeline Stabilization - Potential Duplicates
export const potentialDuplicates = pgTable("potential_duplicates", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	productId1: uuid("product_id_1").notNull(),
	productId2: uuid("product_id_2").notNull(),
	similarityScore: numeric("similarity_score", { precision: 5, scale: 2 }).notNull(),
	detectionReason: varchar("detection_reason", { length: 100 }).notNull(),
	status: varchar({ length: 50 }).default('pending').notNull(),
	reviewedBy: uuid("reviewed_by"),
	reviewedAt: timestamp("reviewed_at", { withTimezone: true, mode: 'string' }),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("idx_potential_duplicates_status").using("btree", table.status.asc().nullsLast().op("text_ops")),
	index("idx_potential_duplicates_product1").using("btree", table.productId1.asc().nullsLast().op("uuid_ops")),
	index("idx_potential_duplicates_product2").using("btree", table.productId2.asc().nullsLast().op("uuid_ops")),
	foreignKey({
		columns: [table.productId1],
		foreignColumns: [products.id],
		name: "potential_duplicates_product_id_1_fkey"
	}).onDelete("cascade"),
	foreignKey({
		columns: [table.productId2],
		foreignColumns: [products.id],
		name: "potential_duplicates_product_id_2_fkey"
	}).onDelete("cascade"),
	foreignKey({
		columns: [table.reviewedBy],
		foreignColumns: [users.id],
		name: "potential_duplicates_reviewed_by_fkey"
	}),
	check("chk_different_products", sql`product_id_1 <> product_id_2`),
	check("chk_ordered_ids", sql`product_id_1 < product_id_2`),
	check("chk_similarity_range", sql`similarity_score >= 0 AND similarity_score <= 100`),
]);
