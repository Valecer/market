# Feature Specification: Product Matching & Data Enrichment Pipeline

**Version:** 1.1.0

**Last Updated:** 2025-11-30

**Status:** Draft (Clarified)

---

## Constitutional Alignment

**Relevant Principles:**

- **Single Responsibility:** Matching, Extraction, and Aggregation are separate, pluggable components
- **Separation of Concerns:** Python worker handles all data processing; API service handles manual override events
- **Strong Typing:** Pydantic models validate all extraction outputs and thresholds
- **KISS:** Start with deterministic fuzzy string matching before exploring ML approaches; extraction patterns as code (not DB config)
- **DRY:** Reusable strategy interfaces for matchers and extractors

**Compliance Statement:**

This specification adheres to all constitutional principles. Any deviations are documented in the Exceptions section below.

---

## Overview

### Purpose

Automatically transform raw supplier data into a unified product catalog by grouping similar items from multiple suppliers, extracting technical specifications, and maintaining accurate aggregate pricing and availability.

### Scope

**In Scope:**

- Automatic matching of unlinked supplier items to existing or new products
- Confidence-based matching with configurable thresholds
- Manual review flagging for uncertain matches
- Extraction of technical specifications (voltage, power, dimensions, weight) from text
- Real-time aggregate calculation (min price, availability) when items are linked
- Manual override handling with verification protection
- Blocking/clustering by category for performance optimization

**Out of Scope:**

- Machine learning-based matching (Phase 5 enhancement)
- Multi-language text extraction (future enhancement)
- Image-based product matching (future enhancement)
- MRP calculation from competitor data (placeholder only, full implementation deferred)
- Frontend UI for manual review queue (Phase 3 scope)

---

## User Scenarios & Testing

### Scenario 1: Automatic High-Confidence Match

**Actor:** System (Background Process)

**Precondition:** A new supplier item is ingested with `product_id IS NULL`

**Flow:**
1. System identifies unlinked supplier item "Samsung Galaxy A54 5G 128GB Black"
2. System finds existing product "Samsung Galaxy A54 5G 128GB" with 96% similarity
3. System automatically links supplier item to existing product (exceeds 95% threshold)
4. System recalculates product's min_price and availability
5. System records the match type as "auto_match"

**Postcondition:** Supplier item is linked, product aggregates are updated

**Test:** Given a supplier item with 96%+ name similarity to an existing product, the item should be automatically linked within 5 seconds of processing.

---

### Scenario 2: Potential Match Requiring Review

**Actor:** System → Sales/Procurement User

**Precondition:** A new supplier item has moderate similarity to existing products

**Flow:**
1. System identifies unlinked supplier item "Samsung A54 Phone Black 128"
2. System finds existing product "Samsung Galaxy A54 5G 128GB" with 78% similarity
3. System flags the item as "potential_match" (between 70-95% threshold)
4. System creates a review task with suggested match candidates
5. User reviews and confirms or rejects the match via Admin UI

**Postcondition:** Item flagged for review; no automatic linking occurs

**Test:** Given a supplier item with 70-95% name similarity, the item should be flagged with match candidates visible in the review queue.

---

### Scenario 3: New Product Creation

**Actor:** System

**Precondition:** A supplier item has no similar products in catalog

**Flow:**
1. System identifies unlinked supplier item "Xiaomi Redmi Note 13 Pro 256GB Blue"
2. System finds no existing products with >70% similarity in same category
3. System creates a new Product record with status "draft"
4. System links supplier item to the new product
5. System populates product aggregates (single supplier data)

**Postcondition:** New product created and linked

**Test:** Given a supplier item with <70% similarity to all existing products, a new draft product should be created and linked.

---

### Scenario 4: Characteristics Extraction

**Actor:** System

**Precondition:** Supplier item has technical specs embedded in name/description

**Flow:**
1. System processes item: "Bosch Drill 750W 220V 2.5kg with case"
2. System extracts: `{"power_watts": 750, "voltage": 220, "weight_kg": 2.5}`
3. System updates `supplier_items.characteristics` JSONB with extracted values
4. Existing manually-entered characteristics are preserved (not overwritten)

**Postcondition:** Characteristics field enriched with extracted data

**Test:** Given an item with "750W 220V 2.5kg" in the name, the extracted characteristics should contain power=750, voltage=220, weight=2.5.

---

