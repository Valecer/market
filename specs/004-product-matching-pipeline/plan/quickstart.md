# Quickstart: Product Matching Pipeline (15 Minutes)

**Feature:** 004-product-matching-pipeline  
**Target Time:** 15 minutes  
**Prerequisites:** Phase 1 (Python Worker) + Phase 2 (Bun API) complete

---

## Overview

This guide walks you through setting up the Product Matching & Data Enrichment Pipeline extension to the existing Python worker. By the end, you'll have:

1. Database schema extended with matching fields
2. RapidFuzz-powered matching service
3. Feature extraction service
4. New queue tasks integrated with existing worker

---

## Step 1: Install Dependencies (1 minute)

```bash
cd services/python-ingestion

# Activate virtual environment
source venv/bin/activate

# Install rapidfuzz
pip install "rapidfuzz>=3.5.0"

# Update requirements.txt
echo "rapidfuzz>=3.5.0" >> requirements.txt
```

---

## Step 2: Run Database Migration (2 minutes)

```bash
# Create migration file
alembic revision --autogenerate -m "add_matching_pipeline"

# Apply migration
alembic upgrade head
```

**Verify migration:**

```bash
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "\d supplier_items"
# Should show new columns: match_status, match_score, match_candidates

docker-compose exec postgres psql -U marketbel_user -d marketbel -c "\d match_review_queue"
# Should show new table
```

---

## Step 3: Create Matching Configuration (1 minute)

Add to `src/config.py`:

```python
# After existing settings class
class MatchingSettings(BaseModel):
    """Matching pipeline configuration."""
    auto_threshold: float = Field(default=95.0, ge=0, le=100)
    potential_threshold: float = Field(default=70.0, ge=0, le=100)
    batch_size: int = Field(default=100, ge=1, le=1000)
    review_expiration_days: int = Field(default=30, ge=1, le=365)
    
    class Config:
        env_prefix = "MATCH_"


# Add to settings instance
matching_settings = MatchingSettings()
```

---

## Step 4: Create Matcher Strategy (3 minutes)

Create `src/services/matching/__init__.py`:

```python
"""Product matching services."""
from src.services.matching.matcher import MatcherStrategy, RapidFuzzMatcher, MatchCandidate, MatchResult

__all__ = ["MatcherStrategy", "RapidFuzzMatcher", "MatchCandidate", "MatchResult"]
```

Create `src/services/matching/matcher.py`:

```python
"""Fuzzy string matching strategies for product matching."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from uuid import UUID
from rapidfuzz import process, fuzz, utils
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MatchCandidate:
    """Data transfer object for match candidates."""
    product_id: UUID
    product_name: str
    score: float  # 0-100
    category_id: Optional[UUID] = None


@dataclass
class MatchResult:
    """Result of matching operation."""
    supplier_item_id: UUID
    match_status: str  # 'auto_matched', 'potential_match', 'unmatched'
    best_match: Optional[MatchCandidate] = None
    candidates: List[MatchCandidate] = field(default_factory=list)
    match_score: Optional[float] = None


class MatcherStrategy(ABC):
    """Abstract interface for product matching algorithms."""
    
    @abstractmethod
    async def find_matches(
        self,
        item_name: str,
        category_id: Optional[UUID],
        candidates: List[dict]
    ) -> List[MatchCandidate]:
        """Find matching products for a supplier item."""
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return unique identifier for this strategy."""
        pass


class RapidFuzzMatcher(MatcherStrategy):
    """RapidFuzz-based fuzzy string matching."""
    
    def __init__(
        self,
        auto_threshold: float = 95.0,
        potential_threshold: float = 70.0,
        max_candidates: int = 5
    ):
        self.auto_threshold = auto_threshold
        self.potential_threshold = potential_threshold
        self.max_candidates = max_candidates
    
    async def find_matches(
        self,
        item_name: str,
        category_id: Optional[UUID],
        candidates: List[dict]
    ) -> List[MatchCandidate]:
        """Find matching products using RapidFuzz WRatio."""
        if not candidates:
            return []
        
        # Build choices dict for process.extract
        choices = {str(c['id']): c['name'] for c in candidates}
        
        # Use process.extract with WRatio and preprocessing
        results = process.extract(
            item_name,
            choices,
            scorer=fuzz.WRatio,
            processor=utils.default_process,
            limit=self.max_candidates,
            score_cutoff=self.potential_threshold
        )
        
        # Convert to MatchCandidate objects
        match_candidates = []
        for name, score, product_id in results:
            # Find original candidate to get category_id
            original = next((c for c in candidates if str(c['id']) == product_id), None)
            match_candidates.append(MatchCandidate(
                product_id=UUID(product_id),
                product_name=name,
                score=score,
                category_id=original.get('category_id') if original else None
            ))
        
        logger.debug(
            "fuzzy_match_completed",
            item_name=item_name,
            candidates_checked=len(candidates),
            matches_found=len(match_candidates)
        )
        
        return match_candidates
    
    def get_strategy_name(self) -> str:
        return "rapidfuzz_wratio"
```

