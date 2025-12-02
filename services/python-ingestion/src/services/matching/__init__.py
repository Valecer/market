"""Product matching services using fuzzy string matching.

This module provides strategies for matching supplier items to products
using RapidFuzz-based fuzzy string matching algorithms.

Key Components:
    - MatcherStrategy: Abstract base class for matching algorithms
    - RapidFuzzMatcher: Default implementation using RapidFuzz WRatio
    - MatchCandidate: Data transfer object for match candidates
    - MatchResult: Result container for matching operations
"""
from src.services.matching.matcher import (
    MatcherStrategy,
    RapidFuzzMatcher,
    MatchCandidate,
    MatchResult,
    MatchStatusEnum,
    create_matcher,
    search_match_candidates,
)

__all__ = [
    "MatcherStrategy",
    "RapidFuzzMatcher",
    "MatchCandidate",
    "MatchResult",
    "MatchStatusEnum",
    "create_matcher",
    "search_match_candidates",
]

