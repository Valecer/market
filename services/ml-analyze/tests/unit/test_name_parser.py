"""
Unit Tests for Composite Name Parser
====================================

Tests for src/utils/name_parser.py module.
"""

import pytest

from src.utils.name_parser import (
    CompositeNameResult,
    parse_category_hierarchy,
    parse_composite_name,
    parse_composite_name_with_fallback,
)


class TestParseCategoryHierarchy:
    """Tests for parse_category_hierarchy function."""

    def test_slash_separator(self) -> None:
        """Test category parsing with slash separator."""
        result = parse_category_hierarchy("Electronics/Bikes/Adult")
        assert result == ["Electronics", "Bikes", "Adult"]

    def test_arrow_separator(self) -> None:
        """Test category parsing with > separator."""
        result = parse_category_hierarchy("Electronics > Bikes > Adult")
        assert result == ["Electronics", "Bikes", "Adult"]

    def test_single_category(self) -> None:
        """Test single category without hierarchy."""
        result = parse_category_hierarchy("Simple Category")
        assert result == ["Simple Category"]

    def test_whitespace_handling(self) -> None:
        """Test that whitespace is properly trimmed."""
        result = parse_category_hierarchy("  Spaced / Category  ")
        assert result == ["Spaced", "Category"]

    def test_empty_string(self) -> None:
        """Test empty string returns empty list."""
        assert parse_category_hierarchy("") == []
        assert parse_category_hierarchy("   ") == []

    def test_empty_segments_filtered(self) -> None:
        """Test that empty segments are filtered out."""
        result = parse_category_hierarchy("Electronics//Bikes")
        assert result == ["Electronics", "Bikes"]


class TestParseCompositeName:
    """Tests for parse_composite_name function."""

    def test_basic_composite_parsing(self) -> None:
        """Test basic three-segment composite name."""
        result = parse_composite_name(
            "Electric Bicycle | Shtenli Model Gt11 | Li-ion 48V 15Ah"
        )

        assert result.category_path == ["Electric Bicycle"]
        assert result.name == "Shtenli Model Gt11"
        assert result.description == "Li-ion 48V 15Ah"
        assert result.was_parsed is True
        assert result.raw_composite is not None

    def test_category_with_hierarchy(self) -> None:
        """Test category with slash hierarchy."""
        result = parse_composite_name("Electronics/Bikes | Mountain Pro | 27.5 inch")

        assert result.category_path == ["Electronics", "Bikes"]
        assert result.name == "Mountain Pro"
        assert result.description == "27.5 inch"

    def test_category_with_arrow_hierarchy(self) -> None:
        """Test category with arrow hierarchy."""
        result = parse_composite_name("Electronics > Phones | iPhone 15 | 256GB")

        assert result.category_path == ["Electronics", "Phones"]
        assert result.name == "iPhone 15"
        assert result.description == "256GB"

    def test_multiple_description_segments(self) -> None:
        """Test multiple description segments are concatenated."""
        result = parse_composite_name(
            "Electronics/Bikes | Mountain Pro | 27.5 inch | Shimano | Black"
        )

        assert result.description == "27.5 inch Shimano Black"

    def test_no_delimiter_returns_name_only(self) -> None:
        """Test string without delimiter is returned as name."""
        result = parse_composite_name("Simple Product Name")

        assert result.category_path == []
        assert result.name == "Simple Product Name"
        assert result.description is None
        assert result.was_parsed is False
        assert result.raw_composite is None  # Not a composite

    def test_two_segments_category_and_name(self) -> None:
        """Test two-segment composite (category | name)."""
        result = parse_composite_name("Electronics | Laptop")

        assert result.category_path == ["Electronics"]
        assert result.name == "Laptop"
        assert result.description is None

    def test_empty_first_segment(self) -> None:
        """Test handling of empty first segment."""
        result = parse_composite_name(" | Name Only")

        assert result.category_path == []
        assert result.name == "Name Only"

    def test_empty_second_segment(self) -> None:
        """Test handling of empty second segment."""
        result = parse_composite_name("Category Only | ")

        assert result.category_path == ["Category Only"]
        assert result.name == ""

    def test_whitespace_trimming(self) -> None:
        """Test whitespace is properly trimmed from all segments."""
        result = parse_composite_name(
            "  Electronics  |  Laptop Pro  |  Intel i7  "
        )

        assert result.category_path == ["Electronics"]
        assert result.name == "Laptop Pro"
        assert result.description == "Intel i7"

    def test_empty_string(self) -> None:
        """Test empty string input."""
        result = parse_composite_name("")

        assert result.category_path == []
        assert result.name == ""
        assert result.was_parsed is False

    def test_custom_delimiter(self) -> None:
        """Test parsing with custom delimiter."""
        result = parse_composite_name(
            "Electronics ; Laptop ; Intel i7",
            delimiter=";"
        )

        assert result.category_path == ["Electronics"]
        assert result.name == "Laptop"
        assert result.description == "Intel i7"

    def test_all_empty_segments(self) -> None:
        """Test string with only delimiters."""
        result = parse_composite_name("|||")

        assert result.category_path == []
        assert result.name == ""
        assert result.was_parsed is True

    def test_result_is_frozen(self) -> None:
        """Test that CompositeNameResult is immutable."""
        result = parse_composite_name("Cat | Name")

        with pytest.raises(Exception):  # FrozenInstanceError
            result.name = "Changed"  # type: ignore[misc]


