"""
E2E Tests for Multi-Sheet File Processing
==========================================

Tests for User Story 2 (US2): Multi-sheet file processing.
Phase 9: Semantic ETL Pipeline Refactoring (T062)

Test Cases:
- Priority sheet detection ("Upload to site")
- Metadata sheet skipping
- Multi-sheet processing (when no priority sheet)
- Cross-sheet deduplication
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.smart_parser import SmartParserService, SheetSelector
from src.services.smart_parser.markdown_converter import MarkdownConverter


# Test data paths
TEST_DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / "specs" / "009-semantic-etl" / "test_data"
MULTI_SHEET_FILE = TEST_DATA_DIR / "multi_sheet_supplier.xlsx"


class TestSheetSelection:
    """Tests for intelligent sheet selection."""
    
    @pytest.fixture
    def markdown_converter(self):
        return MarkdownConverter()
    
    @pytest.fixture
    def sheet_selector(self):
        return SheetSelector()
    
    def test_multi_sheet_file_info(self, markdown_converter):
        """Verify multi-sheet test file structure."""
        if not MULTI_SHEET_FILE.exists():
            pytest.skip(f"Test file not found: {MULTI_SHEET_FILE}")
        
        sheets_info = markdown_converter.get_sheet_info(MULTI_SHEET_FILE)
        
        # Verify we have 5 sheets
        assert len(sheets_info) == 5
        
        # Verify expected sheet names
        sheet_names = [s["name"] for s in sheets_info]
        assert "Instructions" in sheet_names
        assert "Products" in sheet_names
        assert "Pricing" in sheet_names
        assert "Config" in sheet_names
        assert "Upload to site" in sheet_names
    
    @pytest.mark.asyncio
    async def test_priority_sheet_selected(self, sheet_selector, markdown_converter):
        """Priority sheet 'Upload to site' is selected exclusively."""
        if not MULTI_SHEET_FILE.exists():
            pytest.skip(f"Test file not found: {MULTI_SHEET_FILE}")
        
        sheets_info = markdown_converter.get_sheet_info(MULTI_SHEET_FILE)
        result = await sheet_selector.select_sheets(sheets_info)
        
        # Only priority sheet should be selected
        assert result.priority_sheet_found is True
        assert result.selected_sheets == ["Upload to site"]
        
        # All other sheets should be skipped
        assert "Instructions" in result.skipped_sheets
        assert "Products" in result.skipped_sheets
        assert "Pricing" in result.skipped_sheets
        assert "Config" in result.skipped_sheets
    
    @pytest.mark.asyncio
    async def test_metadata_sheets_skipped(self, sheet_selector):
        """Metadata sheets are identified and skipped."""
        sheets_info = [
            {"name": "Instructions", "row_count": 10, "col_count": 5, "is_empty": False},
            {"name": "Config", "row_count": 5, "col_count": 2, "is_empty": False},
            {"name": "Readme", "row_count": 20, "col_count": 1, "is_empty": False},
            {"name": "ProductData", "row_count": 200, "col_count": 8, "is_empty": False},
        ]
        
        result = await sheet_selector.select_sheets(sheets_info)
        
        # Only ProductData should be selected
        assert "ProductData" in result.selected_sheets
        
        # Metadata sheets should be skipped
        assert "Instructions" in result.skipped_sheets
        assert "Config" in result.skipped_sheets
        assert "Readme" in result.skipped_sheets


class TestMultiSheetProcessing:
    """Tests for processing multi-sheet files."""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock SQLAlchemy session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        return session
    
    @pytest.fixture
    def mock_job_service(self):
        """Create mock job service."""
        service = MagicMock()
        service.update_job_status = AsyncMock()
        return service
    
    @pytest.mark.asyncio
    async def test_multi_sheet_file_processing_selects_priority(self, mock_session, mock_job_service):
        """Processing multi-sheet file selects only priority sheet."""
        if not MULTI_SHEET_FILE.exists():
            pytest.skip(f"Test file not found: {MULTI_SHEET_FILE}")
        
        # Patch category normalizer and LLM extractor
        with patch.object(
            SmartParserService, '_normalize_categories', new_callable=AsyncMock
        ) as mock_normalize, \
        patch(
            'src.services.smart_parser.service.LangChainExtractor'
        ) as mock_extractor_class:
            
            # Setup mock extractor
            mock_extractor = MagicMock()
            mock_extractor.extract_from_markdown = AsyncMock(return_value=MagicMock(
                products=[],
                sheet_name="Upload to site",
                total_rows=80,
                successful_extractions=80,
                failed_extractions=0,
                extraction_errors=[],
            ))
            mock_extractor_class.return_value = mock_extractor
            
            service = SmartParserService(
                session=mock_session,
                job_service=mock_job_service,
            )
            
            # Get sheets for inspection
            sheets, selection_result = await service._select_sheets(MULTI_SHEET_FILE)
            
            # Verify only priority sheet is selected
            assert sheets == ["Upload to site"]
            assert selection_result.priority_sheet_found is True
            assert "Instructions" in selection_result.skipped_sheets
    
    @pytest.mark.asyncio
    async def test_sheet_selection_summary_logging(self, mock_session):
        """Sheet selection generates proper summary for logging."""
        if not MULTI_SHEET_FILE.exists():
            pytest.skip(f"Test file not found: {MULTI_SHEET_FILE}")
        
        service = SmartParserService(session=mock_session)
        
        sheets, selection_result = await service._select_sheets(MULTI_SHEET_FILE)
        
        summary = service.sheet_selector.get_selection_summary(selection_result)
        
        # Verify summary contains key information
        assert "Upload to site" in summary
        assert "Instructions" in summary
        assert "Products" in summary or "Config" in summary


class TestCrossSheetDeduplication:
    """Tests for cross-sheet deduplication (T060)."""
    
    def test_aggregate_results_single_sheet(self):
        """Single sheet results are not deduplicated."""
        from src.schemas.extraction import ExtractionResult, ExtractedProduct
        from decimal import Decimal
        
        session = AsyncMock()
        service = SmartParserService(session=session)
        
        products = [
            ExtractedProduct(
                name="Product 1",
                price_rrc=Decimal("100.00"),
                category_path=["Electronics"],
            ),
            ExtractedProduct(
                name="Product 2",
                price_rrc=Decimal("200.00"),
                category_path=["Electronics"],
            ),
        ]
        
        result = ExtractionResult(
            products=products,
            sheet_name="Sheet1",
            total_rows=2,
            successful_extractions=2,
            failed_extractions=0,
        )
        
        # Single sheet - no cross-sheet dedup
        aggregated = service._aggregate_results([result], apply_cross_sheet_dedup=False)
        
        assert len(aggregated.products) == 2
        assert aggregated.duplicates_removed == 0
    
    def test_aggregate_results_multi_sheet_with_duplicates(self):
        """Multiple sheets with duplicates are deduplicated."""
        from src.schemas.extraction import ExtractionResult, ExtractedProduct
        from decimal import Decimal
        
        session = AsyncMock()
        service = SmartParserService(session=session)
        
        # Create products with duplicates across sheets
        products_sheet1 = [
            ExtractedProduct(
                name="Duplicate Product",
                price_rrc=Decimal("100.00"),
                category_path=["Electronics"],
            ),
            ExtractedProduct(
                name="Unique Product 1",
                price_rrc=Decimal("200.00"),
                category_path=["Electronics"],
            ),
        ]
        
        products_sheet2 = [
            ExtractedProduct(
                name="Duplicate Product",  # Same name as sheet1
                price_rrc=Decimal("100.50"),  # Within 1% tolerance
                category_path=["Electronics"],
            ),
            ExtractedProduct(
                name="Unique Product 2",
                price_rrc=Decimal("300.00"),
                category_path=["Electronics"],
            ),
        ]
        
        result1 = ExtractionResult(
            products=products_sheet1,
            sheet_name="Sheet1",
            total_rows=2,
            successful_extractions=2,
            failed_extractions=0,
        )
        
        result2 = ExtractionResult(
            products=products_sheet2,
            sheet_name="Sheet2",
            total_rows=2,
            successful_extractions=2,
            failed_extractions=0,
        )
        
        # Multi-sheet dedup enabled
        aggregated = service._aggregate_results(
            [result1, result2],
            apply_cross_sheet_dedup=True,
        )
        
        # Should have 3 unique products (1 duplicate removed)
        assert len(aggregated.products) == 3
        assert aggregated.duplicates_removed == 1
        assert "Sheet1, Sheet2" in aggregated.sheet_name
    
    def test_aggregate_results_empty_list(self):
        """Empty results list returns proper default."""
        session = AsyncMock()
        service = SmartParserService(session=session)
        
        aggregated = service._aggregate_results([])
        
        assert aggregated.products == []
        assert aggregated.total_rows == 0
        assert aggregated.sheet_name == "(no sheets)"


class TestSheetSelectionWithoutPriority:
    """Tests for sheet selection when no priority sheet exists."""
    
    @pytest.mark.asyncio
    async def test_multiple_product_sheets_selected(self):
        """When no priority sheet, all product sheets are selected."""
        selector = SheetSelector()
        
        sheets_info = [
            {"name": "Data1", "row_count": 100, "col_count": 5, "is_empty": False},
            {"name": "Data2", "row_count": 200, "col_count": 8, "is_empty": False},
            {"name": "Instructions", "row_count": 10, "col_count": 3, "is_empty": False},
        ]
        
        result = await selector.select_sheets(sheets_info)
        
        # No priority sheet
        assert result.priority_sheet_found is False
        
        # Both data sheets should be selected
        assert len(result.selected_sheets) == 2
        assert "Data1" in result.selected_sheets
        assert "Data2" in result.selected_sheets
        
        # Instructions should be skipped
        assert "Instructions" in result.skipped_sheets
    
    @pytest.mark.asyncio
    async def test_empty_sheets_skipped(self):
        """Empty sheets are always skipped."""
        selector = SheetSelector()
        
        sheets_info = [
            {"name": "EmptySheet", "row_count": 0, "col_count": 0, "is_empty": True},
            {"name": "SmallSheet", "row_count": 1, "col_count": 1, "is_empty": False},  # Only header
            {"name": "DataSheet", "row_count": 100, "col_count": 5, "is_empty": False},
        ]
        
        result = await selector.select_sheets(sheets_info)
        
        # Only DataSheet should be selected
        assert result.selected_sheets == ["DataSheet"]
        assert "EmptySheet" in result.skipped_sheets
        assert "SmallSheet" in result.skipped_sheets