### Scenario 5: Price Update Triggers Aggregation

**Actor:** System (Triggered by data ingestion)

**Precondition:** Supplier item's price changes during re-ingestion

**Flow:**
1. Supplier item linked to product receives price update (was $99, now $89)
2. System detects price change event
3. System recalculates product's min_price from all linked suppliers
4. System updates product.min_price if this is now the lowest
5. Price history is recorded (existing Phase 1 behavior)

**Postcondition:** Product aggregates reflect current supplier prices

**Test:** Given a linked item with a price decrease to the lowest among suppliers, the product's min_price should update within 10 seconds.

---

### Scenario 6: Manual Link Override

**Actor:** Admin/Procurement User

**Precondition:** User identifies an incorrect automatic match or wants to manually link items

**Flow:**
1. User identifies supplier item incorrectly linked to wrong product
2. User triggers manual unlink via Admin API
3. System marks old link as broken and old product for aggregate recalculation
4. User links item to correct product
5. System marks new link as `verified_match` (protected from auto-matcher)
6. System recalculates aggregates for both affected products

**Postcondition:** Item correctly linked; both products have accurate aggregates; link is protected

**Test:** Given a manually linked item, the auto-matcher should skip it even if run again.

---

### Scenario 7: Blocking by Category

**Actor:** System (Performance Optimization)

**Precondition:** Large catalog with items in multiple categories

**Flow:**
1. System begins matching process for supplier item in "Power Tools" category
2. System only compares against products in "Power Tools" category (not entire catalog)
3. Matching completes 10x faster than full catalog scan
4. False positive rate remains low due to category constraint

**Postcondition:** Matching performance meets >1000 items/minute target

**Test:** Given 10,000 products across 50 categories, matching 1000 items should complete in under 60 seconds.

---

## Functional Requirements

### FR-1: Automatic Product Matcher ("The Linker")

**Priority:** Critical

**Description:** A background process that continuously identifies unlinked supplier items and attempts to match them with existing products or create new ones based on name similarity.

**Acceptance Criteria:**

- [ ] AC-1: System processes all supplier items where `product_id IS NULL`
- [ ] AC-2: Items with ≥95% similarity to existing product are automatically linked
- [ ] AC-3: Items with 70-94% similarity are flagged as "potential_match" for review
- [ ] AC-4: Items with <70% similarity trigger new product creation
- [ ] AC-5: Matching only compares items within the same category (blocking strategy)
- [ ] AC-6: Thresholds (95%, 70%) are configurable via environment variables
- [ ] AC-7: Matching processes at least 1,000 items per minute

**Dependencies:** Phase 1 (supplier_items table), Phase 2 (Admin API for review queue)

---

### FR-2: Characteristics Extractor ("The Enricher")

**Priority:** High

**Description:** Extracts technical specifications from supplier item names and descriptions using pattern matching, enriching the characteristics JSONB field.

**Acceptance Criteria:**

- [ ] AC-1: Extracts voltage values (e.g., "220V", "110-240V") into `characteristics.voltage`
- [ ] AC-2: Extracts power values (e.g., "750W", "1.5kW") into `characteristics.power_watts`
- [ ] AC-3: Extracts weight values (e.g., "2.5kg", "500g") into `characteristics.weight_kg`
- [ ] AC-4: Extracts dimension values (e.g., "30x20x10cm") into `characteristics.dimensions_cm`
- [ ] AC-5: Extraction does not overwrite existing manually-set characteristics
- [ ] AC-6: New extraction patterns can be added by implementing new Strategy classes in Python code
- [ ] AC-7: Invalid/ambiguous values are skipped (no incorrect data)

**Dependencies:** Phase 1 (supplier_items.characteristics JSONB)

---

### FR-3: Price & Availability Aggregation

**Priority:** Critical

**Description:** Automatically calculates and maintains aggregate fields on products whenever linked supplier items change.

**Acceptance Criteria:**

- [ ] AC-1: `product.min_price` equals lowest `current_price` among all linked active supplier items
- [ ] AC-2: `product.availability` is TRUE if any linked supplier has the item in stock
- [ ] AC-3: Aggregates recalculate when supplier item is linked/unlinked
- [ ] AC-4: Aggregates recalculate when supplier item's price changes
- [ ] AC-5: Aggregates recalculate when supplier item's availability changes
- [ ] AC-6: Calculation completes within 10 seconds of triggering event
- [ ] AC-7: MRP field placeholder exists for future competitor price logic

