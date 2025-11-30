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
from typing import List, Optional, Sequence, Protocol
from uuid import UUID
from decimal import Decimal
from enum import Enum
import structlog

from rapidfuzz import fuzz, process, utils

from src.config import matching_settings

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
    
    Attributes:
        use_preprocessing: Whether to apply default string preprocessing
        score_cutoff: Minimum score to include in results (performance optimization)
    """
    
    def __init__(
        self,
        use_preprocessing: bool = True,
        score_cutoff: Optional[float] = None,
    ):
        """Initialize the RapidFuzz matcher.
        
        Args:
            use_preprocessing: Apply default preprocessing (lowercase, remove special chars)
            score_cutoff: Minimum score cutoff for performance (uses potential_threshold if None)
        """
        self.use_preprocessing = use_preprocessing
        self._score_cutoff = score_cutoff
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