---

## Step 5: Create Feature Extractors (2 minutes)

Create `src/services/extraction/__init__.py`:

```python
"""Feature extraction services."""
from src.services.extraction.extractors import (
    FeatureExtractor,
    ElectronicsExtractor,
    DimensionsExtractor,
    EXTRACTOR_REGISTRY
)

__all__ = [
    "FeatureExtractor",
    "ElectronicsExtractor", 
    "DimensionsExtractor",
    "EXTRACTOR_REGISTRY"
]
```

Create `src/services/extraction/extractors.py`:

```python
"""Feature extraction strategies for supplier items."""
from abc import ABC, abstractmethod
from typing import Dict, Any
import re
import structlog

logger = structlog.get_logger(__name__)


class FeatureExtractor(ABC):
    """Abstract interface for extracting features from text."""
    
    @abstractmethod
    def extract(self, text: str) -> Dict[str, Any]:
        """Extract features from text."""
        pass
    
    @abstractmethod
    def get_extractor_name(self) -> str:
        """Return unique identifier for this extractor."""
        pass


class ElectronicsExtractor(FeatureExtractor):
    """Extracts electrical specifications: voltage, power, wattage."""
    
    VOLTAGE_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*[Vv](?:olt)?s?(?:\s|$|,)', re.IGNORECASE)
    POWER_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*[Ww](?:att)?s?(?:\s|$|,)', re.IGNORECASE)
    KW_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*[Kk][Ww]', re.IGNORECASE)
    
    def extract(self, text: str) -> Dict[str, Any]:
        result = {}
        
        # Extract voltage
        voltage_match = self.VOLTAGE_PATTERN.search(text)
        if voltage_match:
            result['voltage'] = int(float(voltage_match.group(1)))
        
        # Extract power in watts
        power_match = self.POWER_PATTERN.search(text)
        if power_match:
            result['power_watts'] = int(float(power_match.group(1)))
        
        # Extract kilowatts (convert to watts)
        kw_match = self.KW_PATTERN.search(text)
        if kw_match and 'power_watts' not in result:
            result['power_watts'] = int(float(kw_match.group(1)) * 1000)
        
        return result
    
    def get_extractor_name(self) -> str:
        return "electronics"


class DimensionsExtractor(FeatureExtractor):
    """Extracts physical dimensions: weight, dimensions."""
    
    WEIGHT_KG_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*[Kk][Gg]', re.IGNORECASE)
    WEIGHT_G_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*[Gg](?:ram)?s?(?:\s|$|,)', re.IGNORECASE)
    DIMENSIONS_PATTERN = re.compile(
        r'(\d+(?:\.\d+)?)\s*[Xx×]\s*(\d+(?:\.\d+)?)\s*[Xx×]\s*(\d+(?:\.\d+)?)\s*(?:cm|mm)?',
        re.IGNORECASE
    )
    
    def extract(self, text: str) -> Dict[str, Any]:
        result = {}
        
        # Extract weight in kg
        kg_match = self.WEIGHT_KG_PATTERN.search(text)
        if kg_match:
            result['weight_kg'] = float(kg_match.group(1))
        
        # Extract weight in grams (convert to kg)
        g_match = self.WEIGHT_G_PATTERN.search(text)
        if g_match and 'weight_kg' not in result:
            result['weight_kg'] = round(float(g_match.group(1)) / 1000, 3)
        
        # Extract dimensions
        dim_match = self.DIMENSIONS_PATTERN.search(text)
        if dim_match:
            result['dimensions_cm'] = {
                'length': float(dim_match.group(1)),
                'width': float(dim_match.group(2)),
                'height': float(dim_match.group(3))
            }
        
        return result
    
    def get_extractor_name(self) -> str:
        return "dimensions"


# Registry of available extractors
EXTRACTOR_REGISTRY: Dict[str, FeatureExtractor] = {
    "electronics": ElectronicsExtractor(),
    "dimensions": DimensionsExtractor(),
}
```

