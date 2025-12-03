"""Unit tests for Product pricing fields (Phase 9).

Tests for:
- Pydantic validation models
- SQLAlchemy model pricing fields
- Currency code validation
- Price non-negativity constraints
"""
import pytest
from decimal import Decimal
from pydantic import ValidationError

from src.models.product_pricing import (
    ProductPricingUpdate,
    ProductPricingResponse,
    ProductPricingBulkUpdate,
)


class TestProductPricingUpdate:
    """Tests for ProductPricingUpdate Pydantic model."""

    def test_valid_complete_update(self):
        """Test valid complete pricing update."""
        data = {
            "retail_price": "99.99",
            "wholesale_price": "79.99",
            "currency_code": "USD"
        }
        model = ProductPricingUpdate(**data)
        assert model.retail_price == Decimal("99.99")
        assert model.wholesale_price == Decimal("79.99")
        assert model.currency_code == "USD"

    def test_valid_partial_update_retail_only(self):
        """Test valid partial update with only retail price."""
        model = ProductPricingUpdate(retail_price="149.99")
        assert model.retail_price == Decimal("149.99")
        assert model.wholesale_price is None
        assert model.currency_code is None

    def test_valid_partial_update_currency_only(self):
        """Test valid partial update with only currency code."""
        model = ProductPricingUpdate(currency_code="EUR")
        assert model.retail_price is None
        assert model.wholesale_price is None
        assert model.currency_code == "EUR"

    def test_valid_empty_update(self):
        """Test empty update (all fields None)."""
        model = ProductPricingUpdate()
        assert model.retail_price is None
        assert model.wholesale_price is None
        assert model.currency_code is None

    def test_valid_zero_price(self):
        """Test zero price is valid (free products)."""
        model = ProductPricingUpdate(retail_price="0.00")
        assert model.retail_price == Decimal("0.00")

    def test_invalid_negative_retail_price(self):
        """Test negative retail price is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ProductPricingUpdate(retail_price="-5.00")
        assert "greater than or equal to 0" in str(exc_info.value).lower() or "ge" in str(exc_info.value).lower()

    def test_invalid_negative_wholesale_price(self):
        """Test negative wholesale price is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ProductPricingUpdate(wholesale_price="-10.00")
        assert "greater than or equal to 0" in str(exc_info.value).lower() or "ge" in str(exc_info.value).lower()

    def test_invalid_currency_code_lowercase(self):
        """Test lowercase currency code is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ProductPricingUpdate(currency_code="usd")
        assert "uppercase" in str(exc_info.value).lower() or "iso 4217" in str(exc_info.value).lower()

    def test_invalid_currency_code_too_short(self):
        """Test currency code with less than 3 characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ProductPricingUpdate(currency_code="US")
        assert "length" in str(exc_info.value).lower() or "3" in str(exc_info.value)

    def test_invalid_currency_code_too_long(self):
        """Test currency code with more than 3 characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ProductPricingUpdate(currency_code="USDD")
        assert "length" in str(exc_info.value).lower() or "3" in str(exc_info.value)

    def test_invalid_currency_code_numbers(self):
        """Test currency code with numbers is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ProductPricingUpdate(currency_code="US1")
        assert "uppercase" in str(exc_info.value).lower() or "iso 4217" in str(exc_info.value).lower()

    def test_valid_common_currencies(self):
        """Test common currency codes are valid."""
        valid_codes = ["USD", "EUR", "RUB", "CNY", "BYN", "GBP", "JPY"]
        for code in valid_codes:
            model = ProductPricingUpdate(currency_code=code)
            assert model.currency_code == code


class TestProductPricingResponse:
    """Tests for ProductPricingResponse Pydantic model."""

    def test_valid_complete_response(self):
        """Test valid complete response with all fields."""
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "internal_sku": "PROD-001",
            "name": "USB-C Cable 2m",
            "category_id": "660e8400-e29b-41d4-a716-446655440000",
            "status": "active",
            "min_price": "9.99",
            "availability": True,
            "mrp": "19.99",
            "retail_price": "14.99",
            "wholesale_price": "11.99",
            "currency_code": "USD"
        }
        model = ProductPricingResponse(**data)
        assert model.id == "550e8400-e29b-41d4-a716-446655440000"
        assert model.retail_price == Decimal("14.99")
        assert model.wholesale_price == Decimal("11.99")
        assert model.currency_code == "USD"

    def test_valid_response_with_null_pricing(self):
        """Test valid response with null pricing fields (legacy product)."""
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "internal_sku": "PROD-001",
            "name": "USB-C Cable 2m",
            "category_id": None,
            "status": "draft",
        }
        model = ProductPricingResponse(**data)
        assert model.retail_price is None
        assert model.wholesale_price is None
        assert model.currency_code is None

    def test_response_from_attributes(self):
        """Test model can be created from ORM attributes."""
        # Simulate an ORM object
        class MockProduct:
            id = "550e8400-e29b-41d4-a716-446655440000"
            internal_sku = "PROD-001"
            name = "Test Product"
            category_id = None
            status = "active"
            min_price = Decimal("9.99")
            availability = True
            mrp = None
            retail_price = Decimal("14.99")
            wholesale_price = Decimal("11.99")
            currency_code = "EUR"

        model = ProductPricingResponse.model_validate(MockProduct())
        assert model.retail_price == Decimal("14.99")
        assert model.currency_code == "EUR"


class TestProductPricingBulkUpdate:
    """Tests for ProductPricingBulkUpdate Pydantic model."""

    def test_valid_bulk_update(self):
        """Test valid bulk update with multiple product IDs."""
        data = {
            "product_ids": [
                "550e8400-e29b-41d4-a716-446655440000",
                "660e8400-e29b-41d4-a716-446655440001"
            ],
            "retail_price": "99.99",
            "currency_code": "USD"
        }
        model = ProductPricingBulkUpdate(**data)
        assert len(model.product_ids) == 2
        assert model.retail_price == Decimal("99.99")
        assert model.currency_code == "USD"

    def test_invalid_empty_product_ids(self):
        """Test bulk update with empty product_ids is rejected."""
        with pytest.raises(ValidationError):
            ProductPricingBulkUpdate(product_ids=[])

    def test_invalid_currency_in_bulk(self):
        """Test invalid currency code in bulk update is rejected."""
        with pytest.raises(ValidationError):
            ProductPricingBulkUpdate(
                product_ids=["550e8400-e29b-41d4-a716-446655440000"],
                currency_code="invalid"
            )

