"""
Unit Tests for PdfStrategy
===========================

Tests for PDF file parsing using pymupdf4llm.
"""

from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.ingest.pdf_strategy import PdfStrategy
from src.schemas.domain import NormalizedRow


@pytest.fixture
def pdf_strategy() -> PdfStrategy:
    """Create default PdfStrategy instance."""
    return PdfStrategy()


@pytest.fixture
def sample_markdown_table() -> str:
    """Create sample Markdown table content."""
    return """
# Price List

| Название | Цена | Артикул |
|----------|------|---------|
| Товар 1  | 100  | SKU-001 |
| Товар 2  | 200  | SKU-002 |
| Товар 3  | 300  | SKU-003 |

Some text after table.
"""


@pytest.fixture
def sample_markdown_multiple_tables() -> str:
    """Create Markdown with multiple tables."""
    return """
## Category A

| Product | Price |
|---------|-------|
| Item A1 | 10.00 |
| Item A2 | 20.00 |

## Category B

| Product | Price |
|---------|-------|
| Item B1 | 30.00 |
| Item B2 | 40.00 |
"""


class TestPdfStrategySupportedExtensions:
    """Tests for supported_extensions property."""

    def test_supports_pdf(self, pdf_strategy: PdfStrategy) -> None:
        """Should support .pdf files."""
        assert "pdf" in pdf_strategy.supported_extensions

    def test_only_supports_pdf(self, pdf_strategy: PdfStrategy) -> None:
        """Should only support .pdf files."""
        assert pdf_strategy.supported_extensions == ["pdf"]


class TestPdfStrategyCanHandle:
    """Tests for can_handle method."""

    def test_can_handle_pdf(self, pdf_strategy: PdfStrategy) -> None:
        """Should handle .pdf files."""
        assert pdf_strategy.can_handle("file.pdf")

    def test_can_handle_pdf_uppercase(self, pdf_strategy: PdfStrategy) -> None:
        """Should handle .PDF files (case insensitive)."""
        assert pdf_strategy.can_handle("file.PDF")

    def test_cannot_handle_xlsx(self, pdf_strategy: PdfStrategy) -> None:
        """Should not handle .xlsx files."""
        assert not pdf_strategy.can_handle("file.xlsx")

    def test_cannot_handle_docx(self, pdf_strategy: PdfStrategy) -> None:
        """Should not handle .docx files."""
        assert not pdf_strategy.can_handle("file.docx")


class TestPdfStrategyTableExtraction:
    """Tests for Markdown table extraction."""

    def test_extract_single_table(
        self,
        pdf_strategy: PdfStrategy,
        sample_markdown_table: str,
    ) -> None:
        """Should extract single table from Markdown."""
        tables = pdf_strategy._extract_tables_from_markdown(sample_markdown_table)

        assert len(tables) == 1
        assert len(tables[0]) == 3  # 3 data rows

    def test_extract_multiple_tables(
        self,
        pdf_strategy: PdfStrategy,
        sample_markdown_multiple_tables: str,
    ) -> None:
        """Should extract multiple tables from Markdown."""
        tables = pdf_strategy._extract_tables_from_markdown(sample_markdown_multiple_tables)

        assert len(tables) == 2
        assert len(tables[0]) == 2  # 2 rows in first table
        assert len(tables[1]) == 2  # 2 rows in second table

    def test_extract_table_preserves_headers(
        self,
        pdf_strategy: PdfStrategy,
        sample_markdown_table: str,
    ) -> None:
        """Extracted tables should use headers as keys."""
        tables = pdf_strategy._extract_tables_from_markdown(sample_markdown_table)

        first_row = tables[0][0]
        assert "Название" in first_row
        assert "Цена" in first_row
        assert "Артикул" in first_row

    def test_extract_table_values(
        self,
        pdf_strategy: PdfStrategy,
        sample_markdown_table: str,
    ) -> None:
        """Extracted tables should have correct values."""
        tables = pdf_strategy._extract_tables_from_markdown(sample_markdown_table)

        first_row = tables[0][0]
        assert first_row["Название"] == "Товар 1"
        assert first_row["Цена"] == "100"
        assert first_row["Артикул"] == "SKU-001"

    def test_extract_no_tables(
        self,
        pdf_strategy: PdfStrategy,
    ) -> None:
        """Empty result when no tables found."""
        markdown = "# Header\n\nJust some text without tables."
        tables = pdf_strategy._extract_tables_from_markdown(markdown)

        assert tables == []