**Dependencies:** Phase 1 (products table, supplier_items table)

---

### FR-4: Manual Override Handling (Feedback Loop)

**Priority:** High

**Description:** Processes manual link/unlink events from users, immediately updating aggregates and protecting manually verified matches from automatic changes.

**Acceptance Criteria:**

- [ ] AC-1: Manual link events received from Admin API trigger immediate aggregate recalculation
- [ ] AC-2: Manual unlink events trigger aggregate recalculation for the affected product
- [ ] AC-3: Manually linked items are marked as `verified_match`
- [ ] AC-4: Items with `verified_match` status are skipped by the automatic matcher
- [ ] AC-5: Users can remove `verified_match` status to allow re-matching
- [ ] AC-6: Audit log records who made manual changes and when

**Dependencies:** Phase 2 (Admin API), Phase 1 (Redis queue for events)

---

### FR-5: Match Review Queue

**Priority:** Medium

**Description:** Maintains a queue of potential matches requiring human review, including suggested candidates and confidence scores.

**Acceptance Criteria:**

- [ ] AC-1: Potential matches are stored with match_score and candidate_product_ids
- [ ] AC-2: Review queue is queryable by category, date range, and confidence score
- [ ] AC-3: Review items expire after 30 days if not actioned (configurable)
- [ ] AC-4: Approved matches become verified_match; rejected items create new products
- [ ] AC-5: Review statistics (pending count, approval rate) are available

**Dependencies:** Phase 2 (Admin API for review UI)

---

## Non-Functional Requirements

### NFR-1: Performance

- Matching throughput: >1,000 items per minute
- Aggregate recalculation: <10 seconds per product
- Extraction throughput: >5,000 items per minute
- Total pipeline latency (ingest → matched → enriched): <5 minutes for batches of 1,000 items

### NFR-2: Accuracy

- High-confidence matches (≥95%) should have <1% false positive rate
- Medium-confidence matches (70-94%) capture 95%+ of true matches
- Extraction patterns should have <5% error rate on valid inputs
- No data loss: characteristics extraction never removes existing data

### NFR-3: Configurability

- Matching thresholds adjustable without code deployment (environment variables)
- New extraction patterns added by implementing Strategy classes in Python code
- Category blocking can be enabled/disabled per supplier
- Review queue expiration period configurable

### NFR-4: Reliability

- Failed matching jobs are retried with exponential backoff (1s, 5s, 25s)
- Dead letter queue for permanently failed items
- Matching state is recoverable after worker restart
- No duplicate matches due to concurrent processing (enforced via pessimistic locking: SELECT FOR UPDATE SKIP LOCKED)
- Backpressure strategy: Accept all items, process FIFO, alert when backlog >10,000 (no ingestion blocking)

### NFR-5: Observability

- Metrics: items_matched_total, items_flagged_for_review, new_products_created
- Metrics: matching_duration_seconds, extraction_duration_seconds
- Alerts: matching backlog >10,000 items, error rate >5%
- Logs: structured JSON with item_id, action, confidence_score

### NFR-6: Access Control

- **Procurement role:** Can view review queue, approve/reject potential matches, manually link items
- **Admin role:** All procurement permissions + can reset verified_match status to unmatched
- **Sales role:** Read-only access to match status (no modification)
- All manual actions are audit-logged with user_id and timestamp

---

## Success Criteria

1. **Catalog Unification Rate:** >90% of supplier items are automatically linked to products within 24 hours of ingestion
2. **Manual Review Reduction:** <10% of items require manual review (flagged as potential_match)
3. **Processing Speed:** 10,000 new items are matched and enriched within 10 minutes
4. **Data Quality:** Product min_price is accurate to within 1 cent of actual lowest supplier price at all times
5. **User Satisfaction:** Procurement users spend <30 minutes daily on manual matching tasks (down from current manual process)
6. **Accuracy Validation:** Random sample of 100 automatic matches shows >99% correct linkage
7. **Enrichment Coverage:** >80% of items with technical specs in text have them extracted to structured characteristics

---

## Key Entities

### New Fields on Existing Tables

**products table:**
- `min_price` - Lowest price among linked suppliers (NUMERIC)
- `availability` - TRUE if any linked supplier item has `characteristics.in_stock = true` (BOOLEAN). Explicit stock flag only; no price-based inference.
- `mrp` - Manufacturer's recommended price, placeholder (NUMERIC, nullable)

