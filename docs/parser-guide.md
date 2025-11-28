# Parser Implementation Guide

**Purpose:** Guide for adding new data source parsers (CSV, Excel, etc.) to the data ingestion infrastructure.

**Target Audience:** Developers adding support for new data source formats.

**Estimated Time:** 2 hours for a basic parser implementation.

---

## Overview

The data ingestion system uses a pluggable parser architecture that allows new data sources to be added without modifying core service code. This guide walks through implementing a new parser, using the existing Google Sheets parser as a reference.

### Architecture

```
┌─────────────────┐
│  ParseTask      │
│  (Queue)        │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│   ParserRegistry         │
│   (Factory)              │
└────────┬─────────────────┘
         │
         ▼
┌─────────────────────────┐
│   ParserInterface        │◄─── Your Parser
│   (Abstract Base)        │
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│   ParsedSupplierItem    │
│   (Pydantic Model)       │
└─────────────────────────┘
```

---

## Step 1: Understand the Parser Interface

All parsers must implement the `ParserInterface` abstract base class:

```python
from src.parsers.base_parser import ParserInterface
from src.models.parsed_item import ParsedSupplierItem
from typing import List, Dict, Any

class YourParser(ParserInterface):
    async def parse(self, config: Dict[str, Any]) -> List[ParsedSupplierItem]:
        """Extract and validate data from source."""
        pass
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate parser-specific configuration."""
        pass
    
    def get_parser_name(self) -> str:
        """Return unique parser identifier."""
        pass
```

### Required Methods

1. **`parse(config)`** - Async method that:
   - Reads data from the source (file, API, database, etc.)
   - Maps columns to standard fields (sku, name, price)
   - Extracts characteristics from additional columns
   - Validates each row using `ParsedSupplierItem` Pydantic model
   - Returns list of validated items
   - Logs errors to `parsing_logs` table without crashing

2. **`validate_config(config)`** - Synchronous method that:
   - Validates configuration dictionary structure
   - Checks required fields are present
   - Validates field types and constraints
   - Raises `ValidationError` with descriptive message if invalid
   - Returns `True` if valid

3. **`get_parser_name()`** - Returns unique identifier (e.g., "csv", "excel")

---

## Step 2: Create Parser Configuration Model

Create a Pydantic model for your parser's configuration:

```python
# src/models/csv_config.py
from pydantic import BaseModel, Field, field_validator
from pathlib import Path
from typing import Dict, Optional, List

class CSVConfig(BaseModel):
    """Configuration for CSV parser."""
    
    file_path: str = Field(..., description="Path to CSV file")
    delimiter: str = Field(default=",", description="CSV delimiter")
    encoding: str = Field(default="utf-8", description="File encoding")
    column_mapping: Optional[Dict[str, str]] = Field(
        default=None,
        description="Manual column mapping (overrides auto-detection)"
    )
    characteristic_columns: Optional[List[str]] = Field(
        default=None,
        description="Columns to include in characteristics JSONB"
    )
    header_row: int = Field(default=0, ge=0, description="Row index with headers")
    skip_rows: int = Field(default=0, ge=0, description="Rows to skip before header")
    
    @field_validator('file_path')
    @classmethod
    def validate_file_exists(cls, v: str) -> str:
        """Validate file exists."""
        if not Path(v).exists():
            raise ValueError(f"CSV file not found: {v}")
        return v
```

---

## Step 3: Implement the Parser Class

Create your parser implementation:

