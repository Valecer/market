"""
Unit Tests for DeduplicationService
===================================

Tests hash-based deduplication with price tolerance.

Phase 9: Semantic ETL Pipeline Refactoring
"""

from decimal import Decimal

import pytest

from src.schemas.extraction import ExtractedProduct
from src.services.deduplication_service import (
    DeduplicationService,
    DeduplicationStats,
    DuplicateGroup,
)


def create_product(
    name: str,
    price_rrc: float,
    price_opt: float | None = None,
    category: list[str] | None = None,
) -> ExtractedProduct:
    """Helper to create test products."""
    return ExtractedProduct(
        name=name,
        price_rrc=Decimal(str(price_rrc)),
        price_opt=Decimal(str(price_opt)) if price_opt else None,
        category_path=category or [],
    )


class TestDeduplicationService:
    """Tests for DeduplicationService class."""
    
    def test_init_default_values(self) -> None:
        """Test default initialization values."""
        service = DeduplicationService()
        
        assert service.price_tolerance == 0.01
        assert service.case_sensitive is False
    
    def test_init_custom_values(self) -> None:
        """Test custom initialization values."""
        service = DeduplicationService(
            price_tolerance=0.05,
            case_sensitive=True,
        )
        
        assert service.price_tolerance == 0.05
        assert service.case_sensitive is True
    
    def test_deduplicate_empty_list(self) -> None:
        """Test deduplication of empty list."""
        service = DeduplicationService()
        
        unique, stats = service.deduplicate([])
        
        assert unique == []
        assert stats.total_products == 0
        assert stats.unique_products == 0
        assert stats.duplicates_removed == 0
    
    def test_deduplicate_no_duplicates(self) -> None:
        """Test deduplication with no duplicates."""
        service = DeduplicationService()
        products = [
            create_product("Product A", 100.00),
            create_product("Product B", 200.00),
            create_product("Product C", 300.00),
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 3
        assert stats.total_products == 3
        assert stats.unique_products == 3
        assert stats.duplicates_removed == 0
    
    def test_deduplicate_exact_duplicates(self) -> None:
        """Test deduplication of exact duplicates."""
        service = DeduplicationService()
        products = [
            create_product("Product A", 100.00),
            create_product("Product A", 100.00),  # Duplicate
            create_product("Product B", 200.00),
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 2
        assert stats.total_products == 3
        assert stats.unique_products == 2
        assert stats.duplicates_removed == 1
        
        # First occurrence should be kept
        assert unique[0].name == "Product A"
        assert unique[1].name == "Product B"
    
    def test_deduplicate_case_insensitive(self) -> None:
        """Test case-insensitive deduplication."""
        service = DeduplicationService(case_sensitive=False)
        products = [
            create_product("Product A", 100.00),
            create_product("product a", 100.00),  # Same, different case
            create_product("PRODUCT A", 100.00),  # Same, all caps
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 1
        assert stats.duplicates_removed == 2
    
    def test_deduplicate_case_sensitive(self) -> None:
        """Test case-sensitive deduplication."""
        service = DeduplicationService(case_sensitive=True)
        products = [
            create_product("Product A", 100.00),
            create_product("product a", 100.00),  # Different case = different
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 2
        assert stats.duplicates_removed == 0
    
    def test_deduplicate_price_tolerance(self) -> None:
        """Test deduplication with price tolerance (1%)."""
        service = DeduplicationService(price_tolerance=0.01)
        products = [
            create_product("Product A", 100.00),
            create_product("Product A", 100.50),  # 0.5% difference - duplicate
            create_product("Product A", 99.50),   # 0.5% difference - duplicate
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 1
        assert stats.duplicates_removed == 2
    
    def test_deduplicate_price_outside_tolerance(self) -> None:
        """Test products with same name but different prices kept."""
        service = DeduplicationService(price_tolerance=0.01)
        products = [
            create_product("Product A", 100.00),
            create_product("Product A", 110.00),  # 10% difference - not duplicate
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 2
        assert stats.duplicates_removed == 0
    
    def test_deduplicate_preserves_order(self) -> None:
        """Test that first occurrence is kept."""
        service = DeduplicationService()
        products = [
            create_product("Product A", 100.00, category=["Cat1"]),
            create_product("Product A", 100.00, category=["Cat2"]),  # Duplicate
            create_product("Product A", 100.00, category=["Cat3"]),  # Duplicate
        ]
        
        unique, stats = service.deduplicate(products)
        
        assert len(unique) == 1
        assert unique[0].category_path == ["Cat1"]  # First occurrence
    
    def test_dedup_rate_calculation(self) -> None:
        """Test deduplication rate percentage."""
        stats = DeduplicationStats(
            total_products=100,
            unique_products=80,
            duplicates_removed=20,
        )
        
        assert stats.dedup_rate == 20.0
    
    def test_dedup_rate_zero_products(self) -> None:
        """Test deduplication rate with zero products."""
        stats = DeduplicationStats()
        
        assert stats.dedup_rate == 0.0
    
    def test_prices_match_both_zero(self) -> None:
        """Test price matching when both prices are zero."""
        service = DeduplicationService()
        
        assert service._prices_match(0.0, 0.0) is True
    
    def test_prices_match_one_zero(self) -> None:
        """Test price matching when one price is zero."""
        service = DeduplicationService()
        
        assert service._prices_match(0.0, 100.0) is False
        assert service._prices_match(100.0, 0.0) is False


class TestDeduplicationServiceFindDuplicates:
    """Tests for find_duplicates method."""
    
    def test_find_duplicates_none(self) -> None:
        """Test finding duplicates when none exist."""
        service = DeduplicationService()
        products = [
            create_product("Product A", 100.00),
            create_product("Product B", 200.00),
        ]
        
        groups = service.find_duplicates(products)
        
        assert len(groups) == 0
    
    def test_find_duplicates_one_group(self) -> None:
        """Test finding one duplicate group."""
        service = DeduplicationService()
        products = [
            create_product("Product A", 100.00),
            create_product("Product A", 100.00),
            create_product("Product B", 200.00),
        ]
        
        groups = service.find_duplicates(products)
        
        assert len(groups) == 1
        assert groups[0].key == "product a"
        assert len(groups[0].products) == 2
        assert groups[0].removed_count == 1
    
    def test_find_duplicates_multiple_groups(self) -> None:
        """Test finding multiple duplicate groups."""
        service = DeduplicationService()
        products = [
            create_product("Product A", 100.00),
            create_product("Product A", 100.00),
            create_product("Product B", 200.00),
            create_product("Product B", 200.00),
            create_product("Product B", 200.00),
        ]
        
        groups = service.find_duplicates(products)
        
        assert len(groups) == 2
        
        # Find each group
        group_a = next(g for g in groups if g.key == "product a")
        group_b = next(g for g in groups if g.key == "product b")
        
        assert len(group_a.products) == 2
        assert len(group_b.products) == 3
    
    def test_find_duplicates_different_prices(self) -> None:
        """Test that same name with different prices are separate."""
        service = DeduplicationService()
        products = [
            create_product("Product A", 100.00),
            create_product("Product A", 100.00),  # Duplicate
            create_product("Product A", 200.00),  # Different price
        ]
        
        groups = service.find_duplicates(products)
        
        # Should only have one group for the 100.00 price duplicates
        assert len(groups) == 1
        assert len(groups[0].products) == 2


class TestDuplicateGroup:
    """Tests for DuplicateGroup dataclass."""
    
    def test_duplicate_group_creation(self) -> None:
        """Test creating a duplicate group."""
        products = [
            create_product("Product A", 100.00),
            create_product("Product A", 100.00),
        ]
        
        group = DuplicateGroup(
            key="product a",
            products=products,
            kept_product=products[0],
            removed_count=1,
        )
        
        assert group.key == "product a"
        assert len(group.products) == 2
        assert group.kept_product == products[0]
        assert group.removed_count == 1
    
    def test_duplicate_group_defaults(self) -> None:
        """Test default values for DuplicateGroup."""
        group = DuplicateGroup(key="test")
        
        assert group.products == []
        assert group.kept_product is None
        assert group.removed_count == 0