class TestParseCompositeNameWithFallback:
    """Tests for parse_composite_name_with_fallback function."""

    def test_normal_parsing(self) -> None:
        """Test normal parsing works the same."""
        result = parse_composite_name_with_fallback(
            "Category | Name | Description"
        )

        assert result.category_path == ["Category"]
        assert result.name == "Name"
        assert result.description == "Description"

    def test_fallback_on_all_empty_segments(self) -> None:
        """Test fallback when all segments are empty."""
        result = parse_composite_name_with_fallback("|||")

        # With fallback enabled, original string becomes name
        assert result.name == "|||"
        assert result.was_parsed is False

    def test_empty_string_handling(self) -> None:
        """Test empty string returns empty result."""
        result = parse_composite_name_with_fallback("")

        assert result.name == ""
        assert result.was_parsed is False

    def test_whitespace_only_handling(self) -> None:
        """Test whitespace-only string."""
        result = parse_composite_name_with_fallback("   ")

        assert result.name == ""
        assert result.was_parsed is False


class TestCompositeNameResultDataclass:
    """Tests for CompositeNameResult dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        result = CompositeNameResult(
            category_path=[],
            name="Test",
        )

        assert result.description is None
        assert result.raw_composite is None
        assert result.was_parsed is False

    def test_all_fields_set(self) -> None:
        """Test all fields can be set."""
        result = CompositeNameResult(
            category_path=["Cat1", "Cat2"],
            name="Product",
            description="A great product",
            raw_composite="Cat1/Cat2 | Product | A great product",
            was_parsed=True,
        )

        assert result.category_path == ["Cat1", "Cat2"]
        assert result.name == "Product"
        assert result.description == "A great product"
        assert result.raw_composite == "Cat1/Cat2 | Product | A great product"
        assert result.was_parsed is True


class TestRealWorldExamples:
    """Tests with real-world composite name examples."""

    def test_russian_product_name(self) -> None:
        """Test Russian language product name."""
        result = parse_composite_name(
            "Электровелосипеды | Shtenli E-bike GT11 | Li-ion 48V 15Ah"
        )

        assert result.category_path == ["Электровелосипеды"]
        assert result.name == "Shtenli E-bike GT11"
        assert result.description == "Li-ion 48V 15Ah"

    def test_deep_category_hierarchy(self) -> None:
        """Test deep category hierarchy."""
        result = parse_composite_name(
            "Electronics/Computers/Laptops/Gaming | ASUS ROG | RTX 4090, 32GB RAM"
        )

        assert result.category_path == ["Electronics", "Computers", "Laptops", "Gaming"]
        assert result.name == "ASUS ROG"

    def test_product_with_special_characters(self) -> None:
        """Test product name with special characters."""
        result = parse_composite_name(
            "Tools | Drill (1500W) | Bosch™ Professional"
        )

        assert result.category_path == ["Tools"]
        assert result.name == "Drill (1500W)"
        assert result.description == "Bosch™ Professional"

    def test_product_with_measurements(self) -> None:
        """Test product with measurements in name."""
        result = parse_composite_name(
            "Furniture | Table 120x80cm | Oak, Natural Finish"
        )

        assert result.name == "Table 120x80cm"
        assert result.description == "Oak, Natural Finish"

