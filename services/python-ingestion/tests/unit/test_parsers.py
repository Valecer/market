"""Unit tests for parser implementations.

This module tests parser functionality with mocked external dependencies
(gspread API) to ensure parsers work correctly in isolation.
"""
import os

# Set environment variables BEFORE importing modules that use settings
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_PASSWORD", "test_password")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("LOG_LEVEL", "INFO")

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from decimal import Decimal
from typing import List, Dict, Any

from src.parsers.google_sheets_parser import GoogleSheetsParser
from src.parsers.base_parser import ParserInterface
from src.models.parsed_item import ParsedSupplierItem
from src.models.google_sheets_config import GoogleSheetsConfig
from src.errors.exceptions import ParserError, ValidationError


class TestGoogleSheetsParserInitialization:
    """Test GoogleSheetsParser initialization and authentication."""
    
    @patch('src.parsers.google_sheets_parser.gspread.service_account')
    def test_parser_initializes_with_credentials_path(self, mock_service_account):
        """Verify parser initializes with explicit credentials path."""
        mock_client = Mock()
        mock_service_account.return_value = mock_client
        
        parser = GoogleSheetsParser(credentials_path="/path/to/credentials.json")
        
        # The parser uses _client (private attribute), not client
        assert parser._client == mock_client
        mock_service_account.assert_called_once_with(filename="/path/to/credentials.json")
    
    @patch('src.parsers.google_sheets_parser.gspread.service_account')
    @patch('src.parsers.google_sheets_parser.settings')
    def test_parser_initializes_with_default_credentials(self, mock_settings, mock_service_account):
        """Verify parser uses settings.google_credentials_path when no path provided."""
        mock_settings.google_credentials_path = "/default/credentials.json"
        mock_client = Mock()
        mock_service_account.return_value = mock_client
        
        parser = GoogleSheetsParser()
        
        # The parser uses _client (private attribute), not client
        assert parser._client == mock_client
        mock_service_account.assert_called_once_with(filename="/default/credentials.json")
    
    @patch('src.parsers.google_sheets_parser.gspread.service_account')
    def test_parser_raises_error_on_authentication_failure(self, mock_service_account):
        """Verify parser raises ParserError when authentication fails."""
        mock_service_account.side_effect = Exception("Invalid credentials")
        
        with pytest.raises(ParserError) as exc_info:
            GoogleSheetsParser(credentials_path="/invalid/path.json")
        
        assert "authentication" in str(exc_info.value).lower() or "credentials" in str(exc_info.value).lower()


class TestGoogleSheetsParserValidateConfig:
    """Test GoogleSheetsParser.validate_config() method."""
    
    @pytest.fixture
    def parser(self):
        """Create a parser instance with mocked client."""
        with patch('src.parsers.google_sheets_parser.gspread.service_account'):
            return GoogleSheetsParser(credentials_path="/test/credentials.json")
    
    def test_validate_config_accepts_valid_config(self, parser):
        """Verify validate_config() accepts valid GoogleSheetsConfig."""
        config = {
            "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
            "sheet_name": "Sheet1",
            "header_row": 1,
            "data_start_row": 2
        }
        
        result = parser.validate_config(config)
        assert result is True
    
    def test_validate_config_rejects_invalid_url(self, parser):
        """Verify validate_config() rejects invalid sheet URL."""
        config = {
            "sheet_url": "not-a-valid-url",
            "sheet_name": "Sheet1"
        }
        
        with pytest.raises(ValidationError):
            parser.validate_config(config)
    
    def test_validate_config_rejects_missing_sheet_url(self, parser):
        """Verify validate_config() rejects config without sheet_url."""
        config = {
            "sheet_name": "Sheet1"
        }
        
        with pytest.raises(ValidationError):
            parser.validate_config(config)
    
    def test_validate_config_rejects_invalid_column_mapping_keys(self, parser):
        """Verify validate_config() rejects invalid column_mapping keys."""
        config = {
            "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
            "column_mapping": {
                "invalid_key": "Column Name"  # Should be 'sku', 'name', or 'price'
            }
        }
        
        with pytest.raises(ValidationError):
            parser.validate_config(config)
    
    def test_validate_config_rejects_data_start_row_before_header_row(self, parser):
        """Verify validate_config() rejects data_start_row <= header_row."""
        config = {
            "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
            "header_row": 2,
            "data_start_row": 1  # Must be > header_row
        }
        
        with pytest.raises(ValidationError):
            parser.validate_config(config)


