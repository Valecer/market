import { relations } from "drizzle-orm/relations";
import { categories, products, productVariants, suppliers, supplierItems, priceHistory, parsingLogs } from "./schema";

export const categoriesRelations = relations(categories, ({one, many}) => ({
	category: one(categories, {
		fields: [categories.parentId],
		references: [categories.id],
		relationName: "categories_parentId_categories_id"
	}),
	categories: many(categories, {
		relationName: "categories_parentId_categories_id"
	}),
	products: many(products),
}));

export const productsRelations = relations(products, ({one, many}) => ({
	category: one(categories, {
		fields: [products.categoryId],
		references: [categories.id]
	}),
	supplierItems: many(supplierItems),
	// Phase 10: Product Variants
	variants: many(productVariants),
}));

// Phase 10: Product Variants
export const productVariantsRelations = relations(productVariants, ({one, many}) => ({
	product: one(products, {
		fields: [productVariants.productId],
		references: [products.id]
	}),
	supplierItems: many(supplierItems),
}));

export const supplierItemsRelations = relations(supplierItems, ({one, many}) => ({
	supplier: one(suppliers, {
		fields: [supplierItems.supplierId],
		references: [suppliers.id]
	}),
	product: one(products, {
		fields: [supplierItems.productId],
		references: [products.id]
	}),
	// Phase 10: Product Variants
	variant: one(productVariants, {
		fields: [supplierItems.variantId],
		references: [productVariants.id]
	}),
	priceHistories: many(priceHistory),
}));

export const suppliersRelations = relations(suppliers, ({many}) => ({
	supplierItems: many(supplierItems),
	parsingLogs: many(parsingLogs),
}));

export const priceHistoryRelations = relations(priceHistory, ({one}) => ({
	supplierItem: one(supplierItems, {
		fields: [priceHistory.supplierItemId],
		references: [supplierItems.id]
	}),
}));

export const parsingLogsRelations = relations(parsingLogs, ({one}) => ({
	supplier: one(suppliers, {
		fields: [parsingLogs.supplierId],
		references: [suppliers.id]
	}),
}));