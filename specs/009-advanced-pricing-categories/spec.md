# Feature Specification: Advanced Pricing and Categorization

**Version:** 1.0.0

**Last Updated:** 2025-12-03

**Status:** Draft

---

## Constitutional Alignment

**Relevant Principles:**

- **Single Responsibility:** Product pricing fields serve a distinct purpose (retail vs wholesale); Category hierarchy follows established pattern
- **Separation of Concerns:** Data model changes affect multiple services (Python, Bun API, Frontend) but each layer transforms data appropriately
- **Strong Typing:** All new fields are strongly typed (Decimal for prices, ISO string for currency)
- **KISS:** Uses adjacency list for hierarchy (already implemented); adds minimal new fields
- **DRY:** Leverages existing Category entity and Product→Category relationship; only adds truly new pricing fields

**Compliance Statement:**

This specification adheres to all constitutional principles. The implementation reuses existing infrastructure where possible.

---

## Overview

### Purpose

Enable advanced pricing models by supporting dual pricing (retail and wholesale) with currency tracking, while ensuring products are properly organized within a hierarchical category structure.

### Scope

**In Scope:**

- Add retail and wholesale price fields to Product entity
- Add currency code field to Product entity for source currency tracking
- Ensure Product entity maintains link to Category
- Database migrations for new fields
- API updates to expose new pricing fields
- Frontend display of dual pricing and currency

**Out of Scope:**

- Currency conversion or exchange rate management
- Dynamic pricing rules or algorithms
- Bulk pricing tiers beyond retail/wholesale
- Category management UI (already exists)
- Multi-currency display (single source currency per product)

---

## User Scenarios & Testing

### Scenario 1: Procurement Manager Reviews Product Pricing

**Actor:** Procurement Manager

**Preconditions:** Products exist in the catalog with supplier data

**Flow:**
1. User navigates to product catalog
2. User views product details
3. System displays retail price, wholesale price, and source currency
4. User can compare pricing across different products

**Postconditions:** User understands the pricing structure for the product

**Testing Approach:**
- Verify both price fields display correctly
- Verify currency code displays in ISO 4217 format (e.g., "USD", "EUR", "RUB")
- Verify null prices display appropriately (e.g., "—" or "Not set")

### Scenario 2: Admin Imports Product with Dual Pricing

**Actor:** Admin

**Preconditions:** Supplier price list contains retail and wholesale pricing columns

**Flow:**
1. Admin triggers data ingestion from supplier
2. System parses source document extracting both price types
3. System identifies and stores currency from source
4. Product record is created/updated with retail price, wholesale price, and currency

**Postconditions:** Product has both pricing fields and currency populated

**Testing Approach:**
- Import test data with dual pricing columns
- Verify correct parsing and storage of both prices
- Verify currency detection from source data

### Scenario 3: Sales Rep Views Categorized Products

**Actor:** Sales Representative

**Preconditions:** Products are assigned to categories

**Flow:**
1. User browses catalog by category
2. User sees category hierarchy in navigation
3. User selects a category to view products within it
4. Products display with their pricing information

**Postconditions:** User can navigate category structure and view product pricing

**Testing Approach:**
- Verify category hierarchy displays correctly
- Verify products filter by selected category
- Verify pricing displays for products in category

---

## Functional Requirements

### FR-1: Dual Pricing Fields

**Priority:** Critical

**Description:** The Product entity must support two distinct price points: retail price (end-customer pricing) and wholesale price (bulk/dealer pricing). Both prices are optional, as not all products may have both price types defined.

**Acceptance Criteria:**

- [ ] AC-1: Product can store a retail price as a decimal value with 2 decimal places
- [ ] AC-2: Product can store a wholesale price as a decimal value with 2 decimal places
- [ ] AC-3: Both retail and wholesale prices can be null (not all products have both)
- [ ] AC-4: Prices must be non-negative (≥ 0) when present
- [ ] AC-5: Existing products without these fields default to null values after migration

**Dependencies:** Database migration system (Alembic)

### FR-2: Currency Code Storage

**Priority:** Critical

**Description:** The Product entity must store the original currency code from the source data in ISO 4217 format. This enables accurate record-keeping of the source currency without automatic conversion.

**Acceptance Criteria:**

- [ ] AC-1: Product can store a currency code as a 3-character ISO 4217 string (e.g., "USD", "EUR", "RUB")
- [ ] AC-2: Currency code field is optional (can be null for legacy data)
- [ ] AC-3: System validates currency codes against ISO 4217 format (3 uppercase letters)
- [ ] AC-4: Existing products without currency code default to null after migration

**Dependencies:** Database migration system (Alembic)

### FR-3: Product-Category Association

**Priority:** High

**Description:** Products must be linkable to categories within a hierarchical structure. This association enables catalog organization and navigation.

**Acceptance Criteria:**

- [ ] AC-1: Product can be assigned to a single category
- [ ] AC-2: Product's category is optional (can be uncategorized)
- [ ] AC-3: If a category is deleted, associated products become uncategorized (null category)
- [ ] AC-4: Products can be filtered by category including all products in child categories

