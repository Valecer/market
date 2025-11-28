-- Current sql file was generated after introspecting the database
-- If you want to run this migration please uncomment this code before executing migrations
/*
CREATE TYPE "public"."product_status" AS ENUM('draft', 'active', 'archived');--> statement-breakpoint
CREATE TYPE "public"."user_role" AS ENUM('sales', 'procurement', 'admin');--> statement-breakpoint
CREATE TABLE "alembic_version" (
	"version_num" varchar(32) PRIMARY KEY NOT NULL
);
--> statement-breakpoint
CREATE TABLE "categories" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"name" varchar(255) NOT NULL,
	"parent_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "uq_category_name_parent" UNIQUE("name","parent_id")
);
--> statement-breakpoint
CREATE TABLE "products" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"internal_sku" varchar(100) NOT NULL,
	"name" varchar(500) NOT NULL,
	"category_id" uuid,
	"status" "product_status" DEFAULT 'draft' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "products_internal_sku_key" UNIQUE("internal_sku")
);
--> statement-breakpoint
CREATE TABLE "suppliers" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"name" varchar(255) NOT NULL,
	"source_type" varchar(50) NOT NULL,
	"contact_email" varchar(255),
	"metadata" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "check_source_type" CHECK ((source_type)::text = ANY ((ARRAY['google_sheets'::character varying, 'csv'::character varying, 'excel'::character varying])::text[]))
);
--> statement-breakpoint
CREATE TABLE "supplier_items" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"supplier_id" uuid NOT NULL,
	"product_id" uuid,
	"supplier_sku" varchar(255) NOT NULL,
	"name" varchar(500) NOT NULL,
	"current_price" numeric(10, 2) NOT NULL,
	"characteristics" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"last_ingested_at" timestamp with time zone DEFAULT now() NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "unique_supplier_sku" UNIQUE("supplier_id","supplier_sku"),
	CONSTRAINT "check_positive_price" CHECK (current_price >= (0)::numeric)
);
--> statement-breakpoint
CREATE TABLE "price_history" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"supplier_item_id" uuid NOT NULL,
	"price" numeric(10, 2) NOT NULL,
	"recorded_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "check_positive_price" CHECK (price >= (0)::numeric)
);
--> statement-breakpoint
CREATE TABLE "parsing_logs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"task_id" varchar(255) NOT NULL,
	"supplier_id" uuid,
	"error_type" varchar(100) NOT NULL,
	"error_message" text NOT NULL,
	"row_number" integer,
	"row_data" jsonb,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"username" varchar(255) NOT NULL,
	"password_hash" varchar(255) NOT NULL,
	"role" "user_role" NOT NULL,
	"created_at" timestamp DEFAULT CURRENT_TIMESTAMP,
	"updated_at" timestamp DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT "users_username_key" UNIQUE("username")
);
--> statement-breakpoint
ALTER TABLE "categories" ADD CONSTRAINT "categories_parent_id_fkey" FOREIGN KEY ("parent_id") REFERENCES "public"."categories"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "products" ADD CONSTRAINT "products_category_id_fkey" FOREIGN KEY ("category_id") REFERENCES "public"."categories"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "supplier_items" ADD CONSTRAINT "supplier_items_supplier_id_fkey" FOREIGN KEY ("supplier_id") REFERENCES "public"."suppliers"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "supplier_items" ADD CONSTRAINT "supplier_items_product_id_fkey" FOREIGN KEY ("product_id") REFERENCES "public"."products"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "price_history" ADD CONSTRAINT "price_history_supplier_item_id_fkey" FOREIGN KEY ("supplier_item_id") REFERENCES "public"."supplier_items"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "parsing_logs" ADD CONSTRAINT "parsing_logs_supplier_id_fkey" FOREIGN KEY ("supplier_id") REFERENCES "public"."suppliers"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "idx_categories_parent" ON "categories" USING btree ("parent_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "idx_products_category" ON "products" USING btree ("category_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "idx_products_name" ON "products" USING btree ("name" varchar_pattern_ops);--> statement-breakpoint
CREATE INDEX "idx_products_sku" ON "products" USING btree ("internal_sku" text_ops);--> statement-breakpoint
CREATE INDEX "idx_products_status" ON "products" USING btree ("status" enum_ops);--> statement-breakpoint
CREATE INDEX "idx_suppliers_name" ON "suppliers" USING btree ("name" text_ops);--> statement-breakpoint
CREATE INDEX "idx_suppliers_source_type" ON "suppliers" USING btree ("source_type" text_ops);--> statement-breakpoint
CREATE INDEX "idx_supplier_items_characteristics" ON "supplier_items" USING gin ("characteristics" jsonb_ops);--> statement-breakpoint
CREATE INDEX "idx_supplier_items_last_ingested" ON "supplier_items" USING btree ("last_ingested_at" timestamptz_ops);--> statement-breakpoint
CREATE INDEX "idx_supplier_items_price" ON "supplier_items" USING btree ("current_price" numeric_ops);--> statement-breakpoint
CREATE INDEX "idx_supplier_items_product" ON "supplier_items" USING btree ("product_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "idx_supplier_items_supplier" ON "supplier_items" USING btree ("supplier_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "idx_price_history_item" ON "price_history" USING btree ("supplier_item_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "idx_price_history_item_recorded" ON "price_history" USING btree ("supplier_item_id" timestamptz_ops,"recorded_at" timestamptz_ops);--> statement-breakpoint
CREATE INDEX "idx_price_history_recorded" ON "price_history" USING btree ("recorded_at" timestamptz_ops);--> statement-breakpoint
CREATE INDEX "idx_parsing_logs_created" ON "parsing_logs" USING btree ("created_at" timestamptz_ops);--> statement-breakpoint
CREATE INDEX "idx_parsing_logs_error_type" ON "parsing_logs" USING btree ("error_type" text_ops);--> statement-breakpoint
CREATE INDEX "idx_parsing_logs_supplier" ON "parsing_logs" USING btree ("supplier_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "idx_parsing_logs_task" ON "parsing_logs" USING btree ("task_id" text_ops);--> statement-breakpoint
CREATE INDEX "idx_users_username" ON "users" USING btree ("username" text_ops);
*/