"""
Category Hierarchy Service for Pipeline Stabilization
=====================================================

Enforces strict 3-level category hierarchy (Top → Sub-category → Brand).

Phase 11: US3 - Category Hierarchy Enforcement
- T095: Create CategoryHierarchyService class
- T096: Implement ensure_3_level_hierarchy
- T097: Implement find_or_create_category with level validation
- T098: Handle >3 levels (truncate with warning)
- T099: Handle <3 levels (flag needs_review)
- T100: Implement flag_incomplete_hierarchy
"""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Category
from src.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

MAX_HIERARCHY_LEVELS = 3
LEVEL_NAMES = {1: "Top", 2: "Sub-category", 3: "Brand"}


@dataclass
class CategoryLevelResult:
    """Result of creating/finding a category at a specific level."""
    
    category_id: UUID
    category_name: str
    level: int
    action: str  # 'found', 'created'
    parent_id: Optional[UUID] = None
    needs_review: bool = False


@dataclass
class HierarchyEnforcementResult:
    """Result of enforcing 3-level hierarchy on a category path."""
    
    original_path: list[str]
    processed_path: list[str]
    level_results: list[CategoryLevelResult] = field(default_factory=list)
    leaf_category_id: Optional[UUID] = None
    is_complete: bool = False  # True if exactly 3 levels
    was_truncated: bool = False  # True if >3 levels were provided
    needs_review: bool = False  # True if <3 levels (incomplete)
    warning_message: Optional[str] = None
    
    @property
    def level_count(self) -> int:
        """Number of levels in the hierarchy."""
        return len(self.level_results)


