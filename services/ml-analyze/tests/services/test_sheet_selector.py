"""
Unit Tests for SheetSelector
============================

Tests for the intelligent sheet selection logic in the Semantic ETL pipeline.
Phase 9: User Story 2 - Multi-Sheet Files (T057)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.smart_parser.sheet_selector import (
    SheetSelector,
    SheetSelectionResult,
    SheetAnalysisResponse,
)


class TestSheetSelectorHeuristics:
    """Tests for heuristic-based sheet selection."""
    
    def test_select_priority_sheet_upload_to_site(self):
        """Priority sheet 'Upload to site' is selected exclusively."""
        selector = SheetSelector()
        sheets_info = [
            {"name": "Instructions", "row_count": 10, "col_count": 5, "is_empty": False},
            {"name": "Upload to site", "row_count": 300, "col_count": 10, "is_empty": False},
            {"name": "Pricing", "row_count": 100, "col_count": 5, "is_empty": False},
        ]
        
        result = selector._find_priority_sheet(sheets_info)
        
        assert result.priority_sheet_found is True
        assert result.selected_sheets == ["Upload to site"]
        assert "Instructions" in result.skipped_sheets
        assert "Pricing" in result.skipped_sheets
    
    def test_select_priority_sheet_products_russian(self):
        """Priority sheet 'Товары' (Russian) is selected."""
        selector = SheetSelector()
        sheets_info = [
            {"name": "Инструкции", "row_count": 5, "col_count": 3, "is_empty": False},
            {"name": "Товары", "row_count": 500, "col_count": 8, "is_empty": False},
        ]
        
        result = selector._find_priority_sheet(sheets_info)
        
        assert result.priority_sheet_found is True
        assert result.selected_sheets == ["Товары"]
    
    def test_no_priority_sheet_found(self):
        """When no priority sheet exists, result indicates none found."""
        selector = SheetSelector()
        sheets_info = [
            {"name": "Data", "row_count": 100, "col_count": 5, "is_empty": False},
            {"name": "Info", "row_count": 20, "col_count": 3, "is_empty": False},
        ]
        
        result = selector._find_priority_sheet(sheets_info)
        
        assert result.priority_sheet_found is False
    
    def test_skip_metadata_sheets(self):
        """Metadata sheets like 'Instructions' and 'Config' are skipped."""
        selector = SheetSelector()
        sheets_info = [
            {"name": "Instructions", "row_count": 10, "col_count": 5, "is_empty": False},
            {"name": "Config", "row_count": 5, "col_count": 2, "is_empty": False},
            {"name": "ProductData", "row_count": 200, "col_count": 8, "is_empty": False},
        ]
        
        candidates, skipped = selector._filter_by_heuristics(sheets_info)
        
        assert len(candidates) == 1
        assert candidates[0]["name"] == "ProductData"
        assert len(skipped) == 2
        assert any(s["name"] == "Instructions" for s in skipped)
        assert any(s["name"] == "Config" for s in skipped)
    
    def test_skip_empty_sheets(self):
        """Empty sheets are skipped."""
        selector = SheetSelector()
        sheets_info = [
            {"name": "EmptySheet", "row_count": 0, "col_count": 0, "is_empty": True},
            {"name": "ProductData", "row_count": 100, "col_count": 5, "is_empty": False},
        ]
        
        candidates, skipped = selector._filter_by_heuristics(sheets_info)
        
        assert len(candidates) == 1
        assert candidates[0]["name"] == "ProductData"
        assert len(skipped) == 1
        assert skipped[0]["name"] == "EmptySheet"
    
    def test_skip_small_sheets_without_keywords(self):
        """Small sheets without product keywords are skipped."""
        selector = SheetSelector()
        sheets_info = [
            {"name": "Notes", "row_count": 5, "col_count": 2, "is_empty": False},
            {"name": "Catalog", "row_count": 300, "col_count": 10, "is_empty": False},
        ]
        
        candidates, skipped = selector._filter_by_heuristics(sheets_info)
        
        assert len(candidates) == 1
        assert candidates[0]["name"] == "Catalog"
    
    def test_include_sheets_with_product_keywords(self):
        """Sheets with product-related keywords are included."""
        selector = SheetSelector()
        sheets_info = [
            {"name": "Price List", "row_count": 50, "col_count": 5, "is_empty": False},
            {"name": "Stock Inventory", "row_count": 30, "col_count": 4, "is_empty": False},
            {"name": "Random", "row_count": 5, "col_count": 2, "is_empty": False},
        ]
        
        candidates, skipped = selector._filter_by_heuristics(sheets_info)
        
        # Both Price and Stock sheets have keywords
        assert len(candidates) == 2
        assert any(c["name"] == "Price List" for c in candidates)
        assert any(c["name"] == "Stock Inventory" for c in candidates)
    
    def test_is_metadata_sheet_exact_match(self):
        """Test exact match for metadata sheet names."""
        selector = SheetSelector()
        
        assert selector._is_metadata_sheet("instructions") is True
        assert selector._is_metadata_sheet("настройки") is True
        assert selector._is_metadata_sheet("template") is True
        assert selector._is_metadata_sheet("products") is False
    
    def test_is_metadata_sheet_partial_match(self):
        """Test partial match for metadata patterns."""
        selector = SheetSelector()
        
        assert selector._is_metadata_sheet("readme_v2") is True
        assert selector._is_metadata_sheet("configuration_sheet") is True
        assert selector._is_metadata_sheet("my_notes") is True
        assert selector._is_metadata_sheet("product_catalog") is False
    
    def test_has_product_keywords(self):
        """Test product keyword detection."""
        selector = SheetSelector()
        
        assert selector._has_product_keywords("product list") is True
        assert selector._has_product_keywords("товары") is True
        assert selector._has_product_keywords("price catalog") is True
        assert selector._has_product_keywords("inventory") is True
        assert selector._has_product_keywords("random data") is False


class TestSheetSelectorMethods:
    """Tests for public methods of SheetSelector."""
    
    def test_identify_priority_sheets_multiple(self):
        """identify_priority_sheets returns all matching priority sheets."""
        selector = SheetSelector()
        sheets_info = [
            {"name": "Products", "row_count": 100, "col_count": 5},
            {"name": "Catalog", "row_count": 200, "col_count": 8},
            {"name": "Random", "row_count": 50, "col_count": 3},
        ]
        
        result = selector.identify_priority_sheets(sheets_info)
        
        # Both Products and Catalog are priority names
        assert "Products" in result
        assert "Catalog" in result
        assert "Random" not in result
    
    def test_identify_priority_sheets_none(self):
        """identify_priority_sheets returns empty list when no matches."""
        selector = SheetSelector()
        sheets_info = [
            {"name": "Data1", "row_count": 100, "col_count": 5},
            {"name": "Data2", "row_count": 200, "col_count": 8},
        ]
        
        result = selector.identify_priority_sheets(sheets_info)
        
        assert result == []
    
    def test_skip_metadata_sheets_method(self):
        """skip_metadata_sheets correctly separates sheets."""
        selector = SheetSelector()
        sheet_names = ["Products", "Instructions", "Pricing", "Config", "Help"]
        
        kept, skipped = selector.skip_metadata_sheets(sheet_names)
        
        assert "Products" in kept
        assert "Pricing" in kept
        assert "Instructions" in skipped
        assert "Config" in skipped
        assert "Help" in skipped
    
    def test_get_selection_summary(self):
        """get_selection_summary generates readable output."""
        selector = SheetSelector()
        result = SheetSelectionResult(
            selected_sheets=["Products", "Pricing"],
            skipped_sheets=["Instructions", "Config"],
            reasoning="Selected based on heuristic rules",
            used_llm=False,
        )
        
        summary = selector.get_selection_summary(result)
        
        assert "Products" in summary
        assert "Pricing" in summary
        assert "Instructions" in summary
        assert "Config" in summary
        assert "Heuristics" in summary


class TestSheetSelectorAsync:
    """Async tests for select_sheets method."""
    
    @pytest.mark.asyncio
    async def test_select_sheets_priority_sheet(self):
        """select_sheets returns priority sheet immediately."""
        selector = SheetSelector()
        sheets_info = [
            {"name": "Instructions", "row_count": 10, "col_count": 5, "is_empty": False},
            {"name": "Upload to site", "row_count": 300, "col_count": 10, "is_empty": False},
            {"name": "Pricing", "row_count": 100, "col_count": 5, "is_empty": False},
        ]
        
        result = await selector.select_sheets(sheets_info)
        
        assert result.priority_sheet_found is True
        assert result.selected_sheets == ["Upload to site"]
        assert result.used_llm is False
    
    @pytest.mark.asyncio
    async def test_select_sheets_heuristics_single(self):
        """select_sheets uses heuristics for single candidate."""
        selector = SheetSelector()
        sheets_info = [
            {"name": "Instructions", "row_count": 10, "col_count": 5, "is_empty": False},
            {"name": "ProductData", "row_count": 300, "col_count": 10, "is_empty": False},
        ]
        
        result = await selector.select_sheets(sheets_info)
        
        assert result.selected_sheets == ["ProductData"]
        assert result.used_llm is False
    
    @pytest.mark.asyncio
    async def test_select_sheets_heuristics_multiple(self):
        """select_sheets returns multiple candidates without LLM."""
        selector = SheetSelector(use_llm_for_ambiguous=False)
        sheets_info = [
            {"name": "Data1", "row_count": 100, "col_count": 5, "is_empty": False},
            {"name": "Data2", "row_count": 200, "col_count": 8, "is_empty": False},
            {"name": "Config", "row_count": 5, "col_count": 2, "is_empty": False},
        ]
        
        result = await selector.select_sheets(sheets_info)
        
        assert len(result.selected_sheets) == 2
        assert "Data1" in result.selected_sheets
        assert "Data2" in result.selected_sheets
        assert result.used_llm is False
    
    @pytest.mark.asyncio
    async def test_select_sheets_empty_input(self):
        """select_sheets handles empty input gracefully."""
        selector = SheetSelector()
        
        result = await selector.select_sheets([])
        
        assert result.selected_sheets == []
        assert result.reasoning == "No sheets in file"
    
    @pytest.mark.asyncio
    async def test_select_sheets_all_skipped(self):
        """select_sheets handles case where all sheets are metadata."""
        selector = SheetSelector()
        sheets_info = [
            {"name": "Instructions", "row_count": 10, "col_count": 5, "is_empty": False},
            {"name": "Config", "row_count": 5, "col_count": 2, "is_empty": False},
            {"name": "Notes", "row_count": 3, "col_count": 1, "is_empty": False},
        ]
        
        result = await selector.select_sheets(sheets_info)
        
        assert result.selected_sheets == []
        assert len(result.skipped_sheets) == 3


class TestSheetSelectorLLM:
    """Tests for LLM-based sheet selection."""
    
    @pytest.mark.asyncio
    async def test_select_with_llm_success(self):
        """select_sheets uses LLM when configured (no priority sheets)."""
        # Mock LLM
        mock_llm = MagicMock()
        mock_structured_llm = MagicMock()
        
        # Set up mock response
        mock_response = SheetAnalysisResponse(
            selected_sheets=["DataSheet1", "DataSheet2"],
            skipped_sheets=["Instructions"],
            reasoning="LLM selected data sheets"
        )
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.with_structured_output.return_value = mock_structured_llm
        
        selector = SheetSelector(llm=mock_llm, use_llm_for_ambiguous=True)
        # Use non-priority sheet names to trigger LLM path
        sheets_info = [
            {"name": "DataSheet1", "row_count": 100, "col_count": 5, "is_empty": False},
            {"name": "DataSheet2", "row_count": 200, "col_count": 8, "is_empty": False},
            {"name": "Instructions", "row_count": 10, "col_count": 3, "is_empty": False},
        ]
        
        result = await selector.select_sheets(sheets_info, use_llm=True)
        
        assert result.selected_sheets == ["DataSheet1", "DataSheet2"]
        assert result.skipped_sheets == ["Instructions"]
        assert result.used_llm is True
        assert result.reasoning == "LLM selected data sheets"
    
    @pytest.mark.asyncio
    async def test_select_with_llm_fallback_on_error(self):
        """select_sheets falls back to heuristics on LLM error."""
        # Mock LLM that raises error
        mock_llm = MagicMock()
        mock_llm.with_structured_output.side_effect = Exception("LLM error")
        
        selector = SheetSelector(llm=mock_llm, use_llm_for_ambiguous=True)
        sheets_info = [
            {"name": "Data1", "row_count": 100, "col_count": 5, "is_empty": False},
            {"name": "Data2", "row_count": 200, "col_count": 8, "is_empty": False},
        ]
        
        result = await selector._select_with_llm(sheets_info, sheets_info, [])
        
        # Should fall back to heuristics
        assert result.used_llm is False
        assert "failed" in result.reasoning.lower()


class TestSheetSelectionResult:
    """Tests for SheetSelectionResult dataclass."""
    
    def test_default_values(self):
        """SheetSelectionResult has correct defaults."""
        result = SheetSelectionResult()
        
        assert result.selected_sheets == []
        assert result.skipped_sheets == []
        assert result.reasoning == ""
        assert result.used_llm is False
        assert result.priority_sheet_found is False
    
    def test_custom_values(self):
        """SheetSelectionResult accepts custom values."""
        result = SheetSelectionResult(
            selected_sheets=["Sheet1"],
            skipped_sheets=["Sheet2"],
            reasoning="Test reason",
            used_llm=True,
            priority_sheet_found=True,
        )
        
        assert result.selected_sheets == ["Sheet1"]
        assert result.skipped_sheets == ["Sheet2"]
        assert result.reasoning == "Test reason"
        assert result.used_llm is True
        assert result.priority_sheet_found is True

