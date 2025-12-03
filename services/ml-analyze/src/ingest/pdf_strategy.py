"""
PDF Strategy - Complex PDF Table Extractor
==========================================

Parses PDF files containing tabular data using pymupdf4llm.
Extracts tables as Markdown and converts to structured data.

Key Features:
- Table detection with multiple strategies
- Markdown-based extraction preserving structure
- Multi-page document support
- Handles scanned PDFs with text layers

Follows Strategy Pattern: Implements TableNormalizer interface.
"""

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID

import pymupdf4llm

from src.ingest.table_normalizer import (
    ParseResult,
    ParserError,
    TableNormalizer,
)
from src.schemas.domain import NormalizedRow
from src.utils.errors import ParsingError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PdfStrategy(TableNormalizer):
    """
    PDF parsing strategy using pymupdf4llm.

    Uses pymupdf4llm to extract text and tables from PDFs as Markdown,
    then parses the Markdown tables into structured data.

    Extraction Flow:
        1. PDF → Markdown (via pymupdf4llm.to_markdown)
        2. Markdown → Table blocks (regex extraction)
        3. Table blocks → List of dicts (row parsing)
        4. List of dicts → NormalizedRow objects

    Table Detection Strategies:
        - lines_strict: Tables with visible cell borders
        - lines: Tables with partial borders
        - text: Text-aligned tables without borders
        - explicit: User-defined table regions
    """

    # Field patterns for header detection (Russian + English)
    FIELD_PATTERNS = {
        "name": ["название", "наименование", "товар", "модель", "name", "product", "item", "description"],
        "price": ["цена", "стоимость", "price", "cost", "amount"],
        "sku": ["артикул", "код", "sku", "code", "product_id"],
        "category": ["категория", "раздел", "group", "category"],
        "brand": ["бренд", "производитель", "brand", "manufacturer"],
        "unit": ["ед.", "единица", "unit", "uom"],
        "description": ["описание", "характеристики", "description", "details"],
    }

    # Regex pattern for Markdown table extraction
    TABLE_PATTERN = re.compile(
        r"^\|(.+)\|$\n^\|[-:| ]+\|$\n((?:^\|.+\|$\n?)+)",
        re.MULTILINE,
    )

    def __init__(
        self,
        pages: list[int] | None = None,
        table_strategy: str = "lines_strict",
        extract_images: bool = False,
        dpi: int = 150,
    ) -> None:
        """
        Initialize PDF strategy.

        Args:
            pages: Specific page indices to process (0-based), None = all
            table_strategy: Strategy for table detection:
                - "lines_strict": Tables with clear borders (most reliable)
                - "lines": Tables with partial borders
                - "text": Text-aligned tables
                - "explicit": User-defined regions
            extract_images: Whether to extract images from PDF
            dpi: Resolution for image extraction
        """
        self._pages = pages
        self._table_strategy = table_strategy
        self._extract_images = extract_images
        self._dpi = dpi
        logger.debug(
            "PdfStrategy initialized",
            pages=pages,
            table_strategy=table_strategy,
            extract_images=extract_images,
        )

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        return ["pdf"]

    async def parse(
        self,
        file_path: str | Path,
        supplier_id: UUID | None = None,
    ) -> list[NormalizedRow]:
        """
        Parse PDF file and return normalized rows.

        Args:
            file_path: Path to PDF file
            supplier_id: Optional supplier ID for context

        Returns:
            List of NormalizedRow objects

        Raises:
            ParsingError: If file cannot be parsed
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path

        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")

        logger.info(
            "Parsing PDF file",
            file_path=str(path),
            supplier_id=supplier_id,
            table_strategy=self._table_strategy,
        )

        try:
            # Extract content as Markdown
            md_text = pymupdf4llm.to_markdown(
                str(path),
                pages=self._pages,
                table_strategy=self._table_strategy,
                write_images=self._extract_images,
                dpi=self._dpi,
            )

            if not md_text or not md_text.strip():
                logger.warning("Empty PDF content", file_path=str(path))
                return []

            # Extract tables from Markdown
            tables = self._extract_tables_from_markdown(md_text)

            if not tables:
                logger.warning(
                    "No tables found in PDF",
                    file_path=str(path),
                    content_length=len(md_text),
                )
                return []

            # Convert tables to normalized rows
            all_rows: list[NormalizedRow] = []
            for table_idx, table_data in enumerate(tables):
                rows = self._convert_table_to_normalized_rows(table_data, table_idx)
                all_rows.extend(rows)

            logger.info(
                "PDF parsing complete",
                file_path=str(path),
                tables_found=len(tables),
                normalized_rows=len(all_rows),
            )

            return all_rows

        except Exception as e:
            if isinstance(e, (ParsingError, FileNotFoundError)):
                raise
            logger.error("PDF parsing failed", file_path=str(path), error=str(e))
            raise ParsingError(
                message=f"Failed to parse PDF file: {e}",
                details={"file_path": str(path), "error": str(e)},
            ) from e

    async def validate_file(self, file_path: str | Path) -> bool:
        """
        Validate that file can be parsed.

        Args:
            file_path: Path to file

        Returns:
            True if file can be parsed
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path

        if not path.exists():
            return False

        if not self.can_handle(path):
            return False

        try:
            # Try to extract content
            md_text = pymupdf4llm.to_markdown(str(path), pages=[0])
            return bool(md_text and md_text.strip())
        except Exception:
            return False

    def _extract_tables_from_markdown(
        self,
        md_text: str,
    ) -> list[list[dict[str, str]]]:
        """
        Extract table data from Markdown text.

        Args:
            md_text: Markdown-formatted text from PDF

        Returns:
            List of tables, each table is a list of row dicts
        """
        tables: list[list[dict[str, str]]] = []

        # Find all Markdown tables
        for match in self.TABLE_PATTERN.finditer(md_text):
            header_line = match.group(1)
            body = match.group(2)

            # Parse header columns
            headers = [h.strip() for h in header_line.split("|") if h.strip()]

            if not headers:
                continue

            # Parse body rows
            table_rows: list[dict[str, str]] = []
            for line in body.strip().split("\n"):
                if not line.strip() or line.startswith("|--"):
                    continue

                cells = [c.strip() for c in line.split("|")]
                # Remove empty first/last cells from split
                cells = [c for c in cells if c or cells.index(c) not in (0, len(cells) - 1)]

                if len(cells) >= len(headers):
                    row_dict = dict(zip(headers, cells[: len(headers)]))
                    # Include extra columns if any
                    for i, cell in enumerate(cells[len(headers):], start=len(headers)):
                        row_dict[f"col_{i}"] = cell
                    table_rows.append(row_dict)
                elif cells:
                    # Pad with empty strings
                    row_dict = dict(zip(headers, cells + [""] * (len(headers) - len(cells))))
                    table_rows.append(row_dict)

            if table_rows:
                tables.append(table_rows)

        # Also try to extract from page chunks if no tables found via regex
        if not tables:
            tables = self._extract_tables_from_text_blocks(md_text)

        logger.debug(
            "Tables extracted from Markdown",
            table_count=len(tables),
            total_rows=sum(len(t) for t in tables),
        )

        return tables

    def _extract_tables_from_text_blocks(
        self,
        md_text: str,
    ) -> list[list[dict[str, str]]]:
        """
        Fallback table extraction from text blocks.

        Attempts to detect table-like structures from plain text
        when Markdown table format is not present.

        Args:
            md_text: Text content

        Returns:
            List of extracted tables
        """
        tables: list[list[dict[str, str]]] = []

        # Look for lines with multiple tab or multi-space separators
        lines = md_text.split("\n")
        current_table: list[list[str]] = []
        headers: list[str] | None = None

        for line in lines:
            # Check if line looks like a table row (has multiple fields)
            if "\t" in line:
                cells = [c.strip() for c in line.split("\t") if c.strip()]
            elif "  " in line:
                # Split on multiple spaces
                cells = [c.strip() for c in re.split(r"\s{2,}", line) if c.strip()]
            else:
                cells = []

            if len(cells) >= 2:
                if headers is None:
                    # First row with multiple columns is header
                    headers = cells
                    current_table = []
                else:
                    current_table.append(cells)
            elif current_table and headers:
                # End of table block
                if len(current_table) >= 1:
                    table_dicts = [
                        dict(zip(headers, row + [""] * (len(headers) - len(row))))
                        for row in current_table
                    ]
                    tables.append(table_dicts)
                headers = None
                current_table = []

        # Don't forget last table
        if current_table and headers:
            table_dicts = [
                dict(zip(headers, row + [""] * (len(headers) - len(row))))
                for row in current_table
            ]
            tables.append(table_dicts)

        return tables

    def _convert_table_to_normalized_rows(
        self,
        table_data: list[dict[str, str]],
        table_index: int,
    ) -> list[NormalizedRow]:
        """
        Convert a table's row dicts to NormalizedRow objects.

        Args:
            table_data: List of row dictionaries
            table_index: Index of this table in the document

        Returns:
            List of NormalizedRow objects
        """
        if not table_data:
            return []

        # Detect column mapping from first row's keys
        columns = list(table_data[0].keys())
        column_mapping = self._detect_column_mapping(columns)

        rows: list[NormalizedRow] = []

        for row_idx, row in enumerate(table_data):
            try:
                # Extract name field (required)
                name_col = column_mapping.get("name")
                name = row.get(name_col, "").strip() if name_col else ""

                # Try alternative: use first non-empty column if no name detected
                if not name:
                    for col in columns:
                        val = row.get(col, "").strip()
                        if val and len(val) > 2:
                            name = val
                            break

                if not name:
                    continue  # Skip rows without a name

                # Extract other fields
                price = self._parse_price(row, column_mapping)
                sku = self._extract_field(row, column_mapping, "sku")
                category = self._extract_field(row, column_mapping, "category")
                brand = self._extract_field(row, column_mapping, "brand")
                unit = self._extract_field(row, column_mapping, "unit")
                description = self._extract_field(row, column_mapping, "description")

                # Build characteristics
                characteristics = self._extract_characteristics(row, column_mapping)
                characteristics["_source_table"] = table_index
                characteristics["_source_row"] = row_idx + 1

                normalized = NormalizedRow(
                    name=name,
                    description=description,
                    price=price,
                    sku=sku,
                    category=category,
                    brand=brand,
                    unit=unit,
                    characteristics=characteristics,
                    raw_data=row,
                )
                rows.append(normalized)

            except Exception as e:
                logger.warning(
                    "Row conversion failed",
                    table_index=table_index,
                    row_index=row_idx,
                    error=str(e),
                )

        return rows

    def _detect_column_mapping(self, columns: list[str]) -> dict[str, str]:
        """Map columns to standard fields."""
        mapping: dict[str, str] = {}
        columns_lower = {c: c.lower() for c in columns}

        for field, patterns in self.FIELD_PATTERNS.items():
            for col, col_lower in columns_lower.items():
                if any(pattern in col_lower for pattern in patterns):
                    if field not in mapping:
                        mapping[field] = col
                        break

        logger.debug("Column mapping detected", mapping=mapping)
        return mapping

    def _parse_price(
        self,
        row: dict[str, str],
        column_mapping: dict[str, str],
    ) -> Decimal | None:
        """Parse price from row."""
        price_col = column_mapping.get("price")
        if not price_col:
            return None

        value = row.get(price_col, "").strip()
        if not value:
            return None

        try:
            # Clean price string
            cleaned = re.sub(r"[^\d.,]", "", value)
            cleaned = cleaned.replace(",", ".")
            # Handle multiple decimal points
            if cleaned.count(".") > 1:
                parts = cleaned.rsplit(".", 1)
                cleaned = parts[0].replace(".", "") + "." + parts[1]
            return Decimal(cleaned) if cleaned else None
        except (InvalidOperation, ValueError):
            return None

    def _extract_field(
        self,
        row: dict[str, str],
        column_mapping: dict[str, str],
        field: str,
    ) -> str | None:
        """Extract a text field from row."""
        col = column_mapping.get(field)
        if not col:
            return None

        value = row.get(col, "").strip()
        return value if value else None

    def _extract_characteristics(
        self,
        row: dict[str, str],
        column_mapping: dict[str, str],
    ) -> dict[str, Any]:
        """Extract unmapped columns as characteristics."""
        mapped_cols = set(column_mapping.values())
        characteristics: dict[str, Any] = {}

        for col, value in row.items():
            if col not in mapped_cols and value:
                value_str = value.strip()
                if value_str:
                    characteristics[col] = value_str

        return characteristics

