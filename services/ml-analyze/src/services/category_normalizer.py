"""
Category Normalizer for Semantic ETL Pipeline
=============================================

Implements fuzzy matching of extracted categories against existing categories.
Creates new categories with needs_review flag when no match found.

Phase 9: Semantic ETL Pipeline Refactoring
"""

import logging
from typing import Optional

from rapidfuzz import fuzz, process
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Category
from src.schemas.category import (
    CategoryHierarchyResult,
    CategoryMatchResult,
    CategoryNormalizationStats,
)

logger = logging.getLogger(__name__)


class CategoryNormalizer:
    """
    Normalizes extracted categories by fuzzy matching or creating new ones.
    
    Features:
    - Fuzzy matching using RapidFuzz token_set_ratio
    - Configurable similarity threshold (default 85%)
    - Category hierarchy preservation (parent before child)
    - In-memory caching for performance
    - Admin review flag for new categories
    
    Example:
        normalizer = CategoryNormalizer(session)
        await normalizer.load_category_cache()
        
        result = await normalizer.process_category_path(
            ["Electronics", "Laptops", "Gaming"],
            supplier_id=123,
        )
        print(result.leaf_category_id)  # ID of "Gaming" category
    """
    
    def __init__(
        self,
        session: AsyncSession,
        similarity_threshold: float = 85.0,
        cache_enabled: bool = True,
    ):
        """
        Initialize CategoryNormalizer.
        
        Args:
            session: SQLAlchemy async session
            similarity_threshold: Minimum similarity for match (0-100)
            cache_enabled: Whether to cache categories in memory
        """
        self.session = session
        self.similarity_threshold = similarity_threshold
        self.cache_enabled = cache_enabled
        
        # In-memory cache: {normalized_name: (id, name, parent_id)}
        self._cache: dict[str, tuple[int, str, Optional[int]]] = {}
        self._cache_loaded = False
        
        # Stats tracking
        self.stats = CategoryNormalizationStats()
    
    async def load_category_cache(self) -> None:
        """
        Load all active categories into memory cache.
        
        Should be called once before processing to improve performance.
        Cache is keyed by normalized name (lowercase, stripped).
        """
        if not self.cache_enabled:
            return
        
        query = select(
            Category.id,
            Category.name,
            Category.parent_id,
        ).where(Category.is_active == True)  # noqa: E712
        
        result = await self.session.execute(query)
        rows = result.all()
        
        self._cache.clear()
        for row in rows:
            normalized = Category.normalize_name(row.name)
            self._cache[normalized] = (row.id, row.name, row.parent_id)
        
        self._cache_loaded = True
        logger.info(f"Loaded {len(self._cache)} categories into cache")
    
    async def process_category_path(
        self,
        category_path: list[str],
        supplier_id: Optional[int] = None,
    ) -> CategoryHierarchyResult:
        """
        Process a category hierarchy path (e.g., ["Electronics", "Laptops"]).
        
        For each level:
        1. Try fuzzy match against existing categories (with same parent)
        2. If match >= threshold, use existing category
        3. If no match, create new category with needs_review=True
        
        Args:
            category_path: Category names from general to specific
            supplier_id: Supplier ID for tracking new category origin
        
        Returns:
            CategoryHierarchyResult with match details for each level
        """
        if not category_path:
            return CategoryHierarchyResult(
                original_path=[],
                match_results=[],
                leaf_category_id=None,
            )
        
        # Ensure cache is loaded
        if self.cache_enabled and not self._cache_loaded:
            await self.load_category_cache()
        
        self.stats.total_categories_processed += 1
        
        match_results: list[CategoryMatchResult] = []
        parent_id: Optional[int] = None
        
        for level, category_name in enumerate(category_path):
            # Skip empty names
            if not category_name or not category_name.strip():
                self.stats.skipped_count += 1
                continue
            
            # Process this level
            match_result = await self._process_single_category(
                name=category_name.strip(),
                parent_id=parent_id,
                supplier_id=supplier_id,
            )
            
            match_results.append(match_result)
            
            # Update parent_id for next level
            parent_id = match_result.final_category_id
        
        # Get leaf category ID
        leaf_id = match_results[-1].final_category_id if match_results else None
        
        return CategoryHierarchyResult(
            original_path=category_path,
            match_results=match_results,
            leaf_category_id=leaf_id,
        )
    
    async def _process_single_category(
        self,
        name: str,
        parent_id: Optional[int],
        supplier_id: Optional[int],
    ) -> CategoryMatchResult:
        """
        Process a single category at one hierarchy level.
        
        Args:
            name: Category name to match/create
            parent_id: Parent category ID (None for root)
            supplier_id: Supplier ID for tracking
        
        Returns:
            CategoryMatchResult with match or creation details
        """
        # Normalize name for comparison
        normalized_name = Category.normalize_name(name)
        
        # Get candidates at this level (same parent)
        candidates = await self._get_candidates_at_level(parent_id)
        
        if not candidates:
            # No existing categories at this level - create new
            return await self._create_new_category(
                name=name,
                parent_id=parent_id,
                supplier_id=supplier_id,
            )
        
        # Fuzzy match against candidates
        match = self._fuzzy_match(normalized_name, candidates)
        
        if match and match[1] >= self.similarity_threshold:
            # Good match found
            matched_id, matched_name = match[0]
            similarity = match[1]
            
            self.stats.matched_count += 1
            self.stats.average_similarity = (
                (self.stats.average_similarity * (self.stats.matched_count - 1) + similarity)
                / self.stats.matched_count
            )
            
            logger.debug(
                f"Category matched: '{name}' → '{matched_name}' "
                f"(similarity: {similarity:.1f}%)"
            )
            
            return CategoryMatchResult(
                extracted_name=name,
                matched_id=matched_id,
                matched_name=matched_name,
                similarity_score=similarity,
                action="matched",
                needs_review=False,
                parent_id=parent_id,
            )
        
        # No good match - create new category
        return await self._create_new_category(
            name=name,
            parent_id=parent_id,
            supplier_id=supplier_id,
            best_match_score=match[1] if match else 0.0,
        )
    
    async def _get_candidates_at_level(
        self,
        parent_id: Optional[int],
    ) -> list[tuple[tuple[int, str], str]]:
        """
        Get candidate categories at a specific hierarchy level.
        
        Args:
            parent_id: Parent category ID (None for root level)
        
        Returns:
            List of ((id, name), normalized_name) tuples
        """
        if self.cache_enabled and self._cache_loaded:
            # Use cache
            candidates = [
                ((cat_id, cat_name), Category.normalize_name(cat_name))
                for norm_name, (cat_id, cat_name, cat_parent) in self._cache.items()
                if cat_parent == parent_id
            ]
        else:
            # Query database
            query = select(Category.id, Category.name).where(
                Category.is_active == True,  # noqa: E712
                Category.parent_id == parent_id if parent_id else Category.parent_id.is_(None),
            )
            result = await self.session.execute(query)
            rows = result.all()
            
            candidates = [
                ((row.id, row.name), Category.normalize_name(row.name))
                for row in rows
            ]
        
        return candidates
    
    def _fuzzy_match(
        self,
        query: str,
        candidates: list[tuple[tuple[int, str], str]],
    ) -> Optional[tuple[tuple[int, str], float]]:
        """
        Find best fuzzy match among candidates.
        
        Uses RapidFuzz token_set_ratio for word-order-independent matching.
        
        Args:
            query: Normalized query string
            candidates: List of ((id, name), normalized_name) tuples
        
        Returns:
            ((id, name), similarity_score) or None if no candidates
        """
        if not candidates:
            return None
        
        # Build choices dict: normalized_name -> (id, name)
        choices = {norm: (cat_id, cat_name) for (cat_id, cat_name), norm in candidates}
        
        # Find best match using token_set_ratio
        result = process.extractOne(
            query,
            choices.keys(),
            scorer=fuzz.token_set_ratio,
        )
        
        if result is None:
            return None
        
        matched_norm, score, _ = result
        return (choices[matched_norm], score)
    
    async def _create_new_category(
        self,
        name: str,
        parent_id: Optional[int],
        supplier_id: Optional[int],
        best_match_score: float = 0.0,
    ) -> CategoryMatchResult:
        """
        Create a new category with needs_review=True.
        
        Args:
            name: Category name
            parent_id: Parent category ID
            supplier_id: Originating supplier ID
            best_match_score: Best fuzzy match score (for logging)
        
        Returns:
            CategoryMatchResult with action='created'
        """
        # Check if category already exists (exact match)
        normalized = Category.normalize_name(name)
        
        existing_query = select(Category).where(
            func.lower(Category.name) == normalized,
            Category.parent_id == parent_id if parent_id else Category.parent_id.is_(None),
        )
        result = await self.session.execute(existing_query)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Exact match found (shouldn't happen often due to fuzzy matching)
            return CategoryMatchResult(
                extracted_name=name,
                matched_id=existing.id,
                matched_name=existing.name,
                similarity_score=100.0,
                action="matched",
                needs_review=existing.needs_review,
                parent_id=parent_id,
            )
        
        # Create new category
        new_category = Category(
            name=name,
            parent_id=parent_id,
            needs_review=True,
            is_active=True,
            supplier_id=supplier_id,
        )
        
        self.session.add(new_category)
        await self.session.flush()  # Get the ID
        
        # Update cache
        if self.cache_enabled:
            self._cache[normalized] = (new_category.id, name, parent_id)
        
        self.stats.created_count += 1
        self.stats.review_queue_count += 1
        
        logger.info(
            f"Created new category: '{name}' (parent_id={parent_id}, "
            f"best_match={best_match_score:.1f}%)"
        )
        
        return CategoryMatchResult(
            extracted_name=name,
            matched_id=None,
            matched_name=None,
            similarity_score=best_match_score,
            action="created",
            needs_review=True,
            parent_id=parent_id,
            created_category_id=new_category.id,
        )
    
    async def refresh_cache(self) -> None:
        """
        Refresh the category cache from database.
        
        Call after manual category changes or bulk inserts.
        """
        self._cache_loaded = False
        await self.load_category_cache()
    
    def get_stats(self) -> CategoryNormalizationStats:
        """
        Get normalization statistics.
        
        Returns:
            CategoryNormalizationStats with counts and averages
        """
        return self.stats
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self.stats = CategoryNormalizationStats()

