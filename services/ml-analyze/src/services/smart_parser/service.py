"""
Smart Parser Service - Orchestration Layer
==========================================

Orchestrates the semantic ETL pipeline:
1. Read Excel/CSV file
2. Select sheets (priority: "Upload to site", etc.) - Phase 9 US2: Multi-sheet support
3. Convert to Markdown
4. Extract products via LLM
5. Normalize categories
6. Deduplicate products (within-file + cross-sheet)
7. Insert to database
8. Log errors to parsing_logs

Phase 9: Semantic ETL Pipeline Refactoring
- US1: Standard file upload (complete)
- US2: Multi-sheet files (T053-T063)

Phase 9 T80: Enhanced structured logging for observability.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings
from src.db.repositories.parsing_logs_repo import ParsingLogsRepository
from src.schemas.extraction import ExtractionResult
from src.services.category_normalizer import CategoryNormalizer
from src.services.deduplication_service import DeduplicationService
from src.services.job_service import JobService
from src.services.smart_parser.langchain_extractor import LangChainExtractor
from src.services.smart_parser.markdown_converter import MarkdownConverter
from src.services.smart_parser.sheet_selector import SheetSelector, SheetSelectionResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# T83: User-Friendly Error Messages
# =============================================================================

# Error type to user-friendly message mapping
ERROR_MESSAGES: dict[str, dict[str, str]] = {
    "file_not_found": {
        "title": "File Not Found",
        "description": "The specified file could not be located.",
        "recommendation": "Please verify the file path and ensure the file has been uploaded successfully.",
    },
    "no_sheets_found": {
        "title": "No Product Sheets Found",
        "description": "No sheets containing product data were identified in the file.",
        "recommendation": "Ensure your Excel file has a sheet named 'Upload to site', 'Products', or 'Catalog'. The sheet should contain product data with Name and Price columns.",
    },
    "empty_sheet": {
        "title": "Empty Sheet",
        "description": "The selected sheet contains no data rows.",
        "recommendation": "Add product data to your spreadsheet with at least a header row and one data row.",
    },
    "llm_timeout": {
        "title": "Processing Timeout",
        "description": "The AI model took too long to process the data.",
        "recommendation": "Try uploading a smaller file (under 500 rows) or contact support if the issue persists.",
    },
    "llm_error": {
        "title": "AI Processing Error",
        "description": "The AI model encountered an error while extracting products.",
        "recommendation": "This may be a temporary issue. Please try again in a few minutes.",
    },
    "validation_error": {
        "title": "Data Validation Error",
        "description": "Some products could not be validated due to missing or invalid fields.",
        "recommendation": "Ensure each product row has at least a Name and Price. Check that prices are numeric values.",
    },
    "parsing_error": {
        "title": "File Parsing Error",
        "description": "The file could not be parsed correctly.",
        "recommendation": "Verify the file is a valid Excel (.xlsx) or CSV file. Try re-exporting from your source application.",
    },
    "category_error": {
        "title": "Category Processing Error",
        "description": "An error occurred while matching or creating categories.",
        "recommendation": "Check that category names in your file are not excessively long (max 200 characters).",
    },
    "orchestration_error": {
        "title": "Processing Pipeline Error",
        "description": "An unexpected error occurred during file processing.",
        "recommendation": "Please try again. If the issue persists, contact support with the job ID.",
    },
}


def get_user_friendly_error(
    error_type: str,
    context: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Get user-friendly error message for a given error type.
    
    T83: Provides clear, actionable error messages for end users.
    
    Args:
        error_type: Type of error (e.g., 'file_not_found', 'llm_timeout')
        context: Additional context to include in the message
    
    Returns:
        Dictionary with title, description, and recommendation
    """
    base_error = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES["orchestration_error"])
    result = {**base_error}
    
    # Add context-specific details if provided
    if context:
        if "file_path" in context:
            result["description"] += f" (File: {Path(context['file_path']).name})"
        if "sheet_name" in context:
            result["description"] += f" (Sheet: {context['sheet_name']})"
        if "row_count" in context:
            result["description"] += f" (Rows: {context['row_count']})"
    
    return result


