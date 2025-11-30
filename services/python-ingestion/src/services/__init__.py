"""Business logic services for the data ingestion pipeline.

Available Services:
    - matching: Product matching using fuzzy string comparison
    - aggregation: Product aggregate calculations (min_price, availability)
"""
from src.services.matching import (
    RapidFuzzMatcher,
    MatcherStrategy,
    MatchCandidate,
    MatchResult,
    MatchStatusEnum,
    create_matcher,
    search_match_candidates,
)
from src.services.aggregation import (
    calculate_product_aggregates,
    calculate_product_aggregates_batch,
    get_review_queue_stats,
)

__all__: list[str] = [
    # Matching
    "RapidFuzzMatcher",
    "MatcherStrategy",
    "MatchCandidate",
    "MatchResult",
    "MatchStatusEnum",
    "create_matcher",
    "search_match_candidates",
    # Aggregation
    "calculate_product_aggregates",
    "calculate_product_aggregates_batch",
    "get_review_queue_stats",
]

