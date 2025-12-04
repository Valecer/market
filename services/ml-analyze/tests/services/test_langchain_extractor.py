"""
Unit Tests for LangChainExtractor
=================================

Tests LLM-based extraction with mocked Ollama responses.

Phase 9: Semantic ETL Pipeline Refactoring
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.schemas.extraction import ExtractedProduct
from src.services.smart_parser.langchain_extractor import (
    LangChainExtractor,
    LLMExtractionError,
)


@pytest.fixture
def mock_llm_response() -> MagicMock:
    """Create a mock LLM response."""
    response = MagicMock()
    response.content = json.dumps({
        "products": [
            {
                "name": "Product A",
                "price_rrc": 100.50,
                "price_opt": 80.00,
                "description": "A test product",
                "category_path": ["Electronics", "Laptops"],
            },
            {
                "name": "Product B",
                "price_rrc": 200.00,
                "category_path": ["Furniture"],
            },
        ]
    })
    return response


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings."""
    settings = MagicMock()
    settings.ollama_llm_model = "llama3"
    settings.ollama_base_url = "http://localhost:11434"
    return settings


class TestLangChainExtractor:
    """Tests for LangChainExtractor class."""
    
    def test_init_default_values(self, mock_settings: MagicMock) -> None:
        """Test default initialization values."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                assert extractor.model_name == "llama3"
                assert extractor.base_url == "http://localhost:11434"
                assert extractor.temperature == 0.2
                assert extractor.chunk_size == 250
                assert extractor.chunk_overlap == 40
    
    def test_init_custom_values(self, mock_settings: MagicMock) -> None:
        """Test custom initialization values."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor(
                    model_name="custom-model",
                    temperature=0.5,
                    chunk_size=100,
                    chunk_overlap=20,
                )
                
                assert extractor.model_name == "custom-model"
                assert extractor.temperature == 0.5
                assert extractor.chunk_size == 100
                assert extractor.chunk_overlap == 20
    
    def test_clean_price_integer(self, mock_settings: MagicMock) -> None:
        """Test price cleaning with integer."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                assert extractor._clean_price(100) == 100.0
    
    def test_clean_price_float(self, mock_settings: MagicMock) -> None:
        """Test price cleaning with float."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                assert extractor._clean_price(99.99) == 99.99
    
    def test_clean_price_string(self, mock_settings: MagicMock) -> None:
        """Test price cleaning with string."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                assert extractor._clean_price("100.50") == 100.50
    
    def test_clean_price_with_currency(self, mock_settings: MagicMock) -> None:
        """Test price cleaning removes currency symbols."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                assert extractor._clean_price("100.50 р.") == 100.50
                assert extractor._clean_price("100.50 руб.") == 100.50
                assert extractor._clean_price("100.50 BYN") == 100.50
                assert extractor._clean_price("$100.50") == 100.50
                assert extractor._clean_price("€100.50") == 100.50
    
    def test_clean_price_comma_decimal(self, mock_settings: MagicMock) -> None:
        """Test price cleaning with comma decimal separator."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                assert extractor._clean_price("100,50") == 100.50
    
    def test_clean_price_with_spaces(self, mock_settings: MagicMock) -> None:
        """Test price cleaning removes thousand separators."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                assert extractor._clean_price("1 234.56") == 1234.56
    
    def test_clean_price_range(self, mock_settings: MagicMock) -> None:
        """Test price cleaning takes first value from range."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                assert extractor._clean_price("100-150") == 100.0
    
    def test_clean_price_none(self, mock_settings: MagicMock) -> None:
        """Test price cleaning with None value."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                assert extractor._clean_price(None) is None
    
    def test_clean_price_invalid(self, mock_settings: MagicMock) -> None:
        """Test price cleaning with invalid value."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                assert extractor._clean_price("not a price") is None
    
    def test_fix_common_json_issues_markdown(self, mock_settings: MagicMock) -> None:
        """Test JSON fixing removes markdown code blocks."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                text = '```json\n{"key": "value"}\n```'
                fixed = extractor._fix_common_json_issues(text)
                
                assert "```" not in fixed
                assert '{"key": "value"}' in fixed
    
    def test_parse_llm_response_valid(
        self, mock_settings: MagicMock
    ) -> None:
        """Test parsing valid LLM response."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                response_text = json.dumps({
                    "products": [
                        {"name": "Test Product", "price_rrc": 100.00}
                    ]
                })
                
                products, errors = extractor._parse_llm_response(
                    response_text, chunk_id=0, start_row=1
                )
                
                assert len(products) == 1
                assert len(errors) == 0
                assert products[0].name == "Test Product"
                assert products[0].price_rrc == Decimal("100")
    
    def test_parse_llm_response_array(
        self, mock_settings: MagicMock
    ) -> None:
        """Test parsing response as direct array."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                response_text = json.dumps([
                    {"name": "Product 1", "price_rrc": 100.00},
                    {"name": "Product 2", "price_rrc": 200.00},
                ])
                
                products, errors = extractor._parse_llm_response(
                    response_text, chunk_id=0, start_row=1
                )
                
                assert len(products) == 2
    
    def test_parse_llm_response_missing_name(
        self, mock_settings: MagicMock
    ) -> None:
        """Test parsing response with missing required field."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                response_text = json.dumps([
                    {"price_rrc": 100.00}  # Missing name
                ])
                
                products, errors = extractor._parse_llm_response(
                    response_text, chunk_id=0, start_row=1
                )
                
                # Should not create product without name
                assert len(products) == 0
    
    def test_remove_overlap_duplicates(
        self, mock_settings: MagicMock
    ) -> None:
        """Test removing duplicates from chunk overlaps."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                products = [
                    ExtractedProduct(name="Product A", price_rrc=Decimal("100.00")),
                    ExtractedProduct(name="Product A", price_rrc=Decimal("100.00")),
                    ExtractedProduct(name="Product B", price_rrc=Decimal("200.00")),
                ]
                
                unique = extractor._remove_overlap_duplicates(products)
                
                assert len(unique) == 2
    
    def test_validate_product_data_field_variations(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that various field name variations are handled."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                # Russian field names
                product = extractor._validate_product_data({
                    "название": "Product A",
                    "цена": 100.00,
                })
                
                assert product is not None
                assert product.name == "Product A"
    
    def test_validate_product_data_category_string(
        self, mock_settings: MagicMock
    ) -> None:
        """Test category path parsing from string."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                product = extractor._validate_product_data({
                    "name": "Product A",
                    "price_rrc": 100.00,
                    "category": "Electronics / Laptops / Gaming",
                })
                
                assert product is not None
                assert product.category_path == ["Electronics", "Laptops", "Gaming"]


class TestLangChainExtractorAsync:
    """Async tests for LangChainExtractor."""
    
    @pytest.mark.asyncio
    async def test_extract_from_markdown_small_table(
        self,
        mock_settings: MagicMock,
        mock_llm_response: MagicMock,
    ) -> None:
        """Test extraction from a small markdown table."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
            
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama", return_value=mock_llm):
                extractor = LangChainExtractor()
                extractor.llm = mock_llm
                
                markdown = """
                | Name | Price | Category |
                |------|-------|----------|
                | Product A | 100.50 | Electronics |
                """
                
                result = await extractor.extract_from_markdown(
                    markdown_table=markdown,
                    sheet_name="Test",
                    total_rows=1,
                )
                
                assert result.sheet_name == "Test"
                assert len(result.products) == 2  # From mock response
    
    @pytest.mark.asyncio
    async def test_extract_from_chunks_empty(
        self, mock_settings: MagicMock
    ) -> None:
        """Test extraction from empty chunks list."""
        with patch("src.services.smart_parser.langchain_extractor.Settings", return_value=mock_settings):
            with patch("src.services.smart_parser.langchain_extractor.ChatOllama"):
                extractor = LangChainExtractor()
                
                result = await extractor.extract_from_chunks(
                    chunks=[],
                    sheet_name="Empty",
                )
                
                assert result.sheet_name == "Empty"
                assert len(result.products) == 0
                assert result.total_rows == 0

