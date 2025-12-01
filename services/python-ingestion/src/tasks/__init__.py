"""Queue task definitions for the ingestion pipeline.

This module contains arq task functions for:
    - match_items_task: Process unmatched supplier items
    - enrich_item_task: Extract features from item text
    - recalc_product_aggregates_task: Update product min_price/availability
    - handle_manual_match_event: Process manual link/unlink events
    - expire_review_queue_task: Clean up expired review items
    - trigger_master_sync_task: Execute master sync pipeline
    - scheduled_sync_task: Cron wrapper for scheduled syncs
"""
from src.tasks.matching_tasks import (
    match_items_task,
    MatchingMetrics,
    generate_internal_sku,
)
from src.tasks.sync_tasks import (
    trigger_master_sync_task,
    scheduled_sync_task,
    SyncMetrics,
    get_sync_interval_hours,
    get_master_sheet_url,
)

__all__ = [
    # Matching tasks
    "match_items_task",
    "MatchingMetrics",
    "generate_internal_sku",
    # Sync tasks
    "trigger_master_sync_task",
    "scheduled_sync_task",
    "SyncMetrics",
    "get_sync_interval_hours",
    "get_master_sheet_url",
]