---

## Step 6: Create Queue Tasks (4 minutes)

Create `src/tasks/__init__.py`:

```python
"""Queue task definitions for matching pipeline."""
from src.tasks.matching_tasks import match_items_task, enrich_item_task, recalc_product_aggregates_task

__all__ = ["match_items_task", "enrich_item_task", "recalc_product_aggregates_task"]
```

Create `src/tasks/matching_tasks.py`:

```python
"""Queue tasks for product matching pipeline."""
from typing import Dict, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import structlog

from arq.connections import ArqRedis
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import async_session_maker
from src.db.models import Product, SupplierItem, MatchReviewQueue
from src.db.models.supplier_item import MatchStatus
from src.db.models.match_review_queue import ReviewStatus
from src.services.matching import RapidFuzzMatcher
from src.services.extraction import EXTRACTOR_REGISTRY
from src.config import matching_settings

logger = structlog.get_logger(__name__)


async def match_items_task(ctx: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Process batch of unmatched supplier items."""
    task_id = kwargs.get('task_id', 'unknown')
    category_id = kwargs.get('category_id')
    batch_size = kwargs.get('batch_size', matching_settings.batch_size)
    
    log = logger.bind(task_id=task_id)
    log.info("match_items_task_started", batch_size=batch_size, category_id=category_id)
    
    start_time = datetime.now(timezone.utc)
    stats = {
        'items_processed': 0,
        'auto_matched': 0,
        'potential_matches': 0,
        'new_products_created': 0,
        'errors': []
    }
    
    matcher = RapidFuzzMatcher(
        auto_threshold=matching_settings.auto_threshold,
        potential_threshold=matching_settings.potential_threshold
    )
    
    async with async_session_maker() as session:
        async with session.begin():
            # Get unmatched items with locking
            stmt = (
                select(SupplierItem)
                .where(SupplierItem.product_id.is_(None))
                .where(SupplierItem.match_status == MatchStatus.UNMATCHED)
                .order_by(SupplierItem.created_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            
            result = await session.execute(stmt)
            items = result.scalars().all()
            
            if not items:
                log.info("no_unmatched_items_found")
                return {
                    'task_id': task_id,
                    'status': 'success',
                    **stats,
                    'duration_seconds': 0
                }
            
            # Get candidate products (filtered by category if provided)
            products_stmt = select(Product.id, Product.name, Product.category_id)
            if category_id:
                products_stmt = products_stmt.where(Product.category_id == category_id)
            
            products_result = await session.execute(products_stmt)
            candidates = [
                {'id': row.id, 'name': row.name, 'category_id': row.category_id}
                for row in products_result
            ]
            
            # Process each item
            for item in items:
                try:
                    matches = await matcher.find_matches(
                        item_name=item.name,
                        category_id=item.characteristics.get('category_id'),
                        candidates=candidates
                    )
                    
                    if matches and matches[0].score >= matching_settings.auto_threshold:
                        # Auto-match
                        best = matches[0]
                        item.product_id = best.product_id
                        item.match_status = MatchStatus.AUTO_MATCHED
                        item.match_score = Decimal(str(best.score))
                        stats['auto_matched'] += 1
                        
                        # Enqueue aggregation recalc
                        redis: ArqRedis = ctx.get('redis')
                        if redis:
                            await redis.enqueue_job(
                                'recalc_product_aggregates_task',
                                task_id=f"recalc-{task_id}-{item.id}",
                                product_ids=[str(best.product_id)],
                                trigger='auto_match'
                            )
                    
                    elif matches and matches[0].score >= matching_settings.potential_threshold:
                        # Flag for review
                        item.match_status = MatchStatus.POTENTIAL_MATCH
                        item.match_score = Decimal(str(matches[0].score))
                        item.match_candidates = [
                            {'product_id': str(m.product_id), 'product_name': m.product_name, 'score': m.score}
                            for m in matches
                        ]
                        
                        # Create review queue entry
                        review = MatchReviewQueue(
                            supplier_item_id=item.id,
                            candidate_products=item.match_candidates,
                            status=ReviewStatus.PENDING,
                            expires_at=datetime.now(timezone.utc) + timedelta(days=matching_settings.review_expiration_days)
                        )
                        session.add(review)
                        stats['potential_matches'] += 1
                    
                    else:
                        # Create new product (draft status)
                        from src.utils.sku_generator import generate_internal_sku
                        new_product = Product(
                            internal_sku=generate_internal_sku(),
                            name=item.name,
                            category_id=item.characteristics.get('category_id'),
                            status='draft'
                        )
                        session.add(new_product)
                        await session.flush()  # Get product ID
                        
                        item.product_id = new_product.id
                        item.match_status = MatchStatus.AUTO_MATCHED
                        item.match_score = Decimal('100.0')  # Self-match
                        stats['new_products_created'] += 1
                    
                    stats['items_processed'] += 1
                    
                except Exception as e:
                    log.error("item_matching_failed", item_id=str(item.id), error=str(e))
                    stats['errors'].append(f"Item {item.id}: {str(e)}")
    
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    log.info("match_items_task_completed", **stats, duration_seconds=duration)
    
    return {
        'task_id': task_id,
        'status': 'success' if not stats['errors'] else 'partial_success',
        **stats,
        'duration_seconds': duration
    }


async def enrich_item_task(ctx: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Extract features from supplier item text."""
    task_id = kwargs.get('task_id', 'unknown')
    supplier_item_id = kwargs.get('supplier_item_id')
    extractor_names = kwargs.get('extractors', ['electronics', 'dimensions'])
    
    log = logger.bind(task_id=task_id, supplier_item_id=supplier_item_id)
    log.info("enrich_item_task_started")
    
    start_time = datetime.now(timezone.utc)
    extracted_features = {}
    extractors_applied = []
    
    async with async_session_maker() as session:
        async with session.begin():
            result = await session.execute(
                select(SupplierItem).where(SupplierItem.id == supplier_item_id)
            )
            item = result.scalar_one_or_none()
            
            if not item:
                log.warning("supplier_item_not_found")
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'supplier_item_id': supplier_item_id,
                    'errors': ['Supplier item not found']
                }
            
            # Apply extractors
            text_to_analyze = item.name
            for name in extractor_names:
                extractor = EXTRACTOR_REGISTRY.get(name)
                if extractor:
                    features = extractor.extract(text_to_analyze)
                    if features:
                        extracted_features.update(features)
                        extractors_applied.append(name)
            
            # Merge with existing characteristics (don't overwrite)
            if extracted_features:
                merged = {**extracted_features, **item.characteristics}
                item.characteristics = merged
    
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    log.info(
        "enrich_item_task_completed",
        extracted_features=extracted_features,
        extractors_applied=extractors_applied,
        duration_seconds=duration
    )
    
    return {
        'task_id': task_id,
        'status': 'success' if extracted_features else 'no_extraction',
        'supplier_item_id': supplier_item_id,
        'extracted_features': extracted_features,
        'extractors_applied': extractors_applied,
        'duration_seconds': duration
    }


async def recalc_product_aggregates_task(ctx: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Recalculate min_price and availability for products."""
    task_id = kwargs.get('task_id', 'unknown')
    product_ids = kwargs.get('product_ids', [])
    trigger = kwargs.get('trigger', 'unknown')
    
    log = logger.bind(task_id=task_id, trigger=trigger)
    log.info("recalc_aggregates_task_started", product_count=len(product_ids))
    
    start_time = datetime.now(timezone.utc)
    updates = []
    
    async with async_session_maker() as session:
        async with session.begin():
            for product_id_str in product_ids:
                product_id = UUID(product_id_str) if isinstance(product_id_str, str) else product_id_str
                
                # Calculate aggregates
                agg_stmt = (
                    select(
                        func.min(SupplierItem.current_price).label('min_price'),
                        func.bool_or(
                            SupplierItem.characteristics['in_stock'].astext.cast(bool)
                        ).label('availability'),
                        func.count(SupplierItem.id).label('supplier_count')
                    )
                    .where(SupplierItem.product_id == product_id)
                    .where(SupplierItem.match_status.in_([
                        MatchStatus.AUTO_MATCHED,
                        MatchStatus.VERIFIED_MATCH
                    ]))
                )
                
                result = await session.execute(agg_stmt)
                agg = result.one()
                
                # Update product
                await session.execute(
                    update(Product)
                    .where(Product.id == product_id)
                    .values(
                        min_price=agg.min_price,
                        availability=agg.availability or False,
                        updated_at=func.now()
                    )
                )
                
                updates.append({
                    'product_id': str(product_id),
                    'min_price': str(agg.min_price) if agg.min_price else None,
                    'availability': agg.availability or False,
                    'supplier_count': agg.supplier_count
                })
    
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    log.info("recalc_aggregates_task_completed", updates=updates, duration_seconds=duration)
    
    return {
        'task_id': task_id,
        'status': 'success',
        'products_updated': len(updates),
        'updates': updates,
        'duration_seconds': duration
    }
```

