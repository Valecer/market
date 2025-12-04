"""
LangChain Extractor for Semantic ETL Pipeline
=============================================

LLM-based product extraction using LangChain and Ollama.
Implements sliding window processing for large files.

Phase 9: Semantic ETL Pipeline Refactoring
"""

import json
import logging
import time
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

logger = logging.getLogger(__name__)


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
    
    Example:
        extractor = LangChainExtractor()
        result = await extractor.extract_from_markdown(
            markdown_table,
            sheet_name="Products",
            total_rows=300,
        )
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        chunk_size: int = 250,
        chunk_overlap: int = 40,
        request_timeout: int = 120,
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
        """
        settings = Settings()
        
        self.model_name = model_name or settings.ollama_llm_model
        self.base_url = base_url or settings.ollama_base_url
        self.temperature = temperature
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.request_timeout = request_timeout
        
        # Initialize ChatOllama
        self.llm = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=self.temperature,
            request_timeout=self.request_timeout,
            format="json",  # Request JSON output
        )
        
        logger.info(
            f"Initialized LangChainExtractor with model={self.model_name}, "
            f"base_url={self.base_url}, temperature={self.temperature}"
        )
    
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
        
        # Build prompt
        prompt = get_extraction_prompt(markdown_table, complex_layout)
        
        try:
            # Call LLM
            response = await self.llm.ainvoke(prompt)
            
            # Parse response
            content = response.content
            if isinstance(content, str):
                products, errors = self._parse_llm_response(
                    content, chunk_id, start_row
                )
            else:
                raise LLMExtractionError(
                    f"Unexpected response type: {type(content)}"
                )
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in chunk {chunk_id}: {e}")
            errors = [
                ExtractionError(
                    chunk_id=chunk_id,
                    error_type="parsing",
                    error_message=f"JSON parse error: {e}",
                )
            ]
            products = []
            
        except ValidationError as e:
            logger.error(f"Validation error in chunk {chunk_id}: {e}")
            errors = [
                ExtractionError(
                    chunk_id=chunk_id,
                    error_type="validation",
                    error_message=str(e),
                )
            ]
            products = []
            
        except TimeoutError as e:
            logger.error(f"Timeout in chunk {chunk_id}: {e}")
            raise  # Let retry handle it
            
        except Exception as e:
            logger.error(f"LLM error in chunk {chunk_id}: {e}")
            raise LLMExtractionError(f"LLM extraction failed: {e}") from e
        
        processing_time = int((time.time() - start_time) * 1000)
        
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

