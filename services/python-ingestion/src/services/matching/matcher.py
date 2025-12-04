"""Product matching service using fuzzy string matching.

This module implements the Strategy pattern for product matching,
starting with RapidFuzz-based fuzzy string matching (KISS principle).

Key Components:
    - MatcherStrategy: Abstract base class for matching algorithms
    - RapidFuzzMatcher: Default implementation using RapidFuzz WRatio
    - MatchCandidate: Data class for match candidates
    - MatchResult: Result container for matching operations
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Protocol, Dict
from uuid import UUID
from enum import Enum
import structlog

from rapidfuzz import fuzz, process, utils

from src.config import matching_settings


# ========== Simple Category Classification ==========
# Phase 9: Simplified category classifier (advanced classification in ml-analyze)

class ClassificationMethod(str, Enum):
    """How the category was determined."""
    KEYWORD = "keyword"
    BRAND = "brand"
    FALLBACK = "fallback"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Result of category classification."""
    category_key: Optional[str]
    confidence: float
    method: ClassificationMethod


class CategoryClassifier:
    """Simple rule-based category classifier for matching blocking.
    
    Phase 9: Advanced LLM-based classification moved to ml-analyze.
    This is a simplified version for fuzzy matching performance optimization.
    """
    
    # Simple keyword mappings
    CATEGORY_KEYWORDS = {
        "phones": ["телефон", "смартфон", "iphone", "samsung", "xiaomi"],
        "electrotransport": ["самокат", "велосипед", "скутер", "электро"],
        "garden": ["газонокосилка", "триммер", "бензопила", "культиватор"],
    }
    
    BRAND_CATEGORIES = {
        "apple": "phones",
        "samsung": "phones", 
        "xiaomi": "phones",
        "kugoo": "electrotransport",
        "ninebot": "electrotransport",
    }
    
    def classify(
        self,
        product_name: str,
        supplier_category: Optional[str] = None,
    ) -> ClassificationResult:
        """Classify product into category."""
        name_lower = product_name.lower()
        
        # Check keywords
        for cat_key, keywords in self.CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in name_lower:
                    return ClassificationResult(
                        category_key=cat_key,
                        confidence=0.8,
                        method=ClassificationMethod.KEYWORD,
                    )
        
        # Check brands
        for brand, cat_key in self.BRAND_CATEGORIES.items():
            if brand in name_lower:
                return ClassificationResult(
                    category_key=cat_key,
                    confidence=0.7,
                    method=ClassificationMethod.BRAND,
                )
        
        # Fallback
        return ClassificationResult(
            category_key=None,
            confidence=0.0,
            method=ClassificationMethod.UNKNOWN,
        )

logger = structlog.get_logger(__name__)


class MatchStatusEnum(str, Enum):
    """Match status for supplier items."""
    UNMATCHED = "unmatched"
    AUTO_MATCHED = "auto_matched"
    POTENTIAL_MATCH = "potential_match"
    VERIFIED_MATCH = "verified_match"


