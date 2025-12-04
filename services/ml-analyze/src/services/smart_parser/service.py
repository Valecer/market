"""
Smart Parser Service - Orchestration Layer
==========================================

Orchestrates the semantic ETL pipeline:
1. Read Excel/CSV file
2. Select sheets (priority: "Upload to site", etc.)
3. Convert to Markdown
4. Extract products via LLM
5. Normalize categories
6. Deduplicate products
7. Insert to database
8. Log errors to parsing_logs

Phase 9: Semantic ETL Pipeline Refactoring
"""

import logging
import time
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

logger = logging.getLogger(__name__)


class SmartParserError(Exception):
    """Exception raised during smart parsing."""
    
    pass


class SmartParserService:
    """
    Orchestrates semantic ETL pipeline for supplier file processing.
    
    Features:
    - Smart sheet selection (priority sheets, skip metadata)
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
    
    # Priority sheet names (case-insensitive)
    PRIORITY_SHEET_NAMES = [
        "upload to site",
        "загрузка на сайт",
        "products",
        "товары",
        "catalog",
        "каталог",
        "export",
        "экспорт",
    ]
    
    # Sheets to skip (metadata/configuration)
    SKIP_SHEET_NAMES = [
        "instructions",
        "инструкции",
        "settings",
        "настройки",
        "config",
        "конфигурация",
        "template",
        "шаблон",
        "example",
        "пример",
    ]
    
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
        """
        self.session = session
        self.job_service = job_service
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
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
        start_time = time.time()
        path = Path(file_path)
        
        if not path.exists():
            raise SmartParserError(f"File not found: {file_path}")
        
        logger.info(
            f"Starting smart parse: file={path.name}, "
            f"supplier_id={supplier_id}, job_id={job_id}"
        )
        
        # Update job phase: analyzing
        await self._update_job_phase(job_id, "analyzing", 0)
        
        try:
            # Phase 1: Sheet selection
            sheets = await self._select_sheets(path)
            
            if not sheets:
                raise SmartParserError("No product sheets found in file")
            
            logger.info(f"Selected {len(sheets)} sheet(s) for processing")
            
            # Update progress
            await self._update_job_phase(job_id, "extracting", 10)
            
            # Phase 2: Extract products from each sheet
            all_results: list[ExtractionResult] = []
            
            for i, sheet_name in enumerate(sheets):
                progress = 10 + int((i / len(sheets)) * 60)  # 10-70%
                await self._update_job_phase(job_id, "extracting", progress)
                
                result = await self._process_sheet(
                    file_path=path,
                    sheet_name=sheet_name,
                    supplier_id=supplier_id,
                )
                all_results.append(result)
                
                logger.info(
                    f"Sheet '{sheet_name}': {result.successful_extractions} products, "
                    f"{result.failed_extractions} errors"
                )
            
            # Aggregate results
            aggregated = self._aggregate_results(all_results)
            
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
            await self._normalize_categories(aggregated.products, supplier_id)
            
            # Phase 4: Within-file deduplication
            await self._update_job_phase(job_id, "normalizing", 85)
            
            unique_products, dedup_stats = self.deduplication_service.deduplicate(
                aggregated.products
            )
            
            # Update result with dedup count
            aggregated.products = unique_products
            aggregated.duplicates_removed = dedup_stats.duplicates_removed
            aggregated.successful_extractions = len(unique_products)
            
            # Determine final status
            elapsed = time.time() - start_time
            final_status = aggregated.status
            
            await self._update_job_phase(
                job_id,
                final_status,
                100,
                total_rows=aggregated.total_rows,
                successful_extractions=aggregated.successful_extractions,
                failed_extractions=aggregated.failed_extractions,
                duplicates_removed=aggregated.duplicates_removed,
            )
            
            logger.info(
                f"Smart parse completed in {elapsed:.2f}s: "
                f"status={final_status}, "
                f"products={aggregated.successful_extractions}, "
                f"errors={aggregated.failed_extractions}, "
                f"dedup={aggregated.duplicates_removed}"
            )
            
            return aggregated
            
        except Exception as e:
            logger.error(f"Smart parse failed: {e}", exc_info=True)
            
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
    
    async def _select_sheets(self, file_path: Path) -> list[str]:
        """
        Select which sheets to process from an Excel file.
        
        Priority:
        1. If a priority sheet exists, process only that
        2. Otherwise, process all non-metadata sheets
        
        Args:
            file_path: Path to Excel file
        
        Returns:
            List of sheet names to process
        """
        sheets_info = self.markdown_converter.get_sheet_info(file_path)
        
        if not sheets_info:
            return []
        
        # Check for priority sheets first
        for sheet in sheets_info:
            normalized_name = sheet["name"].lower().strip()
            if normalized_name in self.PRIORITY_SHEET_NAMES:
                logger.info(f"Found priority sheet: '{sheet['name']}'")
                return [sheet["name"]]
        
        # Filter out metadata sheets and empty sheets
        selected = []
        for sheet in sheets_info:
            normalized_name = sheet["name"].lower().strip()
            
            if normalized_name in self.SKIP_SHEET_NAMES:
                logger.debug(f"Skipping metadata sheet: '{sheet['name']}'")
                continue
            
            if sheet.get("is_empty"):
                logger.debug(f"Skipping empty sheet: '{sheet['name']}'")
                continue
            
            if sheet.get("row_count", 0) < 2:  # Need at least header + 1 data row
                logger.debug(f"Skipping sheet with insufficient data: '{sheet['name']}'")
                continue
            
            selected.append(sheet["name"])
        
        return selected
    
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
    ) -> ExtractionResult:
        """
        Aggregate results from multiple sheets.
        
        Args:
            results: List of ExtractionResult objects
        
        Returns:
            Combined ExtractionResult
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
        
        for result in results:
            all_products.extend(result.products)
            all_errors.extend(result.extraction_errors)
            total_rows += result.total_rows
            successful += result.successful_extractions
            failed += result.failed_extractions
            sheet_names.append(result.sheet_name)
        
        return ExtractionResult(
            products=all_products,
            sheet_name=", ".join(sheet_names),
            total_rows=total_rows,
            successful_extractions=successful,
            failed_extractions=failed,
            duplicates_removed=0,  # Will be updated after dedup
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