**Dependencies:** Existing Category entity (adjacency list model)

**Note:** The Category entity with parent_id hierarchy (adjacency list model) already exists in the system. No changes to Category entity required.

### FR-4: API Pricing Endpoints

**Priority:** High

**Description:** API endpoints must expose the new pricing fields for product retrieval and updates.

**Acceptance Criteria:**

- [ ] AC-1: Product list endpoints return retail_price, wholesale_price, and currency_code
- [ ] AC-2: Product detail endpoint returns retail_price, wholesale_price, and currency_code
- [ ] AC-3: Admin endpoints allow updating retail_price, wholesale_price, and currency_code
- [ ] AC-4: API validates currency code format on input

**Dependencies:** FR-1, FR-2

### FR-5: Frontend Pricing Display

**Priority:** Medium

**Description:** The frontend must display dual pricing information with currency context.

**Acceptance Criteria:**

- [ ] AC-1: Product list shows at least one price (retail preferred, wholesale as fallback)
- [ ] AC-2: Product detail view shows both retail and wholesale prices when available
- [ ] AC-3: Currency code displays alongside prices
- [ ] AC-4: Null prices display as appropriate placeholder (e.g., "—")

**Dependencies:** FR-4

---

## Success Criteria

1. **Pricing Completeness:** 100% of newly ingested products capture both retail and wholesale pricing when available in source data
2. **Currency Tracking:** 100% of products from sources with identifiable currency have currency_code populated
3. **Data Integrity:** Zero data loss during migration - existing products retain all current values
4. **User Experience:** Users can view and understand dual pricing within 5 seconds of viewing a product
5. **Category Utilization:** Products can be filtered by category including nested subcategories
6. **System Stability:** Feature deployment causes zero downtime
7. **Query Performance:** Product list with pricing loads within current performance thresholds

---

## Key Entities

### Product (Extended)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| retail_price | Decimal(10,2) | No | End-customer price |
| wholesale_price | Decimal(10,2) | No | Bulk/dealer price |
| currency_code | String(3) | No | ISO 4217 currency code |

**Notes:**
- Existing fields (id, internal_sku, name, category_id, status, min_price, availability, mrp, timestamps) remain unchanged
- The existing `min_price` field serves a different purpose (aggregate of supplier prices) and is NOT being replaced
- The new `retail_price` and `wholesale_price` are canonical product-level prices

### Category (Existing - No Changes)

The Category entity already supports nested hierarchy via the adjacency list pattern (parent_id self-reference). No modifications required.

---

## Assumptions

1. **Single Currency per Product:** Each product has one source currency; multi-currency is out of scope
2. **No Automatic Conversion:** The system stores source currency as-is without converting to a base currency
3. **Price Precision:** Two decimal places are sufficient for all supported currencies
4. **Backward Compatibility:** Existing API consumers can handle new optional fields (null values)
5. **Common Currencies:** Primary currencies expected are USD, EUR, RUB, CNY, BYN
6. **Category Hierarchy:** Maximum practical depth of 5 levels is sufficient
7. **ML Service:** The ML-Analyze service will be updated to extract dual pricing when parsing supplier documents

---

## Dependencies

| Dependency | Type | Status | Impact if Unavailable |
|------------|------|--------|----------------------|
| PostgreSQL Database | Infrastructure | Available | Cannot store new fields |
| Alembic Migrations | Infrastructure | Available | Cannot modify schema |
| Drizzle ORM | Infrastructure | Available | API cannot access new fields |
| ML-Analyze Service | Service | Available | New pricing won't be extracted from sources |

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Migration causes downtime | Low | High | Use non-blocking ALTER TABLE with NULL defaults |
| Existing integrations break | Medium | Medium | All new fields are optional (nullable) |
| Currency code validation too strict | Low | Low | Only validate format, not ISO 4217 registry membership |
| Performance impact from new fields | Low | Low | Fields are simple scalars, indexed only if needed |

---

## Out of Scope (Explicit)

- Currency exchange rates or conversion logic
- Price history for retail/wholesale prices (existing price_history tracks supplier items)
- Margin calculation between wholesale and retail
- Price rules or dynamic pricing
- Category CRUD operations (already exist)
- Bulk category assignment UI
- Tax or VAT calculations

---

## Appendix

### References

- ISO 4217 Currency Codes: https://www.iso.org/iso-4217-currency-codes.html
- Existing Category model: `services/python-ingestion/src/db/models/category.py`
- Existing Product model: `services/python-ingestion/src/db/models/product.py`
- Drizzle schema: `services/bun-api/src/db/schema/schema.ts`

### Glossary

- **Retail Price:** The price charged to end consumers or individual purchasers
- **Wholesale Price:** The discounted price for bulk purchases or business-to-business sales
- **ISO 4217:** International standard for currency codes (3-letter codes like USD, EUR)
- **Adjacency List:** Database pattern for hierarchical data using parent_id references

---

**Approval:**

- [ ] Tech Lead: [Name] - [Date]
- [ ] Product: [Name] - [Date]
- [ ] QA: [Name] - [Date]
