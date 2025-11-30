"""Product aggregation service.

This module provides services for calculating and maintaining
aggregate fields on products from linked supplier items:
    - min_price: Lowest price among linked active supplier items
    - availability: TRUE if any linked supplier has stock

Key Components:
    - calculate_product_aggregates: Core aggregation function
    - get_review_queue_stats: Statistics for review queue dashboard
"""
from src.services.aggregation.service import (
    calculate_product_aggregates,
    calculate_product_aggregates_batch,
    get_review_queue_stats,
)

__all__ = [
    "calculate_product_aggregates",
    "calculate_product_aggregates_batch",
    "get_review_queue_stats",
]

