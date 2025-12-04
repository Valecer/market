"""
E2E Test: Deduplication (T051)
===============================

Tests within-file deduplication of extracted products:
1. Verify duplicates are detected by normalized name
2. Verify price tolerance (1%) is applied
3. Verify deduplication stats are tracked

Phase 9: Semantic ETL Pipeline Refactoring
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

# Test data paths
TEST_DATA_DIR = Path("/Users/valecer/work/sites/marketbel/specs/009-semantic-etl/test_data")
METADATA_FILE = TEST_DATA_DIR / "test_metadata.json"


@pytest.fixture(scope="module")
def test_metadata() -> dict[str, Any]:
    """Load test metadata for validation."""
    if METADATA_FILE.exists():
        with open(METADATA_FILE) as f:
            return json.load(f)
    return {"standard_file": {"duplicates": [], "duplicate_count": 0}}


class TestDeduplicationServiceUnit:
    """Unit tests for DeduplicationService."""

    def test_deduplicate_empty_list(self):
        """Test deduplication of empty list."""
        from src.services.deduplication_service import DeduplicationService
        
        service = DeduplicationService(price_tolerance=0.01)
        unique, stats = service.deduplicate([])
        
        assert unique == []
        assert stats.total_products == 0
        assert stats.duplicates_removed == 0

    def test_deduplicate_no_duplicates(self):
        """Test deduplication when no duplicates exist."""
        from src.services.deduplication_service import DeduplicationService
        from src.schemas.extraction import ExtractedProduct
        
        service = DeduplicationService(price_tolerance=0.01)
        
        products = [
            ExtractedProduct(
                name="Product A",
                price_rrc=Decimal("100.00"),
                category_path=["Electronics"],
            ),
            ExtractedProduct(
                name="Product B",
                price_rrc=Decimal("200.00"),
                category_path=["Electronics"],
            ),
            ExtractedProduct(
                name="Product C",
                price_rrc=Decimal("300.00"),
                category_path=["Home"],
            ),
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 3
        assert stats.duplicates_removed == 0
        assert stats.total_products == 3
        assert stats.unique_products == 3

    def test_deduplicate_exact_duplicates(self):
        """Test deduplication of exact duplicates (same name, same price)."""
        from src.services.deduplication_service import DeduplicationService
        from src.schemas.extraction import ExtractedProduct
        
        service = DeduplicationService(price_tolerance=0.01)
        
        products = [
            ExtractedProduct(
                name="Samsung Galaxy S24",
                price_rrc=Decimal("999.00"),
                category_path=["Smartphones"],
            ),
            ExtractedProduct(
                name="Samsung Galaxy S24",  # Duplicate
                price_rrc=Decimal("999.00"),
                category_path=["Smartphones"],
            ),
            ExtractedProduct(
                name="iPhone 15 Pro",
                price_rrc=Decimal("1199.00"),
                category_path=["Smartphones"],
            ),
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 2
        assert stats.duplicates_removed == 1
        assert stats.total_products == 3
        assert stats.unique_products == 2

    def test_deduplicate_case_insensitive(self):
        """Test that name matching is case-insensitive."""
        from src.services.deduplication_service import DeduplicationService
        from src.schemas.extraction import ExtractedProduct
        
        service = DeduplicationService(price_tolerance=0.01, case_sensitive=False)
        
        products = [
            ExtractedProduct(
                name="SAMSUNG Galaxy S24",
                price_rrc=Decimal("999.00"),
                category_path=["Smartphones"],
            ),
            ExtractedProduct(
                name="samsung galaxy s24",  # Same name, different case
                price_rrc=Decimal("999.00"),
                category_path=["Smartphones"],
            ),
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 1
        assert stats.duplicates_removed == 1

    def test_deduplicate_price_within_tolerance(self):
        """
        Test that products with prices within 1% tolerance are duplicates.
        
        Phase 3 criterion: hash-based dedup on normalized name + price (1% tolerance).
        """
        from src.services.deduplication_service import DeduplicationService
        from src.schemas.extraction import ExtractedProduct
        
        service = DeduplicationService(price_tolerance=0.01)  # 1% tolerance
        
        products = [
            ExtractedProduct(
                name="Test Product",
                price_rrc=Decimal("100.00"),  # Base price
                category_path=["Test"],
            ),
            ExtractedProduct(
                name="Test Product",
                price_rrc=Decimal("100.50"),  # 0.5% higher - within tolerance
                category_path=["Test"],
            ),
            ExtractedProduct(
                name="Test Product",
                price_rrc=Decimal("99.50"),  # 0.5% lower - within tolerance
                category_path=["Test"],
            ),
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 1, "Products within 1% tolerance should be duplicates"
        assert stats.duplicates_removed == 2

    def test_deduplicate_price_outside_tolerance(self):
        """Test that products with prices outside 1% tolerance are kept separate."""
        from src.services.deduplication_service import DeduplicationService
        from src.schemas.extraction import ExtractedProduct
        
        service = DeduplicationService(price_tolerance=0.01)  # 1% tolerance
        
        products = [
            ExtractedProduct(
                name="Test Product",
                price_rrc=Decimal("100.00"),  # Base price
                category_path=["Test"],
            ),
            ExtractedProduct(
                name="Test Product",
                price_rrc=Decimal("102.00"),  # 2% higher - outside tolerance
                category_path=["Test"],
            ),
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 2, "Products outside 1% tolerance should be kept"
        assert stats.duplicates_removed == 0

    def test_deduplicate_first_occurrence_kept(self):
        """Test that first occurrence is kept when duplicates found."""
        from src.services.deduplication_service import DeduplicationService
        from src.schemas.extraction import ExtractedProduct
        
        service = DeduplicationService(price_tolerance=0.01)
        
        products = [
            ExtractedProduct(
                name="Test Product",
                price_rrc=Decimal("100.00"),
                description="First occurrence",
                category_path=["Test"],
            ),
            ExtractedProduct(
                name="Test Product",
                price_rrc=Decimal("100.00"),
                description="Second occurrence (duplicate)",
                category_path=["Test"],
            ),
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 1
        assert unique[0].description == "First occurrence"

    def test_deduplicate_whitespace_normalization(self):
        """Test that whitespace in names is normalized."""
        from src.services.deduplication_service import DeduplicationService
        from src.schemas.extraction import ExtractedProduct
        
        service = DeduplicationService(price_tolerance=0.01)
        
        products = [
            ExtractedProduct(
                name="Test  Product",  # Double space
                price_rrc=Decimal("100.00"),
                category_path=["Test"],
            ),
            ExtractedProduct(
                name="Test Product",  # Single space
                price_rrc=Decimal("100.00"),
                category_path=["Test"],
            ),
        ]
        
        unique, stats = service.deduplicate(products)
        
        # Whitespace should be normalized by ExtractedProduct validator
        assert len(unique) == 1
        assert stats.duplicates_removed == 1


class TestDeduplicationStats:
    """Test deduplication statistics."""

    def test_dedup_rate_calculation(self):
        """Test deduplication rate calculation."""
        from src.services.deduplication_service import DeduplicationStats
        
        stats = DeduplicationStats(
            total_products=100,
            unique_products=90,
            duplicates_removed=10,
            duplicate_groups=5,
        )
        
        assert stats.dedup_rate == 10.0  # 10%

    def test_dedup_rate_zero_products(self):
        """Test dedup rate when no products."""
        from src.services.deduplication_service import DeduplicationStats
        
        stats = DeduplicationStats()
        
        assert stats.dedup_rate == 0.0


class TestFindDuplicates:
    """Test the find_duplicates analysis method."""

    def test_find_duplicates_empty(self):
        """Test finding duplicates in empty list."""
        from src.services.deduplication_service import DeduplicationService
        
        service = DeduplicationService(price_tolerance=0.01)
        groups = service.find_duplicates([])
        
        assert groups == []

    def test_find_duplicates_identifies_groups(self):
        """Test that duplicate groups are correctly identified."""
        from src.services.deduplication_service import DeduplicationService
        from src.schemas.extraction import ExtractedProduct
        
        service = DeduplicationService(price_tolerance=0.01)
        
        products = [
            ExtractedProduct(
                name="Product A",
                price_rrc=Decimal("100.00"),
                category_path=["Test"],
            ),
            ExtractedProduct(
                name="Product A",  # Duplicate of first
                price_rrc=Decimal("100.00"),
                category_path=["Test"],
            ),
            ExtractedProduct(
                name="Product A",  # Another duplicate
                price_rrc=Decimal("100.50"),  # Within tolerance
                category_path=["Test"],
            ),
            ExtractedProduct(
                name="Product B",  # Different product
                price_rrc=Decimal("200.00"),
                category_path=["Test"],
            ),
        ]
        
        groups = service.find_duplicates(products)
        
        # Should find one duplicate group (Product A)
        assert len(groups) == 1
        assert groups[0].key == "product a"
        assert groups[0].removed_count == 2  # 2 duplicates in the group


class TestDeduplicationWithTestData:
    """Test deduplication with generated test data."""

    def test_expected_duplicates_removed(self, test_metadata):
        """
        Test that expected number of duplicates from test data are removed.
        
        Uses metadata from generated test file to validate deduplication.
        """
        from src.services.deduplication_service import DeduplicationService
        from src.schemas.extraction import ExtractedProduct
        from decimal import Decimal
        
        # Get expected duplicate count from metadata
        expected_duplicates = test_metadata.get("standard_file", {}).get("duplicate_count", 0)
        
        if expected_duplicates == 0:
            pytest.skip("No duplicates in test data")
        
        service = DeduplicationService(price_tolerance=0.01)
        
        # Create products from test data metadata
        duplicates_info = test_metadata.get("standard_file", {}).get("duplicates", [])
        if not duplicates_info:
            pytest.skip("No duplicate info in metadata")
        
        # Simulate products including duplicates
        products = []
        for i in range(10):  # 10 unique products
            products.append(ExtractedProduct(
                name=f"Unique Product {i}",
                price_rrc=Decimal(str(100 + i * 10)),
                category_path=["Test"],
            ))
        
        # Add duplicates
        for dup in duplicates_info[:5]:
            products.append(ExtractedProduct(
                name=dup["name"],
                price_rrc=Decimal(str(dup.get("duplicate_price", 100))),
                category_path=["Test"],
            ))
            # Add original
            products.insert(0, ExtractedProduct(
                name=dup["name"],
                price_rrc=Decimal(str(dup.get("original_price", 100))),
                category_path=["Test"],
            ))
        
        unique, stats = service.deduplicate(products)
        
        # Should remove duplicates
        assert stats.duplicates_removed > 0, "Expected some duplicates to be removed"
        assert len(unique) < len(products), "Unique list should be smaller"


class TestEdgeCases:
    """Test edge cases in deduplication."""

    def test_special_characters_in_name(self):
        """Test products with special characters in names."""
        from src.services.deduplication_service import DeduplicationService
        from src.schemas.extraction import ExtractedProduct
        
        service = DeduplicationService(price_tolerance=0.01)
        
        products = [
            ExtractedProduct(
                name="Product (Special)",
                price_rrc=Decimal("100.00"),
                category_path=["Test"],
            ),
            ExtractedProduct(
                name="Product (Special)",  # Same special chars
                price_rrc=Decimal("100.00"),
                category_path=["Test"],
            ),
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 1
        assert stats.duplicates_removed == 1

    def test_unicode_in_name(self):
        """Test products with Unicode characters in names."""
        from src.services.deduplication_service import DeduplicationService
        from src.schemas.extraction import ExtractedProduct
        
        service = DeduplicationService(price_tolerance=0.01)
        
        products = [
            ExtractedProduct(
                name="Ноутбук Samsung",  # Russian
                price_rrc=Decimal("100.00"),
                category_path=["Test"],
            ),
            ExtractedProduct(
                name="Ноутбук Samsung",  # Same Russian text
                price_rrc=Decimal("100.00"),
                category_path=["Test"],
            ),
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 1
        assert stats.duplicates_removed == 1

    def test_zero_price_handling(self):
        """Test handling of zero prices."""
        from src.services.deduplication_service import DeduplicationService
        from src.schemas.extraction import ExtractedProduct
        
        service = DeduplicationService(price_tolerance=0.01)
        
        products = [
            ExtractedProduct(
                name="Free Product",
                price_rrc=Decimal("0.00"),
                category_path=["Test"],
            ),
            ExtractedProduct(
                name="Free Product",  # Same name, zero price
                price_rrc=Decimal("0.00"),
                category_path=["Test"],
            ),
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 1
        assert stats.duplicates_removed == 1

