"""Queue task definitions for the ingestion pipeline.

Phase 9: Courier pattern - parsing tasks removed.
All parsing/extraction handled by ml-analyze service.

This module contains arq task functions for:
    - download_and_trigger_ml: Download files and trigger ML processing
    - poll_ml_job_status_task: Poll ML job status
    - cleanup_shared_files_task: Clean up old shared files
    - match_items_task: Process unmatched supplier items
    - enrich_item_task: Extract features from item text (deprecated)
    - recalc_product_aggregates_task: Update product min_price
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
from src.tasks.download_tasks import download_and_trigger_ml
from src.tasks.ml_polling_tasks import poll_ml_job_status_task
from src.tasks.cleanup_tasks import cleanup_shared_files_task

__all__ = [
    # ML pipeline tasks (Phase 8/9)
    "download_and_trigger_ml",
    "poll_ml_job_status_task",
    "cleanup_shared_files_task",
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
