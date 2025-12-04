"""
Unit Tests for Extraction Schemas
==================================

Tests for ExtractedProduct, ExtractionResult, and related Pydantic models.
Validates field validation, normalization, and computed properties.

Phase 9: Semantic ETL Pipeline Refactoring
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.schemas.extraction import (
    ChunkExtractionResult,
    ExtractedProduct,
    ExtractionError,
    ExtractionResult,
    LLMExtractionResponse,
)


class TestExtractedProduct:
    """Tests for ExtractedProduct model."""

    def test_valid_product_minimal(self) -> None:
        """Test creating product with only required fields."""
        product = ExtractedProduct(
            name="Test Product",
            price_rrc=Decimal("99.99"),
        )
        assert product.name == "Test Product"
        assert product.price_rrc == Decimal("99.99")
        assert product.description is None
        assert product.price_opt is None
        assert product.category_path == []
        assert product.raw_data == {}

    def test_valid_product_full(self) -> None:
        """Test creating product with all fields."""
        product = ExtractedProduct(
            name="Gaming Laptop",
            description="High-performance laptop for gaming",
            price_opt=Decimal("1200.00"),
            price_rrc=Decimal("1500.00"),
            category_path=["Electronics", "Laptops", "Gaming"],
            raw_data={"row": 5, "sheet": "Products"},
        )
        assert product.name == "Gaming Laptop"
        assert product.description == "High-performance laptop for gaming"
        assert product.price_opt == Decimal("1200.00")
        assert product.price_rrc == Decimal("1500.00")
        assert product.category_path == ["Electronics", "Laptops", "Gaming"]
        assert product.raw_data == {"row": 5, "sheet": "Products"}

    def test_name_normalization_strips_whitespace(self) -> None:
        """Test that name is normalized: whitespace stripped."""
        product = ExtractedProduct(
            name="  Test Product  ",
            price_rrc=Decimal("10.00"),
        )
        assert product.name == "Test Product"

    def test_name_normalization_collapses_spaces(self) -> None:
        """Test that name is normalized: multiple spaces collapsed."""
        product = ExtractedProduct(
            name="Test   Multiple    Spaces",
            price_rrc=Decimal("10.00"),
        )
        assert product.name == "Test Multiple Spaces"

    def test_name_required(self) -> None:
        """Test that name is required."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractedProduct(price_rrc=Decimal("10.00"))  # type: ignore
        assert "name" in str(exc_info.value)

    def test_name_min_length(self) -> None:
        """Test that name has minimum length of 1."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractedProduct(name="", price_rrc=Decimal("10.00"))
        assert "min_length" in str(exc_info.value) or "at least 1" in str(exc_info.value)

    def test_name_max_length(self) -> None:
        """Test that name has maximum length of 500."""
        long_name = "x" * 501
        with pytest.raises(ValidationError) as exc_info:
            ExtractedProduct(name=long_name, price_rrc=Decimal("10.00"))
        assert "max_length" in str(exc_info.value) or "at most 500" in str(exc_info.value)

    def test_price_rrc_required(self) -> None:
        """Test that price_rrc is required."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractedProduct(name="Test")  # type: ignore
        assert "price_rrc" in str(exc_info.value)

    def test_price_rrc_non_negative(self) -> None:
        """Test that price_rrc must be non-negative."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractedProduct(name="Test", price_rrc=Decimal("-1.00"))
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_price_opt_non_negative(self) -> None:
        """Test that price_opt must be non-negative when provided."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractedProduct(
                name="Test",
                price_rrc=Decimal("10.00"),
                price_opt=Decimal("-5.00"),
            )
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_price_opt_optional(self) -> None:
        """Test that price_opt is optional."""
        product = ExtractedProduct(name="Test", price_rrc=Decimal("10.00"))
        assert product.price_opt is None

    def test_category_path_normalization(self) -> None:
        """Test that category_path entries are normalized."""
        product = ExtractedProduct(
            name="Test",
            price_rrc=Decimal("10.00"),
            category_path=["  Electronics  ", "Laptops", "  ", "Gaming"],
        )
        # Should strip whitespace and filter empty strings
        assert product.category_path == ["Electronics", "Laptops", "Gaming"]

    def test_description_normalization_strips_whitespace(self) -> None:
        """Test that description is normalized."""
        product = ExtractedProduct(
            name="Test",
            price_rrc=Decimal("10.00"),
            description="  Some description  ",
        )
        assert product.description == "Some description"

    def test_description_empty_becomes_none(self) -> None:
        """Test that empty/whitespace-only description becomes None."""
        product = ExtractedProduct(
            name="Test",
            price_rrc=Decimal("10.00"),
            description="   ",
        )
        assert product.description is None

    def test_description_max_length(self) -> None:
        """Test that description has maximum length of 2000."""
        long_desc = "x" * 2001
        with pytest.raises(ValidationError) as exc_info:
            ExtractedProduct(
                name="Test",
                price_rrc=Decimal("10.00"),
                description=long_desc,
            )
        assert "max_length" in str(exc_info.value) or "at most 2000" in str(exc_info.value)

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        product = ExtractedProduct(
            name="Test",
            price_rrc=Decimal("10.00"),
            price_opt=Decimal("8.00"),
            description="Desc",
            category_path=["Cat1", "Cat2"],
            raw_data={"row": 1},
        )
        d = product.to_dict()
        assert d["name"] == "Test"
        assert d["price_rrc"] == 10.0
        assert d["price_opt"] == 8.0
        assert d["description"] == "Desc"
        assert d["category_path"] == ["Cat1", "Cat2"]
        assert d["raw_data"] == {"row": 1}

    def test_get_dedup_key(self) -> None:
        """Test deduplication key generation."""
        product = ExtractedProduct(
            name="  Test Product  ",
            price_rrc=Decimal("10.00"),
        )
        key = product.get_dedup_key()
        assert key == "test product"


