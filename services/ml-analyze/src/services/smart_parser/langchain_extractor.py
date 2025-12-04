"""
LangChain Extractor for Semantic ETL Pipeline
=============================================

LLM-based product extraction using LangChain and Ollama.
Implements sliding window processing for large files.

Phase 9: Semantic ETL Pipeline Refactoring
- T82: Debug mode for logging prompts and responses
- T86: Performance profiling and optimization for chunks >5s
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from langchain_ollama import ChatOllama
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import Settings
from src.schemas.extraction import (
    ChunkExtractionResult,
    ExtractedProduct,
    ExtractionError,
    ExtractionResult,
)
from src.services.smart_parser.prompts import get_extraction_prompt
from src.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# T86: Performance Profiling Infrastructure
# =============================================================================

# Performance thresholds (in seconds)
CHUNK_PROCESSING_WARN_THRESHOLD = 5.0  # Warn if chunk takes >5s
CHUNK_PROCESSING_CRITICAL_THRESHOLD = 15.0  # Critical if chunk takes >15s


@dataclass
class ChunkPerformanceMetrics:
    """T86: Tracks performance metrics for chunk extraction."""
    
    chunk_id: int
    llm_request_time: float = 0.0
    parse_time: float = 0.0
    validation_time: float = 0.0
    total_time: float = 0.0
    input_chars: int = 0
    output_chars: int = 0
    products_extracted: int = 0
    retry_count: int = 0
    
    @property
    def chars_per_second(self) -> float:
        """Calculate throughput as characters per second."""
        if self.total_time > 0:
            return self.input_chars / self.total_time
        return 0.0
    
    @property
    def products_per_second(self) -> float:
        """Calculate extraction rate."""
        if self.total_time > 0:
            return self.products_extracted / self.total_time
        return 0.0
    
    def is_slow(self) -> bool:
        """Check if this chunk exceeded warn threshold."""
        return self.total_time > CHUNK_PROCESSING_WARN_THRESHOLD
    
    def is_critical(self) -> bool:
        """Check if this chunk exceeded critical threshold."""
        return self.total_time > CHUNK_PROCESSING_CRITICAL_THRESHOLD


@dataclass
class ExtractionPerformanceStats:
    """T86: Aggregated performance statistics for extraction session."""
    
    total_chunks: int = 0
    total_time: float = 0.0
    total_llm_time: float = 0.0
    slow_chunks: int = 0
    critical_chunks: int = 0
    total_retries: int = 0
    avg_chunk_time: float = 0.0
    max_chunk_time: float = 0.0
    min_chunk_time: float = float('inf')
    chunk_metrics: list[ChunkPerformanceMetrics] = field(default_factory=list)
    
    def add_chunk_metrics(self, metrics: ChunkPerformanceMetrics) -> None:
        """Add chunk metrics and update aggregates."""
        self.chunk_metrics.append(metrics)
        self.total_chunks += 1
        self.total_time += metrics.total_time
        self.total_llm_time += metrics.llm_request_time
        self.total_retries += metrics.retry_count
        
        if metrics.is_slow():
            self.slow_chunks += 1
        if metrics.is_critical():
            self.critical_chunks += 1
        
        self.max_chunk_time = max(self.max_chunk_time, metrics.total_time)
        self.min_chunk_time = min(self.min_chunk_time, metrics.total_time)
        
        if self.total_chunks > 0:
            self.avg_chunk_time = self.total_time / self.total_chunks
    
    def get_summary(self) -> dict:
        """Get performance summary for logging."""
        return {
            "total_chunks": self.total_chunks,
            "total_time_seconds": round(self.total_time, 2),
            "total_llm_time_seconds": round(self.total_llm_time, 2),
            "avg_chunk_time_seconds": round(self.avg_chunk_time, 2),
            "max_chunk_time_seconds": round(self.max_chunk_time, 2),
            "min_chunk_time_seconds": round(self.min_chunk_time, 2) if self.min_chunk_time != float('inf') else 0,
            "slow_chunks_count": self.slow_chunks,
            "critical_chunks_count": self.critical_chunks,
            "total_retries": self.total_retries,
            "llm_time_percentage": round((self.total_llm_time / self.total_time * 100) if self.total_time > 0 else 0, 1),
        }

# T82: Debug mode environment variable
DEBUG_SEMANTIC_ETL = os.environ.get("DEBUG_SEMANTIC_ETL", "false").lower() in (
    "true", "1", "yes", "on"
)


class LLMExtractionError(Exception):
    """Exception raised when LLM extraction fails."""
    
    pass


class LangChainExtractor:
    """
    LLM-based product extraction using LangChain + Ollama.
    
    Features:
    - Sliding window processing for large files
    - Structured output with Pydantic validation
    - Retry logic with exponential backoff
    - Chunk-level error tracking
    - T86: Performance profiling and optimization
    
    Example:
        extractor = LangChainExtractor()
        result = await extractor.extract_from_markdown(
            markdown_table,
            sheet_name="Products",
            total_rows=300,
        )
        
        # Access performance stats
        print(extractor.get_performance_summary())
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        chunk_size: int = 250,
        chunk_overlap: int = 40,
        request_timeout: int = 120,
        debug_mode: Optional[bool] = None,
        enable_profiling: bool = True,
    ):
        """
        Initialize LangChainExtractor.
        
        Args:
            model_name: Ollama model name (default from settings)
            base_url: Ollama base URL (default from settings)
            temperature: LLM temperature (0.0-1.0, lower = more deterministic)
            chunk_size: Number of rows per chunk
            chunk_overlap: Overlapping rows between chunks (16% default)
            request_timeout: Timeout for LLM requests in seconds
            debug_mode: Enable debug logging (default from DEBUG_SEMANTIC_ETL env)
            enable_profiling: T86: Enable performance profiling (default True)
        """
        settings = Settings()
        
        self.model_name = model_name or settings.ollama_llm_model
        self.base_url = base_url or settings.ollama_base_url
        self.temperature = temperature
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.request_timeout = request_timeout
        
        # T82: Debug mode for logging prompts and responses
        self.debug_mode = debug_mode if debug_mode is not None else DEBUG_SEMANTIC_ETL
        
        # T86: Performance profiling
        self.enable_profiling = enable_profiling
        self._performance_stats = ExtractionPerformanceStats()
        self._retry_count = 0  # Track retries for current chunk
        
        # Initialize ChatOllama
        self.llm = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=self.temperature,
            request_timeout=self.request_timeout,
            format="json",  # Request JSON output
        )
        
        logger.info(
            "llm_extractor.initialized",
            model=self.model_name,
            base_url=self.base_url,
            temperature=self.temperature,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            debug_mode=self.debug_mode,
            profiling_enabled=self.enable_profiling,
        )
    
    def get_performance_summary(self) -> dict:
        """
        T86: Get performance summary for the extraction session.
        
        Returns:
            Dictionary with performance statistics
        """
        return self._performance_stats.get_summary()
    
    def reset_performance_stats(self) -> None:
        """T86: Reset performance statistics for a new extraction session."""
        self._performance_stats = ExtractionPerformanceStats()
    
    async def extract_from_markdown(
        self,
        markdown_table: str,
        sheet_name: str,
        total_rows: int,
        complex_layout: bool = False,
    ) -> ExtractionResult:
        """
        Extract products from a markdown table.
        
        This is the main entry point for single-table extraction.
        For large files, use extract_from_chunks() with pre-chunked data.
        
        Args:
            markdown_table: Markdown-formatted table content
            sheet_name: Name of the source sheet
            total_rows: Total data rows (excluding header)
            complex_layout: Whether to use complex layout handling
        
        Returns:
            ExtractionResult with products and metrics
        """
        logger.info(
            f"Starting extraction from sheet '{sheet_name}' "
            f"with {total_rows} rows"
        )
        
        start_time = time.time()
        
        # For small tables, process directly
        if total_rows <= self.chunk_size:
            chunk_result = await self._extract_chunk(
                markdown_table=markdown_table,
                chunk_id=0,
                start_row=1,
                end_row=total_rows,
                complex_layout=complex_layout,
            )
            
            return ExtractionResult(
                products=chunk_result.products,
                sheet_name=sheet_name,
                total_rows=total_rows,
                successful_extractions=len(chunk_result.products),
                failed_extractions=len(chunk_result.errors),
                duplicates_removed=0,  # Dedup handled separately
                extraction_errors=chunk_result.errors,
            )
        
        # For large tables, this should be called with pre-chunked data
        # from MarkdownConverter.convert_excel_to_markdown_chunks()
        logger.warning(
            f"Large table ({total_rows} rows) passed without chunking. "
            f"Consider using extract_from_chunks() for better results."
        )
        
        chunk_result = await self._extract_chunk(
            markdown_table=markdown_table,
            chunk_id=0,
            start_row=1,
            end_row=total_rows,
            complex_layout=complex_layout,
        )
        
        elapsed = time.time() - start_time
        logger.info(
            f"Extraction completed in {elapsed:.2f}s: "
            f"{len(chunk_result.products)} products extracted"
        )
        
        return ExtractionResult(
            products=chunk_result.products,
            sheet_name=sheet_name,
            total_rows=total_rows,
            successful_extractions=len(chunk_result.products),
            failed_extractions=len(chunk_result.errors),
            duplicates_removed=0,
            extraction_errors=chunk_result.errors,
        )
    
    async def extract_from_chunks(
        self,
        chunks: list[dict],
        sheet_name: str,
        complex_layout: bool = False,
    ) -> ExtractionResult:
        """
        Extract products from pre-chunked markdown data.
        
        This is the recommended method for large files.
        Handles chunk overlap deduplication.
        T86: Includes performance profiling and optimization recommendations.
        
        Args:
            chunks: List of chunk dicts from MarkdownConverter
            sheet_name: Name of the source sheet
            complex_layout: Whether to use complex layout handling
        
        Returns:
            Aggregated ExtractionResult
        """
        if not chunks:
            return ExtractionResult(
                products=[],
                sheet_name=sheet_name,
                total_rows=0,
                successful_extractions=0,
                failed_extractions=0,
            )
        
        # T86: Reset stats for new extraction session
        self.reset_performance_stats()
        
        logger.info(
            f"Starting chunked extraction from sheet '{sheet_name}' "
            f"with {len(chunks)} chunks"
        )
        
        start_time = time.time()
        all_products: list[ExtractedProduct] = []
        all_errors: list[ExtractionError] = []
        total_rows = sum(c.get("total_rows", 0) for c in chunks)
        
        # Process each chunk
        for chunk in chunks:
            chunk_result = await self._extract_chunk(
                markdown_table=chunk["markdown"],
                chunk_id=chunk["chunk_id"],
                start_row=chunk["start_row"],
                end_row=chunk["end_row"],
                complex_layout=complex_layout,
            )
            
            all_products.extend(chunk_result.products)
            all_errors.extend(chunk_result.errors)
            
            logger.debug(
                f"Chunk {chunk['chunk_id']}: "
                f"{len(chunk_result.products)} products, "
                f"{len(chunk_result.errors)} errors"
            )
        
        # Remove overlap duplicates (same name + similar price)
        unique_products = self._remove_overlap_duplicates(all_products)
        overlap_dupes = len(all_products) - len(unique_products)
        
        elapsed = time.time() - start_time
        
        # T86: Log performance summary
        if self.enable_profiling:
            perf_summary = self.get_performance_summary()
            logger.info(
                "llm_extractor.extraction_complete",
                sheet_name=sheet_name,
                total_time_seconds=round(elapsed, 2),
                unique_products=len(unique_products),
                overlap_duplicates_removed=overlap_dupes,
                **perf_summary,
            )
            
            # T86: Log optimization recommendations if slow chunks detected
            if perf_summary["slow_chunks_count"] > 0:
                slow_percentage = (perf_summary["slow_chunks_count"] / perf_summary["total_chunks"]) * 100
                recommendations = self._get_optimization_recommendations(perf_summary)
                
                logger.warning(
                    "llm_extractor.performance_recommendations",
                    slow_chunk_percentage=round(slow_percentage, 1),
                    recommendations=recommendations,
                )
        else:
            logger.info(
                f"Chunked extraction completed in {elapsed:.2f}s: "
                f"{len(unique_products)} unique products "
                f"({overlap_dupes} overlap duplicates removed)"
            )
        
        return ExtractionResult(
            products=unique_products,
            sheet_name=sheet_name,
            total_rows=total_rows,
            successful_extractions=len(unique_products),
            failed_extractions=len(all_errors),
            duplicates_removed=overlap_dupes,
            extraction_errors=all_errors,
        )
    
    def _get_optimization_recommendations(self, perf_summary: dict) -> list[str]:
        """
        T86: Generate optimization recommendations based on performance data.
        
        Args:
            perf_summary: Performance summary dictionary
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Check if LLM is the bottleneck
        if perf_summary.get("llm_time_percentage", 0) > 80:
            recommendations.append(
                "LLM processing dominates (>80%). Consider: "
                "(1) reducing chunk_size to process fewer rows per request, "
                "(2) using a faster LLM model, "
                "(3) increasing Ollama GPU resources"
            )
        
        # Check average chunk time
        avg_time = perf_summary.get("avg_chunk_time_seconds", 0)
        if avg_time > CHUNK_PROCESSING_WARN_THRESHOLD:
            recommendations.append(
                f"Average chunk time ({avg_time:.1f}s) exceeds threshold ({CHUNK_PROCESSING_WARN_THRESHOLD}s). "
                f"Current chunk_size={self.chunk_size}. Try reducing to {max(50, self.chunk_size // 2)}."
            )
        
        # Check retry rate
        if perf_summary.get("total_retries", 0) > perf_summary.get("total_chunks", 1):
            recommendations.append(
                "High retry rate detected. Check: "
                "(1) Ollama service stability, "
                "(2) network connectivity, "
                "(3) increase request_timeout"
            )
        
        # Check for critical chunks
        if perf_summary.get("critical_chunks_count", 0) > 0:
            recommendations.append(
                f"{perf_summary['critical_chunks_count']} chunks exceeded critical threshold "
                f"({CHUNK_PROCESSING_CRITICAL_THRESHOLD}s). "
                "Investigate: (1) LLM hardware capacity, (2) model complexity"
            )
        
        if not recommendations:
            recommendations.append("No specific optimizations recommended")
        
        return recommendations
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((LLMExtractionError, TimeoutError)),
        reraise=True,
    )
    async def _extract_chunk(
        self,
        markdown_table: str,
        chunk_id: int,
        start_row: int,
        end_row: int,
        complex_layout: bool = False,
    ) -> ChunkExtractionResult:
        """
        Extract products from a single markdown chunk.
        
        Uses retry logic with exponential backoff.
        T86: Includes performance profiling and optimization.
        
        Args:
            markdown_table: Markdown content for this chunk
            chunk_id: Chunk identifier
            start_row: Starting row number (1-indexed)
            end_row: Ending row number
            complex_layout: Whether to use complex layout prompt
        
        Returns:
            ChunkExtractionResult with products and errors
        """
        start_time = time.time()
        llm_duration = 0.0
        parse_start = 0.0
        validation_start = 0.0
        
        # T86: Track metrics for this chunk
        chunk_metrics = ChunkPerformanceMetrics(
            chunk_id=chunk_id,
            input_chars=len(markdown_table),
        )
        
        # Build prompt
        prompt = get_extraction_prompt(markdown_table, complex_layout)
        
        # T82: Debug logging for markdown chunks and prompts
        if self.debug_mode:
            logger.debug(
                "llm_extractor.chunk_input",
                chunk_id=chunk_id,
                start_row=start_row,
                end_row=end_row,
                markdown_length=len(markdown_table),
                prompt_length=len(prompt),
                complex_layout=complex_layout,
            )
            # Log first 2000 chars of markdown (truncated for large chunks)
            markdown_preview = markdown_table[:2000] + "..." if len(markdown_table) > 2000 else markdown_table
            logger.debug(
                "llm_extractor.chunk_markdown_preview",
                chunk_id=chunk_id,
                markdown_preview=markdown_preview,
            )
            logger.debug(
                "llm_extractor.prompt_sent",
                chunk_id=chunk_id,
                prompt=prompt[:3000] + "..." if len(prompt) > 3000 else prompt,
            )
        
        try:
            # Call LLM
            llm_start = time.time()
            response = await self.llm.ainvoke(prompt)
            llm_duration = time.time() - llm_start
            chunk_metrics.llm_request_time = llm_duration
            
            # Parse response
            parse_start = time.time()
            content = response.content
            chunk_metrics.output_chars = len(str(content))
            
            # T82: Debug logging for LLM response
            if self.debug_mode:
                response_preview = str(content)[:2000] + "..." if len(str(content)) > 2000 else str(content)
                logger.debug(
                    "llm_extractor.response_received",
                    chunk_id=chunk_id,
                    response_type=type(content).__name__,
                    response_length=len(str(content)),
                    response_preview=response_preview,
                    llm_duration_seconds=round(llm_duration, 3),
                )
            
            if isinstance(content, str):
                validation_start = time.time()
                chunk_metrics.parse_time = validation_start - parse_start
                
                products, errors = self._parse_llm_response(
                    content, chunk_id, start_row
                )
                chunk_metrics.validation_time = time.time() - validation_start
                chunk_metrics.products_extracted = len(products)
                
                # T82: Debug logging for parsed products
                if self.debug_mode:
                    logger.debug(
                        "llm_extractor.parse_result",
                        chunk_id=chunk_id,
                        products_extracted=len(products),
                        errors_count=len(errors),
                        product_names=[p.name[:50] for p in products[:5]],  # First 5 names
                    )
            else:
                raise LLMExtractionError(
                    f"Unexpected response type: {type(content)}"
                )
            
        except json.JSONDecodeError as e:
            logger.error(
                "llm_extractor.json_parse_error",
                chunk_id=chunk_id,
                error=str(e),
                error_position=getattr(e, 'pos', None),
            )
            errors = [
                ExtractionError(
                    chunk_id=chunk_id,
                    error_type="parsing",
                    error_message=f"JSON parse error: {e}",
                )
            ]
            products = []
            
        except ValidationError as e:
            logger.error(
                "llm_extractor.validation_error",
                chunk_id=chunk_id,
                error=str(e),
                error_count=e.error_count() if hasattr(e, 'error_count') else 1,
            )
            errors = [
                ExtractionError(
                    chunk_id=chunk_id,
                    error_type="validation",
                    error_message=str(e),
                )
            ]
            products = []
            
        except TimeoutError as e:
            self._retry_count += 1
            logger.error(
                "llm_extractor.timeout",
                chunk_id=chunk_id,
                timeout_seconds=self.request_timeout,
                retry_count=self._retry_count,
                error=str(e),
            )
            raise  # Let retry handle it
            
        except Exception as e:
            self._retry_count += 1
            logger.error(
                "llm_extractor.error",
                chunk_id=chunk_id,
                error_type=type(e).__name__,
                retry_count=self._retry_count,
                error=str(e),
            )
            raise LLMExtractionError(f"LLM extraction failed: {e}") from e
        
        total_time = time.time() - start_time
        processing_time = int(total_time * 1000)
        chunk_metrics.total_time = total_time
        chunk_metrics.retry_count = self._retry_count
        self._retry_count = 0  # Reset for next chunk
        
        # T86: Record performance metrics
        if self.enable_profiling:
            self._performance_stats.add_chunk_metrics(chunk_metrics)
            
            # Log warning for slow chunks
            if chunk_metrics.is_critical():
                logger.warning(
                    "llm_extractor.chunk_critical_slow",
                    chunk_id=chunk_id,
                    total_time_seconds=round(total_time, 2),
                    llm_time_seconds=round(llm_duration, 2),
                    threshold_seconds=CHUNK_PROCESSING_CRITICAL_THRESHOLD,
                    input_chars=chunk_metrics.input_chars,
                    products_extracted=len(products),
                    recommendation="Consider reducing chunk_size or upgrading LLM hardware",
                )
            elif chunk_metrics.is_slow():
                logger.warning(
                    "llm_extractor.chunk_slow",
                    chunk_id=chunk_id,
                    total_time_seconds=round(total_time, 2),
                    llm_time_seconds=round(llm_duration, 2),
                    threshold_seconds=CHUNK_PROCESSING_WARN_THRESHOLD,
                    input_chars=chunk_metrics.input_chars,
                    products_extracted=len(products),
                )
        
        # T82: Debug summary for chunk processing
        if self.debug_mode:
            logger.debug(
                "llm_extractor.chunk_complete",
                chunk_id=chunk_id,
                products_count=len(products),
                errors_count=len(errors),
                processing_time_ms=processing_time,
                llm_time_ms=int(llm_duration * 1000),
                parse_time_ms=int(chunk_metrics.parse_time * 1000),
                validation_time_ms=int(chunk_metrics.validation_time * 1000),
            )
        
        return ChunkExtractionResult(
            chunk_id=chunk_id,
            start_row=start_row,
            end_row=end_row,
            products=products,
            errors=errors,
            processing_time_ms=processing_time,
        )
    
    def _parse_llm_response(
        self,
        response_text: str,
        chunk_id: int,
        start_row: int,
    ) -> tuple[list[ExtractedProduct], list[ExtractionError]]:
        """
        Parse LLM JSON response into validated products.
        
        Args:
            response_text: Raw JSON text from LLM
            chunk_id: Chunk identifier
            start_row: Starting row for error reporting
        
        Returns:
            Tuple of (valid products, extraction errors)
        """
        products: list[ExtractedProduct] = []
        errors: list[ExtractionError] = []
        
        # Parse JSON
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            # Try to fix common JSON issues
            fixed_text = self._fix_common_json_issues(response_text)
            try:
                data = json.loads(fixed_text)
            except json.JSONDecodeError:
                raise e
        
        # Handle different response formats
        if isinstance(data, dict):
            # Response might have {"products": [...]} wrapper
            if "products" in data:
                items = data["products"]
            else:
                # Single product as dict
                items = [data]
        elif isinstance(data, list):
            items = data
        else:
            logger.warning(f"Unexpected response format: {type(data)}")
            items = []
        
        # Validate each item
        for i, item in enumerate(items):
            try:
                product = self._validate_product_data(item)
                if product:
                    products.append(product)
            except ValidationError as e:
                errors.append(
                    ExtractionError(
                        row_number=start_row + i,
                        chunk_id=chunk_id,
                        error_type="validation",
                        error_message=str(e),
                        raw_data=item if isinstance(item, dict) else {"value": item},
                    )
                )
        
        return products, errors
    
    def _validate_product_data(
        self, item: dict
    ) -> Optional[ExtractedProduct]:
        """
        Validate and normalize a product dict from LLM.
        
        Args:
            item: Raw product dict from LLM
        
        Returns:
            Validated ExtractedProduct or None if invalid
        """
        if not isinstance(item, dict):
            return None
        
        # Map common field name variations
        name = (
            item.get("name")
            or item.get("product_name")
            or item.get("название")
            or item.get("наименование")
        )
        
        if not name:
            return None
        
        # Get price - try multiple field names
        price_rrc = (
            item.get("price_rrc")
            or item.get("retail_price")
            or item.get("price")
            or item.get("цена")
            or item.get("ррц")
            or item.get("розница")
        )
        
        if price_rrc is None:
            return None
        
        # Clean price value
        price_rrc = self._clean_price(price_rrc)
        if price_rrc is None or price_rrc < 0:
            return None
        
        # Get optional fields
        price_opt = item.get("price_opt") or item.get("wholesale_price") or item.get("опт")
        if price_opt is not None:
            price_opt = self._clean_price(price_opt)
        
        description = (
            item.get("description")
            or item.get("описание")
            or item.get("характеристики")
            or item.get("specs")
        )
        
        category_path = (
            item.get("category_path")
            or item.get("category")
            or item.get("категория")
            or []
        )
        
        # Normalize category_path to list
        if isinstance(category_path, str):
            # Split by common delimiters
            for delimiter in [" / ", " > ", " → ", "/", ">"]:
                if delimiter in category_path:
                    category_path = [c.strip() for c in category_path.split(delimiter)]
                    break
            else:
                category_path = [category_path]
        
        # Store original data
        raw_data = {"original": item}
        
        return ExtractedProduct(
            name=str(name),
            description=str(description) if description else None,
            price_opt=price_opt,
            price_rrc=price_rrc,
            category_path=category_path if isinstance(category_path, list) else [],
            raw_data=raw_data,
        )
    
    def _clean_price(self, value: object) -> Optional[float]:
        """
        Clean and parse a price value.
        
        Handles various formats:
        - "1234.56" → 1234.56
        - "1 234,56" → 1234.56
        - "1234.56 р." → 1234.56
        - 1234.56 → 1234.56
        
        Args:
            value: Raw price value
        
        Returns:
            Cleaned float price or None if invalid
        """
        if value is None:
            return None
        
        if isinstance(value, (int, float)):
            return float(value)
        
        text = str(value).strip()
        
        # Remove currency symbols and text
        for symbol in ["р.", "руб.", "BYN", "$", "€", "₽", "руб", "рублей"]:
            text = text.replace(symbol, "")
        
        # Remove thousand separators (spaces)
        text = text.replace(" ", "")
        
        # Replace comma decimal separator
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        elif "," in text and "." in text:
            # Both present: assume comma is thousands separator
            text = text.replace(",", "")
        
        # Handle ranges (take first value)
        if "-" in text:
            text = text.split("-")[0].strip()
        
        try:
            return float(text)
        except ValueError:
            return None
    
    def _fix_common_json_issues(self, text: str) -> str:
        """
        Attempt to fix common JSON formatting issues from LLM output.
        
        Args:
            text: Raw text from LLM
        
        Returns:
            Fixed JSON string
        """
        # Remove markdown code block wrappers
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        
        if text.endswith("```"):
            text = text[:-3]
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _remove_overlap_duplicates(
        self,
        products: list[ExtractedProduct],
    ) -> list[ExtractedProduct]:
        """
        Remove duplicates caused by chunk overlap.
        
        Uses name + price (1% tolerance) for deduplication.
        Keeps first occurrence.
        
        Args:
            products: List of products with potential overlaps
        
        Returns:
            Deduplicated product list
        """
        seen: dict[str, float] = {}  # dedup_key -> price
        unique: list[ExtractedProduct] = []
        
        for product in products:
            key = product.get_dedup_key()
            price = float(product.price_rrc)
            
            if key in seen:
                # Check if price is within 1% tolerance
                existing_price = seen[key]
                tolerance = existing_price * 0.01
                if abs(price - existing_price) <= tolerance:
                    # Skip duplicate
                    continue
            
            seen[key] = price
            unique.append(product)
        
        return unique

