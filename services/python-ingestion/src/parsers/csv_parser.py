"""CSV file parser implementation."""
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
from decimal import Decimal, InvalidOperation
from difflib import get_close_matches
import structlog

from src.parsers.base_parser import ParserInterface
from src.models.parsed_item import ParsedSupplierItem
from src.models.file_parser_config import CsvParserConfig
from src.errors.exceptions import ParserError, ValidationError

logger = structlog.get_logger(__name__)


class CsvParser(ParserInterface):
    """Parser for extracting data from CSV files.
    
    This parser reads CSV files using pandas, performs dynamic column mapping
    with fuzzy matching, extracts product characteristics, and validates data
    using Pydantic models.
    
    Features:
    - Dynamic column mapping with fuzzy matching (difflib)
    - Manual column mapping override support
    - Characteristics extraction from additional columns
    - Row-level validation with graceful error handling
    - Price normalization to 2 decimal places
    - Support for different delimiters and encodings
    """
    
    # Standard field names that parsers should map to
    STANDARD_FIELDS = {
        'sku': ['sku', 'product code', 'item code', 'product_id', 'item_id', 'code', 'артикул', 'код'],
        'name': ['name', 'product name', 'description', 'product description', 'title', 'item', 'название', 'наименование', 'товар'],
        'price': ['price', 'unit price', 'cost', 'unit cost', 'amount', 'value', 'цена', 'стоимость']
    }
    
    def __init__(self):
        """Initialize CSV parser."""
        logger.info("csv_parser_initialized")
    
    def get_parser_name(self) -> str:
        """Return parser identifier."""
        return "csv"
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate parser-specific configuration.
        
        Args:
            config: Configuration dictionary to validate
        
        Returns:
            True if configuration is valid
        
        Raises:
            ValidationError: If configuration is invalid with detailed message
        """
        try:
            CsvParserConfig(**config)
            return True
        except Exception as e:
            raise ValidationError(f"Invalid CSV configuration: {e}") from e
    
    async def parse(self, config: Dict[str, Any]) -> List[ParsedSupplierItem]:
        """Parse data from CSV file and return validated items.
        
        Args:
            config: Parser configuration dictionary (validated as CsvParserConfig)
        
        Returns:
            List of validated ParsedSupplierItem objects
        
        Raises:
            ParserError: If parsing fails due to file access issues
            ValidationError: If data validation fails
        """
        # Validate configuration
        try:
            parsed_config = CsvParserConfig(**config)
        except Exception as e:
            raise ValidationError(f"Invalid configuration: {e}") from e
        
        log = logger.bind(
            file_path=parsed_config.file_path,
            original_filename=parsed_config.original_filename
        )
        
        try:
            # Check file exists
            file_path = Path(parsed_config.file_path)
            if not file_path.exists():
                raise ParserError(f"CSV file not found: {parsed_config.file_path}")
            
            # Read CSV with pandas
            try:
                df = pd.read_csv(
                    file_path,
                    delimiter=parsed_config.delimiter,
                    encoding=parsed_config.encoding,
                    header=parsed_config.header_row - 1,  # Convert to 0-indexed
                    skiprows=range(1, parsed_config.data_start_row - 1) if parsed_config.data_start_row > 2 else None,
                    dtype=str,  # Read all as strings for consistent processing
                    na_values=['', 'N/A', 'n/a', 'NA', 'null', 'NULL', 'None'],
                    keep_default_na=True
                )
            except UnicodeDecodeError as e:
                # Try with latin-1 encoding as fallback
                log.warning("utf8_decode_failed_trying_latin1", error=str(e))
                df = pd.read_csv(
                    file_path,
                    delimiter=parsed_config.delimiter,
                    encoding='latin-1',
                    header=parsed_config.header_row - 1,
                    skiprows=range(1, parsed_config.data_start_row - 1) if parsed_config.data_start_row > 2 else None,
                    dtype=str,
                    na_values=['', 'N/A', 'n/a', 'NA', 'null', 'NULL', 'None'],
                    keep_default_na=True
                )
            
            # Get headers
            headers = list(df.columns)
            log.debug("csv_headers_read", headers=headers, row_count=len(df))
            
            # Perform column mapping
            column_map = self._map_columns(headers, parsed_config.column_mapping, log)
            
            # Determine characteristic columns
            characteristic_cols = self._determine_characteristic_columns(
                headers, column_map, parsed_config.characteristic_columns, log
            )
            
            log.info(
                "csv_data_read",
                total_rows=len(df),
                header_row=parsed_config.header_row,
                data_start_row=parsed_config.data_start_row
            )
            
            # Parse rows into ParsedSupplierItem objects
            parsed_items: List[ParsedSupplierItem] = []
            for row_idx, row in df.iterrows():
                row_number = row_idx + parsed_config.data_start_row  # Human-readable row number
                try:
                    item = self._parse_row(
                        row, row_number, headers, column_map, characteristic_cols, log
                    )
                    parsed_items.append(item)
                except ValidationError as e:
                    log.warning(
                        "row_validation_failed",
                        row_number=row_number,
                        error=str(e)
                    )
            
            log.info(
                "csv_parse_completed",
                total_rows=len(df),
                valid_items=len(parsed_items),
                failed_rows=len(df) - len(parsed_items)
            )
            
            return parsed_items
            
        except pd.errors.EmptyDataError:
            raise ParserError("CSV file is empty or contains no data")
        except pd.errors.ParserError as e:
            raise ParserError(f"CSV parsing error: {e}") from e
        except Exception as e:
            if isinstance(e, (ParserError, ValidationError)):
                raise
            raise ParserError(f"Unexpected error during CSV parsing: {e}") from e
    
    def _map_columns(
        self,
        headers: List[str],
        manual_mapping: Optional[Dict[str, str]],
        log: Any
    ) -> Dict[str, int]:
        """Map file column headers to standard field names.
        
        Args:
            headers: List of header strings from file
            manual_mapping: Optional manual mapping override
            log: Structured logger instance
        
        Returns:
            Dictionary mapping standard field names to column indices (0-indexed)
        
        Raises:
            ValidationError: If required columns cannot be mapped
        """
        column_map: Dict[str, int] = {}
        
        # Normalize headers
        normalized_headers = [h.strip().lower() if pd.notna(h) and h else "" for h in headers]
        
        if manual_mapping:
            log.debug("using_manual_column_mapping", mapping=manual_mapping)
            for field_name, header_name in manual_mapping.items():
                try:
                    col_idx = normalized_headers.index(header_name.strip().lower())
                    column_map[field_name] = col_idx
                except ValueError:
                    raise ValidationError(
                        f"Manual column mapping '{header_name}' not found in headers. "
                        f"Available: {headers}"
                    )
        else:
            log.debug("auto_detecting_columns", headers=headers)
            for field_name, possible_names in self.STANDARD_FIELDS.items():
                found = False
                for possible_name in possible_names:
                    try:
                        col_idx = normalized_headers.index(possible_name.lower())
                        column_map[field_name] = col_idx
                        found = True
                        log.debug("column_mapped", field=field_name, header=headers[col_idx], index=col_idx)
                        break
                    except ValueError:
                        continue
                
                if not found:
                    matches = get_close_matches(possible_names[0], normalized_headers, n=1, cutoff=0.6)
                    if matches:
                        col_idx = normalized_headers.index(matches[0])
                        column_map[field_name] = col_idx
                        log.debug("column_fuzzy_mapped", field=field_name, header=headers[col_idx], index=col_idx)
        
        required_fields = {'sku', 'name', 'price'}
        missing_fields = required_fields - set(column_map.keys())
        if missing_fields:
            raise ValidationError(
                f"Required columns not found: {missing_fields}. "
                f"Available headers: {headers}. "
                f"Consider providing manual column_mapping in config."
            )
        
        log.info("column_mapping_complete", mapping=column_map)
        return column_map
    
    def _determine_characteristic_columns(
        self,
        headers: List[str],
        column_map: Dict[str, int],
        explicit_characteristic_cols: Optional[List[str]],
        log: Any
    ) -> List[int]:
        """Determine which columns should be included in characteristics."""
        mapped_indices = set(column_map.values())
        
        if explicit_characteristic_cols:
            normalized_headers = [h.strip().lower() if pd.notna(h) and h else "" for h in headers]
            characteristic_indices = []
            for col_name in explicit_characteristic_cols:
                try:
                    col_idx = normalized_headers.index(col_name.strip().lower())
                    if col_idx not in mapped_indices:
                        characteristic_indices.append(col_idx)
                except ValueError:
                    log.warning("characteristic_column_not_found", column_name=col_name)
            return characteristic_indices
        else:
            all_indices = set(range(len(headers)))
            return list(all_indices - mapped_indices)
    
    def _parse_row(
        self,
        row: pd.Series,
        row_number: int,
        headers: List[str],
        column_map: Dict[str, int],
        characteristic_cols: List[int],
        log: Any
    ) -> ParsedSupplierItem:
        """Parse a single row into ParsedSupplierItem."""
        # Extract standard fields
        sku = self._get_cell_value(row, headers[column_map['sku']], row_number, 'sku')
        name = self._get_cell_value(row, headers[column_map['name']], row_number, 'name')
        price_str = self._get_cell_value(row, headers[column_map['price']], row_number, 'price')
        
        # Parse and normalize price
        price = self._normalize_price(price_str, row_number)
        
        # Extract characteristics
        characteristics = self._extract_characteristics(row, headers, characteristic_cols)
        
        return ParsedSupplierItem(
            supplier_sku=sku,
            name=name,
            price=price,
            characteristics=characteristics
        )
    
    def _get_cell_value(self, row: pd.Series, column_name: str, row_number: int, field_name: str) -> str:
        """Get cell value with validation."""
        value = row.get(column_name)
        if pd.isna(value) or str(value).strip() == '':
            raise ValidationError(f"Row {row_number}: Required field '{field_name}' is empty")
        return str(value).strip()
    
    def _normalize_price(self, price_str: str, row_number: int) -> Decimal:
        """Normalize price string to Decimal with 2 decimal places."""
        # Remove currency symbols and whitespace
        cleaned = price_str.replace('$', '').replace('€', '').replace('£', '').replace('₽', '').strip()
        cleaned = cleaned.replace(',', '').replace(' ', '')
        
        try:
            price = Decimal(cleaned)
        except (InvalidOperation, ValueError) as e:
            raise ValidationError(f"Row {row_number}: Invalid price format '{price_str}'") from e
        
        if price < 0:
            raise ValidationError(f"Row {row_number}: Price cannot be negative: {price}")
        
        return price.quantize(Decimal('0.01'))
    
    def _extract_characteristics(
        self,
        row: pd.Series,
        headers: List[str],
        characteristic_cols: List[int]
    ) -> Dict[str, Any]:
        """Extract characteristics from additional columns."""
        characteristics: Dict[str, Any] = {}
        
        for col_idx in characteristic_cols:
            if col_idx >= len(headers):
                continue
            
            header_name = headers[col_idx]
            if pd.isna(header_name) or not str(header_name).strip():
                continue
            
            cell_value = row.iloc[col_idx] if col_idx < len(row) else None
            
            if pd.notna(cell_value) and str(cell_value).strip():
                key = str(header_name).lower().strip().replace(' ', '_').replace('-', '_')
                value = str(cell_value).strip()
                
                # Try to convert to number
                try:
                    if '.' not in value:
                        characteristics[key] = int(value)
                    else:
                        characteristics[key] = float(value)
                except ValueError:
                    characteristics[key] = value
        
        return characteristics