class TestPdfStrategyConversion:
    """Tests for converting table data to NormalizedRow."""

    def test_convert_table_to_rows(
        self,
        pdf_strategy: PdfStrategy,
    ) -> None:
        """Should convert table dict list to NormalizedRow list."""
        table_data = [
            {"Название": "Product A", "Цена": "100", "Артикул": "SKU-A"},
            {"Название": "Product B", "Цена": "200", "Артикул": "SKU-B"},
        ]

        rows = pdf_strategy._convert_table_to_normalized_rows(table_data, 0)

        assert len(rows) == 2
        assert all(isinstance(r, NormalizedRow) for r in rows)

    def test_convert_extracts_name(
        self,
        pdf_strategy: PdfStrategy,
    ) -> None:
        """Conversion should extract name field."""
        table_data = [{"Название": "Test Product", "Цена": "50"}]

        rows = pdf_strategy._convert_table_to_normalized_rows(table_data, 0)

        assert rows[0].name == "Test Product"

    def test_convert_extracts_price(
        self,
        pdf_strategy: PdfStrategy,
    ) -> None:
        """Conversion should extract price as Decimal."""
        table_data = [{"Название": "Product", "Цена": "123.45"}]

        rows = pdf_strategy._convert_table_to_normalized_rows(table_data, 0)

        assert rows[0].price == Decimal("123.45")

    def test_convert_handles_formatted_price(
        self,
        pdf_strategy: PdfStrategy,
    ) -> None:
        """Conversion should handle formatted prices (currency symbols, spaces)."""
        table_data = [{"Название": "Product", "Цена": "1 234,56 ₽"}]

        rows = pdf_strategy._convert_table_to_normalized_rows(table_data, 0)

        assert rows[0].price == Decimal("1234.56")

    def test_convert_adds_source_metadata(
        self,
        pdf_strategy: PdfStrategy,
    ) -> None:
        """Conversion should add source table index to characteristics."""
        table_data = [{"Название": "Product", "Цена": "100"}]

        rows = pdf_strategy._convert_table_to_normalized_rows(table_data, table_index=2)

        assert rows[0].characteristics.get("_source_table") == 2

    def test_convert_skips_empty_rows(
        self,
        pdf_strategy: PdfStrategy,
    ) -> None:
        """Conversion should skip rows without name."""
        table_data = [
            {"Название": "Valid Product", "Цена": "100"},
            {"Название": "", "Цена": "50"},  # Empty name
            {"Название": "Another Product", "Цена": "200"},
        ]

        rows = pdf_strategy._convert_table_to_normalized_rows(table_data, 0)

        assert len(rows) == 2
        assert rows[0].name == "Valid Product"
        assert rows[1].name == "Another Product"


class TestPdfStrategyParse:
    """Tests for parse method with mocked pymupdf4llm."""

    @pytest.mark.asyncio
    async def test_parse_calls_pymupdf4llm(
        self,
        pdf_strategy: PdfStrategy,
        sample_markdown_table: str,
        tmp_path: Path,
    ) -> None:
        """Parse should call pymupdf4llm.to_markdown."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        with patch("src.ingest.pdf_strategy.pymupdf4llm") as mock_pymupdf:
            mock_pymupdf.to_markdown.return_value = sample_markdown_table

            rows = await pdf_strategy.parse(pdf_file)

            mock_pymupdf.to_markdown.assert_called_once()
            assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_parse_nonexistent_file_raises(
        self,
        pdf_strategy: PdfStrategy,
    ) -> None:
        """Parse should raise FileNotFoundError for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            await pdf_strategy.parse("/nonexistent/file.pdf")

    @pytest.mark.asyncio
    async def test_parse_empty_content(
        self,
        pdf_strategy: PdfStrategy,
        tmp_path: Path,
    ) -> None:
        """Parse should return empty list for empty PDF."""
        pdf_file = tmp_path / "empty.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        with patch("src.ingest.pdf_strategy.pymupdf4llm") as mock_pymupdf:
            mock_pymupdf.to_markdown.return_value = ""

            rows = await pdf_strategy.parse(pdf_file)

            assert rows == []