```python
# src/parsers/csv_parser.py
import csv
import structlog
from pathlib import Path
from typing import List, Dict, Any
from decimal import Decimal, InvalidOperation
from difflib import get_close_matches

from src.parsers.base_parser import ParserInterface
from src.models.parsed_item import ParsedSupplierItem
from src.models.csv_config import CSVConfig
from src.errors.exceptions import ParserError, ValidationError

logger = structlog.get_logger(__name__)


class CSVParser(ParserInterface):
    """Parser for CSV files."""
    
    # Standard field names for fuzzy matching
    STANDARD_FIELDS = {
        'sku': ['sku', 'product code', 'item code', 'product_id', 'item_id', 'code'],
        'name': ['name', 'product name', 'description', 'product description', 'title', 'item'],
        'price': ['price', 'unit price', 'cost', 'unit cost', 'amount', 'value']
    }
    
    def __init__(self):
        """Initialize CSV parser."""
        pass
    
    async def parse(self, config: Dict[str, Any]) -> List[ParsedSupplierItem]:
        """Parse CSV file and return validated items.
        
        Args:
            config: CSVConfig dictionary
            
        Returns:
            List of ParsedSupplierItem objects
            
        Raises:
            ParserError: If file cannot be read or parsed
        """
        # Validate configuration
        csv_config = CSVConfig.model_validate(config)
        
        items = []
        file_path = Path(csv_config.file_path)
        
        try:
            with open(file_path, 'r', encoding=csv_config.encoding) as f:
                # Skip rows before header
                for _ in range(csv_config.skip_rows):
                    next(f, None)
                
                # Read CSV
                reader = csv.DictReader(f, delimiter=csv_config.delimiter)
                
                # Map columns if needed
                column_mapping = self._map_columns(
                    reader.fieldnames or [],
                    csv_config.column_mapping
                )
                
                # Process each row
                for row_num, row in enumerate(reader, start=csv_config.header_row + 2):
                    try:
                        item = self._parse_row(row, column_mapping, csv_config)
                        items.append(item)
                    except ValidationError as e:
                        # Log error but continue processing
                        logger.warning(
                            "Row validation failed",
                            row_number=row_num,
                            error=str(e),
                            row_data=row
                        )
                        # In production, this would log to parsing_logs table
                        continue
                    except Exception as e:
                        logger.error(
                            "Unexpected error parsing row",
                            row_number=row_num,
                            error=str(e),
                            exc_info=True
                        )
                        continue
        
        except FileNotFoundError:
            raise ParserError(f"CSV file not found: {file_path}")
        except Exception as e:
            raise ParserError(f"Failed to parse CSV file: {e}")
        
        logger.info(
            "CSV parsing complete",
            file_path=str(file_path),
            items_parsed=len(items)
        )
        
        return items
    
    def _map_columns(
        self,
        headers: List[str],
        manual_mapping: Optional[Dict[str, str]]
    ) -> Dict[str, str]:
        """Map CSV headers to standard fields.
        
        Args:
            headers: List of CSV column headers
            manual_mapping: Optional manual mapping override
            
        Returns:
            Dictionary mapping standard fields to CSV column names
        """
        if manual_mapping:
            return manual_mapping
        
        # Auto-detect using fuzzy matching
        mapping = {}
        for field, variations in self.STANDARD_FIELDS.items():
            matches = get_close_matches(
                field,
                headers,
                n=1,
                cutoff=0.6
            )
            if matches:
                mapping[field] = matches[0]
        
        return mapping
    
    def _parse_row(
        self,
        row: Dict[str, str],
        column_mapping: Dict[str, str],
        config: CSVConfig
    ) -> ParsedSupplierItem:
        """Parse a single CSV row into ParsedSupplierItem.
        
        Args:
            row: CSV row as dictionary
            column_mapping: Column mapping dictionary
            config: CSVConfig instance
            
        Returns:
            ParsedSupplierItem object
            
        Raises:
            ValidationError: If row data is invalid
        """
        # Extract standard fields
        sku = row.get(column_mapping.get('sku', ''), '').strip()
        name = row.get(column_mapping.get('name', ''), '').strip()
        price_str = row.get(column_mapping.get('price', ''), '').strip()
        
        # Validate required fields
        if not sku:
            raise ValidationError("Missing required field: supplier_sku")
        if not name:
            raise ValidationError("Missing required field: name")
        if not price_str:
            raise ValidationError("Missing required field: price")
        
        # Parse price
        try:
            price = Decimal(price_str)
            if price < 0:
                raise ValidationError("Price cannot be negative")
        except (InvalidOperation, ValueError) as e:
            raise ValidationError(f"Invalid price format: {price_str}")
        
        # Extract characteristics
        characteristics = {}
        if config.characteristic_columns:
            for col in config.characteristic_columns:
                if col in row and row[col].strip():
                    characteristics[col] = row[col].strip()
        else:
            # Include all non-mapped columns
            mapped_cols = set(column_mapping.values())
            for col, value in row.items():
                if col not in mapped_cols and value.strip():
                    characteristics[col] = value.strip()
        
        # Create and validate ParsedSupplierItem
        return ParsedSupplierItem(
            supplier_sku=sku,
            name=name,
            price=price,
            characteristics=characteristics
        )
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate CSV parser configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If configuration is invalid
        """
        try:
            CSVConfig.model_validate(config)
            return True
        except Exception as e:
            raise ValidationError(f"Invalid CSV configuration: {e}")
    
    def get_parser_name(self) -> str:
        """Return parser identifier.
        
        Returns:
            "csv" as the parser type identifier
        """
        return "csv"
```

