"""
Variant Detection Service
=========================

Detects and groups product variants based on:
1. Vector similarity search (find similar products)
2. LLM-based attribute extraction (identify differentiating specs)
3. Automatic variant grouping and linking

Phase 10: Product Variants

See: /docs/adr/010-product-variants.md
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from rapidfuzz import fuzz
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Category
from src.schemas.extraction import ExtractedProduct

logger = logging.getLogger(__name__)


@dataclass
class VariantGroup:
    """A group of products that are variants of the same base product."""
    
    base_name: str
    variant_schema: list[str]  # e.g., ["voltage", "capacity"]
    variants: list[dict]  # [{key: "48V/20A", attributes: {...}, items: [...]}]


@dataclass
class VariantCandidate:
    """A candidate for variant grouping."""
    
    supplier_item_id: UUID
    name: str
    price: float
    variant_attributes: dict
    similarity_score: float = 0.0


class VariantDetectionService:
    """
    Service for detecting and grouping product variants.
    
    Uses a combination of:
    - Name similarity (RapidFuzz) for initial grouping
    - Variant attributes from extraction for confirmation
    - Price difference thresholds for validation
    
    Example:
        service = VariantDetectionService(session)
        groups = await service.detect_variants(supplier_id)
        for group in groups:
            print(f"Base: {group.base_name}, Variants: {len(group.variants)}")
    """
    
    # Similarity threshold for considering products as variants
    NAME_SIMILARITY_THRESHOLD = 85  # 85% fuzzy match
    
    # Maximum price ratio between variants (e.g., 2.0 = one can't be 2x another)
    MAX_PRICE_RATIO = 2.0
    
    # Common variant attribute patterns (regex)
    VOLTAGE_PATTERN = re.compile(r'(\d+)\s*[Vv][Аа]?[Оо]?[Лл]?[Ьь]?[Тт]?', re.IGNORECASE)
    CAPACITY_PATTERN = re.compile(r'(\d+[,.]?\d*)\s*[АAа][HhЧч]?', re.IGNORECASE)
    STORAGE_PATTERN = re.compile(r'(\d+)\s*(GB|ГБ|TB|ТБ)', re.IGNORECASE)
    SIZE_PATTERN = re.compile(r'\b(XXS|XS|S|M|L|XL|XXL|XXXL|\d{2})\b', re.IGNORECASE)
    
    def __init__(self, session: AsyncSession):
        """Initialize service with database session."""
        self.session = session
    
    def extract_variant_attributes_from_name(self, name: str) -> dict:
        """
        Extract variant attributes from product name using regex.
        
        This is a fallback when LLM extraction doesn't provide variant_attributes.
        
        Args:
            name: Product name to parse
            
        Returns:
            Dictionary of extracted attributes, e.g., {"voltage": "48V", "capacity": "20Ah"}
        """
        attributes = {}
        
        # Extract voltage
        voltage_match = self.VOLTAGE_PATTERN.search(name)
        if voltage_match:
            attributes["voltage"] = f"{voltage_match.group(1)}V"
        
        # Extract capacity (Ah)
        capacity_match = self.CAPACITY_PATTERN.search(name)
        if capacity_match:
            value = capacity_match.group(1).replace(',', '.')
            attributes["capacity"] = f"{value}Ah"
        
        # Extract storage (GB/TB)
        storage_match = self.STORAGE_PATTERN.search(name)
        if storage_match:
            value = storage_match.group(1)
            unit = storage_match.group(2).upper().replace('Г', 'G').replace('Т', 'T')
            attributes["storage"] = f"{value}{unit}"
        
        # Extract size
        size_match = self.SIZE_PATTERN.search(name)
        if size_match:
            attributes["size"] = size_match.group(1).upper()
        
        return attributes
    
    def get_base_name(self, name: str, attributes: dict) -> str:
        """
        Extract base product name by removing variant-specific text.
        
        Args:
            name: Full product name
            attributes: Extracted variant attributes
            
        Returns:
            Normalized base name for grouping
        """
        base = name
        
        # Remove voltage/capacity patterns like "48V20A", "48V/20A", "(48V 20A)"
        base = re.sub(
            r'\s*[\(\[]\s*\d+[Vv][Аа]?/?-?\s*\d+[,.]?\d*[АAа][Hh]?\s*[\)\]]',
            '',
            base
        )
        base = re.sub(
            r'\s+\d+[Vv][Аа]?/?-?\s*\d+[,.]?\d*[АAа][Hh]?\s*$',
            '',
            base
        )
        
        # Remove storage patterns like "(256GB)", "[512 GB]"
        base = re.sub(r'\s*[\(\[]\s*\d+\s*(GB|ГБ|TB|ТБ)\s*[\)\]]', '', base, flags=re.IGNORECASE)
        
        # Remove size patterns
        base = re.sub(r'\s*[\(\[]\s*(XXS|XS|S|M|L|XL|XXL|XXXL|\d{2})\s*[\)\]]', '', base, flags=re.IGNORECASE)
        
        # Remove color at end: "Black", "Черный", etc.
        base = re.sub(r'\s+(Black|White|Red|Blue|Green|Черный|Белый|Красный|Синий)\s*$', '', base, flags=re.IGNORECASE)
        
        return " ".join(base.strip().split())
    
    def calculate_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate fuzzy similarity between two product names.
        
        Uses token_sort_ratio for order-independent comparison.
        
        Args:
            name1: First product name
            name2: Second product name
            
        Returns:
            Similarity score (0-100)
        """
        return fuzz.token_sort_ratio(name1.lower(), name2.lower())
    
    def are_variants(
        self,
        product1: VariantCandidate,
        product2: VariantCandidate,
    ) -> bool:
        """
        Determine if two products are variants of each other.
        
        Criteria:
        1. High name similarity (after removing variant specs)
        2. Different variant attributes
        3. Price within acceptable range
        
        Args:
            product1: First product candidate
            product2: Second product candidate
            
        Returns:
            True if products are variants
        """
        # Get base names
        base1 = self.get_base_name(product1.name, product1.variant_attributes)
        base2 = self.get_base_name(product2.name, product2.variant_attributes)
        
        # Check name similarity
        similarity = self.calculate_similarity(base1, base2)
        if similarity < self.NAME_SIMILARITY_THRESHOLD:
            return False
        
        # Must have at least one different variant attribute
        attrs1 = product1.variant_attributes or self.extract_variant_attributes_from_name(product1.name)
        attrs2 = product2.variant_attributes or self.extract_variant_attributes_from_name(product2.name)
        
        if not attrs1 and not attrs2:
            # No variant attributes - could be duplicates, not variants
            return False
        
        # Check if there's at least one common attribute with different values
        common_keys = set(attrs1.keys()) & set(attrs2.keys())
        has_different_values = any(attrs1[k] != attrs2[k] for k in common_keys)
        
        if not has_different_values:
            # Same variant attributes - not variants of each other
            return False
        
        # Check price ratio
        if product1.price > 0 and product2.price > 0:
            ratio = max(product1.price, product2.price) / min(product1.price, product2.price)
            if ratio > self.MAX_PRICE_RATIO:
                return False
        
        return True
    
    def group_variants(
        self,
        candidates: list[VariantCandidate],
    ) -> list[VariantGroup]:
        """
        Group a list of product candidates into variant groups.
        
        Uses Union-Find algorithm for efficient grouping.
        
        Args:
            candidates: List of variant candidates
            
        Returns:
            List of variant groups
        """
        if not candidates:
            return []
        
        n = len(candidates)
        parent = list(range(n))
        
        def find(x: int) -> int:
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x: int, y: int) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        # Compare all pairs and union variants
        for i in range(n):
            for j in range(i + 1, n):
                if self.are_variants(candidates[i], candidates[j]):
                    union(i, j)
        
        # Build groups
        groups_map: dict[int, list[int]] = {}
        for i in range(n):
            root = find(i)
            if root not in groups_map:
                groups_map[root] = []
            groups_map[root].append(i)
        
        # Convert to VariantGroup objects
        result = []
        for indices in groups_map.values():
            if len(indices) < 2:
                # Single product - not a variant group
                continue
            
            # Get base name from first product
            first = candidates[indices[0]]
            attrs = first.variant_attributes or self.extract_variant_attributes_from_name(first.name)
            base_name = self.get_base_name(first.name, attrs)
            
            # Collect all variant schemas (unique attributes across group)
            all_attrs = set()
            variants = []
            for idx in indices:
                c = candidates[idx]
                c_attrs = c.variant_attributes or self.extract_variant_attributes_from_name(c.name)
                all_attrs.update(c_attrs.keys())
                
                # Generate variant key
                key_parts = [f"{c_attrs.get(k, '?')}" for k in sorted(all_attrs)]
                key = "/".join(key_parts) if key_parts else "default"
                
                variants.append({
                    "key": key,
                    "attributes": c_attrs,
                    "supplier_item_id": str(c.supplier_item_id),
                    "name": c.name,
                    "price": c.price,
                })
            
            result.append(VariantGroup(
                base_name=base_name,
                variant_schema=sorted(all_attrs),
                variants=variants,
            ))
        
        return result
    
    def build_variant_key(self, attributes: dict, schema: list[str]) -> str:
        """
        Build a consistent variant key from attributes.
        
        Args:
            attributes: Variant attributes dict
            schema: List of attribute keys in order
            
        Returns:
            Slash-separated key, e.g., "48V/20Ah"
        """
        parts = []
        for key in schema:
            if key in attributes:
                parts.append(str(attributes[key]))
        return "/".join(parts) if parts else "default"


async def detect_variants_for_supplier(
    session: AsyncSession,
    supplier_id: UUID,
    products: list[ExtractedProduct],
) -> list[VariantGroup]:
    """
    Detect variant groups from extracted products for a supplier.
    
    This is the main entry point for variant detection during ingestion.
    
    Args:
        session: Database session
        supplier_id: Supplier UUID
        products: List of extracted products
        
    Returns:
        List of detected variant groups
    """
    service = VariantDetectionService(session)
    
    # Convert extracted products to candidates
    candidates = []
    for i, product in enumerate(products):
        # Use index as temporary ID during extraction
        candidates.append(VariantCandidate(
            supplier_item_id=UUID(int=i),  # Placeholder
            name=product.name,
            price=float(product.price_rrc),
            variant_attributes=product.variant_attributes,
        ))
    
    # Group variants
    groups = service.group_variants(candidates)
    
    logger.info(
        f"Detected {len(groups)} variant groups from {len(products)} products "
        f"for supplier {supplier_id}"
    )
    
    return groups