---

## Step 7: Register Tasks with Worker (1 minute)

Update `src/worker.py` to include new tasks:

```python
# Add to imports
from src.tasks import match_items_task, enrich_item_task, recalc_product_aggregates_task

# Update WorkerSettings.functions
class WorkerSettings:
    # ... existing settings ...
    
    functions = [
        parse_task,
        match_items_task,        # NEW
        enrich_item_task,        # NEW
        recalc_product_aggregates_task  # NEW
    ]
```

---

## Step 8: Test the Pipeline (1 minute)

```bash
# Start the worker
docker-compose up -d worker

# Enqueue a test matching task
python -c "
import asyncio
from arq import create_pool
from arq.connections import RedisSettings

async def main():
    redis = await create_pool(RedisSettings())
    job = await redis.enqueue_job('match_items_task', task_id='test-match-001', batch_size=10)
    print(f'Enqueued job: {job.job_id}')
    await redis.close()

asyncio.run(main())
"

# Check worker logs
docker-compose logs -f worker
```

---

## Verification Checklist

- [ ] Migration applied successfully
- [ ] `supplier_items` has `match_status`, `match_score`, `match_candidates` columns
- [ ] `match_review_queue` table exists
- [ ] `products` has `min_price`, `availability`, `mrp` columns
- [ ] Worker starts without import errors
- [ ] Test matching task enqueues and processes
- [ ] Extractor patterns work on sample text

