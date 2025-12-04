"""
Deduplication Service for Semantic ETL Pipeline
===============================================

Implements within-file deduplication of extracted products.
Uses hash-based deduplication with price tolerance.

Phase 9: Semantic ETL Pipeline Refactoring
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from src.schemas.extraction import ExtractedProduct

logger = logging.getLogger(__name__)


@dataclass
class DeduplicationStats:
    """Statistics from deduplication process."""
    
    total_products: int = 0
    unique_products: int = 0
    duplicates_removed: int = 0
    duplicate_groups: int = 0
    
    @property
    def dedup_rate(self) -> float:
        """Percentage of products that were duplicates."""
        if self.total_products == 0:
            return 0.0
        return (self.duplicates_removed / self.total_products) * 100


@dataclass
class DuplicateGroup:
    """Group of duplicate products."""
    
    key: str
    products: list[ExtractedProduct] = field(default_factory=list)
    kept_product: Optional[ExtractedProduct] = None
    removed_count: int = 0


class DeduplicationService:
    """
    Within-file product deduplication using hash-based detection.
    
    Features:
    - Normalized name-based deduplication key
    - Price tolerance (default 1%) for duplicate detection
    - Keeps first occurrence in file order
    - Detailed statistics and duplicate group tracking
    
    Example:
        service = DeduplicationService(price_tolerance=0.01)
        unique_products, stats = service.deduplicate(products)
        print(f"Removed {stats.duplicates_removed} duplicates")
    """
    
    def __init__(
        self,
        price_tolerance: float = 0.01,
        case_sensitive: bool = False,
    ):
        """
        Initialize DeduplicationService.
        
        Args:
            price_tolerance: Price difference tolerance (0.01 = 1%)
            case_sensitive: Whether name comparison is case-sensitive
        """
        self.price_tolerance = price_tolerance
        self.case_sensitive = case_sensitive
    
    def deduplicate(
        self,
        products: list[ExtractedProduct],
    ) -> tuple[list[ExtractedProduct], DeduplicationStats]:
        """
        Remove duplicate products from a list.
        
        Duplicates are identified by:
        1. Same normalized name (case-insensitive by default)
        2. Similar price (within tolerance)
        
        First occurrence is kept; subsequent duplicates are removed.
        
        Args:
            products: List of products to deduplicate
        
        Returns:
            Tuple of (unique products, deduplication stats)
        """
        if not products:
            return [], DeduplicationStats()
        
        stats = DeduplicationStats(total_products=len(products))
        
        # Track seen products: key -> (price, product)
        seen: dict[str, tuple[float, ExtractedProduct]] = {}
        unique: list[ExtractedProduct] = []
        duplicate_groups: dict[str, DuplicateGroup] = {}
        
        for product in products:
            key = self._get_dedup_key(product)
            price = float(product.price_rrc)
            
            if key not in seen:
                # New product
                seen[key] = (price, product)
                unique.append(product)
            else:
                # Potential duplicate - check price
                existing_price, existing_product = seen[key]
                
                if self._prices_match(price, existing_price):
                    # Duplicate found
                    stats.duplicates_removed += 1
                    
                    # Track duplicate group
                    if key not in duplicate_groups:
                        duplicate_groups[key] = DuplicateGroup(
                            key=key,
                            products=[existing_product],
                            kept_product=existing_product,
                        )
                    duplicate_groups[key].products.append(product)
                    duplicate_groups[key].removed_count += 1
                    
                    logger.debug(
                        f"Duplicate found: '{product.name}' "
                        f"(price: {price} vs {existing_price})"
                    )
                else:
                    # Different price - keep as separate product
                    # Use a variant key
                    variant_key = f"{key}__price_{price}"
                    if variant_key not in seen:
                        seen[variant_key] = (price, product)
                        unique.append(product)
                        logger.debug(
                            f"Same name, different price: '{product.name}' "
                            f"({price} vs {existing_price})"
                        )
        
        stats.unique_products = len(unique)
        stats.duplicate_groups = len(duplicate_groups)
        
        logger.info(
            f"Deduplication: {stats.total_products} → {stats.unique_products} "
            f"({stats.duplicates_removed} duplicates in {stats.duplicate_groups} groups)"
        )
        
        return unique, stats
    
    def _get_dedup_key(self, product: ExtractedProduct) -> str:
        """
        Generate deduplication key for a product.
        
        Args:
            product: Product to generate key for
        
        Returns:
            Normalized key string
        """
        key = product.get_dedup_key()  # Uses lowercase by default
        
        if self.case_sensitive:
            key = product.name.strip()
        
        return key
    
    def _prices_match(self, price1: float, price2: float) -> bool:
        """
        Check if two prices are within tolerance.
        
        Args:
            price1: First price
            price2: Second price
        
        Returns:
            True if prices are within tolerance
        """
        if price1 == 0 and price2 == 0:
            return True
        
        if price1 == 0 or price2 == 0:
            return False
        
        # Use the larger price as the base for tolerance calculation
        base_price = max(price1, price2)
        tolerance = base_price * self.price_tolerance
        
        return abs(price1 - price2) <= tolerance
    
    def find_duplicates(
        self,
        products: list[ExtractedProduct],
    ) -> list[DuplicateGroup]:
        """
        Find duplicate groups without removing them.
        
        Useful for analysis and reporting.
        
        Args:
            products: List of products to analyze
        
        Returns:
            List of DuplicateGroup objects
        """
        if not products:
            return []
        
        # Group by key
        groups: dict[str, list[tuple[float, ExtractedProduct]]] = {}
        
        for product in products:
            key = self._get_dedup_key(product)
            price = float(product.price_rrc)
            
            if key not in groups:
                groups[key] = []
            groups[key].append((price, product))
        
        # Find groups with duplicates (same price within tolerance)
        duplicate_groups: list[DuplicateGroup] = []
        
        for key, items in groups.items():
            if len(items) < 2:
                continue
            
            # Cluster by price
            price_clusters: dict[float, list[ExtractedProduct]] = {}
            
            for price, product in items:
                # Find matching price cluster
                matched_cluster = None
                for cluster_price in price_clusters:
                    if self._prices_match(price, cluster_price):
                        matched_cluster = cluster_price
                        break
                
                if matched_cluster is not None:
                    price_clusters[matched_cluster].append(product)
                else:
                    price_clusters[price] = [product]
            
            # Create duplicate groups from clusters with >1 product
            for cluster_price, cluster_products in price_clusters.items():
                if len(cluster_products) > 1:
                    group = DuplicateGroup(
                        key=key,
                        products=cluster_products,
                        kept_product=cluster_products[0],
                        removed_count=len(cluster_products) - 1,
                    )
                    duplicate_groups.append(group)
        
        return duplicate_groups

