"""
E2E Tests for Sheet Selection Logic
====================================

Tests for User Story 2 (US2): Sheet selection and metadata sheet skipping.
Phase 9: Semantic ETL Pipeline Refactoring (T063)

Test Cases:
- Metadata sheets (Instructions, Config) are always skipped
- Priority sheets override all other selections
- Product keyword detection in sheet names
- Correct handling of edge cases
"""

import pytest
from pathlib import Path

from src.services.smart_parser import SheetSelector, SheetSelectionResult
from src.services.smart_parser.markdown_converter import MarkdownConverter


# Test data paths
TEST_DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / "specs" / "009-semantic-etl" / "test_data"
MULTI_SHEET_FILE = TEST_DATA_DIR / "multi_sheet_supplier.xlsx"


class TestMetadataSheetsSkipped:
    """Tests verifying that metadata sheets are correctly skipped (T063)."""
    
    @pytest.fixture
    def sheet_selector(self):
        return SheetSelector()
    
    @pytest.mark.asyncio
    async def test_instructions_sheet_skipped(self, sheet_selector):
        """Sheet named 'Instructions' is always skipped."""
        sheets_info = [
            {"name": "Instructions", "row_count": 50, "col_count": 10, "is_empty": False},
            {"name": "Data", "row_count": 100, "col_count": 5, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert "Instructions" in result.skipped_sheets
        assert "Instructions" not in result.selected_sheets
    
    @pytest.mark.asyncio
    async def test_config_sheet_skipped(self, sheet_selector):
        """Sheet named 'Config' is always skipped."""
        sheets_info = [
            {"name": "Config", "row_count": 20, "col_count": 5, "is_empty": False},
            {"name": "Data", "row_count": 100, "col_count": 5, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert "Config" in result.skipped_sheets
    
    @pytest.mark.asyncio
    async def test_settings_sheet_skipped(self, sheet_selector):
        """Sheet named 'Settings' is always skipped."""
        sheets_info = [
            {"name": "Settings", "row_count": 30, "col_count": 3, "is_empty": False},
            {"name": "Data", "row_count": 100, "col_count": 5, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert "Settings" in result.skipped_sheets
    
    @pytest.mark.asyncio
    async def test_russian_metadata_sheets_skipped(self, sheet_selector):
        """Russian metadata sheet names are skipped."""
        sheets_info = [
            {"name": "Инструкции", "row_count": 15, "col_count": 3, "is_empty": False},
            {"name": "Настройки", "row_count": 10, "col_count": 2, "is_empty": False},
            {"name": "Товары", "row_count": 200, "col_count": 8, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        # Russian metadata should be skipped
        assert "Инструкции" in result.skipped_sheets
        assert "Настройки" in result.skipped_sheets
        
        # Russian priority sheet should be selected
        assert "Товары" in result.selected_sheets
    
    @pytest.mark.asyncio
    async def test_readme_variations_skipped(self, sheet_selector):
        """Variations of README sheets are skipped."""
        sheets_info = [
            {"name": "README", "row_count": 20, "col_count": 3, "is_empty": False},
            {"name": "Readme_v2", "row_count": 15, "col_count": 2, "is_empty": False},
            {"name": "Data", "row_count": 100, "col_count": 5, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert "README" in result.skipped_sheets
        assert "Readme_v2" in result.skipped_sheets
        assert "Data" in result.selected_sheets
    
    @pytest.mark.asyncio
    async def test_template_sheet_skipped(self, sheet_selector):
        """Template sheets are skipped."""
        sheets_info = [
            {"name": "Template", "row_count": 50, "col_count": 10, "is_empty": False},
            {"name": "Data", "row_count": 100, "col_count": 5, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert "Template" in result.skipped_sheets
    
    @pytest.mark.asyncio
    async def test_help_sheet_skipped(self, sheet_selector):
        """Help sheets are skipped."""
        sheets_info = [
            {"name": "Help", "row_count": 30, "col_count": 5, "is_empty": False},
            {"name": "Data", "row_count": 100, "col_count": 5, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert "Help" in result.skipped_sheets


class TestPrioritySheetSelection:
    """Tests for priority sheet selection logic."""
    
    @pytest.fixture
    def sheet_selector(self):
        return SheetSelector()
    
    @pytest.mark.asyncio
    async def test_upload_to_site_is_priority(self, sheet_selector):
        """'Upload to site' is a priority sheet and is selected exclusively."""
        sheets_info = [
            {"name": "Upload to site", "row_count": 100, "col_count": 8, "is_empty": False},
            {"name": "Products", "row_count": 200, "col_count": 10, "is_empty": False},
            {"name": "Data", "row_count": 150, "col_count": 6, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        # Priority sheet should be the only one selected
        assert result.priority_sheet_found is True
        assert result.selected_sheets == ["Upload to site"]
        assert "Products" in result.skipped_sheets
        assert "Data" in result.skipped_sheets
    
    @pytest.mark.asyncio
    async def test_products_is_priority(self, sheet_selector):
        """'Products' is a priority sheet when no 'Upload to site' exists."""
        sheets_info = [
            {"name": "Products", "row_count": 200, "col_count": 10, "is_empty": False},
            {"name": "Data", "row_count": 150, "col_count": 6, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert result.priority_sheet_found is True
        assert result.selected_sheets == ["Products"]
    
    @pytest.mark.asyncio
    async def test_catalog_is_priority(self, sheet_selector):
        """'Catalog' is a priority sheet."""
        sheets_info = [
            {"name": "Catalog", "row_count": 300, "col_count": 12, "is_empty": False},
            {"name": "Data", "row_count": 150, "col_count": 6, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert result.priority_sheet_found is True
        assert result.selected_sheets == ["Catalog"]
    
    @pytest.mark.asyncio
    async def test_russian_priority_sheets(self, sheet_selector):
        """Russian priority sheet names are recognized."""
        sheets_info = [
            {"name": "Загрузка на сайт", "row_count": 100, "col_count": 8, "is_empty": False},
            {"name": "Data", "row_count": 150, "col_count": 6, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert result.priority_sheet_found is True
        assert result.selected_sheets == ["Загрузка на сайт"]
    
    @pytest.mark.asyncio
    async def test_first_priority_sheet_selected(self, sheet_selector):
        """When multiple priority sheets exist, the first one is selected."""
        sheets_info = [
            {"name": "Products", "row_count": 200, "col_count": 10, "is_empty": False},
            {"name": "Upload to site", "row_count": 100, "col_count": 8, "is_empty": False},  # Second in list
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        # First priority sheet in list should be selected
        assert result.priority_sheet_found is True
        assert len(result.selected_sheets) == 1


class TestProductKeywordDetection:
    """Tests for product-related keyword detection in sheet names."""
    
    @pytest.fixture
    def sheet_selector(self):
        return SheetSelector()
    
    @pytest.mark.asyncio
    async def test_price_keyword_detected(self, sheet_selector):
        """Sheet with 'price' in name is selected."""
        sheets_info = [
            {"name": "Price List 2024", "row_count": 100, "col_count": 5, "is_empty": False},
            {"name": "Instructions", "row_count": 10, "col_count": 3, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert "Price List 2024" in result.selected_sheets
    
    @pytest.mark.asyncio
    async def test_inventory_keyword_detected(self, sheet_selector):
        """Sheet with 'inventory' in name is selected."""
        sheets_info = [
            {"name": "Inventory Data", "row_count": 150, "col_count": 8, "is_empty": False},
            {"name": "Instructions", "row_count": 10, "col_count": 3, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert "Inventory Data" in result.selected_sheets
    
    @pytest.mark.asyncio
    async def test_stock_keyword_detected(self, sheet_selector):
        """Sheet with 'stock' in name is selected."""
        sheets_info = [
            {"name": "Stock Report", "row_count": 200, "col_count": 10, "is_empty": False},
            {"name": "Config", "row_count": 5, "col_count": 2, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert "Stock Report" in result.selected_sheets


class TestEdgeCases:
    """Tests for edge cases in sheet selection."""
    
    @pytest.fixture
    def sheet_selector(self):
        return SheetSelector()
    
    @pytest.mark.asyncio
    async def test_all_metadata_sheets(self, sheet_selector):
        """When all sheets are metadata, none are selected."""
        sheets_info = [
            {"name": "Instructions", "row_count": 10, "col_count": 5, "is_empty": False},
            {"name": "Config", "row_count": 5, "col_count": 2, "is_empty": False},
            {"name": "Help", "row_count": 20, "col_count": 3, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert result.selected_sheets == []
        assert len(result.skipped_sheets) == 3
    
    @pytest.mark.asyncio
    async def test_all_empty_sheets(self, sheet_selector):
        """When all sheets are empty, none are selected."""
        sheets_info = [
            {"name": "Sheet1", "row_count": 0, "col_count": 0, "is_empty": True},
            {"name": "Sheet2", "row_count": 0, "col_count": 0, "is_empty": True},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        assert result.selected_sheets == []
    
    @pytest.mark.asyncio
    async def test_empty_sheets_info(self, sheet_selector):
        """Empty sheets info returns proper result."""
        result = await sheet_selector.select_sheets([])
        
        assert result.selected_sheets == []
        assert result.reasoning == "No sheets in file"
    
    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self, sheet_selector):
        """Sheet name matching is case-insensitive."""
        sheets_info = [
            {"name": "UPLOAD TO SITE", "row_count": 100, "col_count": 8, "is_empty": False},
            {"name": "Data", "row_count": 150, "col_count": 6, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        # Should match despite uppercase
        assert result.priority_sheet_found is True
        assert "UPLOAD TO SITE" in result.selected_sheets


class TestRealFileValidation:
    """Tests with actual multi-sheet test file."""
    
    @pytest.fixture
    def markdown_converter(self):
        return MarkdownConverter()
    
    @pytest.fixture
    def sheet_selector(self):
        return SheetSelector()
    
    @pytest.mark.asyncio
    async def test_real_file_metadata_sheets_skipped(self, sheet_selector, markdown_converter):
        """Verify metadata sheets in real test file are skipped."""
        if not MULTI_SHEET_FILE.exists():
            pytest.skip(f"Test file not found: {MULTI_SHEET_FILE}")
        
        sheets_info = markdown_converter.get_sheet_info(MULTI_SHEET_FILE)
        result = await sheet_selector.select_sheets(sheets_info)
        
        # Instructions and Config should be skipped
        assert "Instructions" in result.skipped_sheets
        assert "Config" in result.skipped_sheets
    
    @pytest.mark.asyncio
    async def test_real_file_priority_overrides(self, sheet_selector, markdown_converter):
        """Verify priority sheet overrides other product sheets."""
        if not MULTI_SHEET_FILE.exists():
            pytest.skip(f"Test file not found: {MULTI_SHEET_FILE}")
        
        sheets_info = markdown_converter.get_sheet_info(MULTI_SHEET_FILE)
        result = await sheet_selector.select_sheets(sheets_info)
        
        # Only priority sheet should be selected
        assert result.selected_sheets == ["Upload to site"]
        
        # Other product sheets should be skipped (due to priority)
        assert "Products" in result.skipped_sheets
        assert "Pricing" in result.skipped_sheets
    
    def test_real_file_sheet_row_counts(self, markdown_converter):
        """Verify sheet row counts in real test file."""
        if not MULTI_SHEET_FILE.exists():
            pytest.skip(f"Test file not found: {MULTI_SHEET_FILE}")
        
        sheets_info = markdown_converter.get_sheet_info(MULTI_SHEET_FILE)
        
        # Find "Upload to site" sheet
        upload_sheet = next((s for s in sheets_info if s["name"] == "Upload to site"), None)
        assert upload_sheet is not None
        
        # Should have 81 rows (header + 80 products)
        assert upload_sheet["row_count"] == 81

