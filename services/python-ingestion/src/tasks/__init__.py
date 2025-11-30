"""Queue task definitions for the matching pipeline.

This module contains arq task functions for:
    - match_items_task: Process unmatched supplier items
    - enrich_item_task: Extract features from item text
    - recalc_product_aggregates_task: Update product min_price/availability
    - handle_manual_match_event: Process manual link/unlink events
    - expire_review_queue_task: Clean up expired review items
"""
from src.tasks.matching_tasks import (
    match_items_task,
    MatchingMetrics,
    generate_internal_sku,
)

__all__ = [
    "match_items_task",
    "MatchingMetrics",
    "generate_internal_sku",
]