**supplier_items table:**
- `match_status` - Enum: unmatched, auto_matched, potential_match, verified_match
- `match_score` - Confidence score of last match attempt (DECIMAL)
- `match_candidates` - JSONB array of potential product matches with scores

**match_status State Transitions:**
- `unmatched` → `auto_matched` (system: high-confidence match)
- `unmatched` → `potential_match` (system: medium-confidence match)
- `unmatched` → `verified_match` (admin: manual link)
- `potential_match` → `verified_match` (admin: approve match)
- `potential_match` → `unmatched` (admin: reject, triggers new product creation)
- `auto_matched` → `verified_match` (admin: confirm match)
- `auto_matched` → `unmatched` (admin: reject match)
- `verified_match` → `unmatched` (admin only: reset for re-matching)

### New Tables

**match_review_queue:**
- `id` - Unique identifier
- `supplier_item_id` - Reference to supplier item needing review
- `candidate_products` - JSONB array of {product_id, score, name}
- `status` - Enum: pending, approved, rejected, expired, needs_category
- `reviewed_by` - User who actioned (nullable)
- `reviewed_at` - Timestamp of action (nullable)
- `created_at` - When item was flagged
- `expires_at` - Auto-expiration timestamp

**Note:** Extraction patterns are implemented as Python Strategy classes (see `services/python-ingestion/src/services/extraction/extractors.py`), not stored in the database. This follows KISS principle—adding new patterns requires implementing a new class, no database schema changes needed.

---

## Assumptions

1. **Category Assignment:** Supplier items have a category_id assigned (either from supplier data or inferred during Phase 1 ingestion). Items without category are flagged for manual review with "needs_category" status instead of attempting full catalog scan.

2. **Text Quality:** Supplier item names are reasonably descriptive (>10 characters average) and contain product identifiers. Very short or coded names may have lower match accuracy.

3. **Single Best Match:** When multiple products have similar scores, the system selects the highest-scoring match. Tie-breaking uses the oldest product (first created wins).

4. **Availability Signal:** Stock availability is derived from `supplier_items.characteristics.in_stock` field (boolean or "yes"/"true" string). Product-level availability is TRUE if ANY linked supplier item has `in_stock = true`. No price-based inference is used (KISS principle).

5. **Queue Integration:** The existing Redis queue infrastructure (arq) from Phase 1 will be extended for matching events. No new queue infrastructure needed.

6. **MRP Deferred:** MRP calculation from competitor pricing (21vek reference in spec) is a placeholder. The field will exist but calculation logic is deferred to a future phase.

---

## Clarifications

### Session 2025-11-30

- Q: How should concurrent workers prevent duplicate matches or product creation? → A: Pessimistic locking (SELECT FOR UPDATE SKIP LOCKED)
- Q: Can verified_match status be reverted to allow re-matching? → A: Admin-reversible only (admin can reset to unmatched)
- Q: Who can access match review queue and manual linking? → A: Procurement can review/approve/reject; Admin can do all + reset verified_match
- Q: How should system behave when matching backlog exceeds capacity? → A: Accept & alert (continue processing in order, alert operators)
- Q: How should items without category assignment be handled? → A: Flag for review with "needs category" status (no full catalog scan)

---

## Glossary

- **Master SKU:** The unified product identifier (internal_sku) that groups supplier items
- **Blocking:** Strategy of limiting comparison candidates by a shared attribute (category) to improve performance
- **Verified Match:** A supplier-to-product link confirmed by a human, protected from automatic changes
- **Characteristics:** Structured JSONB field containing technical specifications (voltage, weight, etc.)
- **Aggregate:** Calculated fields on products derived from linked supplier items (min_price, availability)
- **Confidence Score:** Percentage (0-100) indicating how similar two items are based on fuzzy matching

---

## References

- Phase 1 Data Model: `/specs/001-data-ingestion-infra/plan/data-model.md`
- Phase 2 Admin API: `/specs/002-api-layer/plan/contracts/admin-api.json`
- Python Ingestion Service: `/services/python-ingestion/`

---

**Approval:**

- [ ] Tech Lead: [Name] - [Date]
- [ ] Product: [Name] - [Date]
- [ ] QA: [Name] - [Date]