class TestGoogleSheetsParserParse:
    """Test GoogleSheetsParser.parse() method with mocked gspread."""
    
    @pytest.fixture
    def parser(self):
        """Create a parser instance with mocked client."""
        with patch('src.parsers.google_sheets_parser.gspread.service_account'):
            return GoogleSheetsParser(credentials_path="/test/credentials.json")
    
    @pytest.fixture
    def mock_sheet_data(self):
        """Create mock sheet data for testing."""
        return {
            "headers": ["Product Code", "Description", "Price", "Color", "Size"],
            "rows": [
                ["SKU-001", "Product 1", "10.99", "Red", "M"],
                ["SKU-002", "Product 2", "20.50", "Blue", "L"],
                ["SKU-003", "Product 3", "15.00", "Green", "S"],
            ]
        }
    
    @pytest.fixture
    def mock_worksheet(self, mock_sheet_data):
        """Create a mocked worksheet with sample data."""
        mock_ws = Mock()
        # Return actual list values, not MagicMock
        # row_values is called with row number (1-indexed), return headers for row 1
        def row_values_side_effect(row_num):
            if row_num == 1:  # Header row
                return mock_sheet_data["headers"]
            return []
        mock_ws.row_values = Mock(side_effect=row_values_side_effect)
        mock_ws.get_all_values = Mock(return_value=(
            [mock_sheet_data["headers"]] + mock_sheet_data["rows"]
        ))
        return mock_ws
    
    @pytest.fixture
    def mock_spreadsheet(self, mock_worksheet):
        """Create a mocked spreadsheet with worksheet."""
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        return mock_spreadsheet
    
    @pytest.mark.asyncio
    async def test_parse_reads_all_rows_from_sheet(self, parser, mock_spreadsheet):
        """Verify parse() reads all rows from the specified sheet."""
        with patch.object(parser._client, 'open_by_key', return_value=mock_spreadsheet):
            config = {
                "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
                "sheet_name": "Sheet1",
                "header_row": 1,
                "data_start_row": 2
            }
            
            result = await parser.parse(config)
            
            assert len(result) == 3
            assert all(isinstance(item, ParsedSupplierItem) for item in result)
            parser._client.open_by_key.assert_called_once_with("abc123")
            mock_spreadsheet.worksheet.assert_called_once_with("Sheet1")
    
    @pytest.mark.asyncio
    async def test_parse_maps_columns_with_fuzzy_matching(self, parser, mock_spreadsheet):
        """Verify parse() uses fuzzy matching to map columns."""
        with patch.object(parser._client, 'open_by_key', return_value=mock_spreadsheet):
            config = {
                "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
                "sheet_name": "Sheet1",
                "header_row": 1,
                "data_start_row": 2
            }
            
            result = await parser.parse(config)
            
            # Verify columns were mapped correctly
            assert result[0].supplier_sku == "SKU-001"
            assert result[0].name == "Product 1"
            assert result[0].price == Decimal("10.99")
    
    @pytest.mark.asyncio
    async def test_parse_uses_manual_column_mapping_override(self, parser, mock_spreadsheet):
        """Verify parse() uses manual column_mapping when provided."""
        with patch.object(parser._client, 'open_by_key', return_value=mock_spreadsheet):
            config = {
                "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
                "sheet_name": "Sheet1",
                "column_mapping": {
                    "sku": "Product Code",
                    "name": "Description",
                    "price": "Price"
                },
                "header_row": 1,
                "data_start_row": 2
            }
            
            result = await parser.parse(config)
            
            # Verify manual mapping was used
            assert result[0].supplier_sku == "SKU-001"
            assert result[0].name == "Product 1"
            assert result[0].price == Decimal("10.99")
    
    @pytest.mark.asyncio
    async def test_parse_extracts_characteristics_from_columns(self, parser, mock_spreadsheet):
        """Verify parse() extracts characteristics from additional columns."""
        with patch.object(parser._client, 'open_by_key', return_value=mock_spreadsheet):
            config = {
                "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
                "sheet_name": "Sheet1",
                "characteristic_columns": ["Color", "Size"],
                "header_row": 1,
                "data_start_row": 2
            }
            
            result = await parser.parse(config)
            
            # Verify characteristics were extracted
            # Note: Parser normalizes header names to lowercase with underscores
            assert result[0].characteristics == {"color": "Red", "size": "M"}
            assert result[1].characteristics == {"color": "Blue", "size": "L"}
    
    @pytest.mark.asyncio
    async def test_parse_handles_missing_price_gracefully(self, parser):
        """Verify parse() handles missing price without crashing."""
        # Create sheet data with missing price
        mock_ws = Mock()
        # Return actual list values, not MagicMock
        # row_values is called with row number (1-indexed), return headers for row 1
        def row_values_side_effect(row_num):
            if row_num == 1:  # Header row
                return ["Product Code", "Description", "Price", "Color"]
            return []
        mock_ws.row_values = Mock(side_effect=row_values_side_effect)
        mock_ws.get_all_values = Mock(return_value=[
            ["Product Code", "Description", "Price", "Color"],
            ["SKU-001", "Product 1", "", "Red"],  # Missing price
            ["SKU-002", "Product 2", "20.50", "Blue"],
        ])
        
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        
        with patch.object(parser._client, 'open_by_key', return_value=mock_spreadsheet):
            config = {
                "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
                "sheet_name": "Sheet1",
                "header_row": 1,
                "data_start_row": 2
            }
            
            # Should return only valid items (one with price)
            result = await parser.parse(config)
            
            # Should have 1 valid item (the one with price)
            assert len(result) == 1
            assert result[0].supplier_sku == "SKU-002"
            assert result[0].price == Decimal("20.50")
    
    @pytest.mark.asyncio
    async def test_parse_normalizes_price_to_2_decimal_places(self, parser):
        """Verify parse() normalizes prices to 2 decimal places."""
        # Create sheet data with prices having more than 2 decimal places
        mock_ws = Mock()
        # Return actual list values, not MagicMock
        # row_values is called with row number (1-indexed), return headers for row 1
        def row_values_side_effect(row_num):
            if row_num == 1:  # Header row
                return ["Product Code", "Description", "Price"]
            return []
        mock_ws.row_values = Mock(side_effect=row_values_side_effect)
        mock_ws.get_all_values = Mock(return_value=[
            ["Product Code", "Description", "Price"],
            ["SKU-001", "Product 1", "10.999"],  # 3 decimal places
            ["SKU-002", "Product 2", "20.5"],    # 1 decimal place
        ])
        
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_ws
        
        with patch.object(parser._client, 'open_by_key', return_value=mock_spreadsheet):
            config = {
                "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
                "sheet_name": "Sheet1",
                "header_row": 1,
                "data_start_row": 2
            }
            
            result = await parser.parse(config)
            
            # Verify prices are normalized
            assert result[0].price == Decimal("11.00")  # Rounded from 10.999
            assert result[1].price == Decimal("20.50")   # Padded to 2 decimals
    
    @pytest.mark.asyncio
    async def test_parse_raises_error_on_sheet_not_found(self, parser):
        """Verify parse() raises ParserError when sheet is not found."""
        from gspread.exceptions import SpreadsheetNotFound
        
        with patch.object(
            parser._client,
            'open_by_key',
            side_effect=SpreadsheetNotFound("Sheet not found")
        ):
            config = {
                "sheet_url": "https://docs.google.com/spreadsheets/d/invalid/edit",
                "sheet_name": "Sheet1"
            }
            
            with pytest.raises(ParserError) as exc_info:
                await parser.parse(config)
            
            assert "not found" in str(exc_info.value).lower() or "spreadsheet" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_parse_raises_error_on_worksheet_not_found(self, parser):
        """Verify parse() raises ParserError when worksheet tab is not found."""
        from gspread.exceptions import WorksheetNotFound
        
        mock_spreadsheet = Mock()
        mock_spreadsheet.worksheet.side_effect = WorksheetNotFound("Worksheet not found")
        # Parser tries to list available worksheets, so we need to mock worksheets() method
        mock_worksheet1 = Mock()
        mock_worksheet1.title = "Sheet1"
        mock_worksheet2 = Mock()
        mock_worksheet2.title = "Sheet2"
        mock_spreadsheet.worksheets = Mock(return_value=[mock_worksheet1, mock_worksheet2])
        
        with patch.object(parser._client, 'open_by_key', return_value=mock_spreadsheet):
            config = {
                "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
                "sheet_name": "NonExistentSheet"
            }
            
            with pytest.raises(ParserError) as exc_info:
                await parser.parse(config)
            
            assert "not found" in str(exc_info.value).lower() or "worksheet" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_parse_raises_error_on_api_error(self, parser):
        """Verify parse() raises ParserError on Google Sheets API errors."""
        from gspread.exceptions import APIError
        from unittest.mock import Mock as MockResponse
        
        # Create a mock response object that APIError expects
        # APIError expects response with 'error' dict containing 'code' and 'message'
        mock_response = MockResponse()
        mock_response.status = 403
        mock_response.text = "Forbidden"
        # APIError.__init__ accesses response.error["code"], so we need to provide that structure
        mock_response.error = {"code": 403, "message": "Forbidden"}
        # Use patch.object() to configure mock method instead of direct assignment
        with patch.object(mock_response, 'json', return_value={"error": {"code": 403, "message": "Forbidden"}}), \
             patch.object(
                parser._client,
                'open_by_key',
                side_effect=APIError(mock_response)
             ):
            config = {
                "sheet_url": "https://docs.google.com/spreadsheets/d/abc123/edit",
                "sheet_name": "Sheet1"
            }
            
            with pytest.raises(ParserError) as exc_info:
                await parser.parse(config)
            
            assert "api" in str(exc_info.value).lower() or "error" in str(exc_info.value).lower()


