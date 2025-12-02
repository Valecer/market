"""Excel file parser implementation."""
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
from decimal import Decimal, InvalidOperation
from difflib import get_close_matches
import structlog

from src.parsers.base_parser import ParserInterface
from src.models.parsed_item import ParsedSupplierItem
from src.models.file_parser_config import ExcelParserConfig
from src.errors.exceptions import ParserError, ValidationError

logger = structlog.get_logger(__name__)


class ExcelParser(ParserInterface):
    """Parser for extracting data from Excel files (.xlsx, .xls).
    
    This parser reads Excel files using pandas + openpyxl, performs dynamic
    column mapping with fuzzy matching, extracts product characteristics,
    and validates data using Pydantic models.
    
    Features:
    - Support for .xlsx and .xls formats (via openpyxl and xlrd)
    - Dynamic column mapping with fuzzy matching (difflib)
    - Manual column mapping override support
    - Characteristics extraction from additional columns
    - Row-level validation with graceful error handling
    - Price normalization to 2 decimal places
    - Multi-sheet support
    """
    
    # Standard field names that parsers should map to
    STANDARD_FIELDS = {
        'sku': ['sku', 'product code', 'item code', 'product_id', 'item_id', 'code', 'артикул', 'код'],
        'name': ['name', 'product name', 'description', 'product description', 'title', 'item', 'название', 'Наименование', 'товар', 'модель'],
        'price': ['price', 'unit price', 'cost', 'unit cost', 'amount', 'value', 'цена', 'стоимость', 'сток']
    }
    
    def __init__(self):
        """Initialize Excel parser."""
        logger.info("excel_parser_initialized")
    
    def get_parser_name(self) -> str:
        """Return parser identifier."""
        return "excel"
    
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
            ExcelParserConfig(**config)
            return True
        except Exception as e:
            raise ValidationError(f"Invalid Excel configuration: {e}") from e
    
    async def parse(self, config: Dict[str, Any]) -> List[ParsedSupplierItem]:
        """Parse data from Excel file and return validated items.
        
        Args:
            config: Parser configuration dictionary (validated as ExcelParserConfig)
        
        Returns:
            List of validated ParsedSupplierItem objects
        
        Raises:
            ParserError: If parsing fails due to file access issues
            ValidationError: If data validation fails
        """
        # Validate configuration
        try:
            parsed_config = ExcelParserConfig(**config)
        except Exception as e:
            raise ValidationError(f"Invalid configuration: {e}") from e
        
        log = logger.bind(
            file_path=parsed_config.file_path,
            sheet_name=parsed_config.sheet_name,
            original_filename=parsed_config.original_filename
        )
        
        try:
            # Check file exists
            file_path = Path(parsed_config.file_path)
            if not file_path.exists():
                raise ParserError(f"Excel file not found: {parsed_config.file_path}")
            
            # Determine engine based on file extension
            extension = file_path.suffix.lower()
            if extension == '.xlsx':
                engine = 'openpyxl'
            elif extension in ('.xls', '.xlsb'):
                engine = 'xlrd' if extension == '.xls' else 'pyxlsb'
            else:
                engine = 'openpyxl'  # Default to openpyxl
            
            # Determine header rows range
            header_row_start = parsed_config.header_row - 1  # Convert to 0-indexed
            header_row_end = (parsed_config.header_row_end - 1) if parsed_config.header_row_end else header_row_start
            header_rows = list(range(header_row_start, header_row_end + 1))
            
            # Read Excel file to get raw data
            try:
                # First, read without headers to get raw data
                df_raw = pd.read_excel(
                    file_path,
                    sheet_name=parsed_config.sheet_name,
                    header=None,
                    skiprows=0,
                    dtype=str,
                    na_values=['', 'N/A', 'n/a', 'NA', 'null', 'NULL', 'None'],
                    keep_default_na=True,
                    engine=engine
                )
            except ValueError as e:
                # Sheet not found - try fallback to first sheet
                if "Worksheet" in str(e) or "sheet" in str(e).lower():
                    # List available sheets
                    xl = pd.ExcelFile(file_path, engine=engine)
                    available_sheets = xl.sheet_names
                    
                    if not available_sheets:
                        raise ParserError("No sheets found in Excel file")
                    
                    # Fallback to first available sheet
                    first_sheet = available_sheets[0]
                    log.warning(
                        "sheet_not_found_using_fallback",
                        requested_sheet=parsed_config.sheet_name,
                        fallback_sheet=first_sheet,
                        available_sheets=available_sheets
                    )
                    
                    # Try reading with first sheet
                    df_raw = pd.read_excel(
                        file_path,
                        sheet_name=first_sheet,
                        header=None,
                        skiprows=0,
                        dtype=str,
                        na_values=['', 'N/A', 'n/a', 'NA', 'null', 'NULL', 'None'],
                        keep_default_na=True,
                        engine=engine
                    )
                else:
                    raise ParserError(f"Excel read error: {e}") from e
            
            # Extract and combine headers from multiple rows
            headers = self._combine_header_rows(df_raw, header_rows, log)
            
            # Try to map columns - if fails, try auto-detecting header rows
            try:
                column_map = self._map_columns(headers, parsed_config.column_mapping, log)
            except ValidationError as e:
                # If mapping failed and header_row_end not specified, try auto-detection
                if parsed_config.header_row_end is None:
                    log.warning(
                        "column_mapping_failed_trying_auto_detect",
                        error=str(e),
                        current_header_row=parsed_config.header_row
                    )
                    # Try to find headers in next rows (up to data_start_row)
                    detected_header_rows = self._auto_detect_header_rows(
                        df_raw,
                        parsed_config.header_row - 1,
                        parsed_config.data_start_row - 1,
                        log
                    )
                    if detected_header_rows and detected_header_rows != header_rows:
                        log.info(
                            "header_rows_auto_detected",
                            original_rows=header_rows,
                            detected_rows=detected_header_rows
                        )
                        headers = self._combine_header_rows(df_raw, detected_header_rows, log)
                        column_map = self._map_columns(headers, parsed_config.column_mapping, log)
                    else:
                        raise  # Re-raise original error
                else:
                    raise  # Re-raise original error
            
            # Read data rows (skip header rows)
            data_start_idx = parsed_config.data_start_row - 1  # Convert to 0-indexed
            df = df_raw.iloc[data_start_idx:].copy()
            df.columns = range(len(headers))  # Temporary column names
            log.debug("excel_headers_read", headers=headers, header_rows=header_rows, row_count=len(df))
            
            # Perform column mapping (if not done above)
            if 'column_map' not in locals():
                column_map = self._map_columns(headers, parsed_config.column_mapping, log)
            
            # Perform column mapping
            column_map = self._map_columns(headers, parsed_config.column_mapping, log)
            
            # Determine characteristic columns
            characteristic_cols = self._determine_characteristic_columns(
                headers, column_map, parsed_config.characteristic_columns, log
            )
            
            log.info(
                "excel_data_read",
                total_rows=len(df),
                sheet_name=parsed_config.sheet_name,
                header_row=parsed_config.header_row,
                data_start_row=parsed_config.data_start_row
            )
            
            # Parse rows into ParsedSupplierItem objects
            parsed_items: List[ParsedSupplierItem] = []
            for df_idx, row in df.iterrows():
                row_number = df_idx + parsed_config.data_start_row  # Human-readable row number
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
                "excel_parse_completed",
                total_rows=len(df),
                valid_items=len(parsed_items),
                failed_rows=len(df) - len(parsed_items)
            )
            
            return parsed_items
            
        except pd.errors.EmptyDataError:
            raise ParserError("Excel file is empty or contains no data")
        except Exception as e:
            if isinstance(e, (ParserError, ValidationError)):
                raise
            raise ParserError(f"Unexpected error during Excel parsing: {e}") from e
    
    def _combine_header_rows(
        self,
        df_raw: pd.DataFrame,
        header_rows: List[int],
        log: Any
    ) -> List[str]:
        """Combine headers from multiple rows into a single header row.
        
        Args:
            df_raw: Raw DataFrame without headers
            header_rows: List of row indices (0-indexed) containing headers
            log: Structured logger instance
        
        Returns:
            List of combined header strings
        """
        if not header_rows:
            raise ValidationError("No header rows specified")
        
        # Get maximum number of columns
        max_cols = df_raw.shape[1]
        
        # Combine headers from all specified rows
        combined_headers = []
        for col_idx in range(max_cols):
            header_parts = []
            for row_idx in header_rows:
                if row_idx < len(df_raw) and col_idx < len(df_raw.iloc[row_idx]):
                    cell_value = df_raw.iloc[row_idx, col_idx]
                    if pd.notna(cell_value) and str(cell_value).strip():
                        header_parts.append(str(cell_value).strip())
            
            # Join header parts with space, filter empty
            combined_header = ' '.join(header_parts).strip()
            if not combined_header:
                combined_header = f"Column_{col_idx + 1}"  # Fallback name
            
            combined_headers.append(combined_header)
        
        log.debug(
            "headers_combined",
            header_rows=header_rows,
            combined_count=len(combined_headers),
            sample_headers=combined_headers[:5]
        )
        
        return combined_headers
    
    def _auto_detect_header_rows(
        self,
        df_raw: pd.DataFrame,
        start_row: int,
        max_row: int,
        log: Any
    ) -> List[int]:
        """Automatically detect which rows contain headers by searching for standard fields.
        
        Args:
            df_raw: Raw DataFrame without headers
            start_row: Starting row index (0-indexed) to search from
            max_row: Maximum row index (0-indexed) to search up to (exclusive)
            log: Structured logger instance
        
        Returns:
            List of row indices (0-indexed) that should be used as headers
        """
        # Try combining rows starting from start_row
        for end_row in range(start_row, min(start_row + 3, max_row)):  # Try up to 3 rows
            test_header_rows = list(range(start_row, end_row + 1))
            try:
                test_headers = self._combine_header_rows(df_raw, test_header_rows, log)
                # Try to map columns
                test_column_map = {}
                normalized_headers = [h.strip().lower() if h else "" for h in test_headers]
                
                for field_name, possible_names in self.STANDARD_FIELDS.items():
                    found = False
                    for possible_name in possible_names:
                        try:
                            col_idx = normalized_headers.index(possible_name.lower())
                            test_column_map[field_name] = col_idx
                            found = True
                            break
                        except ValueError:
                            continue
                    
                    if not found:
                        # Try fuzzy matching
                        matches = get_close_matches(
                            possible_names[0],
                            normalized_headers,
                            n=1,
                            cutoff=0.6
                        )
                        if matches:
                            col_idx = normalized_headers.index(matches[0])
                            test_column_map[field_name] = col_idx
                            found = True
                
                # If we found all required fields, return these header rows
                required_fields = {'sku', 'name', 'price'}
                if required_fields.issubset(set(test_column_map.keys())):
                    log.debug("auto_detect_success", header_rows=test_header_rows, column_map=test_column_map)
                    return test_header_rows
            except Exception:
                continue
        
        # If nothing found, return original start_row
        return [start_row]
    
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
        
        # Normalize headers - handle non-string headers
        normalized_headers = []
        for h in headers:
            if pd.notna(h) and h is not None:
                normalized_headers.append(str(h).strip().lower())
            else:
                normalized_headers.append("")
        
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
            normalized_headers = []
            for h in headers:
                if pd.notna(h) and h is not None:
                    normalized_headers.append(str(h).strip().lower())
                else:
                    normalized_headers.append("")
            
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
        # Extract standard fields using column indices
        sku = self._get_cell_value_by_index(row, column_map['sku'], row_number, 'sku')
        name = self._get_cell_value_by_index(row, column_map['name'], row_number, 'name')
        price_str = self._get_cell_value_by_index(row, column_map['price'], row_number, 'price')
        
        # Parse and normalize price
        price = self._normalize_price(price_str, row_number)
        
        # Extract characteristics
        characteristics = self._extract_characteristics(row, headers, characteristic_cols, row_number)
        
        return ParsedSupplierItem(
            supplier_sku=sku,
            name=name,
            price=price,
            characteristics=characteristics
        )
    
    def _get_cell_value(self, row: pd.Series, column_name: str, row_number: int, field_name: str) -> str:
        """Get cell value by column name with validation."""
        value = row.get(column_name)
        if pd.isna(value) or str(value).strip() == '':
            raise ValidationError(f"Row {row_number}: Required field '{field_name}' is empty")
        return str(value).strip()
    
    def _get_cell_value_by_index(self, row: pd.Series, col_idx: int, row_number: int, field_name: str) -> str:
        """Get cell value by column index with validation."""
        if col_idx >= len(row):
            raise ValidationError(
                f"Row {row_number}: Column index {col_idx} out of bounds "
                f"(row has {len(row)} columns, expected at least {col_idx + 1})"
            )
        value = row.iloc[col_idx]
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
        characteristic_cols: List[int],
        row_number: int
    ) -> Dict[str, Any]:
        """Extract characteristics from additional columns."""
        characteristics: Dict[str, Any] = {}
        
        for col_idx in characteristic_cols:
            if col_idx >= len(headers):
                continue
            
            header_name = headers[col_idx]
            if pd.isna(header_name) or not str(header_name).strip():
                continue
            
            if col_idx >= len(row):
                continue
            
            cell_value = row.iloc[col_idx]
            
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

