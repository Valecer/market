# Research: Advanced Pricing and Categorization

**Phase:** 009  
**Date:** 2025-12-03  
**Status:** Complete

---

## Overview

This document captures research decisions for implementing dual pricing (retail/wholesale) with currency tracking on the Product entity using the existing Python SQLAlchemy ORM stack.

---

## Decision 1: Decimal Type for Monetary Fields

### Decision
Use `Numeric(10, 2)` (SQLAlchemy) / `DECIMAL(10,2)` (PostgreSQL) for all monetary fields.

### Rationale
- **Exact arithmetic**: Avoids floating-point errors inherent in `FLOAT` or `REAL` types
- **Consistency**: Existing `min_price`, `mrp`, and `current_price` fields already use `Numeric(10, 2)`
- **Industry standard**: Financial applications require exact decimal representation
- **Precision**: 10 digits total, 2 decimal places supports values up to 99,999,999.99

### Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| `Numeric(10, 2)` | Exact, consistent with existing | None | ✅ Selected |
| `Float` | Native Python type | Rounding errors, not suitable for money | ❌ Rejected |
| `Integer` (cents) | Exact, fast | Requires conversion everywhere | ❌ Rejected |
| `Numeric(12, 4)` | More precision | Inconsistent with existing fields | ❌ Rejected |

---

## Decision 2: Currency Code Storage

### Decision
Use `String(3)` with application-level validation for ISO 4217 format (3 uppercase letters).

### Rationale
- **Simplicity**: Simple format validation (regex: `^[A-Z]{3}$`) vs. maintaining full ISO 4217 lookup table
- **Flexibility**: Allows future currencies without schema changes
- **Spec requirement**: Only validate format, not ISO 4217 registry membership (per spec risk mitigation)
- **Nullable**: Existing products default to `NULL` (backward compatibility)

### Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| `String(3)` + regex | Simple, flexible | No registry validation | ✅ Selected |
| `ENUM` type | Type safety | Requires migration for new currencies | ❌ Rejected |
| Lookup table FK | Full validation | Over-engineered for use case | ❌ Rejected |
| `String(10)` | Future proof | Wastes space, inconsistent with standard | ❌ Rejected |

### Validation Implementation
```python
# Pydantic validator for API input
from pydantic import field_validator
import re

class ProductPricingUpdate(BaseModel):
    currency_code: str | None = None
    
    @field_validator('currency_code')
    @classmethod
    def validate_currency_code(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r'^[A-Z]{3}$', v):
            raise ValueError('Currency code must be 3 uppercase letters (ISO 4217)')
        return v
```

---

## Decision 3: Migration Strategy

### Decision
Use non-blocking `ALTER TABLE ADD COLUMN` with `NULL` defaults for zero-downtime deployment.

### Rationale
- **Zero downtime**: PostgreSQL `ADD COLUMN` with `NULL` default is non-blocking
- **Backward compatibility**: All new fields are nullable; existing queries unaffected
- **Spec compliance**: FR-1 AC-5 and FR-2 AC-4 require null defaults for existing records
- **Atomic**: Single migration file adds all three columns

### Migration Sequence
1. Add `retail_price DECIMAL(10,2) NULL` — non-blocking
2. Add `wholesale_price DECIMAL(10,2) NULL` — non-blocking
3. Add `currency_code VARCHAR(3) NULL` — non-blocking
4. Add check constraint for non-negative prices — non-blocking (for new rows)

### Why NOT Default Currency to 'USD'
The spec explicitly states:
> "FR-2 AC-4: Existing products without currency code default to null after migration"

Setting a default would misrepresent data provenance. Legacy products with `min_price` came from supplier aggregation, not direct currency assignment.

---

## Decision 4: Category Hierarchy (No Changes Required)

### Decision
Retain existing adjacency list pattern; no modifications to Category entity.

### Rationale
The Category model already implements self-referential hierarchy:

```python
# Existing implementation in src/db/models/category.py
parent_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("categories.id", ondelete="CASCADE"),
    nullable=True,
    index=True
)
parent: Mapped[Optional["Category"]] = relationship(
    remote_side="Category.id",
    back_populates="children"
)
children: Mapped[List["Category"]] = relationship(back_populates="parent")
```

- **Infinite nesting**: Already supported via `parent_id` self-reference
- **ON DELETE CASCADE**: Deleting parent removes children (spec requirement)
- **Indexed**: `parent_id` already indexed for performance
- **Spec alignment**: "No changes to Category entity required" (spec line 163)

---

## Decision 5: Price Field Constraint Strategy

### Decision
Add database-level `CHECK` constraint for non-negative prices.

### Rationale
- **Data integrity**: Prevents negative prices at database level
- **Existing pattern**: `supplier_items.current_price` already uses `CHECK (price >= 0)`
- **Spec requirement**: FR-1 AC-4 "Prices must be non-negative (≥ 0) when present"

### Constraint Definition
```sql
ALTER TABLE products ADD CONSTRAINT check_retail_price_non_negative 
  CHECK (retail_price IS NULL OR retail_price >= 0);

ALTER TABLE products ADD CONSTRAINT check_wholesale_price_non_negative 
  CHECK (wholesale_price IS NULL OR wholesale_price >= 0);
```

---

## Decision 6: Index Strategy

### Decision
Initially NO indexes on new pricing columns; add if query patterns emerge.

### Rationale
- **KISS principle**: Spec states "indexed only if needed"
- **Low cardinality**: Prices are not typically used for filtering
- **Query patterns**: Primary access is by category, status, SKU (all indexed)
- **Future flexibility**: Easy to add indexes later without schema lock

### When to Add Indexes
- If reports query `WHERE retail_price BETWEEN X AND Y` frequently
- If sorting by price becomes a common operation
- Monitor query plans after feature launch

---

## Technical Context Summary

| Aspect | Decision | Source |
|--------|----------|--------|
| ORM | SQLAlchemy 2.0 AsyncIO | Existing stack |
| Migration tool | Alembic | Existing stack |
| Decimal type | `Numeric(10, 2)` | Consistency with `min_price` |
| Currency storage | `String(3)` nullable | ISO 4217 format |
| Category hierarchy | Adjacency list (existing) | No changes |
| Migration strategy | Non-blocking ADD COLUMN | Zero downtime |
| Default values | `NULL` for all new fields | Backward compatibility |
| Constraints | CHECK ≥ 0 for prices | Data integrity |

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| SQLAlchemy | 2.0+ | ORM with async support |
| Alembic | 1.13+ | Database migrations |
| Pydantic | 2.x | Request validation |
| PostgreSQL | 16 | DECIMAL type, CHECK constraints |

---

## Risk Assessment

| Risk | Probability | Mitigation |
|------|-------------|------------|
| Migration blocks table | Low | NULL defaults are non-blocking |
| Float precision issues | Eliminated | Using Numeric type |
| Invalid currency codes | Low | Regex validation in Pydantic |
| Breaking existing queries | Low | All fields nullable |

---

## References

- [ISO 4217 Currency Codes](https://www.iso.org/iso-4217-currency-codes.html)
- [PostgreSQL NUMERIC Type](https://www.postgresql.org/docs/16/datatype-numeric.html)
- [SQLAlchemy Numeric Column](https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Numeric)
- [Alembic Operations](https://alembic.sqlalchemy.org/en/latest/ops.html)
- Existing migration: `002_add_matching_pipeline.py`

