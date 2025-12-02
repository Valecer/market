"""Dynamic header detector for Google Sheets with varying structures.

This module provides intelligent detection of:
- Header rows (single or multi-row)
- Section/category rows
- Column types based on Russian field names
- Repeated headers within data

Part of Marketbel project - Phase 1 enhancement.
"""

import re
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class RowType(Enum):
    """Classification of row types in a spreadsheet."""
    HEADER = "header"
    DATA = "data"
    SECTION = "section"
    SUBSECTION = "subsection"
    EMPTY = "empty"
    INFO = "info"
    REPEATED_HEADER = "repeated_header"


class FieldType(Enum):
    """Standard field types for mapping."""
    NAME = "name"
    DESCRIPTION = "description"
    PRICE_WHOLESALE = "price_wholesale"
    PRICE_RETAIL = "price_retail"
    AVAILABILITY = "availability"
    IMAGE = "image"
    SKU = "sku"
    LINK = "link"
    CATEGORY = "category"
    UNKNOWN = "unknown"


@dataclass
class ColumnMapping:
    """Mapping of a column to a field type."""
    index: int
    header_text: str
    field_type: FieldType
    confidence: float


@dataclass
class RowClassification:
    """Classification result for a single row."""
    row_index: int
    row_type: RowType
    section_name: Optional[str] = None
    data: Optional[List[str]] = None


@dataclass
class SheetStructure:
    """Complete structure analysis of a worksheet."""
    header_rows: List[int]
    data_start_row: int
    column_mappings: List[ColumnMapping]
    sections: List[Tuple[int, str]]
    repeated_header_rows: Set[int]
    info_rows: Set[int] = field(default_factory=set)  # Footnotes, annotations, metadata
    priority_score: float = 0.0


@dataclass
class DetectorConfig:
    """Configuration for the header detector."""
    min_header_columns: int = 2
    max_header_scan_rows: int = 15
    min_field_confidence: float = 0.5
    priority_sheet_keywords: List[str] = field(default_factory=lambda: [
        'загрузк', '1с', 'сайт', 'выгрузк', 'импорт', 'экспорт', 'основн'
    ])


class FieldPatternMatcher:
    """Matches column headers to field types using patterns."""
    
    FIELD_PATTERNS: Dict[FieldType, List[str]] = {
        FieldType.NAME: [
            'наименование', 'название', 'модель', 'товар', 'продукт',
            'наименование|ссылка', 'наименование товара', 'имя', 'позиция',
            'наименование (вся техника', 'name', 'product name', 'description',
        ],
        FieldType.DESCRIPTION: [
            'характеристики', 'описание', 'спецификация', 'параметры',
            'свойства', 'детали', 'примечание'
        ],
        FieldType.PRICE_WHOLESALE: [
            'опт', 'оптовая', 'цена с ндс', 'закупка', 'закупочная',
            'оптовая цена', 'оптовая цена с ндс', 'цена опт', 'предзаказ',
            'закупка бел', 'закупка бел. руб', 'закупочная цена',
            'предзаказ (пз)', 'сток', 'сток*', 'предзаказ*',
        ],
        FieldType.PRICE_RETAIL: [
            'мрц', 'ррц', 'розница', 'розничная', 'рекомендуемая',
            'рц', 'розничная цена', 'цена розница', 'мрц*', 'ррц*',
            'мрц бел', 'мрц бел. руб', 'ррц бел', 'рекомендуемая цена',
            'рц, руб', 'рц руб', 'мрц (byn)', 'мрц* (byn)',
        ],
        FieldType.AVAILABILITY: [
            'наличие', 'остаток', 'статус', 'в наличии', 'stock',
            'количество', 'кол-во', 'доступно', 'availability',
        ],
        FieldType.IMAGE: [
            'фото', 'фотография', 'изображение', 'картинка', 'фотографии',
            'медиабанк', 'медиа', 'image', 'photo', 'img',
        ],
        FieldType.SKU: [
            'артикул', 'код', 'sku', 'id', 'код товара', 'product code',
            'item code', 'номер',
        ],
        FieldType.LINK: [
            'ссылка', 'url', 'сайт', 'link', 'href', 'характеристики на сайте',
        ],
    }
    
    GENERIC_PRICE_WORDS = ['цена', 'price', 'стоимость', 'руб', 'byn', 'рц']
    
    @classmethod
    def match_field(cls, header: str) -> Tuple[FieldType, float]:
        """Match a header string to a field type."""
        if not header or not header.strip():
            return FieldType.UNKNOWN, 0.0
        
        normalized = header.strip().lower()
        normalized = re.sub(r'[*\(\)]', '', normalized).strip()
        
        # Check for exact match with generic price words first
        # Standalone "Цена" should default to retail (customer-facing price)
        if normalized in cls.GENERIC_PRICE_WORDS:
            return FieldType.PRICE_RETAIL, 0.5
        
        best_match = FieldType.UNKNOWN
        best_confidence = 0.0
        
        for field_type, patterns in cls.FIELD_PATTERNS.items():
            for pattern in patterns:
                if normalized == pattern:
                    return field_type, 1.0
                
                if pattern in normalized:
                    confidence = len(pattern) / len(normalized) * 0.9
                    if confidence > best_confidence:
                        best_match = field_type
                        best_confidence = confidence
                
                if any(word in normalized for word in pattern.split()):
                    confidence = 0.6
                    if confidence > best_confidence:
                        best_match = field_type
                        best_confidence = confidence
        
        if best_match == FieldType.UNKNOWN:
            for word in cls.GENERIC_PRICE_WORDS:
                if word in normalized:
                    return FieldType.PRICE_RETAIL, 0.5
        
        return best_match, best_confidence