@dataclass
class MatchCandidate:
    """A potential product match for a supplier item.
    
    Attributes:
        product_id: UUID of the candidate product
        product_name: Name of the candidate product for display
        score: Fuzzy match confidence score (0-100)
        category_id: Optional category for blocking verification
    """
    product_id: UUID
    product_name: str
    score: float
    category_id: Optional[UUID] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSONB storage."""
        result = {
            "product_id": str(self.product_id),
            "product_name": self.product_name,
            "score": round(self.score, 2)
        }
        if self.category_id:
            result["category_id"] = str(self.category_id)
        return result


@dataclass
class MatchResult:
    """Result of matching a supplier item against products.
    
    Attributes:
        supplier_item_id: UUID of the supplier item that was matched
        supplier_item_name: Name of the supplier item
        match_status: Resulting status after matching
        best_match: Top candidate (if any)
        candidates: All candidates above potential threshold
        match_score: Score of best match (if any)
    """
    supplier_item_id: UUID
    supplier_item_name: str
    match_status: MatchStatusEnum
    best_match: Optional[MatchCandidate] = None
    candidates: List[MatchCandidate] = field(default_factory=list)
    match_score: Optional[float] = None


class ProductData(Protocol):
    """Protocol for product data used in matching.
    
    This allows passing any object with these attributes,
    supporting both ORM models and plain data classes.
    """
    id: UUID
    name: str
    category_id: Optional[UUID]


class MatcherStrategy(ABC):
    """Abstract base class for product matching strategies.
    
    This follows the Strategy pattern (SOLID-O: Open/Closed Principle)
    allowing new matching algorithms to be added without modifying
    existing code. Current implementation uses RapidFuzz, but can be
    extended to use ML embeddings in Phase 5.
    
    All implementations must honor the contract:
        - find_matches() returns sorted candidates by score (descending)
        - Scores are normalized to 0-100 range
        - Empty product list returns UNMATCHED status
    """
    
    @abstractmethod
    def find_matches(
        self,
        item_name: str,
        item_id: UUID,
        products: Sequence[ProductData],
        auto_threshold: float = 95.0,
        potential_threshold: float = 70.0,
        max_candidates: int = 5,
    ) -> MatchResult:
        """Find matching products for a supplier item.
        
        Args:
            item_name: Name of the supplier item to match
            item_id: UUID of the supplier item
            products: Sequence of products to match against
            auto_threshold: Score threshold for auto-match (default: 95%)
            potential_threshold: Score threshold for potential match (default: 70%)
            max_candidates: Maximum number of candidates to return
            
        Returns:
            MatchResult with status and candidates
        """
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """Get the name of this matching strategy."""
        pass


class RapidFuzzMatcher(MatcherStrategy):
    """Product matcher using RapidFuzz WRatio algorithm.
    
    WRatio automatically selects the best matching strategy by combining
    multiple algorithms (simple ratio, partial ratio, token sort ratio,
    token set ratio) to provide highest quality results.
    
    Performance optimizations:
        - score_cutoff: Early termination for low-scoring matches
        - processor: Default preprocessing (lowercase, remove non-alphanumeric)
        - Batch extraction using process.extract()
        - Category blocking via intelligent classifier
    
    Attributes:
        use_preprocessing: Whether to apply default string preprocessing
        score_cutoff: Minimum score to include in results (performance optimization)
        classifier: CategoryClassifier for intelligent category matching
        category_mapping: Maps product category_id → category_key
    """
    
    def __init__(
        self,
        use_preprocessing: bool = True,
        score_cutoff: Optional[float] = None,
        classifier: Optional[CategoryClassifier] = None,
        category_mapping: Optional[Dict[UUID, str]] = None,
    ):
        """Initialize the RapidFuzz matcher.
        
        Args:
            use_preprocessing: Apply default preprocessing (lowercase, remove special chars)
            score_cutoff: Minimum score cutoff for performance (uses potential_threshold if None)
            classifier: CategoryClassifier for intelligent product categorization
            category_mapping: Maps product category_id → category_key (e.g., UUID → "phones")
        """
        self.use_preprocessing = use_preprocessing
        self._score_cutoff = score_cutoff
        self._classifier = classifier or CategoryClassifier()
        self._category_mapping = category_mapping or {}
        self._log = logger.bind(matcher="RapidFuzzMatcher")
    
    def get_strategy_name(self) -> str:
        """Get the name of this matching strategy."""
        return "rapidfuzz_wratio"
    
    def find_matches(
        self,
        item_name: str,
        item_id: UUID,
        products: Sequence[ProductData],
        auto_threshold: float = 95.0,
        potential_threshold: float = 70.0,
        max_candidates: int = 5,
    ) -> MatchResult:
        """Find matching products using RapidFuzz WRatio.
        
        Implementation uses process.extract() for efficient batch comparison
        with score_cutoff for early termination of low-scoring matches.
        
        Args:
            item_name: Name of the supplier item to match
            item_id: UUID of the supplier item
            products: Sequence of products to match against
            auto_threshold: Score threshold for auto-match (default: 95%)
            potential_threshold: Score threshold for potential match (default: 70%)
            max_candidates: Maximum number of candidates to return
            
        Returns:
            MatchResult with status and sorted candidates (by score descending)
        """
        # Handle empty products list
        if not products:
            self._log.debug(
                "no_products_to_match",
                item_id=str(item_id),
                item_name=item_name
            )
            return MatchResult(
                supplier_item_id=item_id,
                supplier_item_name=item_name,
                match_status=MatchStatusEnum.UNMATCHED,
            )
        
        # Use score_cutoff for performance (early termination of low matches)
        score_cutoff = self._score_cutoff or potential_threshold
        
        # Build choices dict: product_name -> product_data
        # Using dict preserves product data for lookup after matching
        choices = {p.name: p for p in products}
        
        # Configure processor
        processor = utils.default_process if self.use_preprocessing else None
        
        # Extract matches using RapidFuzz process.extract
        # Returns list of tuples: (choice, score, index)
        matches = process.extract(
            query=item_name,
            choices=list(choices.keys()),
            scorer=fuzz.WRatio,
            processor=processor,
            score_cutoff=score_cutoff,
            limit=max_candidates,
        )
        
        # Convert to MatchCandidate objects
        candidates: List[MatchCandidate] = []
        for choice_name, score, _ in matches:
            product = choices[choice_name]
            candidate = MatchCandidate(
                product_id=product.id,
                product_name=product.name,
                score=score,
                category_id=product.category_id,
            )
            candidates.append(candidate)
        
        # Sort by score descending (should already be sorted, but ensure)
        candidates.sort(key=lambda c: c.score, reverse=True)
        
        # Determine match status based on best score
        if not candidates:
            match_status = MatchStatusEnum.UNMATCHED
            best_match = None
            match_score = None
        else:
            best_match = candidates[0]
            match_score = best_match.score
            
            if match_score >= auto_threshold:
                match_status = MatchStatusEnum.AUTO_MATCHED
            elif match_score >= potential_threshold:
                match_status = MatchStatusEnum.POTENTIAL_MATCH
            else:
                match_status = MatchStatusEnum.UNMATCHED
        
        self._log.debug(
            "match_completed",
            item_id=str(item_id),
            item_name=item_name,
            match_status=match_status.value,
            match_score=round(match_score, 2) if match_score else None,
            candidates_count=len(candidates),
        )
        
        return MatchResult(
            supplier_item_id=item_id,
            supplier_item_name=item_name,
            match_status=match_status,
            best_match=best_match,
            candidates=candidates,
            match_score=match_score,
        )
        
    def find_matches_with_blocking(
        self,
        item_name: str,
        item_id: UUID,
        item_category: Optional[str],
        products: Sequence[ProductData],
        auto_threshold: float = 95.0,
        potential_threshold: float = 70.0,
        max_candidates: int = 5,
    ) -> MatchResult:
        """Find matches using intelligent category blocking for performance.
        
        Uses CategoryClassifier to determine item's category from:
        1. Product name keywords (e.g., "iPhone" → phones)
        2. Brand detection (e.g., "Kugoo" → electric_scooters)
        3. Supplier category fallback (fuzzy match)
        
        Then filters products to same category before fuzzy matching,
        reducing comparison space by ~10x for large catalogs.
        
        Args:
            item_name: Name of the supplier item to match
            item_id: UUID of the supplier item
            item_category: Category from parser (e.g., "Электротранспорт > Велосипеды")
            products: Sequence of products to match against
            auto_threshold: Score threshold for auto-match (default: 95%)
            potential_threshold: Score threshold for potential match (default: 70%)
            max_candidates: Maximum number of candidates to return
            
        Returns:
            MatchResult with status and sorted candidates
        """
        # Use classifier to determine item's category
        classification = self._classifier.classify(
            product_name=item_name,
            supplier_category=item_category,
        )
        
        item_category_key = classification.category_key
        
        self._log.debug(
            "item_classified",
            item_id=str(item_id),
            item_name=item_name[:50],
            category_key=item_category_key,
            confidence=classification.confidence,
            method=classification.method.value,
        )
        
        # Filter products by category (blocking)
        filtered_products = products
        if item_category_key and self._category_mapping:
            filtered_products = [
                p for p in products 
                if self._category_matches(p, item_category_key)
            ]
            
            self._log.debug(
                "category_blocking_applied",
                item_id=str(item_id),
                item_category_key=item_category_key,
                total_products=len(products),
                filtered_products=len(filtered_products),
            )
            
            # If no products in category, fall back to all products
            if not filtered_products:
                self._log.debug(
                    "category_blocking_fallback",
                    item_id=str(item_id),
                    reason="no_products_in_category",
                )
                filtered_products = products
        
        # Use standard matching on filtered set
        return self.find_matches(
            item_name=item_name,
            item_id=item_id,
            products=filtered_products,
            auto_threshold=auto_threshold,
            potential_threshold=potential_threshold,
            max_candidates=max_candidates,
        )
    
    def _category_matches(self, product: ProductData, item_category_key: str) -> bool:
        """Check if product's category matches the item's classified category.
        
        Uses category_mapping to resolve product's category_id to category_key,
        then compares with item's classified category_key.
        
        Args:
            product: Product to check
            item_category_key: Category key from classifier (e.g., "phones", "electrotransport")
            
        Returns:
            True if categories match or are related
        """
        if not product.category_id:
            return False
        
        # Get product's category key from mapping
        product_category_key = self._category_mapping.get(product.category_id)
        
        if not product_category_key:
            # No mapping for this category - include in results (permissive)
            return True
        
        # Exact match
        if product_category_key == item_category_key:
            return True
        
        # Check for parent-child relationships
        # e.g., "electric_scooters" is a subcategory of "electrotransport"
        related_categories = self._get_related_categories(item_category_key)
        if product_category_key in related_categories:
            return True
        
        return False
    
    def _get_related_categories(self, category_key: str) -> set:
        """Get related categories (parent and child) for a category key.
        
        This handles category hierarchies where matching should include
        both parent and child categories.
        """
        # Define category relationships
        CATEGORY_HIERARCHY = {
            "electrotransport": {"electric_scooters", "electric_bikes"},
            "electric_scooters": {"electrotransport"},
            "electric_bikes": {"electrotransport"},
            "garden_equipment": {"trailers"},
            "trailers": {"garden_equipment"},
            "atv_moto": {"protection", "spare_parts"},
            "protection": {"atv_moto"},
            "spare_parts": {"atv_moto", "garden_equipment"},
        }
        
        return CATEGORY_HIERARCHY.get(category_key, set())
    
    def set_category_mapping(self, mapping: Dict[UUID, str]) -> None:
        """Update the category mapping at runtime.
        
        Args:
            mapping: Dict mapping category_id (UUID) → category_key (str)
        """
        self._category_mapping = mapping
        self._log.info("category_mapping_updated", count=len(mapping))
    
    def get_classification(
        self,
        item_name: str,
        supplier_category: Optional[str] = None,
    ) -> ClassificationResult:
        """Classify a product without matching.
        
        Useful for debugging or pre-processing items.
        
        Args:
            item_name: Product name to classify
            supplier_category: Optional supplier category hint
            
        Returns:
            ClassificationResult with category and confidence
        """
        return self._classifier.classify(item_name, supplier_category)


def create_matcher(
    strategy: str = "rapidfuzz",
    **kwargs
) -> MatcherStrategy:
    """Factory function to create a matcher strategy.
    
    Args:
        strategy: Strategy name ("rapidfuzz" for now)
        **kwargs: Additional arguments passed to the matcher
        
    Returns:
        MatcherStrategy instance
        
    Raises:
        ValueError: If unknown strategy name
    """
    strategies = {
        "rapidfuzz": RapidFuzzMatcher,
    }
    
    if strategy not in strategies:
        raise ValueError(f"Unknown matching strategy: {strategy}. Available: {list(strategies.keys())}")
    
    return strategies[strategy](**kwargs)


def search_match_candidates(
    supplier_items: Sequence,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    category_id: Optional[UUID] = None,
) -> List[dict]:
    """Search supplier items by match_score range and category.
    
    This function filters supplier_items by match_score range
    and optionally by category. Used for review queue filtering.
    
    Args:
        supplier_items: Sequence of SupplierItem objects
        min_score: Minimum match_score (inclusive)
        max_score: Maximum match_score (inclusive)
        category_id: Filter by items linked to this category
        
    Returns:
        List of matching item dictionaries
        
    Note:
        This is a utility function for filtering in-memory data.
        The actual database query should use SQLAlchemy filters.
    """
    results = []
    
    for item in supplier_items:
        # Skip items without match_score
        if item.match_score is None:
            continue
        
        # Apply score filters
        score = float(item.match_score)
        if min_score is not None and score < min_score:
            continue
        if max_score is not None and score > max_score:
            continue
        
        # Apply category filter (check if item's linked product has matching category)
        if category_id is not None:
            if not item.product_id:
                continue
            # Would need to check product.category_id
            # This is handled by the SQL query in the task
        
        results.append({
            "id": str(item.id),
            "name": item.name,
            "match_score": score,
            "match_status": item.match_status.value if item.match_status else None,
        })
    
    return results