---

## Step 4: Register the Parser

Register your parser in the parser registry:

```python
# src/parsers/__init__.py
from src.parsers.csv_parser import CSVParser
from src.parsers.parser_registry import register_parser

# Register CSV parser
register_parser("csv", CSVParser)
```

Or add it to the existing registry file:

```python
# src/parsers/parser_registry.py
from src.parsers.csv_parser import CSVParser

# ... existing code ...

# Register parsers
register_parser("stub", StubParser)
register_parser("google_sheets", GoogleSheetsParser)
register_parser("csv", CSVParser)  # Add this line
```

---

## Step 5: Update Queue Message Model

If your parser type isn't already in the `ParseTaskMessage` model, add it:

```python
# src/models/queue_message.py
parser_type: Literal["google_sheets", "csv", "excel", "stub"] = Field(
    ...,
    description="Type of parser to use"
)
```

---

## Step 6: Write Tests

Create unit tests for your parser:

```python
# tests/unit/test_csv_parser.py
import pytest
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch, mock_open

from src.parsers.csv_parser import CSVParser
from src.models.parsed_item import ParsedSupplierItem
from src.errors.exceptions import ParserError, ValidationError


class TestCSVParser:
    """Test CSV parser implementation."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return CSVParser()
    
    @pytest.fixture
    def sample_csv_data(self):
        """Sample CSV data."""
        return "Product Code,Description,Price,Color\nSKU-001,Product 1,10.99,Red\n"
    
    @pytest.mark.asyncio
    async def test_parse_reads_csv_file(self, parser, sample_csv_data, tmp_path):
        """Verify parse() reads CSV file correctly."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(sample_csv_data)
        
        config = {
            "file_path": str(csv_file),
            "delimiter": ",",
            "encoding": "utf-8"
        }
        
        result = await parser.parse(config)
        
        assert len(result) == 1
        assert result[0].supplier_sku == "SKU-001"
        assert result[0].name == "Product 1"
        assert result[0].price == Decimal("10.99")
    
    def test_validate_config_accepts_valid_config(self, parser):
        """Verify validate_config() accepts valid configuration."""
        config = {
            "file_path": "/path/to/file.csv",
            "delimiter": ",",
            "encoding": "utf-8"
        }
        
        result = parser.validate_config(config)
        assert result is True
    
    def test_get_parser_name_returns_csv(self, parser):
        """Verify get_parser_name() returns 'csv'."""
        assert parser.get_parser_name() == "csv"
```

---

## Step 7: Integration Testing

Test your parser with the end-to-end pipeline:

```python
# tests/integration/test_csv_parser_integration.py
import pytest
from pathlib import Path

from src.models.queue_message import ParseTaskMessage
from src.parsers.csv_parser import CSVParser


@pytest.mark.integration
async def test_csv_parser_end_to_end(tmp_path, db_session):
    """Test CSV parser with real database."""
    # Create test CSV file
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "Product Code,Description,Price\n"
        "SKU-001,Product 1,10.99\n"
        "SKU-002,Product 2,20.50\n"
    )
    
    # Create parse task
    message = ParseTaskMessage(
        task_id="test-csv-001",
        parser_type="csv",
        supplier_name="Test CSV Supplier",
        source_config={
            "file_path": str(csv_file),
            "delimiter": ",",
            "encoding": "utf-8"
        }
    )
    
    # Parse
    parser = CSVParser()
    items = await parser.parse(message.source_config)
    
    assert len(items) == 2
    # ... verify items are correct
```