class RowClassifier:
    """Classifies rows by their type."""
    
    SECTION_PATTERNS = [
        r'^электро',
        r'^мото',
        r'^минитрактор',
        r'оборудование$',
        r'^модификация\s*[-–—]',
        r'^категория',
        r'^раздел',
        r'^группа',
        r'топ продаж',
        r'^квадроцикл',
        r'^прицеп',
        r'^адаптер',
        r'^трицикл',
        r'^самокат',
        r'^велосипед',
        r'^скутер',
        r'^снегоуборщик',
        r'^культиватор',
        r'^навесное',
        r'транспорт$',
        r'транспорт\s+shtenli',
        r'^бензиновый',
        r'^шлем',
        r'^запчаст',
    ]
    
    INFO_INDICATORS = [
        'поставщик', 'компания', 'контакт', 'телефон', 'адрес',
        'email', 'сайт:', 'р/с', 'унп', 'инн', 'что мы предлагаем',
        'не является публичной офертой', 'прайс-лист', 'оптовый прайс',
        'контактные номера', 'выходной', 'ежедневно', 'sales.opt',
    ]
    
    # Patterns for footnote/annotation rows (explanatory text about columns/prices)
    FOOTNOTE_PATTERNS = [
        r'^\*+\d*\.?\s*',                    # Rows starting with * or ** and optional number: *1. , **2.
        r'^примечани[ея]',                   # Notes
        r'^внимание',                        # Warning
        r'^важно',                           # Important
        r'минимальная\s+розничная\s+цена',   # МРЦ explanations
        r'рекомендуемая\s+розничная',        # РРЦ explanations
        r'конечная\s+стоимость',             # Final price notes
        r'определяется\s+после',             # "Determined after..." notes
        r'цена\s+может\s+(меняться|измениться)', # "Price may change" notes
        r'уточняйте\s+',                     # "Please clarify" notes
    ]
    
    def __init__(self, field_matcher: FieldPatternMatcher):
        self.field_matcher = field_matcher
    
    def classify_row(
        self,
        row_data: List[str],
        row_index: int,
        known_headers: Optional[List[str]] = None
    ) -> RowClassification:
        """Classify a single row."""
        non_empty_cells = [c for c in row_data if c and str(c).strip()]
        if not non_empty_cells:
            return RowClassification(row_index, RowType.EMPTY)
        
        combined_text = ' '.join(str(c).strip().lower() for c in row_data if c)
        
        # Check for info indicators
        if any(indicator in combined_text for indicator in self.INFO_INDICATORS):
            return RowClassification(row_index, RowType.INFO)
        
        # Check for footnote/annotation patterns (e.g., *1. МРЦ - ..., **2. Цена...)
        if self._is_footnote_row(row_data, non_empty_cells, combined_text):
            return RowClassification(row_index, RowType.INFO)
        
        section_name = self._detect_section(row_data, non_empty_cells)
        if section_name:
            if 'модификация' in section_name.lower():
                return RowClassification(row_index, RowType.SUBSECTION, section_name=section_name)
            return RowClassification(row_index, RowType.SECTION, section_name=section_name)
        
        if self._is_header_row(row_data, known_headers):
            if known_headers and self._headers_match(row_data, known_headers):
                return RowClassification(row_index, RowType.REPEATED_HEADER)
            return RowClassification(row_index, RowType.HEADER)
        
        if self._is_data_row(row_data):
            return RowClassification(row_index, RowType.DATA, data=row_data)
        
        return RowClassification(row_index, RowType.INFO)
    
    def _detect_section(self, row_data: List[str], non_empty_cells: List[str]) -> Optional[str]:
        """Detect if row is a section header."""
        if len(non_empty_cells) > 3:
            return None
        
        first_cell = str(row_data[0]).strip() if row_data and row_data[0] else ''
        if not first_cell:
            for cell in row_data:
                if cell and str(cell).strip():
                    first_cell = str(cell).strip()
                    break
        
        if not first_cell:
            return None
        
        first_lower = first_cell.lower()
        
        for pattern in self.SECTION_PATTERNS:
            if re.search(pattern, first_lower):
                return first_cell
        
        if (len(non_empty_cells) == 1 and 
            len(first_cell) > 10 and
            not any(c.isdigit() for c in first_cell[:20])):
            if not re.search(r'\d{3,}', first_cell):
                return first_cell
        
        return None
    
    def _is_header_row(self, row_data: List[str], known_headers: Optional[List[str]] = None) -> bool:
        """Check if row appears to be a header row."""
        non_empty = [c for c in row_data if c and str(c).strip()]
        if len(non_empty) < 2:
            return False
        
        matches = 0
        has_numeric = False
        
        for cell in row_data:
            if cell:
                cell_str = str(cell).strip()
                if re.match(r'^[\d\s,\.]+$', cell_str.replace(' ', '')):
                    has_numeric = True
                
                field_type, confidence = self.field_matcher.match_field(cell_str)
                if field_type != FieldType.UNKNOWN and confidence >= 0.5:
                    matches += 1
        
        if has_numeric and matches < 3:
            return False
        
        return matches >= 2
    
    def _headers_match(self, row_data: List[str], known_headers: List[str]) -> bool:
        """Check if row matches known headers."""
        row_non_empty = [str(c).strip().lower() for c in row_data if c and str(c).strip()]
        header_non_empty = [str(h).strip().lower() for h in known_headers if h and str(h).strip()]
        
        if not row_non_empty or not header_non_empty:
            return False
        
        matches = sum(1 for cell in row_non_empty if cell in header_non_empty)
        return matches / len(row_non_empty) > 0.5 if row_non_empty else False
    
    def _is_footnote_row(
        self,
        row_data: List[str],
        non_empty_cells: List[str],
        combined_text: str
    ) -> bool:
        """Check if row is a footnote/annotation row (explanatory text about columns).
        
        Examples:
        - "*1. Конечная стоимость , определяется после поступления товара на склад"
        - "**2. МРЦ - Минимальная Розничная Цена"
        """
        # Footnotes typically have 1-2 filled cells and are text-heavy without prices
        if len(non_empty_cells) > 3:
            return False
        
        # Get first non-empty cell
        first_cell = ''
        for cell in row_data:
            if cell and str(cell).strip():
                first_cell = str(cell).strip()
                break
        
        if not first_cell:
            return False
        
        first_lower = first_cell.lower()
        
        # Check footnote patterns
        for pattern in self.FOOTNOTE_PATTERNS:
            if re.search(pattern, first_lower):
                return True
        
        # Check if row starts with asterisk(s) and looks like an annotation
        # e.g., "* примечание", "** важно", "*1.", "**2."
        if first_cell.startswith('*'):
            # Strip asterisks and check if remaining text is explanatory
            stripped = first_cell.lstrip('*').strip()
            # If it's just a number or number+period, or starts with text
            if stripped and (
                re.match(r'^\d+\.?\s*\D', stripped) or  # "*1. text" or "*2 text"
                (len(stripped) > 5 and not re.match(r'^[\d\s,\.]+$', stripped))  # "*explanatory text"
            ):
                return True
        
        return False
    
    def _is_data_row(self, row_data: List[str]) -> bool:
        """Check if row appears to be a data row."""
        non_empty = [c for c in row_data if c and str(c).strip()]
        if len(non_empty) < 2:
            return False
        
        has_number = False
        has_text = False
        
        for cell in row_data:
            if cell:
                cell_str = str(cell).strip()
                if re.match(r'^[\d\s,\.]+$', cell_str.replace(' ', '')):
                    has_number = True
                elif len(cell_str) > 3 and any(c.isalpha() for c in cell_str):
                    has_text = True
        
        return has_number and has_text


