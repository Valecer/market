"""Excel file parser implementation with dynamic header detection.

This parser automatically:
- Detects header rows (single or multi-row)
- Maps Russian column names to standard fields
- Tracks categories from section headers
- Parses all worksheets with priority scoring
- Backward compatible with manual configuration

Implements ParserInterface for Marketbel project.
"""
import re
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


class ExcelParser(ParserInterface):
    """Enhanced Excel parser with dynamic structure detection.
    
    This parser reads Excel files using pandas + openpyxl with automatic
    structure detection for Russian price lists.
    
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
    - _source_sheet: Source sheet name
    """
    
    # Legacy standard fields for backward compatibility
    STANDARD_FIELDS = {
        'sku': ['sku', 'product code', 'item code', 'product_id', 'item_id', 'code', 'артикул', 'код'],
        'name': ['name', 'product name', 'description', 'product description', 'title', 'item', 'название', 'наименование', 'товар', 'модель'],
        'price': ['price', 'unit price', 'cost', 'unit cost', 'amount', 'value', 'цена', 'стоимость', 'сток']
    }
    
    def __init__(self):
        """Initialize Excel parser with dynamic detector."""
        self._detector = DynamicHeaderDetector()
        self._name_parser = ProductNameParser()
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
        
        This method supports two modes:
        1. Auto-detect mode (default): Automatically finds headers, sections, columns
        2. Manual mode: Uses config settings for header_row, column_mapping, etc.
        
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
            
            # Check if auto-detect should be used
            use_auto_detect = self._should_use_auto_detect(parsed_config)
            
            if use_auto_detect:
                log.info("using_auto_detect_mode")
                return await self._parse_with_auto_detect(file_path, engine, parsed_config, log)
            else:
                log.info("using_manual_mode")
                return await self._parse_with_manual_config(file_path, engine, parsed_config, log)
            
        except pd.errors.EmptyDataError:
            raise ParserError("Excel file is empty or contains no data")
        except Exception as e:
            if isinstance(e, (ParserError, ValidationError)):
                raise
            raise ParserError(f"Unexpected error during Excel parsing: {e}") from e
    
    def _should_use_auto_detect(self, config: ExcelParserConfig) -> bool:
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
        file_path: Path,
        engine: str,
        config: ExcelParserConfig,
        log: Any
    ) -> List[ParsedSupplierItem]:
        """Parse using automatic structure detection."""
        
        # Get all sheet names
        xl = pd.ExcelFile(file_path, engine=engine)
        all_sheets = xl.sheet_names
        
        if not all_sheets:
            raise ParserError("No sheets found in Excel file")
        
        log.info("sheets_found", sheet_count=len(all_sheets), sheets=all_sheets)
        
        # Determine which sheets to parse
        sheets_to_parse = self._select_sheets_to_parse(all_sheets, config.sheet_name, log)
        
        all_parsed_items: List[ParsedSupplierItem] = []
        
        for sheet_name in sheets_to_parse:
            try:
                # Read sheet data
                df_raw = pd.read_excel(
                    file_path,
                    sheet_name=sheet_name,
                    header=None,
                    skiprows=0,
                    dtype=str,
                    na_values=['', 'N/A', 'n/a', 'NA', 'null', 'NULL', 'None'],
                    keep_default_na=True,
                    engine=engine
                )
                
                if df_raw.empty:
                    log.warning("empty_sheet_skipped", sheet_name=sheet_name)
                    continue
                
                # Convert to list of lists for detector
                all_values = df_raw.fillna('').values.tolist()
                all_values = [[str(cell) for cell in row] for row in all_values]
                
                # Analyze structure
                try:
                    structure = self._detector.analyze_sheet(all_values, sheet_name)
                except ValueError as e:
                    log.warning("sheet_analysis_failed", sheet_name=sheet_name, error=str(e))
                    continue
                
                log.info(
                    "structure_detected",
                    sheet_name=sheet_name,
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
                    log.warning("name_column_not_found_skipping_sheet", sheet_name=sheet_name)
                    continue
                
                # Get combined headers
                combined_headers = self._get_combined_headers(all_values, structure)
                
                # Initialize section tracker
                section_tracker = SectionTracker(structure.sections)
                
                # Use sheet name as fallback category
                fallback_category = self._clean_sheet_name_for_category(sheet_name)
                
                # Parse data rows
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
                            sheet_name,
                            fallback_category,
                            log
                        )
                        if item:
                            all_parsed_items.append(item)
                            
                    except ValidationError as e:
                        log.warning("row_validation_failed", sheet_name=sheet_name, row_number=row_idx + 1, error=str(e))
                    except Exception as e:
                        log.warning("row_parse_error", sheet_name=sheet_name, row_number=row_idx + 1, error=str(e))
                
            except Exception as e:
                log.warning("sheet_parse_failed", sheet_name=sheet_name, error=str(e))
                continue
        
        log.info(
            "parse_completed",
            total_sheets=len(sheets_to_parse),
            total_items=len(all_parsed_items)
        )
        
        return all_parsed_items
    
    def _select_sheets_to_parse(
        self,
        all_sheets: List[str],
        requested_sheet: Optional[str],
        log: Any
    ) -> List[str]:
        """Select which sheets to parse based on configuration."""
        if requested_sheet:
            # If specific sheet requested, use only that
            if requested_sheet in all_sheets:
                return [requested_sheet]
            else:
                log.warning(
                    "requested_sheet_not_found",
                    requested=requested_sheet,
                    available=all_sheets
                )
                # Fall back to all sheets
        
        # Parse all sheets
        return all_sheets
    
    def _clean_sheet_name_for_category(self, sheet_name: str) -> Optional[str]:
        """Clean sheet name to use as fallback category."""
        if not sheet_name:
            return None
        
        # Skip generic sheet names
        skip_names = ['лист1', 'лист2', 'лист3', 'sheet1', 'sheet2', 'sheet3',
                      'общий прайс', 'прайс', 'для загрузки', '1с', 'data']
        
        if sheet_name.lower().strip() in skip_names:
            return None
        
        return sheet_name.strip()
    
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
        sheet_name: str,
        fallback_category: Optional[str],
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
        
        price_retail = self._parse_price_auto(price_retail_str)
        price_wholesale = self._parse_price_auto(price_wholesale_str)
        
        # Determine primary price (prefer retail)
        primary_price = price_retail or price_wholesale
        if primary_price is None:
            log.debug("no_price_found", row=row_idx + 1, name=name[:30] if name else '')
            primary_price = Decimal("0")
        
        # Extract other fields
        sku = get_cell(FieldType.SKU)
        availability = get_cell(FieldType.AVAILABILITY)
        image = get_cell(FieldType.IMAGE)
        description = get_cell(FieldType.DESCRIPTION)
        link = get_cell(FieldType.LINK)
        
        # Get category from section tracker, fallback to parsed category or sheet name
        category = section_tracker.get_category(row_idx)
        if not category and parsed_name.category_prefix:
            category = parsed_name.category_prefix
        if not category and fallback_category:
            category = fallback_category
        
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
        characteristics['_source_sheet'] = sheet_name
        
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
    
    def _parse_price_auto(self, price_str: Optional[str]) -> Optional[Decimal]:
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
        
        negative = [
            'нет в наличии', 'нет', 'отсутствует', 'под заказ',
            'временно недоступно', 'закончились', 'out of stock',
            'по запросу', 'ожидается', 'в пути', 'уточнять',
            'недоступно к заказу', 'временно нет',
        ]
        
        positive = [
            'в наличии', 'есть', 'да', '+', 'available', 'in stock',
            'на складе', 'имеется',
        ]
        
        for neg in negative:
            if neg in text_lower:
                return False
        
        for pos in positive:
            if pos in text_lower:
                return True
        
        # Date pattern = out of stock
        if re.search(r'\d{2}\.\d{2}', text_lower):
            return False
        
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
    
    async def _parse_with_manual_config(
        self,
        file_path: Path,
        engine: str,
        config: ExcelParserConfig,
        log: Any
    ) -> List[ParsedSupplierItem]:
        """Parse using manual configuration (legacy mode)."""
        
        # Determine header rows range
        header_row_start = config.header_row - 1  # Convert to 0-indexed
        header_row_end = (config.header_row_end - 1) if config.header_row_end else header_row_start
        header_rows = list(range(header_row_start, header_row_end + 1))
        
        # Read Excel file to get raw data
        try:
            df_raw = pd.read_excel(
                file_path,
                sheet_name=config.sheet_name,
                header=None,
                skiprows=0,
                dtype=str,
                na_values=['', 'N/A', 'n/a', 'NA', 'null', 'NULL', 'None'],
                keep_default_na=True,
                engine=engine
            )
        except ValueError as e:
            if "Worksheet" in str(e) or "sheet" in str(e).lower():
                xl = pd.ExcelFile(file_path, engine=engine)
                available_sheets = xl.sheet_names
                
                if not available_sheets:
                    raise ParserError("No sheets found in Excel file")
                
                first_sheet = available_sheets[0]
                log.warning(
                    "sheet_not_found_using_fallback",
                    requested_sheet=config.sheet_name,
                    fallback_sheet=first_sheet,
                    available_sheets=available_sheets
                )
                
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
        
        # Extract and combine headers
        headers = self._combine_header_rows(df_raw, header_rows, log)
        column_map = self._map_columns(headers, config.column_mapping, log)
        
        # Determine characteristic columns
        characteristic_cols = self._determine_characteristic_columns(
            headers, column_map, config.characteristic_columns, log
        )
        
        # Read data rows
        data_start_idx = config.data_start_row - 1
        df = df_raw.iloc[data_start_idx:].copy()
        df.columns = range(len(headers))
        
        log.info(
            "excel_data_read",
            total_rows=len(df),
            sheet_name=config.sheet_name,
            header_row=config.header_row,
            data_start_row=config.data_start_row
        )
        
        # Parse rows
        parsed_items: List[ParsedSupplierItem] = []
        for df_idx, row in df.iterrows():
            row_number = df_idx + config.data_start_row
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