class TestExtractionError:
    """Tests for ExtractionError model."""

    def test_valid_error(self) -> None:
        """Test creating a valid extraction error."""
        error = ExtractionError(
            row_number=5,
            chunk_id=0,
            error_type="validation",
            error_message="Missing required field: name",
            raw_data={"price": "10.00"},
        )
        assert error.row_number == 5
        assert error.chunk_id == 0
        assert error.error_type == "validation"
        assert error.error_message == "Missing required field: name"

    def test_row_number_must_be_positive(self) -> None:
        """Test that row_number must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractionError(
                row_number=0,
                error_type="validation",
                error_message="Error",
            )
        assert "greater than or equal to 1" in str(exc_info.value)


class TestExtractionResult:
    """Tests for ExtractionResult model."""

    def test_valid_result(self) -> None:
        """Test creating a valid extraction result."""
        products = [
            ExtractedProduct(name="P1", price_rrc=Decimal("10.00")),
            ExtractedProduct(name="P2", price_rrc=Decimal("20.00")),
        ]
        result = ExtractionResult(
            products=products,
            sheet_name="Products",
            total_rows=10,
            successful_extractions=2,
            failed_extractions=8,
        )
        assert len(result.products) == 2
        assert result.sheet_name == "Products"
        assert result.total_rows == 10
        assert result.successful_extractions == 2
        assert result.failed_extractions == 8
        assert result.duplicates_removed == 0

    def test_success_rate_calculation(self) -> None:
        """Test success_rate property calculation."""
        result = ExtractionResult(
            products=[],
            sheet_name="Test",
            total_rows=100,
            successful_extractions=85,
            failed_extractions=15,
        )
        assert result.success_rate == 85.0

    def test_success_rate_zero_rows(self) -> None:
        """Test success_rate with zero total rows."""
        result = ExtractionResult(
            products=[],
            sheet_name="Test",
            total_rows=0,
            successful_extractions=0,
            failed_extractions=0,
        )
        assert result.success_rate == 0.0

    def test_status_success(self) -> None:
        """Test status property returns 'success' at 100%."""
        result = ExtractionResult(
            products=[],
            sheet_name="Test",
            total_rows=100,
            successful_extractions=100,
            failed_extractions=0,
        )
        assert result.status == "success"

    def test_status_completed_with_errors(self) -> None:
        """Test status property returns 'completed_with_errors' at 80-99%."""
        result = ExtractionResult(
            products=[],
            sheet_name="Test",
            total_rows=100,
            successful_extractions=80,
            failed_extractions=20,
        )
        assert result.status == "completed_with_errors"

        result2 = ExtractionResult(
            products=[],
            sheet_name="Test",
            total_rows=100,
            successful_extractions=99,
            failed_extractions=1,
        )
        assert result2.status == "completed_with_errors"

    def test_status_failed(self) -> None:
        """Test status property returns 'failed' below 80%."""
        result = ExtractionResult(
            products=[],
            sheet_name="Test",
            total_rows=100,
            successful_extractions=79,
            failed_extractions=21,
        )
        assert result.status == "failed"

    def test_to_summary_dict(self) -> None:
        """Test conversion to summary dictionary."""
        result = ExtractionResult(
            products=[],
            sheet_name="Products",
            total_rows=100,
            successful_extractions=95,
            failed_extractions=5,
            duplicates_removed=3,
            extraction_errors=[
                ExtractionError(
                    error_type="validation",
                    error_message="Missing name",
                )
            ],
        )
        summary = result.to_summary_dict()
        assert summary["sheet_name"] == "Products"
        assert summary["total_rows"] == 100
        assert summary["successful_extractions"] == 95
        assert summary["failed_extractions"] == 5
        assert summary["duplicates_removed"] == 3
        assert summary["success_rate"] == 95.0
        assert summary["status"] == "completed_with_errors"
        assert summary["error_count"] == 1


class TestChunkExtractionResult:
    """Tests for ChunkExtractionResult model."""

    def test_valid_chunk_result(self) -> None:
        """Test creating a valid chunk extraction result."""
        result = ChunkExtractionResult(
            chunk_id=0,
            start_row=1,
            end_row=25,
            products=[
                ExtractedProduct(name="P1", price_rrc=Decimal("10.00")),
            ],
            processing_time_ms=1500,
        )
        assert result.chunk_id == 0
        assert result.start_row == 1
        assert result.end_row == 25
        assert len(result.products) == 1
        assert result.processing_time_ms == 1500

    def test_chunk_id_non_negative(self) -> None:
        """Test that chunk_id must be non-negative."""
        with pytest.raises(ValidationError) as exc_info:
            ChunkExtractionResult(
                chunk_id=-1,
                start_row=1,
                end_row=10,
            )
        assert "greater than or equal to 0" in str(exc_info.value)


class TestLLMExtractionResponse:
    """Tests for LLMExtractionResponse model."""

    def test_valid_response(self) -> None:
        """Test creating a valid LLM extraction response."""
        response = LLMExtractionResponse(
            products=[
                ExtractedProduct(name="P1", price_rrc=Decimal("10.00")),
            ],
            parsing_notes="Some ambiguity in column 3",
        )
        assert len(response.products) == 1
        assert response.parsing_notes == "Some ambiguity in column 3"

    def test_empty_products_allowed(self) -> None:
        """Test that empty products list is allowed."""
        response = LLMExtractionResponse(products=[])
        assert response.products == []
        assert response.parsing_notes is None

