# ADR 010: Product Variants Architecture

**Status:** Accepted  
**Date:** December 2024  
**Author:** Claude (AI Assistant)

## Context

Suppliers often provide the same product with different specifications at different prices:
- Electric bikes: Shtenli GT 15 with 48V/20A battery vs 60V/20A battery
- Electronics: iPhone 17 Pro with 256GB vs 512GB vs 1TB storage
- Apparel: T-shirt in S/M/L/XL sizes

Currently, each variant is stored as a separate `supplier_item` with no relationship between them. This leads to:
1. Duplicated product entries in the catalog
2. No ability for users to compare variants
3. Manual matching effort for each variant separately

## Decision

Implement a **Product Variants** system with:

1. **New `product_variants` table** linking variant instances to a base product
2. **Structured `variant_attributes` JSONB** storing differentiating specifications
3. **LLM-based variant attribute extraction** during semantic ETL
4. **ML-based variant grouping** during matching phase
5. **Frontend VariantSelector component** for user navigation

### Schema Design

```
┌─────────────────┐       ┌─────────────────────┐       ┌─────────────────┐
│    products     │       │  product_variants   │       │  supplier_items │
├─────────────────┤       ├─────────────────────┤       ├─────────────────┤
│ id (PK)         │◄──────│ product_id (FK)     │       │ id (PK)         │
│ name            │       │ id (PK)             │◄──────│ variant_id (FK) │
│ internal_sku    │       │ variant_key         │       │ product_id (FK) │
│ category_id     │       │ variant_attributes  │       │ name            │
│ status          │       │ display_order       │       │ current_price   │
└─────────────────┘       └─────────────────────┘       │ characteristics │
                                                         └─────────────────┘
```

### Variant Attributes Schema

Common patterns by category:

| Category | Variant Attributes | Example Key |
|----------|-------------------|-------------|
| Electric Transport | voltage, capacity | "48V/20A" |
| Smartphones | storage, color | "256GB/Black" |
| Laptops | RAM, storage, color | "16GB/512GB/Silver" |
| Apparel | size, color | "M/Blue" |

### Data Flow

```
Extraction → supplier_items.characteristics (raw specs)
     ↓
Matching → Detect similar products via vector similarity
     ↓
Variant Detection → LLM identifies differentiating attributes
     ↓
Grouping → Create product_variants, link supplier_items
     ↓
Frontend → VariantSelector component displays options
```

## Consequences

### Positive
- Users can compare product variants in one view
- Reduced catalog clutter (one product card per base product)
- Price range display shows all variant prices
- Better UX matching e-commerce standards (like Onliner.by)

### Negative
- Additional complexity in matching pipeline
- Need admin review workflow for variant groupings
- Migration required for existing data

### Neutral
- No breaking changes to existing API (additive only)
- Variant grouping is optional (products can exist without variants)

## Implementation Phases

1. **Phase 1: Schema** - Create `product_variants` table, add `variant_id` to `supplier_items`
2. **Phase 2: Extraction** - Enhance LLM prompts to extract structured characteristics
3. **Phase 3: Detection** - Create VariantDetectionService for grouping
4. **Phase 4: API** - Add variant endpoints to bun-api
5. **Phase 5: Frontend** - VariantSelector component + ProductDetailPage update

## References

- Phase 9: Semantic ETL Pipeline (`/specs/009-semantic-etl/`)
- Onliner.by product page (variant UI reference)
- Electric bike supplier catalogs (domain examples)

