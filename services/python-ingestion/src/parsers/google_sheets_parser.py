"""Enhanced Google Sheets parser with dynamic header detection.

This parser automatically:
- Detects header rows (single or multi-row)
- Maps Russian column names to standard fields
- Tracks categories from section headers
- Handles repeated headers within data
- Parses all worksheets with priority scoring

Implements ParserInterface for Marketbel project.
"""

import re
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound, APIError
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal, InvalidOperation
from difflib import get_close_matches
import structlog
from urllib.parse import urlparse

from src.parsers.base_parser import ParserInterface
from src.models.parsed_item import ParsedSupplierItem
from src.models.google_sheets_config import GoogleSheetsConfig
from src.errors.exceptions import ParserError, ValidationError
from src.config import settings

# Import dynamic detector
from src.parsers.dynamic_header_detector import (
    DynamicHeaderDetector,
    SheetStructure,
    FieldType,
    SectionTracker,
    DetectorConfig
)

# Import name parser for extracting structured components from raw names
from src.services.extraction.name_parser import ProductNameParser

logger = structlog.get_logger(__name__)


class GoogleSheetsParser(ParserInterface):
    """Enhanced Google Sheets parser with dynamic structure detection.
    
    Features:
    - Automatic header row detection (including multi-row headers)
    - Russian field name recognition  
    - Section/category tracking
    - Multiple worksheet support with priority selection
    - Dual price extraction (wholesale + retail)
    - Backward compatible with existing ParsedSupplierItem model
    
    Extended data is stored in characteristics with '_' prefix:
    - _category: Category path from sections
    - _price_wholesale: Wholesale price
    - _price_retail: Retail price
    - _availability: Availability text
    - _availability_normalized: Boolean availability
    - _images: List of image URLs
    - _source_row: Source row number for debugging
    """
    
    # Legacy standard fields for backward compatibility
    STANDARD_FIELDS = {
        'sku': ['sku', 'product code', 'item code', 'product_id', 'item_id', 'code'],
        'name': ['name', 'product name', 'description', 'product description', 'title', 'item'],
        'price': ['price', 'unit price', 'cost', 'unit cost', 'amount', 'value']
    }
    
    def __init__(self, credentials_path: Optional[str] = None):
        """Initialize Google Sheets parser with authentication."""
        self.credentials_path = credentials_path or settings.google_credentials_path
        self._client: Optional[gspread.Client] = None
        self._detector = DynamicHeaderDetector()
        self._name_parser = ProductNameParser()
        
        try:
            self._client = gspread.service_account(filename=self.credentials_path)
            logger.info("google_sheets_parser_initialized", credentials_path=self.credentials_path)
        except FileNotFoundError as e:
            raise ParserError(f"Google credentials file not found: {self.credentials_path}") from e
        except Exception as e:
            raise ParserError(f"Failed to authenticate with Google Sheets API: {e}") from e
    
    def get_parser_name(self) -> str:
        """Return parser identifier."""
        return "google_sheets"
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate parser-specific configuration."""
        try:
            GoogleSheetsConfig(**config)
            return True
        except Exception as e:
            raise ValidationError(f"Invalid Google Sheets configuration: {e}") from e
    
    async def parse(self, config: Dict[str, Any]) -> List[ParsedSupplierItem]:
        """Parse data from Google Sheets and return validated items.
        
        This method supports two modes:
        1. Auto-detect mode (default): Automatically finds headers, sections, columns
        2. Manual mode: Uses config settings for header_row, column_mapping, etc.
        
        Args:
            config: Parser configuration dictionary
        
        Returns:
            List of validated ParsedSupplierItem objects
        """
        try:
            parsed_config = GoogleSheetsConfig(**config)
        except Exception as e:
            raise ValidationError(f"Invalid configuration: {e}") from e
        
        log = logger.bind(
            sheet_url=str(parsed_config.sheet_url),
            sheet_name=parsed_config.sheet_name
        )
        
        try:
            spreadsheet = self._open_spreadsheet_by_url(str(parsed_config.sheet_url), log)
            
            # Check if auto-detect should be used
            use_auto_detect = self._should_use_auto_detect(parsed_config)
            
            if use_auto_detect:
                log.info("using_auto_detect_mode")
                return await self._parse_with_auto_detect(spreadsheet, parsed_config, log)
            else:
                log.info("using_manual_mode")
                return await self._parse_with_manual_config(spreadsheet, parsed_config, log)
                
        except (SpreadsheetNotFound, WorksheetNotFound) as e:
            raise ParserError(f"Sheet or worksheet not found: {e}") from e
        except APIError as e:
            raise ParserError(f"Google Sheets API error: {e}") from e
        except Exception as e:
            raise ParserError(f"Unexpected error during parsing: {e}") from e
    
    def _should_use_auto_detect(self, config: GoogleSheetsConfig) -> bool:
        """Determine if auto-detect mode should be used."""
        # Use manual mode if explicit column_mapping is provided
        if config.column_mapping:
            return False
        # Use manual mode if non-default header_row is set
        if config.header_row != 1:
            return False
        return True
    
    async def _parse_with_auto_detect(
        self,
        spreadsheet: gspread.Spreadsheet,
        config: GoogleSheetsConfig,
        log: Any
    ) -> List[ParsedSupplierItem]:
        """Parse using automatic structure detection."""
        
        # Get worksheet
        worksheet = self._get_worksheet(spreadsheet, config.sheet_name, log)
        all_values = worksheet.get_all_values()
        
        if not all_values:
            log.warning("empty_worksheet")
            return []
        
        # Analyze structure
        structure = self._detector.analyze_sheet(all_values, worksheet.title)
        log.info(
            "structure_detected",
            header_rows=structure.header_rows,
            data_start=structure.data_start_row,
            sections=len(structure.sections),
            priority=structure.priority_score
        )
        
        # Build field indices
        field_indices = self._build_field_indices(structure)
        log.debug("field_indices", indices={k.value: v for k, v in field_indices.items()})
        
        # Check for required fields
        if FieldType.NAME not in field_indices:
            log.error("name_column_not_found")
            raise ValidationError("Name column not found. Consider providing manual column_mapping.")
        
        # Get combined headers
        combined_headers = self._get_combined_headers(all_values, structure)
        
        # Initialize section tracker
        section_tracker = SectionTracker(structure.sections)
        
        # Parse data rows
        parsed_items: List[ParsedSupplierItem] = []
        
        for row_idx in range(structure.data_start_row, len(all_values)):
            # Skip repeated headers, sections, and info/footnote rows
            if row_idx in structure.repeated_header_rows:
                continue
            if row_idx in structure.info_rows:
                continue
            if any(s[0] == row_idx for s in structure.sections):
                continue
            
            row_data = all_values[row_idx]
            
            # Skip empty rows
            if not any(cell and str(cell).strip() for cell in row_data):
                continue
            
            try:
                item = self._parse_row_auto(
                    row_data,
                    row_idx,
                    field_indices,
                    combined_headers,
                    section_tracker,
                    structure,
                    log
                )
                if item:
                    parsed_items.append(item)
                    
            except ValidationError as e:
                log.warning("row_validation_failed", row_number=row_idx + 1, error=str(e))
            except Exception as e:
                log.warning("row_parse_error", row_number=row_idx + 1, error=str(e))
        
        log.info(
            "parse_completed",
            total_rows=len(all_values),
            valid_items=len(parsed_items),
            sections_found=[s[1] for s in structure.sections]
        )
        
        return parsed_items
    
    async def _parse_with_manual_config(
        self,
        spreadsheet: gspread.Spreadsheet,
        config: GoogleSheetsConfig,
        log: Any
    ) -> List[ParsedSupplierItem]:
        """Parse using manual configuration (legacy mode)."""
        
        worksheet = self._get_worksheet(spreadsheet, config.sheet_name, log)
        
        # Read headers
        header_row_start = config.header_row
        header_row_end = config.header_row_end if config.header_row_end else header_row_start
        
        header_rows_data = []
        for row_num in range(header_row_start, header_row_end + 1):
            row_data = worksheet.row_values(row_num)
            header_rows_data.append(row_data)
        
        combined_headers = self._combine_header_rows(header_rows_data)
        
        # Map columns
        column_map = self._map_columns_legacy(combined_headers, config.column_mapping, log)
        
        # Determine characteristic columns
        characteristic_cols = self._determine_characteristic_columns(
            combined_headers, column_map, config.characteristic_columns, log
        )
        
        # Read all data
        all_values = worksheet.get_all_values()
        data_rows = all_values[config.data_start_row - 1:]
        
        log.info("data_rows_read", total_rows=len(data_rows))
        
        # Parse rows
        parsed_items: List[ParsedSupplierItem] = []
        
        for row_idx, row_data in enumerate(data_rows, start=config.data_start_row):
            try:
                item = self._parse_row_legacy(
                    row_data, row_idx, combined_headers,
                    column_map, characteristic_cols, log
                )
                parsed_items.append(item)
            except ValidationError as e:
                log.warning("row_validation_failed", row_number=row_idx, error=str(e))
        
        log.info("parse_completed", valid_items=len(parsed_items))
        return parsed_items
    
    def _build_field_indices(self, structure: SheetStructure) -> Dict[FieldType, int]:
        """Build mapping from field types to column indices."""
        indices = {}
        for mapping in structure.column_mappings:
            if mapping.field_type != FieldType.UNKNOWN:
                if mapping.field_type not in indices:
                    indices[mapping.field_type] = mapping.index
        return indices
    
    def _get_combined_headers(self, all_values: List[List[str]], structure: SheetStructure) -> List[str]:
        """Get combined headers from header rows."""
        if not structure.header_rows:
            return []
        header_data = [all_values[i] for i in structure.header_rows if i < len(all_values)]
        return self._detector._combine_headers(header_data)
    
    def _parse_row_auto(
        self,
        row_data: List[str],
        row_idx: int,
        field_indices: Dict[FieldType, int],
        headers: List[str],
        section_tracker: SectionTracker,
        structure: SheetStructure,
        log: Any
    ) -> Optional[ParsedSupplierItem]:
        """Parse a single data row using auto-detected structure."""
        
        def get_cell(field_type: FieldType) -> Optional[str]:
            if field_type not in field_indices:
                return None
            idx = field_indices[field_type]
            if idx < len(row_data):
                val = row_data[idx]
                return str(val).strip() if val else None
            return None
        
        # Extract name (required)
        name = get_cell(FieldType.NAME)
        if not name:
            return None
        
        # Parse the raw name into structured components
        parsed_name = self._name_parser.parse(name)
        
        # Extract prices
        price_retail_str = get_cell(FieldType.PRICE_RETAIL)
        price_wholesale_str = get_cell(FieldType.PRICE_WHOLESALE)
        
        price_retail = self._parse_price(price_retail_str)
        price_wholesale = self._parse_price(price_wholesale_str)
        
        # Determine primary price (prefer retail)
        primary_price = price_retail or price_wholesale
        if primary_price is None:
            log.debug("no_price_found", row=row_idx + 1, name=name[:30])
            primary_price = Decimal("0")
        
        # Extract other fields
        sku = get_cell(FieldType.SKU)
        availability = get_cell(FieldType.AVAILABILITY)
        image = get_cell(FieldType.IMAGE)
        description = get_cell(FieldType.DESCRIPTION)
        link = get_cell(FieldType.LINK)
        
        # Get category from section tracker, fallback to parsed category
        category = section_tracker.get_category(row_idx)
        if not category and parsed_name.category_prefix:
            category = parsed_name.category_prefix
        
        # Build characteristics
        characteristics: Dict[str, Any] = {}
        
        # Add extended fields with '_' prefix
        if category:
            characteristics['_category'] = category
        if price_wholesale is not None:
            characteristics['_price_wholesale'] = str(price_wholesale)
        if price_retail is not None:
            characteristics['_price_retail'] = str(price_retail)
        if availability:
            characteristics['_availability'] = availability
            characteristics['_availability_normalized'] = self._normalize_availability(availability)
        if image:
            characteristics['_images'] = [image]
        if description:
            characteristics['_description'] = description
        if link:
            characteristics['_link'] = link
        characteristics['_source_row'] = row_idx + 1
        
        # Add parsed name components
        if parsed_name.category_key:
            characteristics['_parsed_category_key'] = parsed_name.category_key
        if parsed_name.brand:
            characteristics['_parsed_brand'] = parsed_name.brand
        if parsed_name.model:
            characteristics['_parsed_model'] = parsed_name.model
        if parsed_name.clean_name:
            characteristics['_parsed_clean_name'] = parsed_name.clean_name
        if parsed_name.characteristics:
            characteristics['_parsed_characteristics'] = parsed_name.characteristics
        
        # Add unmapped columns as regular characteristics
        mapped_indices = set(field_indices.values())
        for idx, header in enumerate(headers):
            if idx not in mapped_indices and idx < len(row_data):
                cell_val = row_data[idx]
                if cell_val and str(cell_val).strip() and header.strip():
                    key = self._normalize_header_key(header)
                    if key and len(key) < 100:
                        characteristics[key] = self._parse_cell_value(cell_val)
        
        # Generate SKU if not found
        if not sku:
            import hashlib
            name_hash = hashlib.md5(name.encode()).hexdigest()[:8].upper()
            sku = f"AUTO-{name_hash}"
        
        return ParsedSupplierItem(
            supplier_sku=sku,
            name=name,
            price=primary_price,
            characteristics=characteristics
        )
    
    def _parse_price(self, price_str: Optional[str]) -> Optional[Decimal]:
        """Parse price string to Decimal."""
        if not price_str or price_str.strip() in ('', '-'):
            return None
        
        cleaned = price_str.strip()
        # Remove currency symbols and text (but not decimal point!)
        cleaned = re.sub(r'[₽$€£рp]', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'руб\.?', '', cleaned, flags=re.IGNORECASE)
        # Handle comma as decimal separator
        cleaned = cleaned.replace(',', '.')
        # Remove spaces
        cleaned = re.sub(r'\s+', '', cleaned)
        # Remove non-numeric except decimal point
        cleaned = re.sub(r'[^\d.]', '', cleaned)
        
        if not cleaned:
            return None
        
        try:
            return Decimal(cleaned).quantize(Decimal('0.01'))
        except InvalidOperation:
            return None
    
    def _normalize_availability(self, text: str) -> Optional[bool]:
        """Normalize availability text to boolean."""
        if not text:
            return None
        
        text_lower = text.strip().lower()
        
        # Negative patterns (out of stock)
        negative = [
            'нет в наличии', 'нет', 'отсутствует', 'под заказ',
            'временно недоступно', 'закончились', 'out of stock',
            'по запросу', 'ожидается', 'в пути', 'уточнять',
            'недоступно к заказу', 'временно нет', 'ожидается поступление',
        ]
        
        # Positive patterns (in stock)
        positive = [
            'в наличии', 'есть', 'да', '+', 'available', 'in stock',
            'на складе', 'имеется', 'в наличии!',
        ]
        
        # Check negative first (more specific patterns)
        for neg in negative:
            if neg in text_lower:
                return False
        
        # Check positive
        for pos in positive:
            if pos in text_lower:
                return True
        
        # Date pattern (e.g., "17.10.25", "Закончились 17.10.25") = out of stock
        if re.search(r'\d{2}\.\d{2}\.?\d{0,2}', text_lower):
            return False
        
        # Single "+" character
        if text_lower.strip() == '+':
            return True
        
        return None
    
    def _normalize_header_key(self, header: str) -> str:
        """Normalize header to a valid key name."""
        key = header.strip().lower()
        key = re.sub(r'[^a-zа-яё0-9]+', '_', key)
        key = re.sub(r'_+', '_', key).strip('_')
        return key
    
    def _parse_cell_value(self, value: Any) -> Any:
        """Parse cell value to appropriate Python type."""
        if value is None:
            return None
        
        str_val = str(value).strip()
        if not str_val:
            return None
        
        try:
            if '.' not in str_val and ',' not in str_val:
                return int(str_val.replace(' ', ''))
            cleaned = str_val.replace(',', '.').replace(' ', '')
            return float(cleaned)
        except ValueError:
            pass
        
        return str_val
    
    # ==================== Legacy Methods ====================
    
    def _open_spreadsheet_by_url(self, sheet_url: str, log: Any) -> gspread.Spreadsheet:
        """Open spreadsheet by URL."""
        try:
            parsed_url = urlparse(sheet_url)
            path_parts = parsed_url.path.split('/')
            
            if 'd' in path_parts:
                spreadsheet_id = path_parts[path_parts.index('d') + 1]
            else:
                raise ParserError(f"Invalid Google Sheets URL format: {sheet_url}")
            
            spreadsheet = self._client.open_by_key(spreadsheet_id)
            log.debug("spreadsheet_opened", spreadsheet_id=spreadsheet_id, title=spreadsheet.title)
            return spreadsheet
            
        except Exception as e:
            raise ParserError(f"Failed to open spreadsheet: {e}") from e
    
    def _get_worksheet(self, spreadsheet: gspread.Spreadsheet, sheet_name: str, log: Any) -> gspread.Worksheet:
        """Get worksheet by name with fallback."""
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            log.debug("worksheet_found", sheet_name=sheet_name)
            return worksheet
        except WorksheetNotFound:
            available = [ws.title for ws in spreadsheet.worksheets()]
            if not available:
                raise ParserError("No worksheets found in spreadsheet")
            
            first_sheet = available[0]
            log.warning(
                "worksheet_not_found_using_fallback",
                requested_sheet=sheet_name,
                fallback_sheet=first_sheet,
                available_sheets=available
            )
            return spreadsheet.worksheet(first_sheet)
    
    def _combine_header_rows(self, header_rows_data: List[List[str]]) -> List[str]:
        """Combine headers from multiple rows."""
        if not header_rows_data:
            raise ValidationError("No header rows provided")
        
        max_cols = max(len(row) for row in header_rows_data) if header_rows_data else 0
        combined_headers = []
        
        for col_idx in range(max_cols):
            header_parts = []
            for row_data in header_rows_data:
                if col_idx < len(row_data):
                    cell_value = row_data[col_idx]
                    if cell_value and str(cell_value).strip():
                        header_parts.append(str(cell_value).strip())
            
            combined_header = ' '.join(header_parts).strip()
            if not combined_header:
                combined_header = f"Column_{col_idx + 1}"
            
            combined_headers.append(combined_header)
        
        return combined_headers
    
    def _map_columns_legacy(
        self,
        headers: List[str],
        manual_mapping: Optional[Dict[str, str]],
        log: Any
    ) -> Dict[str, int]:
        """Map columns using legacy approach (for backward compatibility)."""
        column_map: Dict[str, int] = {}
        normalized_headers = [h.strip().lower() if h else "" for h in headers]
        
        if manual_mapping:
            log.debug("using_manual_column_mapping", mapping=manual_mapping)
            for field_name, header_name in manual_mapping.items():
                try:
                    col_idx = normalized_headers.index(header_name.strip().lower())
                    column_map[field_name] = col_idx
                except ValueError:
                    raise ValidationError(
                        f"Manual column mapping '{header_name}' not found. "
                        f"Available headers: {headers}"
                    )
        else:
            log.debug("auto_detecting_columns")
            for field_name, possible_names in self.STANDARD_FIELDS.items():
                found = False
                for possible_name in possible_names:
                    try:
                        col_idx = normalized_headers.index(possible_name.lower())
                        column_map[field_name] = col_idx
                        found = True
                        break
                    except ValueError:
                        continue
                
                if not found:
                    matches = get_close_matches(possible_names[0], normalized_headers, n=1, cutoff=0.6)
                    if matches:
                        col_idx = normalized_headers.index(matches[0])
                        column_map[field_name] = col_idx
        
        required_fields = {'sku', 'name', 'price'}
        missing_fields = required_fields - set(column_map.keys())
        if missing_fields:
            raise ValidationError(
                f"Required columns not found: {missing_fields}. "
                f"Available headers: {headers}. "
                f"Consider providing manual column_mapping."
            )
        
        return column_map
    
    def _determine_characteristic_columns(
        self,
        headers: List[str],
        column_map: Dict[str, int],
        explicit_cols: Optional[List[str]],
        log: Any
    ) -> List[int]:
        """Determine which columns become characteristics."""
        mapped_indices = set(column_map.values())
        
        if explicit_cols:
            normalized_headers = [h.strip().lower() if h else "" for h in headers]
            characteristic_indices = []
            for col_name in explicit_cols:
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
    
    def _parse_row_legacy(
        self,
        row_data: List[str],
        row_number: int,
        headers: List[str],
        column_map: Dict[str, int],
        characteristic_cols: List[int],
        log: Any
    ) -> ParsedSupplierItem:
        """Parse row using legacy approach."""
        
        def get_cell(col_idx: int) -> str:
            if col_idx >= len(row_data):
                raise ValidationError(f"Row {row_number}: Column index {col_idx} out of bounds")
            value = row_data[col_idx].strip() if row_data[col_idx] else ""
            return value
        
        sku = get_cell(column_map['sku'])
        name = get_cell(column_map['name'])
        price_str = get_cell(column_map['price'])
        
        if not sku:
            raise ValidationError(f"Row {row_number}: SKU is empty")
        if not name:
            raise ValidationError(f"Row {row_number}: Name is empty")
        
        price = self._parse_price(price_str)
        if price is None:
            raise ValidationError(f"Row {row_number}: Invalid price '{price_str}'")
        
        # Build characteristics
        characteristics: Dict[str, Any] = {}
        for col_idx in characteristic_cols:
            if col_idx >= len(headers):
                continue
            header_name = headers[col_idx].strip()
            if not header_name:
                continue
            
            if col_idx < len(row_data):
                cell_value = row_data[col_idx].strip() if row_data[col_idx] else None
            else:
                cell_value = None
            
            if cell_value:
                key = self._normalize_header_key(header_name)
                characteristics[key] = self._parse_cell_value(cell_value)
        
        return ParsedSupplierItem(
            supplier_sku=sku,
            name=name,
            price=price,
            characteristics=characteristics
        )
