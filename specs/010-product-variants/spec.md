# Phase 10: Product Variants

**Status:** 🚧 In Progress  
**Started:** December 2024

## Overview

Product Variants feature enables grouping of products that are essentially the same but with different specifications (e.g., different battery voltage, storage capacity, color).

## Problem Statement

Currently, suppliers provide products like:
- "Электровелосипед Shtenli GT 15 48V/20A" @ 1990 BYN
- "Электровелосипед Shtenli GT 15 60V/20A" @ 2090 BYN

These are stored as separate `supplier_items` with no relationship, leading to:
1. Duplicated product entries in catalog
2. No variant comparison for users
3. Manual matching effort per variant

## Solution

### Database Schema

```sql
-- New table: product_variants
CREATE TABLE product_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    variant_key VARCHAR(255) NOT NULL,          -- "48V/20A"
    variant_attributes JSONB NOT NULL DEFAULT '{}',  -- {"voltage": "48V", "capacity": "20A"}
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(product_id, variant_key)
);

-- Add to products
ALTER TABLE products ADD COLUMN has_variants BOOLEAN DEFAULT FALSE;
ALTER TABLE products ADD COLUMN variant_schema JSONB;  -- ["voltage", "capacity"]

-- Add to supplier_items
ALTER TABLE supplier_items ADD COLUMN variant_id UUID REFERENCES product_variants(id);
```

### Data Flow

```
1. LLM Extraction → Extract variant_attributes from product names
   "Shtenli GT15 48V20A" → {"voltage": "48V", "capacity": "20A"}

2. Variant Detection → Group similar products
   - Name similarity (RapidFuzz > 85%)
   - Different variant attributes
   - Price within 2x ratio

3. Variant Grouping → Create product_variants, link supplier_items

4. Frontend → Display variant selector (like Onliner.by)
```

## Implementation Files

### Backend (ml-analyze)
- `src/schemas/extraction.py` - Added `variant_attributes` field
- `src/services/smart_parser/prompts.py` - LLM prompts for variant extraction
- `src/services/variant_detection_service.py` - Grouping algorithm

### Backend (bun-api)
- `src/db/schema/schema.ts` - Drizzle schema updates
- `src/db/repositories/variant.repository.ts` - CRUD operations

### Frontend
- `src/components/catalog/VariantSelector.tsx` - Variant UI component
- `src/types/variant.ts` - TypeScript types
- `public/locales/*/translation.json` - i18n keys

### Database
- `migrations/versions/010_product_variants.py` - Alembic migration

## Variant Attribute Keys

| Category | Attributes | Example Key |
|----------|-----------|-------------|
| Electric Transport | voltage, capacity | "48V/20A" |
| Electronics | storage, color | "256GB/Black" |
| Laptops | ram, storage | "16GB/512GB" |
| Apparel | size, color | "M/Blue" |

## API Endpoints

### GET /api/v1/catalog/:id
Returns product with variants:
```json
{
  "id": "uuid",
  "name": "Электровелосипед Shtenli GT 15 Maxi Range",
  "hasVariants": true,
  "variantSchema": ["voltage", "capacity"],
  "variants": [
    {
      "id": "variant-uuid-1",
      "variantKey": "48V/20A",
      "variantAttributes": {"voltage": "48V", "capacity": "20A"},
      "minPrice": "1990.00",
      "maxPrice": "1990.00",
      "supplierCount": 1
    },
    {
      "id": "variant-uuid-2",
      "variantKey": "60V/20A",
      "variantAttributes": {"voltage": "60V", "capacity": "20A"},
      "minPrice": "2090.00",
      "maxPrice": "2090.00",
      "supplierCount": 1
    }
  ]
}
```

## Frontend Component

```tsx
<VariantSelector
  variants={product.variants}
  variantSchema={product.variantSchema}
  selectedVariantId={selectedVariant}
  onVariantSelect={setSelectedVariant}
/>
```

Renders:
```
Напряжение:
[48V] [60V]

Ёмкость:
[20A]

Выбранный вариант: 48V/20A
Цена: 1 990 BYN
```

## Success Criteria

- [ ] Variants extracted from product names during LLM processing
- [ ] Similar products grouped automatically
- [ ] Admin can review/adjust variant groupings
- [ ] Frontend displays variant selectors
- [ ] Price updates when variant is selected

## Related Documentation

- ADR: `/docs/adr/010-product-variants.md`
- Migration: `/services/python-ingestion/migrations/versions/010_product_variants.py`