---

## Environment Variables

Add to `.env`:

```bash
# Matching Pipeline Configuration
MATCH_AUTO_THRESHOLD=95.0
MATCH_POTENTIAL_THRESHOLD=70.0
MATCH_BATCH_SIZE=100
MATCH_REVIEW_EXPIRATION_DAYS=30
```

---

## Next Steps

After quickstart completion:

1. **Integration Testing:** Run full pipeline tests with Docker services
2. **Performance Tuning:** Profile batch size and concurrency settings
3. **Bun API Integration:** Add endpoints for manual review queue
4. **Monitoring:** Set up alerts for backlog and error rates

---

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError`:

```bash
# Ensure __init__.py files exist
touch src/services/__init__.py
touch src/services/matching/__init__.py
touch src/services/extraction/__init__.py
touch src/tasks/__init__.py
```

### Migration Failures

If migration fails with enum errors:

```sql
-- Check if enums already exist
SELECT typname FROM pg_type WHERE typname IN ('match_status', 'review_status');

-- Drop if needed and re-run migration
DROP TYPE IF EXISTS match_status CASCADE;
DROP TYPE IF EXISTS review_status CASCADE;
```

### Worker Not Processing Tasks

Check Redis connection:

```bash
docker-compose exec redis redis-cli PING
# Should return: PONG

# Check queue depth
docker-compose exec redis redis-cli LLEN arq:queue:default
```

---

**Total Setup Time:** ~15 minutes