def format_error_for_user(
    error_type: str,
    technical_message: str,
    context: dict[str, Any] | None = None,
) -> str:
    """
    Format an error message for user display.
    
    T83: Combines user-friendly description with technical details.
    
    Args:
        error_type: Type of error
        technical_message: Technical error message for debugging
        context: Additional context
    
    Returns:
        Formatted error message string
    """
    user_error = get_user_friendly_error(error_type, context)
    
    return (
        f"{user_error['title']}: {user_error['description']} "
        f"Recommendation: {user_error['recommendation']} "
        f"(Technical: {technical_message})"
    )


@dataclass
class PhaseMetrics:
    """
    Metrics for a single processing phase.
    
    T80: Structured logging enhancement for semantic ETL phases.
    """
    
    phase_name: str
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    items_processed: int = 0
    items_failed: int = 0
    context: dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> float:
        """Get phase duration in seconds."""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    @property
    def success_rate(self) -> float:
        """Get success rate as percentage (0-100)."""
        total = self.items_processed + self.items_failed
        if total == 0:
            return 100.0
        return (self.items_processed / total) * 100.0
    
    def complete(self, items_processed: int = 0, items_failed: int = 0) -> None:
        """Mark phase as complete with final counts."""
        self.end_time = time.time()
        self.items_processed = items_processed
        self.items_failed = items_failed
    
    def to_log_dict(self) -> dict[str, Any]:
        """Convert to structured log dictionary."""
        return {
            "phase": self.phase_name,
            "duration_seconds": round(self.duration_seconds, 3),
            "items_processed": self.items_processed,
            "items_failed": self.items_failed,
            "success_rate": round(self.success_rate, 1),
            **self.context,
        }


@dataclass
class ETLMetrics:
    """
    Aggregate metrics for entire ETL pipeline run.
    
    T80: Comprehensive metrics tracking for semantic ETL.
    """
    
    job_id: str
    supplier_id: int
    file_path: str
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    phases: list[PhaseMetrics] = field(default_factory=list)
    
    # Final metrics
    total_rows: int = 0
    successful_extractions: int = 0
    failed_extractions: int = 0
    duplicates_removed: int = 0
    categories_matched: int = 0
    categories_created: int = 0
    final_status: str = "pending"
    error_message: str | None = None
    
    @property
    def duration_seconds(self) -> float:
        """Get total ETL duration in seconds."""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    @property
    def extraction_success_rate(self) -> float:
        """Get extraction success rate as percentage."""
        total = self.successful_extractions + self.failed_extractions
        if total == 0:
            return 100.0
        return (self.successful_extractions / total) * 100.0
    
    @property
    def category_match_rate(self) -> float:
        """Get category match rate as percentage."""
        total = self.categories_matched + self.categories_created
        if total == 0:
            return 100.0
        return (self.categories_matched / total) * 100.0
    
    def start_phase(self, phase_name: str, **context: Any) -> PhaseMetrics:
        """Start a new processing phase."""
        phase = PhaseMetrics(phase_name=phase_name, context=context)
        self.phases.append(phase)
        return phase
    
    def complete(
        self,
        status: str,
        successful: int = 0,
        failed: int = 0,
        duplicates: int = 0,
        error: str | None = None,
    ) -> None:
        """Mark ETL run as complete."""
        self.end_time = time.time()
        self.final_status = status
        self.successful_extractions = successful
        self.failed_extractions = failed
        self.duplicates_removed = duplicates
        self.error_message = error
    
    def to_log_dict(self) -> dict[str, Any]:
        """Convert to structured log dictionary for final summary."""
        return {
            "job_id": self.job_id,
            "supplier_id": self.supplier_id,
            "file_path": self.file_path,
            "status": self.final_status,
            "duration_seconds": round(self.duration_seconds, 3),
            "total_rows": self.total_rows,
            "successful_extractions": self.successful_extractions,
            "failed_extractions": self.failed_extractions,
            "duplicates_removed": self.duplicates_removed,
            "extraction_success_rate": round(self.extraction_success_rate, 1),
            "category_match_rate": round(self.category_match_rate, 1),
            "phase_count": len(self.phases),
            "phases": [p.to_log_dict() for p in self.phases],
            "error": self.error_message,
        }


class SmartParserError(Exception):
    """Exception raised during smart parsing."""
    
    pass


