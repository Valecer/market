"""
Category Normalizer for Semantic ETL Pipeline
=============================================

Implements fuzzy matching of extracted categories against existing categories.
Creates new categories with needs_review flag when no match found.

Phase 9: Semantic ETL Pipeline Refactoring
- T87: Auto-refresh cache on insert to reduce DB queries
- T88: Optimized fuzzy matching for large category sets (>1000 categories)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Category
from src.schemas.category import (
    CategoryHierarchyResult,
    CategoryMatchResult,
    CategoryNormalizationStats,
)

logger = logging.getLogger(__name__)


# =============================================================================
# T87 & T88: Performance Configuration
# =============================================================================

# T87: Cache refresh configuration
CACHE_AUTO_REFRESH_THRESHOLD = 50  # Refresh cache after N inserts
CACHE_STALE_THRESHOLD_SECONDS = 300  # Consider cache stale after 5 minutes

# T88: Large category set optimization thresholds
LARGE_CATEGORY_SET_THRESHOLD = 1000  # Use optimized matching above this
PREFILTER_LENGTH_TOLERANCE = 5  # Length difference tolerance for pre-filtering


@dataclass
class CacheMetrics:
    """T87: Tracks cache performance metrics."""
    
    hits: int = 0
    misses: int = 0
    inserts_since_refresh: int = 0
    last_refresh_time: float = field(default_factory=time.time)
    total_refresh_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0
    
    def should_refresh(self) -> bool:
        """Check if cache should be refreshed."""
        # Refresh if too many inserts
        if self.inserts_since_refresh >= CACHE_AUTO_REFRESH_THRESHOLD:
            return True
        # Refresh if cache is stale
        if time.time() - self.last_refresh_time > CACHE_STALE_THRESHOLD_SECONDS:
            return True
        return False
    
    def record_refresh(self) -> None:
        """Record a cache refresh."""
        self.inserts_since_refresh = 0
        self.last_refresh_time = time.time()
        self.total_refresh_count += 1


class CategoryNormalizer:
    """
    Normalizes extracted categories by fuzzy matching or creating new ones.
    
    Features:
    - Fuzzy matching using RapidFuzz token_set_ratio
    - Configurable similarity threshold (default 85%)
    - Category hierarchy preservation (parent before child)
    - In-memory caching for performance
    - Admin review flag for new categories
    - T87: Auto-refresh cache on insert
    - T88: Optimized matching for large category sets
    
    Example:
        normalizer = CategoryNormalizer(session)
        await normalizer.load_category_cache()
        
        result = await normalizer.process_category_path(
            ["Electronics", "Laptops", "Gaming"],
            supplier_id=123,
        )
        print(result.leaf_category_id)  # ID of "Gaming" category
        
        # Check cache metrics
        print(normalizer.get_cache_metrics())
    """
    
    def __init__(
        self,
        session: AsyncSession,
        similarity_threshold: float = 85.0,
        cache_enabled: bool = True,
        auto_refresh: bool = True,
    ):
        """
        Initialize CategoryNormalizer.
        
        Args:
            session: SQLAlchemy async session
            similarity_threshold: Minimum similarity for match (0-100)
            cache_enabled: Whether to cache categories in memory
            auto_refresh: T87: Auto-refresh cache after threshold inserts
        """
        self.session = session
        self.similarity_threshold = similarity_threshold
        self.cache_enabled = cache_enabled
        self.auto_refresh = auto_refresh
        
        # In-memory cache: {normalized_name: (id, name, parent_id)}
        self._cache: dict[str, tuple[int, str, Optional[int]]] = {}
        self._cache_loaded = False
        
        # T87: Cache metrics tracking
        self._cache_metrics = CacheMetrics()
        
        # T88: Level-wise cache for optimized matching
        # {parent_id: [(id, name, normalized_name), ...]}
        self._level_cache: dict[Optional[int], list[tuple[int, str, str]]] = {}
        
        # Stats tracking
        self.stats = CategoryNormalizationStats()
    
    def get_cache_metrics(self) -> dict:
        """
        T87: Get cache performance metrics.
        
        Returns:
            Dictionary with cache hit rate, refresh count, etc.
        """
        return {
            "hit_rate": round(self._cache_metrics.hit_rate, 1),
            "total_hits": self._cache_metrics.hits,
            "total_misses": self._cache_metrics.misses,
            "inserts_since_refresh": self._cache_metrics.inserts_since_refresh,
            "total_refresh_count": self._cache_metrics.total_refresh_count,
            "cache_size": len(self._cache),
            "level_cache_size": sum(len(v) for v in self._level_cache.values()),
        }
    
    async def load_category_cache(self) -> None:
        """
        Load all active categories into memory cache.
        
        Should be called once before processing to improve performance.
        Cache is keyed by normalized name (lowercase, stripped).
        T87: Also populates level-wise cache for optimized matching.
        T88: Pre-indexes categories by parent for fast level lookup.
        """
        if not self.cache_enabled:
            return
        
        start_time = time.time()
        
        query = select(
            Category.id,
            Category.name,
            Category.parent_id,
        ).where(Category.is_active == True)  # noqa: E712
        
        result = await self.session.execute(query)
        rows = result.all()
        
        # Clear existing caches
        self._cache.clear()
        self._level_cache.clear()
        
        for row in rows:
            normalized = Category.normalize_name(row.name)
            self._cache[normalized] = (row.id, row.name, row.parent_id)
            
            # T88: Build level-wise cache for optimized matching
            parent_id = row.parent_id
            if parent_id not in self._level_cache:
                self._level_cache[parent_id] = []
            self._level_cache[parent_id].append((row.id, row.name, normalized))
        
        self._cache_loaded = True
        
        # T87: Record cache refresh
        self._cache_metrics.record_refresh()
        
        load_time = time.time() - start_time
        logger.info(
            "category_normalizer.cache_loaded",
            total_categories=len(self._cache),
            level_groups=len(self._level_cache),
            load_time_seconds=round(load_time, 3),
            is_large_set=len(self._cache) >= LARGE_CATEGORY_SET_THRESHOLD,
        )
    
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
        
        T87: Checks for auto-refresh before processing.
        T88: Uses optimized matching for large candidate sets.
        
        Args:
            name: Category name to match/create
            parent_id: Parent category ID (None for root)
            supplier_id: Supplier ID for tracking
        
        Returns:
            CategoryMatchResult with match or creation details
        """
        # T87: Check if cache needs refresh
        if self.auto_refresh and self._cache_metrics.should_refresh():
            logger.debug(
                "category_normalizer.auto_refresh_triggered",
                inserts_since_refresh=self._cache_metrics.inserts_since_refresh,
            )
            await self.refresh_cache()
        
        # Normalize name for comparison
        normalized_name = Category.normalize_name(name)
        
        # T88: Use level cache for faster lookup
        candidates = self._get_candidates_at_level_fast(parent_id)
        
        if not candidates:
            # No existing categories at this level - create new
            self._cache_metrics.misses += 1
            return await self._create_new_category(
                name=name,
                parent_id=parent_id,
                supplier_id=supplier_id,
            )
        
        # T88: Use optimized matching for large sets
        if len(candidates) >= LARGE_CATEGORY_SET_THRESHOLD:
            match = self._fuzzy_match_optimized(normalized_name, candidates)
        else:
            match = self._fuzzy_match(normalized_name, candidates)
        
        if match and match[1] >= self.similarity_threshold:
            # Good match found
            matched_id, matched_name = match[0]
            similarity = match[1]
            
            self._cache_metrics.hits += 1
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
        self._cache_metrics.misses += 1
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
    
    def _get_candidates_at_level_fast(
        self,
        parent_id: Optional[int],
    ) -> list[tuple[tuple[int, str], str]]:
        """
        T88: Get candidates using pre-indexed level cache.
        
        O(1) lookup instead of O(n) iteration over all categories.
        
        Args:
            parent_id: Parent category ID (None for root level)
        
        Returns:
            List of ((id, name), normalized_name) tuples
        """
        if not self.cache_enabled or not self._cache_loaded:
            # Fall back to empty - will trigger DB query in caller
            return []
        
        # O(1) lookup from level cache
        level_entries = self._level_cache.get(parent_id, [])
        
        return [
            ((cat_id, cat_name), normalized)
            for cat_id, cat_name, normalized in level_entries
        ]
    
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
    
    def _fuzzy_match_optimized(
        self,
        query: str,
        candidates: list[tuple[tuple[int, str], str]],
    ) -> Optional[tuple[tuple[int, str], float]]:
        """
        T88: Optimized fuzzy matching for large category sets (>1000).
        
        Optimization strategies:
        1. Pre-filter by length difference (skip unlikely matches)
        2. Use faster QRatio scorer for initial pass
        3. Only use token_set_ratio for close matches
        
        Args:
            query: Normalized query string
            candidates: List of ((id, name), normalized_name) tuples
        
        Returns:
            ((id, name), similarity_score) or None if no candidates
        """
        if not candidates:
            return None
        
        query_len = len(query)
        
        # Step 1: Pre-filter by length difference
        # This is O(n) but very fast - eliminates obviously bad candidates
        filtered_candidates = [
            ((cat_id, cat_name), norm)
            for (cat_id, cat_name), norm in candidates
            if abs(len(norm) - query_len) <= max(PREFILTER_LENGTH_TOLERANCE, query_len // 2)
        ]
        
        # If filter removed too many, use all candidates
        if len(filtered_candidates) < len(candidates) // 10:
            filtered_candidates = candidates
        
        # Step 2: Fast initial pass with QRatio
        choices = {norm: (cat_id, cat_name) for (cat_id, cat_name), norm in filtered_candidates}
        
        # Find top 10 matches with fast QRatio
        fast_results = process.extract(
            query,
            choices.keys(),
            scorer=fuzz.QRatio,
            limit=10,
            score_cutoff=self.similarity_threshold * 0.7,  # Lower cutoff for initial pass
        )
        
        if not fast_results:
            # No good matches even with lenient threshold
            return None
        
        # Step 3: Re-score top candidates with accurate token_set_ratio
        best_match = None
        best_score = 0.0
        
        for matched_norm, fast_score, _ in fast_results:
            # Use accurate scorer for final decision
            accurate_score = fuzz.token_set_ratio(query, matched_norm)
            
            if accurate_score > best_score:
                best_score = accurate_score
                best_match = matched_norm
        
        if best_match is None:
            return None
        
        return (choices[best_match], best_score)
    
    async def _create_new_category(
        self,
        name: str,
        parent_id: Optional[int],
        supplier_id: Optional[int],
        best_match_score: float = 0.0,
    ) -> CategoryMatchResult:
        """
        Create a new category with needs_review=True.
        
        T87: Updates both caches and tracks insert count for auto-refresh.
        
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
            self._cache_metrics.hits += 1
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
        
        # T87: Update both caches and track insert count
        if self.cache_enabled:
            # Update main cache
            self._cache[normalized] = (new_category.id, name, parent_id)
            
            # T88: Update level cache for O(1) lookup
            if parent_id not in self._level_cache:
                self._level_cache[parent_id] = []
            self._level_cache[parent_id].append((new_category.id, name, normalized))
            
            # T87: Track insert count for auto-refresh
            self._cache_metrics.inserts_since_refresh += 1
        
        self.stats.created_count += 1
        self.stats.review_queue_count += 1
        
        logger.info(
            "category_normalizer.category_created",
            name=name,
            parent_id=parent_id,
            category_id=new_category.id,
            best_match_score=round(best_match_score, 1),
            inserts_since_refresh=self._cache_metrics.inserts_since_refresh,
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