class TestPdfStrategyConfiguration:
    """Tests for strategy configuration options."""

    def test_custom_pages(self) -> None:
        """Custom pages list should be respected."""
        strategy = PdfStrategy(pages=[0, 1, 2])
        assert strategy._pages == [0, 1, 2]

    def test_custom_table_strategy(self) -> None:
        """Custom table_strategy should be respected."""
        strategy = PdfStrategy(table_strategy="text")
        assert strategy._table_strategy == "text"

    def test_custom_extract_images(self) -> None:
        """Custom extract_images should be respected."""
        strategy = PdfStrategy(extract_images=True)
        assert strategy._extract_images is True

    def test_custom_dpi(self) -> None:
        """Custom dpi should be respected."""
        strategy = PdfStrategy(dpi=300)
        assert strategy._dpi == 300


class TestPdfStrategyColumnDetection:
    """Tests for automatic column detection."""

    def test_detect_russian_columns(
        self,
        pdf_strategy: PdfStrategy,
    ) -> None:
        """Should detect Russian column names."""
        columns = ["Название", "Цена", "Артикул"]
        mapping = pdf_strategy._detect_column_mapping(columns)

        assert mapping.get("name") == "Название"
        assert mapping.get("price") == "Цена"
        assert mapping.get("sku") == "Артикул"

    def test_detect_english_columns(
        self,
        pdf_strategy: PdfStrategy,
    ) -> None:
        """Should detect English column names."""
        columns = ["Product Name", "Price", "SKU"]
        mapping = pdf_strategy._detect_column_mapping(columns)

        assert mapping.get("name") == "Product Name"
        assert mapping.get("price") == "Price"
        assert mapping.get("sku") == "SKU"

    def test_detect_partial_match(
        self,
        pdf_strategy: PdfStrategy,
    ) -> None:
        """Should detect columns with partial pattern match."""
        columns = ["Product Description", "Unit Price", "Item Code"]
        mapping = pdf_strategy._detect_column_mapping(columns)

        assert mapping.get("price") == "Unit Price"
        assert mapping.get("sku") == "Item Code"


class TestPdfStrategyPriceParser:
    """Tests for price parsing edge cases."""

    def test_parse_integer_price(self, pdf_strategy: PdfStrategy) -> None:
        """Should parse integer prices."""
        row = {"Цена": "100"}
        mapping = {"price": "Цена"}
        price = pdf_strategy._parse_price(row, mapping)
        assert price == Decimal("100")

    def test_parse_decimal_price_dot(self, pdf_strategy: PdfStrategy) -> None:
        """Should parse decimal prices with dot."""
        row = {"Цена": "99.99"}
        mapping = {"price": "Цена"}
        price = pdf_strategy._parse_price(row, mapping)
        assert price == Decimal("99.99")

    def test_parse_decimal_price_comma(self, pdf_strategy: PdfStrategy) -> None:
        """Should parse decimal prices with comma."""
        row = {"Цена": "99,99"}
        mapping = {"price": "Цена"}
        price = pdf_strategy._parse_price(row, mapping)
        assert price == Decimal("99.99")

    def test_parse_price_with_currency(self, pdf_strategy: PdfStrategy) -> None:
        """Should strip currency symbols."""
        row = {"Цена": "$50.00"}
        mapping = {"price": "Цена"}
        price = pdf_strategy._parse_price(row, mapping)
        assert price == Decimal("50.00")

    def test_parse_empty_price(self, pdf_strategy: PdfStrategy) -> None:
        """Empty price should return None."""
        row = {"Цена": ""}
        mapping = {"price": "Цена"}
        price = pdf_strategy._parse_price(row, mapping)
        assert price is None

    def test_parse_invalid_price(self, pdf_strategy: PdfStrategy) -> None:
        """Invalid price should return None."""
        row = {"Цена": "N/A"}
        mapping = {"price": "Цена"}
        price = pdf_strategy._parse_price(row, mapping)
        assert price is None