class DynamicHeaderDetector:
    """Main detector class for analyzing Google Sheets structure."""
    
    def __init__(self, config: Optional[DetectorConfig] = None):
        self.config = config or DetectorConfig()
        self.field_matcher = FieldPatternMatcher()
        self.row_classifier = RowClassifier(self.field_matcher)
        self.log = logger.bind(component="DynamicHeaderDetector")
    
    def analyze_sheet(self, all_values: List[List[str]], sheet_name: str = "") -> SheetStructure:
        """Analyze a worksheet and return its structure."""
        if not all_values:
            raise ValueError("Empty worksheet provided")
        
        log = self.log.bind(sheet_name=sheet_name, total_rows=len(all_values))
        
        header_rows, header_data = self._find_header_rows(all_values)
        log.debug("header_rows_found", header_rows=header_rows)
        
        combined_headers = self._combine_headers(header_data)
        column_mappings = self._map_columns(combined_headers)
        
        data_start_row = header_rows[-1] + 1 if header_rows else 0
        sections, repeated_headers, info_rows = self._find_sections_and_repeated_headers(
            all_values, data_start_row, combined_headers
        )
        
        # Calculate priority with row count
        data_row_count = self._count_data_rows(all_values, data_start_row, sections, repeated_headers, info_rows)
        priority_score = self._calculate_priority_score(sheet_name, column_mappings, data_row_count)
        
        return SheetStructure(
            header_rows=header_rows,
            data_start_row=data_start_row,
            column_mappings=column_mappings,
            sections=sections,
            repeated_header_rows=repeated_headers,
            info_rows=info_rows,
            priority_score=priority_score
        )
    
    def _find_header_rows(self, all_values: List[List[str]]) -> Tuple[List[int], List[List[str]]]:
        """Find header row(s) in the worksheet."""
        header_rows = []
        header_data = []
        max_scan = min(self.config.max_header_scan_rows, len(all_values))
        
        for row_idx in range(max_scan):
            row = all_values[row_idx]
            classification = self.row_classifier.classify_row(row, row_idx)
            
            if classification.row_type == RowType.HEADER:
                header_rows.append(row_idx)
                header_data.append(row)
                
                if row_idx + 1 < max_scan:
                    next_row = all_values[row_idx + 1]
                    has_numbers = any(
                        cell and re.match(r'^[\d\s,\.]+$', str(cell).strip().replace(' ', ''))
                        for cell in next_row if cell
                    )
                    if not has_numbers:
                        next_class = self.row_classifier.classify_row(next_row, row_idx + 1)
                        if next_class.row_type == RowType.HEADER:
                            header_rows.append(row_idx + 1)
                            header_data.append(next_row)
                break
            
            if classification.row_type == RowType.DATA:
                if row_idx > 0:
                    prev_row = all_values[row_idx - 1]
                    non_empty = [c for c in prev_row if c and str(c).strip()]
                    if len(non_empty) >= 2:
                        header_rows = [row_idx - 1]
                        header_data = [prev_row]
                break
        
        if not header_rows:
            for row_idx, row in enumerate(all_values[:max_scan]):
                non_empty = [c for c in row if c and str(c).strip()]
                if len(non_empty) >= 2:
                    header_rows = [row_idx]
                    header_data = [row]
                    break
        
        return header_rows, header_data
    
    def _combine_headers(self, header_rows_data: List[List[str]]) -> List[str]:
        """Combine multi-row headers into single header list."""
        if not header_rows_data:
            return []
        
        if len(header_rows_data) == 1:
            return [str(c).strip() if c else '' for c in header_rows_data[0]]
        
        max_cols = max(len(row) for row in header_rows_data)
        combined = []
        
        for col_idx in range(max_cols):
            parts = []
            for row in header_rows_data:
                if col_idx < len(row) and row[col_idx]:
                    part = str(row[col_idx]).strip()
                    if part and part not in parts:
                        parts.append(part)
            combined.append(' '.join(parts))
        
        return combined
    
    def _map_columns(self, headers: List[str]) -> List[ColumnMapping]:
        """Map columns to field types."""
        mappings = []
        assigned_fields: Dict[FieldType, int] = {}
        
        for idx, header in enumerate(headers):
            field_type, confidence = self.field_matcher.match_field(header)
            
            if field_type != FieldType.UNKNOWN:
                if field_type in assigned_fields:
                    existing_idx = assigned_fields[field_type]
                    existing_mapping = mappings[existing_idx]
                    if confidence > existing_mapping.confidence:
                        mappings[existing_idx] = ColumnMapping(existing_idx, headers[existing_idx], FieldType.UNKNOWN, 0.0)
                        assigned_fields[field_type] = len(mappings)
                    else:
                        field_type = FieldType.UNKNOWN
                        confidence = 0.0
                else:
                    assigned_fields[field_type] = len(mappings)
            
            mappings.append(ColumnMapping(idx, header, field_type, confidence))
        
        return mappings
    
    def _find_sections_and_repeated_headers(
        self,
        all_values: List[List[str]],
        start_row: int,
        known_headers: List[str]
    ) -> Tuple[List[Tuple[int, str]], Set[int], Set[int]]:
        """Find section headers, repeated header rows, and info/footnote rows."""
        sections = []
        repeated_headers = set()
        info_rows = set()
        
        for row_idx in range(start_row, len(all_values)):
            row = all_values[row_idx]
            classification = self.row_classifier.classify_row(row, row_idx, known_headers)
            
            if classification.row_type == RowType.SECTION:
                sections.append((row_idx, classification.section_name))
            elif classification.row_type == RowType.SUBSECTION:
                sections.append((row_idx, f"[sub]{classification.section_name}"))
            elif classification.row_type == RowType.REPEATED_HEADER:
                repeated_headers.add(row_idx)
            elif classification.row_type == RowType.INFO:
                info_rows.add(row_idx)
        
        return sections, repeated_headers, info_rows
    
    def _count_data_rows(
        self,
        all_values: List[List[str]],
        start_row: int,
        sections: List[Tuple[int, str]],
        repeated_headers: Set[int],
        info_rows: Set[int] = None
    ) -> int:
        """Count actual data rows."""
        count = 0
        section_rows = {s[0] for s in sections}
        info_rows = info_rows or set()
        
        for row_idx in range(start_row, len(all_values)):
            if row_idx in repeated_headers or row_idx in section_rows or row_idx in info_rows:
                continue
            row = all_values[row_idx]
            if any(cell and str(cell).strip() for cell in row):
                count += 1
        
        return count
    
    def _calculate_priority_score(
        self,
        sheet_name: str,
        column_mappings: List[ColumnMapping],
        data_row_count: int = 0
    ) -> float:
        """Calculate priority score for sheet selection."""
        score = 0.0
        name_lower = sheet_name.lower()
        
        negative_keywords = [
            'шаблон', 'template', 'пример', 'example', 'старый', 'old',
            'архив', 'archive', 'тест', 'test', 'копия', 'copy'
        ]
        for keyword in negative_keywords:
            if keyword in name_lower:
                score -= 15.0
                break
        
        for keyword in self.config.priority_sheet_keywords:
            if keyword in name_lower:
                score += 10.0
                break
        
        mapped_count = sum(1 for m in column_mappings if m.field_type != FieldType.UNKNOWN)
        score += mapped_count * 2.0
        
        essential = {FieldType.NAME, FieldType.PRICE_RETAIL, FieldType.PRICE_WHOLESALE}
        mapped_types = {m.field_type for m in column_mappings}
        score += len(essential & mapped_types) * 5.0
        
        if FieldType.PRICE_RETAIL in mapped_types and FieldType.PRICE_WHOLESALE in mapped_types:
            score += 5.0
        
        if data_row_count > 0:
            score += min(data_row_count * 0.1, 20.0)
        
        return score


class SectionTracker:
    """Tracks current section/category while iterating through rows."""
    
    def __init__(self, sections: List[Tuple[int, str]]):
        self.sections = sorted(sections, key=lambda x: x[0])
        self._current_section: Optional[str] = None
        self._current_subsection: Optional[str] = None
    
    def get_category(self, row_index: int) -> Optional[str]:
        """Get the category for a given row."""
        for section_row, section_name in self.sections:
            if section_row > row_index:
                break
            
            if section_name.startswith('[sub]'):
                self._current_subsection = section_name[5:]
            else:
                self._current_section = section_name
                self._current_subsection = None
        
        if self._current_section and self._current_subsection:
            return f"{self._current_section} > {self._current_subsection}"
        return self._current_section or self._current_subsection
    
    def reset(self):
        """Reset tracking state."""
        self._current_section = None
        self._current_subsection = None


def detect_sheet_structure(all_values: List[List[str]], sheet_name: str = "") -> SheetStructure:
    """Convenience function to detect sheet structure."""
    detector = DynamicHeaderDetector()
    return detector.analyze_sheet(all_values, sheet_name)