class SmartParserService:
    """
    Orchestrates semantic ETL pipeline for supplier file processing.
    
    Features:
    - Smart sheet selection via SheetSelector (US2: priority sheets, skip metadata)
    - Multi-sheet file processing with cross-sheet deduplication
    - Sliding window LLM extraction
    - Category normalization with fuzzy matching
    - Within-file deduplication
    - Progress tracking via Redis
    - Partial success handling (80% threshold)
    
    Example:
        async with async_session() as session:
            service = SmartParserService(session)
            result = await service.parse_file(
                file_path="/shared/uploads/supplier_123.xlsx",
                supplier_id=123,
                job_id="job_abc123",
            )
    """
    
    # Success rate threshold for "completed_with_errors"
    SUCCESS_THRESHOLD = 0.80
    
    def __init__(
        self,
        session: AsyncSession,
        job_service: Optional[JobService] = None,
        chunk_size: int = 250,
        chunk_overlap: int = 40,
        similarity_threshold: float = 85.0,
        price_tolerance: float = 0.01,
        use_llm_for_sheet_selection: bool = False,
    ):
        """
        Initialize SmartParserService.
        
        Args:
            session: SQLAlchemy async session for DB operations
            job_service: Optional JobService for progress tracking
            chunk_size: Rows per LLM extraction chunk
            chunk_overlap: Overlapping rows between chunks
            similarity_threshold: Fuzzy match threshold for categories
            price_tolerance: Price tolerance for deduplication
            use_llm_for_sheet_selection: Whether to use LLM for ambiguous sheet selection
        """
        self.session = session
        self.job_service = job_service
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.price_tolerance = price_tolerance
        
        # Initialize sub-services
        self.markdown_converter = MarkdownConverter()
        self.langchain_extractor = LangChainExtractor(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self.category_normalizer = CategoryNormalizer(
            session=session,
            similarity_threshold=similarity_threshold,
        )
        self.deduplication_service = DeduplicationService(
            price_tolerance=price_tolerance,
        )
        
        # Initialize sheet selector (T053-T056)
        self.sheet_selector = SheetSelector(
            llm=None,  # LLM can be set later if needed
            use_llm_for_ambiguous=use_llm_for_sheet_selection,
        )
        
        # Initialize parsing logs repository (T039)
        self.parsing_logs_repo = ParsingLogsRepository(session)
        
        self.settings = Settings()
    
    async def parse_file(
        self,
        file_path: str,
        supplier_id: int,
        job_id: str,
    ) -> ExtractionResult:
        """
        Parse a supplier file end-to-end.
        
        Phases:
        1. analyzing - Sheet selection and structure analysis
        2. extracting - LLM product extraction
        3. normalizing - Category matching and deduplication
        4. complete/completed_with_errors/failed - Final status
        
        Args:
            file_path: Absolute path to Excel/CSV file
            supplier_id: Supplier ID for category tracking
            job_id: Job ID for progress updates
        
        Returns:
            ExtractionResult with products and metrics
        
        Raises:
            SmartParserError: If parsing fails critically
        """
        path = Path(file_path)
        
        # T80: Initialize ETL metrics for structured logging
        etl_metrics = ETLMetrics(
            job_id=job_id,
            supplier_id=supplier_id,
            file_path=str(path),
        )
        
        if not path.exists():
            etl_metrics.complete(status="failed", error=f"File not found: {file_path}")
            logger.error(
                "semantic_etl.file_not_found",
                **etl_metrics.to_log_dict(),
            )
            raise SmartParserError(f"File not found: {file_path}")
        
        # T80: Log ETL start with structured context
        logger.info(
            "semantic_etl.started",
            job_id=job_id,
            supplier_id=supplier_id,
            file_name=path.name,
            file_size_bytes=path.stat().st_size,
        )
        
        # Update job phase: analyzing
        await self._update_job_phase(job_id, "analyzing", 0)
        
        try:
            # Phase 1: Sheet selection (T053-T056)
            phase_analyzing = etl_metrics.start_phase("analyzing")
            sheets, selection_result = await self._select_sheets(path)
            
            if not sheets:
                error_msg = (
                    f"No product sheets found in file. "
                    f"Skipped: {selection_result.skipped_sheets}"
                )
                phase_analyzing.complete(items_processed=0, items_failed=1)
                phase_analyzing.context["skipped_sheets"] = selection_result.skipped_sheets
                etl_metrics.complete(status="failed", error=error_msg)
                
                logger.error(
                    "semantic_etl.no_sheets_found",
                    skipped_sheets=selection_result.skipped_sheets,
                    **etl_metrics.to_log_dict(),
                )
                raise SmartParserError(error_msg)
            
            phase_analyzing.complete(items_processed=len(sheets), items_failed=0)
            phase_analyzing.context.update({
                "selected_sheets": sheets,
                "skipped_sheets": selection_result.skipped_sheets,
            })
            
            # T80: Log sheet selection with structured data
            logger.info(
                "semantic_etl.sheets_selected",
                job_id=job_id,
                selected_count=len(sheets),
                selected_sheets=sheets,
                skipped_sheets=selection_result.skipped_sheets,
                **phase_analyzing.to_log_dict(),
            )
            
            # Update progress
            await self._update_job_phase(job_id, "extracting", 10)
            
            # Phase 2: Extract products from each sheet
            phase_extracting = etl_metrics.start_phase("extracting", sheets_to_process=sheets)
            all_results: list[ExtractionResult] = []
            total_extracted = 0
            total_errors = 0
            
            for i, sheet_name in enumerate(sheets):
                progress = 10 + int((i / len(sheets)) * 60)  # 10-70%
                await self._update_job_phase(job_id, "extracting", progress)
                
                sheet_start_time = time.time()
                result = await self._process_sheet(
                    file_path=path,
                    sheet_name=sheet_name,
                    supplier_id=supplier_id,
                )
                all_results.append(result)
                
                total_extracted += result.successful_extractions
                total_errors += result.failed_extractions
                
                # T80: Log per-sheet extraction metrics
                logger.info(
                    "semantic_etl.sheet_extracted",
                    job_id=job_id,
                    sheet_name=sheet_name,
                    products_extracted=result.successful_extractions,
                    extraction_errors=result.failed_extractions,
                    duration_seconds=round(time.time() - sheet_start_time, 3),
                    sheet_index=i + 1,
                    total_sheets=len(sheets),
                )
            
            phase_extracting.complete(items_processed=total_extracted, items_failed=total_errors)
            
            # Aggregate results (T059-T060)
            # Cross-sheet dedup is performed here for multi-sheet files
            is_multi_sheet = len(all_results) > 1
            aggregated = self._aggregate_results(
                all_results,
                apply_cross_sheet_dedup=is_multi_sheet,
            )
            etl_metrics.total_rows = aggregated.total_rows
            
            # T039: Log extraction errors to parsing_logs
            if aggregated.extraction_errors:
                await self._log_extraction_errors_batch(
                    supplier_id=supplier_id,
                    job_id=job_id,
                    errors=aggregated.extraction_errors,
                )
            
            # Update progress
            await self._update_job_phase(job_id, "normalizing", 70)
            
            # Phase 3: Category normalization
            phase_normalizing = etl_metrics.start_phase("normalizing")
            await self._normalize_categories(aggregated.products, supplier_id)
            
            # Get category stats
            cat_stats = self.category_normalizer.get_stats()
            etl_metrics.categories_matched = cat_stats.matched_count
            etl_metrics.categories_created = cat_stats.created_count
            phase_normalizing.context.update({
                "categories_matched": cat_stats.matched_count,
                "categories_created": cat_stats.created_count,
                "average_similarity": round(cat_stats.average_similarity, 1),
            })
            
            # Phase 4: Within-file deduplication (skip for multi-sheet as already done)
            await self._update_job_phase(job_id, "normalizing", 85)
            
            if not is_multi_sheet:
                # Single sheet: dedup now
                unique_products, dedup_stats = self.deduplication_service.deduplicate(
                    aggregated.products
                )
                
                # Update result with dedup count
                aggregated.products = unique_products
                aggregated.duplicates_removed = dedup_stats.duplicates_removed
            
            phase_normalizing.complete(
                items_processed=len(aggregated.products),
                items_failed=aggregated.duplicates_removed,
            )
            
            # Update successful extractions after dedup
            aggregated.successful_extractions = len(aggregated.products)
            
            # Determine final status
            final_status = aggregated.status
            
            # T80: Complete metrics and log structured summary
            etl_metrics.complete(
                status=final_status,
                successful=aggregated.successful_extractions,
                failed=aggregated.failed_extractions,
                duplicates=aggregated.duplicates_removed,
            )
            
            await self._update_job_phase(
                job_id,
                final_status,
                100,
                total_rows=aggregated.total_rows,
                successful_extractions=aggregated.successful_extractions,
                failed_extractions=aggregated.failed_extractions,
                duplicates_removed=aggregated.duplicates_removed,
            )
            
            # T80: Log comprehensive ETL completion summary
            logger.info(
                "semantic_etl.completed",
                **etl_metrics.to_log_dict(),
            )
            
            return aggregated
            
        except SmartParserError:
            # Already logged, re-raise
            raise
        except Exception as e:
            # T80: Log failure with full context
            etl_metrics.complete(
                status="failed",
                error=str(e),
            )
            
            logger.error(
                "semantic_etl.failed",
                exception_type=type(e).__name__,
                exception_message=str(e),
                **etl_metrics.to_log_dict(),
                exc_info=True,
            )
            
            # T039: Log critical error to parsing_logs
            await self._log_extraction_error(
                supplier_id=supplier_id,
                job_id=job_id,
                error_type="parsing",
                message=str(e),
                extraction_phase="orchestration",
                context={"exception_type": type(e).__name__},
            )
            
            await self._update_job_phase(
                job_id, "failed", 0, error_message=str(e)
            )
            raise SmartParserError(f"Parsing failed: {e}") from e
    
    async def _select_sheets(self, file_path: Path) -> tuple[list[str], SheetSelectionResult]:
        """
        Select which sheets to process from an Excel file using SheetSelector.
        
        US2: Multi-sheet file support with intelligent sheet selection.
        
        Priority:
        1. If a priority sheet exists, process only that
        2. Otherwise, process all non-metadata sheets
        3. Optionally use LLM for ambiguous cases
        
        Args:
            file_path: Path to Excel file
        
        Returns:
            Tuple of (sheet_names_to_process, selection_result)
        """
        sheets_info = self.markdown_converter.get_sheet_info(file_path)
        
        if not sheets_info:
            return [], SheetSelectionResult(reasoning="No sheets found in file")
        
        # Use SheetSelector for intelligent selection (T053-T056)
        selection_result = await self.sheet_selector.select_sheets(sheets_info)
        
        # Log selection summary
        summary = self.sheet_selector.get_selection_summary(selection_result)
        logger.info(f"Sheet selection:\n{summary}")
        
        return selection_result.selected_sheets, selection_result
    
    async def _process_sheet(
        self,
        file_path: Path,
        sheet_name: str,
        supplier_id: int,
    ) -> ExtractionResult:
        """
        Process a single sheet: convert to markdown and extract products.
        
        Args:
            file_path: Path to Excel file
            sheet_name: Sheet name to process
            supplier_id: Supplier ID
        
        Returns:
            ExtractionResult for this sheet
        """
        # Get sheet info for total rows
        sheets_info = self.markdown_converter.get_sheet_info(file_path)
        sheet_info = next(
            (s for s in sheets_info if s["name"] == sheet_name),
            {"row_count": 0}
        )
        total_rows = max(0, sheet_info.get("row_count", 0) - 1)  # Exclude header
        
        if total_rows <= self.chunk_size:
            # Small sheet - process directly
            markdown = self.markdown_converter.convert_excel_to_markdown(
                file_path, sheet_name
            )
            return await self.langchain_extractor.extract_from_markdown(
                markdown_table=markdown,
                sheet_name=sheet_name,
                total_rows=total_rows,
            )
        
        # Large sheet - use chunks
        chunks = self.markdown_converter.convert_excel_to_markdown_chunks(
            file_path=file_path,
            sheet_name=sheet_name,
            chunk_size=self.chunk_size,
            overlap=self.chunk_overlap,
        )
        
        return await self.langchain_extractor.extract_from_chunks(
            chunks=chunks,
            sheet_name=sheet_name,
        )
    
    async def _normalize_categories(
        self,
        products: list,
        supplier_id: int,
    ) -> None:
        """
        Normalize categories for all products.
        
        Updates product category references in-place.
        Creates new categories with needs_review=True when no match.
        
        Args:
            products: List of ExtractedProduct objects
            supplier_id: Supplier ID for tracking new categories
        """
        # Load category cache
        await self.category_normalizer.load_category_cache()
        
        for product in products:
            if not product.category_path:
                continue
            
            try:
                result = await self.category_normalizer.process_category_path(
                    category_path=product.category_path,
                    supplier_id=supplier_id,
                )
                
                # Store category ID in raw_data for later use
                if result.leaf_category_id:
                    product.raw_data["category_id"] = result.leaf_category_id
                    product.raw_data["category_match_results"] = [
                        {
                            "name": r.extracted_name,
                            "action": r.action,
                            "similarity": r.similarity_score,
                        }
                        for r in result.match_results
                    ]
                    
            except Exception as e:
                logger.warning(
                    f"Category normalization failed for '{product.name}': {e}"
                )
        
        # Commit category changes
        await self.session.commit()
        
        # Log stats
        stats = self.category_normalizer.get_stats()
        logger.info(
            f"Category normalization: "
            f"matched={stats.matched_count}, "
            f"created={stats.created_count}, "
            f"avg_similarity={stats.average_similarity:.1f}%"
        )
    
    def _aggregate_results(
        self,
        results: list[ExtractionResult],
        apply_cross_sheet_dedup: bool = True,
    ) -> ExtractionResult:
        """
        Aggregate results from multiple sheets with cross-sheet deduplication.
        
        US2 (T059-T060): Multi-sheet file processing.
        
        Args:
            results: List of ExtractionResult objects
            apply_cross_sheet_dedup: Whether to deduplicate across sheets
        
        Returns:
            Combined ExtractionResult with cross-sheet duplicates removed
        """
        if not results:
            return ExtractionResult(
                products=[],
                sheet_name="(no sheets)",
                total_rows=0,
                successful_extractions=0,
                failed_extractions=0,
            )
        
        if len(results) == 1:
            return results[0]
        
        # Combine all products and metrics
        all_products = []
        all_errors = []
        total_rows = 0
        successful = 0
        failed = 0
        
        sheet_names = []
        per_sheet_counts = []
        
        for result in results:
            all_products.extend(result.products)
            all_errors.extend(result.extraction_errors)
            total_rows += result.total_rows
            successful += result.successful_extractions
            failed += result.failed_extractions
            sheet_names.append(result.sheet_name)
            per_sheet_counts.append(len(result.products))
        
        logger.info(
            f"Aggregating {len(results)} sheets: "
            f"{dict(zip(sheet_names, per_sheet_counts, strict=False))}"
        )
        
        # T060: Cross-sheet deduplication
        cross_sheet_dupes_removed = 0
        if apply_cross_sheet_dedup and len(all_products) > 0:
            original_count = len(all_products)
            all_products, dedup_stats = self.deduplication_service.deduplicate(all_products)
            cross_sheet_dupes_removed = dedup_stats.duplicates_removed
            
            logger.info(
                f"Cross-sheet deduplication: {original_count} → {len(all_products)} "
                f"({cross_sheet_dupes_removed} duplicates across {len(results)} sheets)"
            )
        
        return ExtractionResult(
            products=all_products,
            sheet_name=", ".join(sheet_names),
            total_rows=total_rows,
            successful_extractions=successful,  # Before cross-sheet dedup
            failed_extractions=failed,
            duplicates_removed=cross_sheet_dupes_removed,  # Updated with cross-sheet count
            extraction_errors=all_errors,
        )
    
    async def _update_job_phase(
        self,
        job_id: str,
        phase: str,
        progress: int,
        total_rows: Optional[int] = None,
        successful_extractions: Optional[int] = None,
        failed_extractions: Optional[int] = None,
        duplicates_removed: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update job status in Redis.
        
        Args:
            job_id: Job identifier
            phase: Current phase name
            progress: Progress percentage (0-100)
            total_rows: Total rows processed
            successful_extractions: Successful product count
            failed_extractions: Failed extraction count
            duplicates_removed: Duplicate count removed
            error_message: Error message if failed
        """
        if not self.job_service:
            logger.debug(f"Job {job_id}: phase={phase}, progress={progress}%")
            return
        
        try:
            await self.job_service.update_job_status(
                job_id=job_id,
                phase=phase,
                progress_percent=progress,
                total_rows=total_rows,
                successful_extractions=successful_extractions,
                failed_extractions=failed_extractions,
                duplicates_removed=duplicates_removed,
                error_message=error_message,
            )
        except Exception as e:
            logger.warning(f"Failed to update job status: {e}")

    async def _log_extraction_error(
        self,
        supplier_id: int,
        job_id: str,
        error_type: str,
        message: str,
        extraction_phase: str,
        chunk_id: Optional[int] = None,
        row_number: Optional[int] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Log extraction error to parsing_logs table.
        
        Task T039: Error logging for semantic ETL pipeline.
        
        Args:
            supplier_id: Supplier ID
            job_id: Job identifier
            error_type: Type of error (validation, parsing, llm_error, timeout)
            message: Human-readable error message
            extraction_phase: Phase where error occurred (sheet_selection, markdown_conversion, llm_extraction, category_matching)
            chunk_id: Optional chunk identifier for sliding window
            row_number: Optional row number in source file
            context: Additional context data (raw row data, etc.)
        """
        try:
            # Prepare context with semantic ETL metadata
            error_context = context or {}
            error_context.update({
                "extraction_phase": extraction_phase,
                "job_id": job_id,
            })
            if chunk_id is not None:
                error_context["chunk_id"] = chunk_id
            if row_number is not None:
                error_context["row_number"] = row_number
            
            # Convert supplier_id to UUID format for repo
            supplier_uuid = UUID(int=supplier_id) if isinstance(supplier_id, int) and supplier_id < 2**128 else None
            if supplier_uuid is None:
                # Use job_id as fallback reference
                logger.warning(f"Cannot convert supplier_id {supplier_id} to UUID, using job reference")
                error_context["supplier_id_int"] = supplier_id
                # Create a deterministic UUID from supplier_id
                import hashlib
                hash_bytes = hashlib.md5(str(supplier_id).encode()).digest()
                supplier_uuid = UUID(bytes=hash_bytes)
            
            await self.parsing_logs_repo.log_error(
                supplier_id=supplier_uuid,
                error_type=error_type,  # type: ignore[arg-type]
                message=f"[{extraction_phase}] {message}",
                severity="error",
                job_id=UUID(job_id) if job_id and len(job_id) >= 32 else None,
                context=error_context,
            )
            
            logger.debug(
                f"Error logged to parsing_logs: {error_type} in {extraction_phase}",
                extra={"job_id": job_id, "supplier_id": supplier_id}
            )
            
        except Exception as e:
            # Don't let logging errors break the pipeline
            logger.warning(f"Failed to log extraction error to parsing_logs: {e}")

    async def _log_extraction_errors_batch(
        self,
        supplier_id: int,
        job_id: str,
        errors: list[dict[str, Any]],
    ) -> None:
        """
        Log multiple extraction errors in batch.
        
        Args:
            supplier_id: Supplier ID
            job_id: Job identifier
            errors: List of error dicts from ExtractionResult.extraction_errors
        """
        if not errors:
            return
        
        try:
            # Convert to parsing_logs format
            formatted_errors = []
            for err in errors:
                formatted_errors.append({
                    "error_type": err.get("error_type", "parsing"),
                    "message": err.get("message", "Unknown error"),
                    "severity": "error",
                    "context": {
                        "extraction_phase": err.get("phase", "llm_extraction"),
                        "job_id": job_id,
                        "chunk_id": err.get("chunk_id"),
                        "row_number": err.get("row_number"),
                        "raw_data": err.get("raw_data"),
                    },
                })
            
            # Create supplier UUID
            import hashlib
            hash_bytes = hashlib.md5(str(supplier_id).encode()).digest()
            supplier_uuid = UUID(bytes=hash_bytes)
            
            job_uuid = UUID(job_id) if job_id and len(job_id) >= 32 else None
            
            await self.parsing_logs_repo.log_batch(
                supplier_id=supplier_uuid,
                errors=formatted_errors,
                job_id=job_uuid,
            )
            
            logger.info(
                f"Logged {len(errors)} extraction errors to parsing_logs",
                extra={"job_id": job_id, "supplier_id": supplier_id}
            )
            
        except Exception as e:
            logger.warning(f"Failed to batch log extraction errors: {e}")

