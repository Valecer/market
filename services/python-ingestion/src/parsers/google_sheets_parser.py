"""Google Sheets parser implementation."""
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound, APIError
from typing import Dict, Any, List, Optional
from decimal import Decimal, InvalidOperation
from difflib import get_close_matches
import structlog
from urllib.parse import urlparse

from src.parsers.base_parser import ParserInterface
from src.models.parsed_item import ParsedSupplierItem
from src.models.google_sheets_config import GoogleSheetsConfig
from src.errors.exceptions import ParserError, ValidationError
from src.config import settings

logger = structlog.get_logger(__name__)


class GoogleSheetsParser(ParserInterface):
    """Parser for extracting data from Google Sheets.
    
    This parser authenticates with Google Sheets API using service account credentials,
    reads data from a specified worksheet, performs dynamic column mapping with fuzzy
    matching, extracts product characteristics, and validates data using Pydantic models.
    
    Features:
    - Service account authentication via gspread
    - Dynamic column mapping with fuzzy matching (difflib)
    - Manual column mapping override support
    - Characteristics extraction from additional columns
    - Row-level validation with graceful error handling
    - Price normalization to 2 decimal places
    """
    
    # Standard field names that parsers should map to
    STANDARD_FIELDS = {
        'sku': ['sku', 'product code', 'item code', 'product_id', 'item_id', 'code'],
        'name': ['name', 'product name', 'description', 'product description', 'title', 'item'],
        'price': ['price', 'unit price', 'cost', 'unit cost', 'amount', 'value']
    }
    
    def __init__(self, credentials_path: Optional[str] = None):
        """Initialize Google Sheets parser with authentication.
        
        Args:
            credentials_path: Path to service account JSON credentials file.
                            If None, uses settings.google_credentials_path.
        
        Raises:
            ParserError: If authentication fails or credentials are invalid
        """
        self.credentials_path = credentials_path or settings.google_credentials_path
        self._client: Optional[gspread.Client] = None
        
        try:
            # Authenticate with service account
            self._client = gspread.service_account(filename=self.credentials_path)
            logger.info(
                "google_sheets_parser_initialized",
                credentials_path=self.credentials_path
            )
        except FileNotFoundError as e:
            raise ParserError(
                f"Google credentials file not found: {self.credentials_path}"
            ) from e
        except Exception as e:
            raise ParserError(
                f"Failed to authenticate with Google Sheets API: {e}"
            ) from e
    
    def get_parser_name(self) -> str:
        """Return parser identifier."""
        return "google_sheets"
    
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
            # Validate using Pydantic model
            GoogleSheetsConfig(**config)
            return True
        except Exception as e:
            raise ValidationError(
                f"Invalid Google Sheets configuration: {e}"
            ) from e
    
    async def parse(self, config: Dict[str, Any]) -> List[ParsedSupplierItem]:
        """Parse data from Google Sheets and return validated items.
        
        This method:
        1. Validates configuration
        2. Opens spreadsheet by URL
        3. Gets worksheet by name
        4. Reads header row to detect columns
        5. Performs column mapping (manual override or fuzzy matching)
        6. Reads all data rows
        7. Extracts characteristics from additional columns
        8. Validates each row with Pydantic
        9. Returns list of ParsedSupplierItem objects
        
        Args:
            config: Parser configuration dictionary (validated as GoogleSheetsConfig)
        
        Returns:
            List of validated ParsedSupplierItem objects
        
        Raises:
            ParserError: If parsing fails due to source access issues
            ValidationError: If data validation fails (should be logged, not raised)
        """
        # Validate configuration
        try:
            parsed_config = GoogleSheetsConfig(**config)
        except Exception as e:
            raise ValidationError(f"Invalid configuration: {e}") from e
        
        log = logger.bind(
            sheet_url=str(parsed_config.sheet_url),
            sheet_name=parsed_config.sheet_name
        )
        
        try:
            # Open spreadsheet by URL
            spreadsheet = self._open_spreadsheet_by_url(str(parsed_config.sheet_url), log)
            
            # Get worksheet by name
            worksheet = self._get_worksheet(spreadsheet, parsed_config.sheet_name, log)
            
            # Determine header rows range
            header_row_start = parsed_config.header_row
            header_row_end = parsed_config.header_row_end if parsed_config.header_row_end else header_row_start
            header_rows = list(range(header_row_start, header_row_end + 1))
            
            # Read and combine headers from multiple rows
            header_rows_data = []
            for row_num in header_rows:
                row_data = worksheet.row_values(row_num)
                header_rows_data.append(row_data)
            
            # Combine headers from multiple rows
            combined_headers = self._combine_header_rows(header_rows_data, log)
            log.debug(
                "headers_combined",
                header_rows=header_rows,
                combined_count=len(combined_headers),
                sample_headers=combined_headers[:5]
            )
            
            # Try to map columns - if fails, try auto-detecting header rows
            try:
                column_map = self._map_columns(
                    combined_headers,
                    parsed_config.column_mapping,
                    log
                )
            except ValidationError as e:
                # If mapping failed and header_row_end not specified, try auto-detection
                if parsed_config.header_row_end is None:
                    log.warning(
                        "column_mapping_failed_trying_auto_detect",
                        error=str(e),
                        current_header_row=parsed_config.header_row
                    )
                    # Try to find headers in next rows (up to data_start_row)
                    all_values = worksheet.get_all_values()
                    detected_header_rows = self._auto_detect_header_rows(
                        all_values,
                        parsed_config.header_row - 1,  # Convert to 0-indexed
                        parsed_config.data_start_row - 1,  # Convert to 0-indexed
                        log
                    )
                    if detected_header_rows and detected_header_rows != [r - 1 for r in header_rows]:  # Convert back
                        log.info(
                            "header_rows_auto_detected",
                            original_rows=header_rows,
                            detected_rows=[r + 1 for r in detected_header_rows]  # Convert to 1-indexed for log
                        )
                        # Re-read headers with detected rows
                        detected_header_rows_data = []
                        for row_num in [r + 1 for r in detected_header_rows]:  # Convert to 1-indexed
                            row_data = worksheet.row_values(row_num)
                            detected_header_rows_data.append(row_data)
                        combined_headers = self._combine_header_rows(detected_header_rows_data, log)
                        column_map = self._map_columns(combined_headers, parsed_config.column_mapping, log)
                    else:
                        raise  # Re-raise original error
                else:
                    raise  # Re-raise original error
            
            # Determine characteristic columns
            characteristic_cols = self._determine_characteristic_columns(
                combined_headers,
                column_map,
                parsed_config.characteristic_columns,
                log
            )
            
            # Read all data rows
            all_values = worksheet.get_all_values()
            data_rows = all_values[parsed_config.data_start_row - 1:]  # Convert to 0-indexed
            
            log.info(
                "data_rows_read",
                total_rows=len(data_rows),
                header_row=parsed_config.header_row,
                data_start_row=parsed_config.data_start_row
            )
            
            # Parse rows into ParsedSupplierItem objects
            parsed_items: List[ParsedSupplierItem] = []
            for row_idx, row_data in enumerate(data_rows, start=parsed_config.data_start_row):
                try:
                    item = self._parse_row(
                        row_data,
                        row_idx,
                        header_row_data,
                        column_map,
                        characteristic_cols,
                        log
                    )
                    parsed_items.append(item)
                except ValidationError as e:
                    # Log validation error but continue processing
                    log.warning(
                        "row_validation_failed",
                        row_number=row_idx,
                        error=str(e),
                        row_data=row_data
                    )
                    # Don't raise - continue processing other rows
                    # Errors will be logged to parsing_logs table in Phase 7
            
            log.info(
                "parse_completed",
                total_rows=len(data_rows),
                valid_items=len(parsed_items),
                failed_rows=len(data_rows) - len(parsed_items)
            )
            
            return parsed_items
            
        except (SpreadsheetNotFound, WorksheetNotFound) as e:
            raise ParserError(f"Sheet or worksheet not found: {e}") from e
        except APIError as e:
            raise ParserError(f"Google Sheets API error: {e}") from e
        except Exception as e:
            raise ParserError(f"Unexpected error during parsing: {e}") from e
    
    def _open_spreadsheet_by_url(
        self,
        sheet_url: str,
        log: Any
    ) -> gspread.Spreadsheet:
        """Open spreadsheet by URL.
        
        Args:
            sheet_url: Google Sheets URL
            log: Structured logger instance
        
        Returns:
            gspread.Spreadsheet object
        
        Raises:
            ParserError: If spreadsheet cannot be opened
        """
        try:
            # Extract spreadsheet ID from URL
            # URLs can be in formats:
            # https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit
            # https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid={GID}
            parsed_url = urlparse(sheet_url)
            path_parts = parsed_url.path.split('/')
            
            # Find 'd' in path and get next part (spreadsheet ID)
            if 'd' in path_parts:
                spreadsheet_id = path_parts[path_parts.index('d') + 1]
            else:
                raise ParserError(f"Invalid Google Sheets URL format: {sheet_url}")
            
            # Open by ID
            spreadsheet = self._client.open_by_key(spreadsheet_id)
            log.debug("spreadsheet_opened", spreadsheet_id=spreadsheet_id, title=spreadsheet.title)
            return spreadsheet
            
        except Exception as e:
            raise ParserError(f"Failed to open spreadsheet: {e}") from e
    
    def _get_worksheet(
        self,
        spreadsheet: gspread.Spreadsheet,
        sheet_name: str,
        log: Any
    ) -> gspread.Worksheet:
        """Get worksheet by name.
        
        If the specified worksheet is not found, falls back to the first available worksheet.
        
        Args:
            spreadsheet: gspread.Spreadsheet object
            sheet_name: Name of worksheet tab
            log: Structured logger instance
        
        Returns:
            gspread.Worksheet object
        
        Raises:
            ParserError: If no worksheets are available
        """
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            log.debug("worksheet_found", sheet_name=sheet_name, row_count=worksheet.row_count)
            return worksheet
        except WorksheetNotFound:
            # List available worksheets
            available = [ws.title for ws in spreadsheet.worksheets()]
            
            if not available:
                raise ParserError("No worksheets found in spreadsheet")
            
            # Fallback to first available worksheet
            first_sheet = available[0]
            log.warning(
                "worksheet_not_found_using_fallback",
                requested_sheet=sheet_name,
                fallback_sheet=first_sheet,
                available_sheets=available
            )
            worksheet = spreadsheet.worksheet(first_sheet)
            return worksheet
    
    def _combine_header_rows(
        self,
        header_rows_data: List[List[str]],
        log: Any
    ) -> List[str]:
        """Combine headers from multiple rows into a single header row.
        
        Args:
            header_rows_data: List of row data lists, each containing header values
            log: Structured logger instance
        
        Returns:
            List of combined header strings
        """
        if not header_rows_data:
            raise ValidationError("No header rows provided")
        
        # Get maximum number of columns across all header rows
        max_cols = max(len(row) for row in header_rows_data) if header_rows_data else 0
        
        # Combine headers from all specified rows
        combined_headers = []
        for col_idx in range(max_cols):
            header_parts = []
            for row_data in header_rows_data:
                if col_idx < len(row_data):
                    cell_value = row_data[col_idx]
                    if cell_value and str(cell_value).strip():
                        header_parts.append(str(cell_value).strip())
            
            # Join header parts with space, filter empty
            combined_header = ' '.join(header_parts).strip()
            if not combined_header:
                combined_header = f"Column_{col_idx + 1}"  # Fallback name
            
            combined_headers.append(combined_header)
        
        return combined_headers
    
    def _auto_detect_header_rows(
        self,
        all_values: List[List[str]],
        start_row: int,
        max_row: int,
        log: Any
    ) -> List[int]:
        """Automatically detect which rows contain headers by searching for standard fields.
        
        Args:
            all_values: All worksheet values as list of rows
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
                test_header_rows_data = []
                for row_idx in test_header_rows:
                    if row_idx < len(all_values):
                        test_header_rows_data.append(all_values[row_idx])
                
                test_headers = self._combine_header_rows(test_header_rows_data, log)
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
        """Map sheet column headers to standard field names.
        
        Args:
            headers: List of header strings from sheet
            manual_mapping: Optional manual mapping override
            log: Structured logger instance
        
        Returns:
            Dictionary mapping standard field names to column indices (0-indexed)
        
        Raises:
            ValidationError: If required columns cannot be mapped
        """
        column_map: Dict[str, int] = {}
        
        # Normalize headers (strip whitespace, lowercase for comparison)
        normalized_headers = [h.strip().lower() if h else "" for h in headers]
        
        # If manual mapping provided, use it (case-insensitive matching)
        if manual_mapping:
            log.debug("using_manual_column_mapping", mapping=manual_mapping)
            for field_name, header_name in manual_mapping.items():
                # Find column index (case-insensitive)
                try:
                    col_idx = normalized_headers.index(header_name.strip().lower())
                    column_map[field_name] = col_idx
                except ValueError:
                    raise ValidationError(
                        f"Manual column mapping '{header_name}' not found in sheet headers. "
                        f"Available headers: {headers}"
                    )
        else:
            # Auto-detect using fuzzy matching
            log.debug("auto_detecting_columns", headers=headers)
            for field_name, possible_names in self.STANDARD_FIELDS.items():
                # Try exact match first (case-insensitive)
                found = False
                for possible_name in possible_names:
                    try:
                        col_idx = normalized_headers.index(possible_name.lower())
                        column_map[field_name] = col_idx
                        found = True
                        log.debug(
                            "column_mapped",
                            field=field_name,
                            header=headers[col_idx],
                            index=col_idx
                        )
                        break
                    except ValueError:
                        continue
                
                # If exact match failed, try fuzzy matching
                if not found:
                    # Get close matches from actual headers
                    matches = get_close_matches(
                        possible_names[0],  # Use first standard name as reference
                        normalized_headers,
                        n=1,
                        cutoff=0.6  # 60% similarity threshold
                    )
                    if matches:
                        col_idx = normalized_headers.index(matches[0])
                        column_map[field_name] = col_idx
                        log.debug(
                            "column_fuzzy_mapped",
                            field=field_name,
                            header=headers[col_idx],
                            index=col_idx,
                            similarity_match=matches[0]
                        )
        
        # Validate required fields are mapped
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
        """Determine which columns should be included in characteristics.
        
        Args:
            headers: List of header strings
            column_map: Mapping of standard fields to column indices
            explicit_characteristic_cols: Optional explicit list of column names
            log: Structured logger instance
        
        Returns:
            List of column indices (0-indexed) to include in characteristics
        """
        mapped_indices = set(column_map.values())
        
        if explicit_characteristic_cols:
            # Use explicit list (case-insensitive matching)
            normalized_headers = [h.strip().lower() if h else "" for h in headers]
            characteristic_indices = []
            for col_name in explicit_characteristic_cols:
                try:
                    col_idx = normalized_headers.index(col_name.strip().lower())
                    if col_idx not in mapped_indices:  # Don't duplicate mapped fields
                        characteristic_indices.append(col_idx)
                except ValueError:
                    log.warning(
                        "characteristic_column_not_found",
                        column_name=col_name,
                        available_headers=headers
                    )
            log.debug(
                "explicit_characteristic_columns",
                columns=explicit_characteristic_cols,
                indices=characteristic_indices
            )
            return characteristic_indices
        else:
            # Include all columns not mapped to standard fields
            all_indices = set(range(len(headers)))
            characteristic_indices = list(all_indices - mapped_indices)
            log.debug(
                "auto_characteristic_columns",
                total_columns=len(headers),
                mapped_columns=len(mapped_indices),
                characteristic_columns=len(characteristic_indices)
            )
            return characteristic_indices
    
    def _parse_row(
        self,
        row_data: List[str],
        row_number: int,
        headers: List[str],
        column_map: Dict[str, int],
        characteristic_cols: List[int],
        log: Any
    ) -> ParsedSupplierItem:
        """Parse a single row into ParsedSupplierItem.
        
        Args:
            row_data: List of cell values (may be shorter than headers)
            row_number: Row number (1-indexed) for error reporting
            headers: List of header strings
            column_map: Mapping of standard fields to column indices
            characteristic_cols: List of column indices for characteristics
            log: Structured logger instance
        
        Returns:
            ParsedSupplierItem object
        
        Raises:
            ValidationError: If row data is invalid
        """
        # Extract standard fields using column indices
        try:
            sku = self._get_cell_value(row_data, column_map['sku'], row_number, 'sku')
            name = self._get_cell_value(row_data, column_map['name'], row_number, 'name')
            price_str = self._get_cell_value(row_data, column_map['price'], row_number, 'price')
        except ValidationError:
            raise  # Re-raise validation errors
        
        # Parse and normalize price
        try:
            price = self._normalize_price(price_str, row_number)
        except ValidationError as e:
            raise ValidationError(f"Row {row_number}: {e}") from e
        
        # Extract characteristics
        characteristics = self._extract_characteristics(
            row_data,
            headers,
            characteristic_cols,
            row_number
        )
        
        # Create and validate ParsedSupplierItem
        try:
            item = ParsedSupplierItem(
                supplier_sku=sku,
                name=name,
                price=price,
                characteristics=characteristics
            )
            return item
        except Exception as e:
            raise ValidationError(f"Row {row_number}: Failed to create ParsedSupplierItem: {e}") from e
    
    def _get_cell_value(
        self,
        row_data: List[str],
        col_idx: int,
        row_number: int,
        field_name: str
    ) -> str:
        """Get cell value from row data with validation.
        
        Args:
            row_data: List of cell values
            col_idx: Column index (0-indexed)
            row_number: Row number (1-indexed) for error reporting
            field_name: Field name for error messages
        
        Returns:
            Cell value as string
        
        Raises:
            ValidationError: If column index is out of bounds or value is empty
        """
        if col_idx >= len(row_data):
            raise ValidationError(
                f"Row {row_number}: Column index {col_idx} out of bounds "
                f"(row has {len(row_data)} columns, expected at least {col_idx + 1})"
            )
        
        value = row_data[col_idx].strip() if row_data[col_idx] else ""
        if not value:
            raise ValidationError(
                f"Row {row_number}: Required field '{field_name}' is empty"
            )
        
        return value
    
    def _normalize_price(self, price_str: str, row_number: int) -> Decimal:
        """Normalize price string to Decimal with 2 decimal places.
        
        Args:
            price_str: Price as string (may include currency symbols, commas)
            row_number: Row number (1-indexed) for error reporting
        
        Returns:
            Decimal price normalized to 2 decimal places
        
        Raises:
            ValidationError: If price cannot be parsed or is negative
        """
        # Remove currency symbols and whitespace
        cleaned = price_str.replace('$', '').replace('€', '').replace('£', '').strip()
        # Remove commas (thousand separators)
        cleaned = cleaned.replace(',', '')
        
        try:
            price = Decimal(cleaned)
        except (InvalidOperation, ValueError) as e:
            raise ValidationError(
                f"Row {row_number}: Invalid price format '{price_str}': {e}"
            ) from e
        
        if price < 0:
            raise ValidationError(
                f"Row {row_number}: Price cannot be negative: {price}"
            )
        
        # Quantize to 2 decimal places (Pydantic validator will also do this)
        price = price.quantize(Decimal('0.01'))
        return price
    
    def _extract_characteristics(
        self,
        row_data: List[str],
        headers: List[str],
        characteristic_cols: List[int],
        row_number: int
    ) -> Dict[str, Any]:
        """Extract characteristics from additional columns.
        
        Args:
            row_data: List of cell values
            headers: List of header strings
            characteristic_cols: List of column indices to include
            row_number: Row number (1-indexed) for error reporting
        
        Returns:
            Dictionary of characteristics (JSONB-compatible)
        """
        characteristics: Dict[str, Any] = {}
        
        for col_idx in characteristic_cols:
            if col_idx >= len(headers):
                continue  # Skip if header doesn't exist
            
            header_name = headers[col_idx].strip()
            if not header_name:
                continue  # Skip empty headers
            
            # Get cell value (may be empty)
            if col_idx < len(row_data):
                cell_value = row_data[col_idx].strip() if row_data[col_idx] else None
            else:
                cell_value = None
            
            # Only include non-empty values
            if cell_value:
                # Normalize header name for JSON key (lowercase, replace spaces with underscores)
                key = header_name.lower().replace(' ', '_').replace('-', '_')
                # Try to convert to number if possible
                try:
                    # Try int first
                    if '.' not in cell_value:
                        characteristics[key] = int(cell_value)
                    else:
                        characteristics[key] = float(cell_value)
                except ValueError:
                    # Keep as string
                    characteristics[key] = cell_value
        
        return characteristics