---

## Best Practices

### Error Handling

1. **Row-level errors** should be logged but not stop processing:
   ```python
   try:
       item = self._parse_row(row, mapping, config)
       items.append(item)
   except ValidationError as e:
       logger.warning("Row validation failed", row_number=row_num, error=str(e))
       # Log to parsing_logs table in production
       continue
   ```

2. **File-level errors** should raise `ParserError`:
   ```python
   except FileNotFoundError:
       raise ParserError(f"File not found: {file_path}")
   ```

### Column Mapping

1. **Support manual mapping** for flexibility:
   ```python
   if config.column_mapping:
       return config.column_mapping  # Use manual mapping
   # Otherwise, auto-detect
   ```

2. **Use fuzzy matching** for auto-detection:
   ```python
   from difflib import get_close_matches
   matches = get_close_matches(field, headers, n=1, cutoff=0.6)
   ```

### Characteristics Extraction

1. **Allow explicit column list**:
   ```python
   if config.characteristic_columns:
       # Use specified columns
   else:
       # Include all non-mapped columns
   ```

2. **Store as JSONB-compatible dict**:
   ```python
   characteristics = {}
   for col in characteristic_columns:
       if row[col].strip():
           characteristics[col] = row[col].strip()
   ```

### Performance

1. **Process rows incrementally** (don't load entire file into memory)
2. **Use async I/O** for network-based sources
3. **Batch database operations** when possible

---

## Example: Excel Parser Skeleton

```python
# src/parsers/excel_parser.py
import openpyxl  # or pandas
from src.parsers.base_parser import ParserInterface
from src.models.parsed_item import ParsedSupplierItem

class ExcelParser(ParserInterface):
    """Parser for Excel files (.xlsx, .xls)."""
    
    async def parse(self, config: Dict[str, Any]) -> List[ParsedSupplierItem]:
        # 1. Load Excel file
        # 2. Read worksheet
        # 3. Map columns
        # 4. Parse rows
        # 5. Return items
        pass
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        # Validate Excel file path, sheet name, etc.
        pass
    
    def get_parser_name(self) -> str:
        return "excel"
```

---

## Testing Checklist

- [ ] Unit tests for `parse()` method
- [ ] Unit tests for `validate_config()` method
- [ ] Unit tests for `get_parser_name()` method
- [ ] Tests for error handling (missing file, invalid data, etc.)
- [ ] Tests for column mapping (auto-detect and manual)
- [ ] Tests for characteristics extraction
- [ ] Integration test with real database
- [ ] Performance test with large file (1000+ rows)

---

## Troubleshooting

### Parser not found

**Problem:** `ParserError: Parser 'csv' is not registered`

**Solution:** Ensure parser is registered in `parser_registry.py`:
```python
register_parser("csv", CSVParser)
```

### Configuration validation fails

**Problem:** `ValidationError: Invalid CSV configuration`

**Solution:** Check your `CSVConfig` model matches the config structure being passed.

### Rows not parsing

**Problem:** Parser returns empty list

**Solution:**
1. Check file encoding (try `utf-8-sig` for BOM)
2. Verify delimiter matches file format
3. Check `header_row` and `skip_rows` settings
4. Enable debug logging to see row processing

---

## Next Steps

1. **Add parser to requirements.txt** if it needs new dependencies:
   ```txt
   openpyxl>=3.1.0  # For Excel parser
   ```

2. **Update documentation** with parser-specific configuration examples

3. **Add to deployment guide** if parser requires special setup (credentials, file permissions, etc.)

---

## Reference Implementation

See `src/parsers/google_sheets_parser.py` for a complete reference implementation with:
- Authentication handling
- Dynamic column mapping
- Characteristics extraction
- Error handling
- Logging

---

**Questions?** Check the existing Google Sheets parser implementation or review the parser interface documentation in `src/parsers/base_parser.py`.