class CategoryHierarchyService:
    """
    Service to enforce strict 3-level category hierarchy.
    
    Hierarchy Structure:
        Level 1: Top Category (e.g., "Electric Transport")
        Level 2: Sub-category (e.g., "Motorcycles")
        Level 3: Brand (e.g., "Shtenli")
    
    Rules:
        1. All products MUST be assigned to Level 3 categories
        2. If extraction provides >3 levels, take first 3 and log warning
        3. If extraction provides <3 levels, create partial hierarchy with needs_review=True
        4. Log incomplete hierarchies to parsing_logs table
    
    Usage:
        service = CategoryHierarchyService(session)
        result = await service.ensure_3_level_hierarchy(
            ["Electronics", "Laptops", "Dell"],
            supplier_id=supplier_uuid
        )
        
        # result.leaf_category_id is the Level 3 category for product assignment
        # result.is_complete is True if all 3 levels present
    """
    
    def __init__(
        self,
        session: AsyncSession,
        task_id: Optional[str] = None,
    ):
        """
        Initialize CategoryHierarchyService.
        
        Args:
            session: SQLAlchemy async session
            task_id: Optional task ID for logging to parsing_logs
        """
        self.session = session
        self.task_id = task_id or "unknown"
        
        # Statistics tracking
        self._stats = {
            "hierarchies_processed": 0,
            "complete_hierarchies": 0,
            "truncated_hierarchies": 0,
            "incomplete_hierarchies": 0,
            "categories_created": 0,
            "categories_found": 0,
        }
    
    def get_stats(self) -> dict:
        """Get processing statistics."""
        return self._stats.copy()
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        for key in self._stats:
            self._stats[key] = 0
    
    async def ensure_3_level_hierarchy(
        self,
        category_path: list[str],
        supplier_id: Optional[UUID] = None,
    ) -> HierarchyEnforcementResult:
        """
        Ensure category path follows strict 3-level hierarchy.
        
        T096: Main entry point for hierarchy enforcement.
        
        Processing Logic:
            - If path has 3 levels: Process normally (ideal case)
            - If path has >3 levels: Take first 3, log warning (T098)
            - If path has <3 levels: Create partial, flag needs_review (T099)
            - If path is empty: Return with warning
        
        Args:
            category_path: List of category names from general to specific
                          e.g., ["Electronics", "Laptops", "Dell"]
            supplier_id: Supplier ID for tracking new category origin
        
        Returns:
            HierarchyEnforcementResult with processed hierarchy details
        """
        self._stats["hierarchies_processed"] += 1
        
        # Handle empty path
        if not category_path:
            logger.warning(
                "category_hierarchy.empty_path",
                message="Empty category path provided",
            )
            return HierarchyEnforcementResult(
                original_path=[],
                processed_path=[],
                warning_message="Empty category path provided",
            )
        
        # Clean and filter empty elements
        cleaned_path = [
            name.strip() for name in category_path
            if name and name.strip()
        ]
        
        if not cleaned_path:
            logger.warning(
                "category_hierarchy.all_empty_elements",
                original_path=category_path,
                message="All category path elements were empty",
            )
            return HierarchyEnforcementResult(
                original_path=category_path,
                processed_path=[],
                warning_message="All category path elements were empty",
            )
        
        # Determine processing strategy based on path length
        original_path = cleaned_path.copy()
        processed_path = cleaned_path
        was_truncated = False
        needs_review = False
        warning_message = None
        
        if len(cleaned_path) > MAX_HIERARCHY_LEVELS:
            # T098: Truncate to first 3 levels
            processed_path = cleaned_path[:MAX_HIERARCHY_LEVELS]
            was_truncated = True
            self._stats["truncated_hierarchies"] += 1
            
            warning_message = (
                f"Category path truncated from {len(cleaned_path)} to "
                f"{MAX_HIERARCHY_LEVELS} levels. Discarded: {cleaned_path[MAX_HIERARCHY_LEVELS:]}"
            )
            
            logger.warning(
                "category_hierarchy.path_truncated",
                original_path=cleaned_path,
                processed_path=processed_path,
                discarded=cleaned_path[MAX_HIERARCHY_LEVELS:],
            )
            
        elif len(cleaned_path) < MAX_HIERARCHY_LEVELS:
            # T099: Handle incomplete hierarchy
            needs_review = True
            self._stats["incomplete_hierarchies"] += 1
            
            warning_message = (
                f"Incomplete category hierarchy: {len(cleaned_path)} of "
                f"{MAX_HIERARCHY_LEVELS} levels provided. Categories flagged for review."
            )
            
            logger.info(
                "category_hierarchy.incomplete_path",
                path=cleaned_path,
                level_count=len(cleaned_path),
                expected=MAX_HIERARCHY_LEVELS,
            )
        else:
            self._stats["complete_hierarchies"] += 1
        
        # Process each level in hierarchy
        level_results: list[CategoryLevelResult] = []
        parent_id: Optional[UUID] = None
        
        for level_idx, category_name in enumerate(processed_path):
            level = level_idx + 1  # 1-indexed levels
            
            result = await self.find_or_create_category(
                name=category_name,
                parent_id=parent_id,
                level=level,
                supplier_id=supplier_id,
                needs_review=needs_review,  # Flag if partial hierarchy
            )
            
            level_results.append(result)
            parent_id = result.category_id
        
        # Get leaf category ID (last category in hierarchy)
        leaf_category_id = level_results[-1].category_id if level_results else None
        
        # Flag incomplete hierarchy if <3 levels
        if needs_review and leaf_category_id:
            await self.flag_incomplete_hierarchy(
                category_id=leaf_category_id,
                category_path=processed_path,
                supplier_id=supplier_id,
            )
        
        return HierarchyEnforcementResult(
            original_path=original_path,
            processed_path=processed_path,
            level_results=level_results,
            leaf_category_id=leaf_category_id,
            is_complete=len(processed_path) == MAX_HIERARCHY_LEVELS,
            was_truncated=was_truncated,
            needs_review=needs_review,
            warning_message=warning_message,
        )
    
    async def find_or_create_category(
        self,
        name: str,
        parent_id: Optional[UUID],
        level: int,
        supplier_id: Optional[UUID] = None,
        needs_review: bool = False,
    ) -> CategoryLevelResult:
        """
        Find existing category or create new one at specific level.
        
        T097: Find or create with level validation.
        
        Args:
            name: Category name
            parent_id: Parent category ID (None for Level 1)
            level: Category level (1, 2, or 3)
            supplier_id: Supplier ID for tracking
            needs_review: Whether to flag category for review
        
        Returns:
            CategoryLevelResult with category details
        
        Raises:
            ValueError: If level is not 1, 2, or 3
        """
        # Validate level
        if level not in (1, 2, 3):
            raise ValueError(f"Invalid category level: {level}. Must be 1, 2, or 3.")
        
        # Validate parent_id based on level
        if level == 1 and parent_id is not None:
            logger.warning(
                "category_hierarchy.invalid_parent_for_level1",
                name=name,
                parent_id=parent_id,
                message="Level 1 categories should have no parent, ignoring parent_id",
            )
            parent_id = None
        elif level > 1 and parent_id is None:
            raise ValueError(f"Level {level} categories must have a parent_id")
        
        # Normalize name for comparison
        normalized_name = Category.normalize_name(name)
        
        # Try to find existing category at this level with same parent
        if parent_id is None:
            query = select(Category).where(
                func.lower(func.trim(Category.name)) == normalized_name,
                Category.parent_id.is_(None),
                Category.is_active == True,  # noqa: E712
            )
        else:
            query = select(Category).where(
                func.lower(func.trim(Category.name)) == normalized_name,
                Category.parent_id == parent_id,
                Category.is_active == True,  # noqa: E712
            )
        
        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            self._stats["categories_found"] += 1
            
            logger.debug(
                "category_hierarchy.category_found",
                name=name,
                category_id=existing.id,
                level=level,
            )
            
            return CategoryLevelResult(
                category_id=existing.id,
                category_name=existing.name,
                level=level,
                action="found",
                parent_id=parent_id,
                needs_review=existing.needs_review,
            )
        
        # Create new category
        new_category = Category(
            name=name,
            parent_id=parent_id,
            category_level=level,
            needs_review=needs_review,
            is_active=True,
            supplier_id=supplier_id,
        )
        
        self.session.add(new_category)
        await self.session.flush()  # Get the ID
        
        self._stats["categories_created"] += 1
        
        logger.info(
            "category_hierarchy.category_created",
            name=name,
            category_id=new_category.id,
            level=level,
            parent_id=parent_id,
            needs_review=needs_review,
            level_name=LEVEL_NAMES.get(level, "Unknown"),
        )
        
        return CategoryLevelResult(
            category_id=new_category.id,
            category_name=name,
            level=level,
            action="created",
            parent_id=parent_id,
            needs_review=needs_review,
        )
    
    async def flag_incomplete_hierarchy(
        self,
        category_id: UUID,
        category_path: list[str],
        supplier_id: Optional[UUID] = None,
    ) -> None:
        """
        Log incomplete hierarchy to parsing_logs table.
        
        T100: Flag incomplete hierarchies for admin review.
        
        This creates a parsing_log entry that admins can review to
        understand which categories need hierarchy completion.
        
        Args:
            category_id: The leaf category ID (incomplete)
            category_path: The incomplete category path
            supplier_id: Supplier ID for reference
        """
        from src.db.models import ParsingLog
        
        log_entry = ParsingLog(
            task_id=self.task_id,
            supplier_id=supplier_id,
            error_type="incomplete_category_hierarchy",
            error_message=(
                f"Category hierarchy has only {len(category_path)} of "
                f"{MAX_HIERARCHY_LEVELS} required levels: {' > '.join(category_path)}"
            ),
            row_data={
                "category_path": category_path,
                "category_id": str(category_id),
                "expected_levels": MAX_HIERARCHY_LEVELS,
                "actual_levels": len(category_path),
            },
            extraction_phase="category_hierarchy_enforcement",
        )
        
        self.session.add(log_entry)
        
        logger.info(
            "category_hierarchy.incomplete_flagged",
            category_id=category_id,
            category_path=category_path,
            level_count=len(category_path),
        )
    
    async def get_category_breadcrumb(
        self,
        category_id: UUID,
    ) -> list[dict]:
        """
        Get full category breadcrumb from root to leaf.
        
        Useful for displaying category hierarchy in UI.
        
        Args:
            category_id: The category ID to get breadcrumb for
        
        Returns:
            List of dicts with category info from root to leaf:
            [
                {"id": "...", "name": "Electronics", "level": 1},
                {"id": "...", "name": "Laptops", "level": 2},
                {"id": "...", "name": "Dell", "level": 3},
            ]
        """
        breadcrumb: list[dict] = []
        
        # Fetch the category
        query = select(Category).where(Category.id == category_id)
        result = await self.session.execute(query)
        current = result.scalar_one_or_none()
        
        if not current:
            return breadcrumb
        
        # Build path from leaf to root
        while current is not None:
            breadcrumb.insert(0, {
                "id": str(current.id),
                "name": current.name,
                "level": current.category_level,
                "needs_review": current.needs_review,
            })
            
            if current.parent_id:
                query = select(Category).where(Category.id == current.parent_id)
                result = await self.session.execute(query)
                current = result.scalar_one_or_none()
            else:
                break
        
        return breadcrumb
    
    async def pad_incomplete_hierarchy(
        self,
        category_id: UUID,
        padding_name: str = "Uncategorized",
    ) -> list[dict]:
        """
        Get breadcrumb with padding for incomplete hierarchies.
        
        If a category has fewer than 3 levels, pads with "Uncategorized"
        entries to maintain consistent 3-level display.
        
        Args:
            category_id: The category ID
            padding_name: Name to use for padding (default: "Uncategorized")
        
        Returns:
            List of exactly 3 breadcrumb entries
        """
        breadcrumb = await self.get_category_breadcrumb(category_id)
        
        # Pad to 3 levels if needed
        while len(breadcrumb) < MAX_HIERARCHY_LEVELS:
            level = len(breadcrumb) + 1
            breadcrumb.append({
                "id": None,
                "name": padding_name,
                "level": level,
                "needs_review": True,
                "is_placeholder": True,
            })
        
        return breadcrumb


# Import ParsingLog at module level (needed for flag_incomplete_hierarchy)
try:
    from src.db.models import ParsingLog
except ImportError:
    # ParsingLog may be in python-ingestion service
    # We'll define a minimal model for ml-analyze
    pass