class TestGoogleSheetsParserGetParserName:
    """Test GoogleSheetsParser.get_parser_name() method."""
    
    @pytest.fixture
    def parser(self):
        """Create a parser instance with mocked client."""
        with patch('src.parsers.google_sheets_parser.gspread.service_account'):
            return GoogleSheetsParser(credentials_path="/test/credentials.json")
    
    def test_get_parser_name_returns_google_sheets(self, parser):
        """Verify get_parser_name() returns 'google_sheets'."""
        assert parser.get_parser_name() == "google_sheets"


class TestGoogleSheetsParserInheritance:
    """Test that GoogleSheetsParser properly inherits from ParserInterface."""
    
    def test_google_sheets_parser_inherits_from_parser_interface(self):
        """Verify GoogleSheetsParser inherits from ParserInterface."""
        assert issubclass(GoogleSheetsParser, ParserInterface)
    
    def test_google_sheets_parser_implements_all_abstract_methods(self):
        """Verify GoogleSheetsParser implements all required abstract methods."""
        with patch('src.parsers.google_sheets_parser.gspread.service_account'):
            parser = GoogleSheetsParser(credentials_path="/test/credentials.json")
            
            assert hasattr(parser, 'parse')
            assert hasattr(parser, 'validate_config')
            assert hasattr(parser, 'get_parser_name')
            
            # Verify methods are not abstract
            assert not getattr(parser.parse, '__isabstractmethod__', False)
            assert not getattr(parser.validate_config, '__isabstractmethod__', False)
            assert not getattr(parser.get_parser_name, '__isabstractmethod__', False)

