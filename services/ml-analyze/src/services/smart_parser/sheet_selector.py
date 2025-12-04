"""
Sheet Selector for Semantic ETL Pipeline
=========================================

Intelligently selects which Excel sheets contain product data
using both heuristics and optional LLM analysis.

Phase 9: User Story 2 - Multi-Sheet Files

Features:
- Priority sheet detection (exact name match)
- Metadata sheet filtering
- LLM-based content analysis for ambiguous cases
- Multi-sheet processing support
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.config.settings import Settings
from src.services.smart_parser.prompts import get_sheet_analysis_prompt

logger = logging.getLogger(__name__)


@dataclass
class SheetSelectionResult:
    """Result of sheet selection process."""
    
    selected_sheets: list[str] = field(default_factory=list)
    skipped_sheets: list[str] = field(default_factory=list)
    reasoning: str = ""
    used_llm: bool = False
    priority_sheet_found: bool = False


class SheetAnalysisResponse(BaseModel):
    """LLM response schema for sheet analysis."""
    
    selected_sheets: list[str] = Field(
        default_factory=list,
        description="Sheet names selected for processing"
    )
    skipped_sheets: list[str] = Field(
        default_factory=list,
        description="Sheet names skipped as metadata/config"
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation of selection logic"
    )


class SheetSelector:
    """
    Selects product data sheets from multi-sheet Excel files.
    
    Selection Strategy:
    1. Check for priority sheet names (highest priority)
    2. Filter out known metadata sheet names
    3. Skip empty/small sheets
    4. Optionally use LLM for ambiguous cases
    
    Example:
        selector = SheetSelector()
        result = await selector.select_sheets(sheets_info)
        # result.selected_sheets = ["Products", "Pricing"]
        # result.skipped_sheets = ["Instructions", "Config"]
    """
    
    # Priority sheet names - if found, ONLY process this sheet (case-insensitive)
    PRIORITY_SHEET_NAMES: list[str] = [
        "upload to site",
        "загрузка на сайт",
        "products",
        "товары",
        "catalog",
        "каталог",
        "export",
        "экспорт",
        "price list",
        "прайс-лист",
        "прайс",
    ]
    
    # Sheets to always skip (metadata/configuration)
    SKIP_SHEET_NAMES: list[str] = [
        "instructions",
        "инструкции",
        "settings",
        "настройки",
        "config",
        "configuration",
        "конфигурация",
        "template",
        "шаблон",
        "example",
        "пример",
        "readme",
        "info",
        "help",
        "справка",
        "about",
        "notes",
        "заметки",
        "summary",
        "итого",
        "totals",
        "sheet1",  # Default sheet names often contain temp data
        "лист1",
    ]
    
    # Keywords that suggest product data
    PRODUCT_KEYWORDS: list[str] = [
        "product",
        "товар",
        "item",
        "артикул",
        "sku",
        "price",
        "цена",
        "catalog",
        "каталог",
        "stock",
        "склад",
        "inventory",
    ]
    
    # Minimum rows to consider a sheet as having data
    MIN_DATA_ROWS: int = 2  # Header + at least 1 data row
    
    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        use_llm_for_ambiguous: bool = True,
        min_rows: int = 2,
    ):
        """
        Initialize SheetSelector.
        
        Args:
            llm: LangChain chat model for LLM-based analysis (optional)
            use_llm_for_ambiguous: Whether to use LLM for ambiguous cases
            min_rows: Minimum rows to consider a sheet as having data
        """
        self.llm = llm
        self.use_llm_for_ambiguous = use_llm_for_ambiguous
        self.min_rows = min_rows
        self.settings = Settings()
    
    async def select_sheets(
        self,
        sheets_info: list[dict],
        use_llm: bool = False,
    ) -> SheetSelectionResult:
        """
        Select which sheets to process from sheet metadata.
        
        Args:
            sheets_info: List of sheet info dicts from MarkdownConverter.get_sheet_info()
                Each dict: {name, row_count, col_count, is_empty}
            use_llm: Force LLM analysis even for clear cases
        
        Returns:
            SheetSelectionResult with selected and skipped sheets
        """
        if not sheets_info:
            return SheetSelectionResult(reasoning="No sheets in file")
        
        logger.debug(f"Analyzing {len(sheets_info)} sheets for selection")
        
        # Step 1: Check for priority sheets (instant selection)
        priority_result = self._find_priority_sheet(sheets_info)
        if priority_result.priority_sheet_found:
            logger.info(f"Found priority sheet: {priority_result.selected_sheets}")
            return priority_result
        
        # Step 2: Filter using heuristics
        candidates, skipped = self._filter_by_heuristics(sheets_info)
        
        # Step 3: If single candidate or no LLM, return heuristic result
        if len(candidates) <= 1 or not use_llm:
            result = SheetSelectionResult(
                selected_sheets=[s["name"] for s in candidates],
                skipped_sheets=[s["name"] for s in skipped],
                reasoning="Selected based on heuristic rules",
                used_llm=False,
            )
            logger.info(f"Selected {len(result.selected_sheets)} sheet(s) via heuristics")
            return result
        
        # Step 4: Use LLM for ambiguous multi-sheet cases
        if self.use_llm_for_ambiguous and self.llm:
            return await self._select_with_llm(sheets_info, candidates, skipped)
        
        # Fallback: Return all candidates
        return SheetSelectionResult(
            selected_sheets=[s["name"] for s in candidates],
            skipped_sheets=[s["name"] for s in skipped],
            reasoning="Multiple candidate sheets found; processing all",
            used_llm=False,
        )
    
    def _find_priority_sheet(
        self,
        sheets_info: list[dict],
    ) -> SheetSelectionResult:
        """
        Check for priority sheet names that should be processed exclusively.
        
        Priority is determined by order in PRIORITY_SHEET_NAMES list,
        not by sheet order in the file. "Upload to site" has highest priority.
        
        Args:
            sheets_info: Sheet metadata list
        
        Returns:
            SheetSelectionResult (priority_sheet_found=True if found)
        """
        # Build a map of normalized names to sheets
        sheet_map: dict[str, dict] = {
            sheet["name"].lower().strip(): sheet
            for sheet in sheets_info
        }
        
        # Check priority names in order (highest priority first)
        for priority_name in self.PRIORITY_SHEET_NAMES:
            if priority_name in sheet_map:
                sheet = sheet_map[priority_name]
                # Found priority sheet - process ONLY this sheet
                skipped = [s["name"] for s in sheets_info if s["name"] != sheet["name"]]
                
                return SheetSelectionResult(
                    selected_sheets=[sheet["name"]],
                    skipped_sheets=skipped,
                    reasoning=f"Priority sheet '{sheet['name']}' found - processing exclusively",
                    used_llm=False,
                    priority_sheet_found=True,
                )
        
        return SheetSelectionResult(priority_sheet_found=False)
    
    def _filter_by_heuristics(
        self,
        sheets_info: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        """
        Filter sheets using heuristic rules.
        
        Args:
            sheets_info: Sheet metadata list
        
        Returns:
            Tuple of (candidate_sheets, skipped_sheets)
        """
        candidates: list[dict] = []
        skipped: list[dict] = []
        
        for sheet in sheets_info:
            normalized_name = sheet["name"].lower().strip()
            row_count = sheet.get("row_count", 0)
            is_empty = sheet.get("is_empty", False)
            
            # Skip empty sheets
            if is_empty or row_count < self.min_rows:
                logger.debug(f"Skipping empty/small sheet: '{sheet['name']}'")
                skipped.append(sheet)
                continue
            
            # Skip known metadata sheets
            if self._is_metadata_sheet(normalized_name):
                logger.debug(f"Skipping metadata sheet: '{sheet['name']}'")
                skipped.append(sheet)
                continue
            
            # Check for product-related keywords
            if self._has_product_keywords(normalized_name):
                logger.debug(f"Sheet '{sheet['name']}' has product keywords")
                candidates.append(sheet)
                continue
            
            # Include sheets with substantial data
            if row_count >= 10:  # Arbitrary threshold for "substantial"
                candidates.append(sheet)
            else:
                # Small sheets without product keywords are skipped
                skipped.append(sheet)
        
        return candidates, skipped
    
    def _is_metadata_sheet(self, normalized_name: str) -> bool:
        """
        Check if sheet name matches known metadata patterns.
        
        Args:
            normalized_name: Lowercase, stripped sheet name
        
        Returns:
            True if sheet should be skipped
        """
        # Exact match
        if normalized_name in self.SKIP_SHEET_NAMES:
            return True
        
        # Partial match for common patterns
        skip_patterns = ["readme", "info", "help", "note", "config", "setting"]
        return any(pattern in normalized_name for pattern in skip_patterns)
    
    def _has_product_keywords(self, normalized_name: str) -> bool:
        """
        Check if sheet name contains product-related keywords.
        
        Args:
            normalized_name: Lowercase, stripped sheet name
        
        Returns:
            True if sheet likely contains product data
        """
        return any(keyword in normalized_name for keyword in self.PRODUCT_KEYWORDS)
    
    async def _select_with_llm(
        self,
        sheets_info: list[dict],
        candidates: list[dict],
        skipped: list[dict],
    ) -> SheetSelectionResult:
        """
        Use LLM to select sheets from ambiguous candidates.
        
        Args:
            sheets_info: All sheet metadata
            candidates: Pre-filtered candidate sheets
            skipped: Already skipped sheets
        
        Returns:
            SheetSelectionResult from LLM analysis
        """
        if not self.llm:
            raise ValueError("LLM not configured for sheet selection")
        
        try:
            # Build prompt
            prompt = get_sheet_analysis_prompt(sheets_info)
            
            # Create messages
            messages = [
                SystemMessage(content="You are an expert at analyzing Excel file structures."),
                HumanMessage(content=prompt),
            ]
            
            # Try structured output first
            try:
                llm_with_structure = self.llm.with_structured_output(SheetAnalysisResponse)
                response: SheetAnalysisResponse = await llm_with_structure.ainvoke(messages)
                
                return SheetSelectionResult(
                    selected_sheets=response.selected_sheets,
                    skipped_sheets=response.skipped_sheets,
                    reasoning=response.reasoning,
                    used_llm=True,
                )
            except Exception as struct_err:
                logger.warning(f"Structured output failed: {struct_err}, trying raw JSON")
                
                # Fallback to raw JSON parsing
                raw_response = await self.llm.ainvoke(messages)
                content = raw_response.content
                
                # Parse JSON from response
                if isinstance(content, str):
                    # Try to extract JSON
                    json_start = content.find("{")
                    json_end = content.rfind("}") + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = content[json_start:json_end]
                        data = json.loads(json_str)
                        
                        return SheetSelectionResult(
                            selected_sheets=data.get("selected_sheets", []),
                            skipped_sheets=data.get("skipped_sheets", []),
                            reasoning=data.get("reasoning", "LLM analysis"),
                            used_llm=True,
                        )
                
                raise ValueError(f"Could not parse LLM response: {content}")
                
        except Exception as e:
            logger.error(f"LLM sheet selection failed: {e}")
            
            # Fallback to heuristic result
            return SheetSelectionResult(
                selected_sheets=[s["name"] for s in candidates],
                skipped_sheets=[s["name"] for s in skipped],
                reasoning=f"LLM analysis failed ({e}), using heuristics",
                used_llm=False,
            )
    
    def identify_priority_sheets(
        self,
        sheets_info: list[dict],
    ) -> list[str]:
        """
        Identify sheets that should be processed with priority.
        
        This is a synchronous method for simple priority detection.
        
        Args:
            sheets_info: Sheet metadata list
        
        Returns:
            List of priority sheet names (empty if none found)
        """
        priority_sheets = []
        
        for sheet in sheets_info:
            normalized_name = sheet["name"].lower().strip()
            
            if normalized_name in self.PRIORITY_SHEET_NAMES:
                priority_sheets.append(sheet["name"])
        
        return priority_sheets
    
    def skip_metadata_sheets(
        self,
        sheet_names: list[str],
    ) -> tuple[list[str], list[str]]:
        """
        Filter out metadata sheets from a list of sheet names.
        
        Args:
            sheet_names: List of sheet names
        
        Returns:
            Tuple of (kept_sheets, skipped_sheets)
        """
        kept = []
        skipped = []
        
        for name in sheet_names:
            normalized = name.lower().strip()
            if self._is_metadata_sheet(normalized):
                skipped.append(name)
            else:
                kept.append(name)
        
        return kept, skipped
    
    def get_selection_summary(
        self,
        result: SheetSelectionResult,
    ) -> str:
        """
        Generate a human-readable summary of sheet selection.
        
        Args:
            result: Selection result
        
        Returns:
            Summary string
        """
        lines = [
            f"Sheet Selection Summary:",
            f"  Selected: {', '.join(result.selected_sheets) or 'None'}",
            f"  Skipped: {', '.join(result.skipped_sheets) or 'None'}",
            f"  Method: {'LLM' if result.used_llm else 'Heuristics'}",
            f"  Reasoning: {result.reasoning}",
        ]
        return "\n".join(lines)

