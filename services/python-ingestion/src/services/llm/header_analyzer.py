"""LLM-based header analyzer for spreadsheets.

Uses local LLM to intelligently detect:
- Header row positions
- Column type mappings
- Metadata vs data rows
- Merged cell handling

This analyzer enhances the rule-based DynamicHeaderDetector
by using LLM understanding for ambiguous cases.

Example:
    analyzer = LLMHeaderAnalyzer()
    result = await analyzer.analyze_headers(sheet_data)
    print(result.header_row, result.column_mapping)
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import structlog

from .client import LLMClient, LLMConfig, get_llm_client

logger = structlog.get_logger(__name__)


@dataclass
class ColumnInfo:
    """Information about a detected column."""
    index: int
    header_text: str
    field_type: str  # name, price, sku, availability, etc.
    confidence: float
    reasoning: Optional[str] = None


@dataclass
class HeaderAnalysisResult:
    """Result of LLM header analysis."""
    header_row: int  # 0-indexed
    header_row_end: int  # For multi-row headers
    data_start_row: int
    columns: List[ColumnInfo]
    metadata_rows: List[int] = field(default_factory=list)
    section_rows: List[Tuple[int, str]] = field(default_factory=list)
    confidence: float = 0.0
    llm_reasoning: Optional[str] = None
    
    @property
    def column_mapping(self) -> Dict[str, int]:
        """Get field_type -> column_index mapping."""
        return {
            col.field_type: col.index
            for col in self.columns
            if col.field_type != "unknown"
        }
    
    @property
    def has_name_column(self) -> bool:
        return any(c.field_type == "name" for c in self.columns)
    
    @property
    def has_price_column(self) -> bool:
        return any(c.field_type in ("price", "price_wholesale", "price_retail") for c in self.columns)


# Prompt templates for header analysis
HEADER_ANALYSIS_SYSTEM_PROMPT = """Ты - эксперт по анализу прайс-листов и таблиц поставщиков.
Твоя задача - определить структуру таблицы:

1. Найти строку(и) с заголовками колонок
2. Определить тип данных каждой колонки
3. Найти строки с метаданными (контакты, описание компании)
4. Найти строки-разделители категорий

Типы колонок:
- name: название товара, модель, наименование
- sku: артикул, код товара
- price_wholesale: оптовая цена, закупочная цена, цена с НДС
- price_retail: МРЦ, РРЦ, розничная цена, рекомендуемая цена  
- availability: наличие, остаток, статус
- image: фото, изображение
- description: характеристики, описание
- link: ссылка, URL
- unknown: неопределённый тип

Отвечай ТОЛЬКО в формате JSON."""

HEADER_ANALYSIS_PROMPT_TEMPLATE = """Проанализируй эту таблицу и определи её структуру.

Первые {num_rows} строк таблицы:
{rows_text}

Определи:
1. header_row: номер строки с основными заголовками (0-indexed)
2. header_row_end: номер последней строки заголовков (для многострочных заголовков)
3. data_start_row: номер первой строки с данными
4. columns: список колонок с типами
5. metadata_rows: номера строк с метаданными (контакты, реквизиты)
6. section_rows: номера строк-разделителей категорий

JSON формат ответа:
{{
  "header_row": 0,
  "header_row_end": 0,
  "data_start_row": 1,
  "columns": [
    {{"index": 0, "header_text": "Наименование", "field_type": "name", "confidence": 0.95}},
    {{"index": 1, "header_text": "Цена", "field_type": "price_wholesale", "confidence": 0.9}}
  ],
  "metadata_rows": [],
  "section_rows": [],
  "reasoning": "Объяснение анализа"
}}"""


class LLMHeaderAnalyzer:
    """Analyzes spreadsheet headers using LLM.
    
    Works in two modes:
    1. Full LLM analysis - uses LLM for complete structure detection
    2. Hybrid mode - combines rule-based detection with LLM for ambiguous cases
    
    Example:
        analyzer = LLMHeaderAnalyzer()
        result = await analyzer.analyze_headers(sheet_data)
    """
    
    def __init__(
        self,
        client: Optional[LLMClient] = None,
        config: Optional[LLMConfig] = None,
        max_rows_to_analyze: int = 20,
    ):
        """Initialize analyzer.
        
        Args:
            client: LLM client to use (creates default if not provided)
            config: LLM configuration
            max_rows_to_analyze: Maximum rows to send to LLM
        """
        self._client = client
        self._config = config
        self.max_rows_to_analyze = max_rows_to_analyze
        self._log = logger.bind(component="LLMHeaderAnalyzer")
    
    @property
    def client(self) -> LLMClient:
        """Get LLM client (lazy initialization)."""
        if self._client is None:
            self._client = get_llm_client(self._config)
        return self._client
    
    async def analyze_headers(
        self,
        rows: List[List[str]],
        sheet_name: str = "",
        hint_header_row: Optional[int] = None,
    ) -> HeaderAnalysisResult:
        """Analyze spreadsheet to detect headers and structure.
        
        Args:
            rows: List of rows, each row is a list of cell values
            sheet_name: Optional sheet name for context
            hint_header_row: Optional hint for expected header row
            
        Returns:
            HeaderAnalysisResult with detected structure
        """
        if not rows:
            return self._empty_result()
        
        # Check if LLM is available
        if not await self.client.is_available():
            self._log.warning("llm_not_available_falling_back_to_rules")
            return await self._fallback_analysis(rows)
        
        # Prepare rows for analysis
        analyze_rows = rows[:self.max_rows_to_analyze]
        rows_text = self._format_rows_for_prompt(analyze_rows)
        
        # Build prompt
        prompt = HEADER_ANALYSIS_PROMPT_TEMPLATE.format(
            num_rows=len(analyze_rows),
            rows_text=rows_text,
        )
        
        if sheet_name:
            prompt = f"Название листа: {sheet_name}\n\n{prompt}"
        
        if hint_header_row is not None:
            prompt += f"\n\nПодсказка: заголовки скорее всего в строке {hint_header_row}"
        
        try:
            # Get LLM analysis
            response = await self.client.complete_json(
                prompt=prompt,
                system_prompt=HEADER_ANALYSIS_SYSTEM_PROMPT,
            )
            
            result = self._parse_response(response, len(rows))
            
            self._log.info(
                "header_analysis_complete",
                header_row=result.header_row,
                data_start=result.data_start_row,
                columns_found=len(result.columns),
                confidence=result.confidence,
            )
            
            return result
            
        except Exception as e:
            self._log.error("llm_analysis_failed", error=str(e))
            return await self._fallback_analysis(rows)
    
    async def detect_column_types(
        self,
        headers: List[str],
        sample_data: Optional[List[List[str]]] = None,
    ) -> List[ColumnInfo]:
        """Detect column types from headers and optional sample data.
        
        This is a lighter-weight analysis when headers are already known.
        
        Args:
            headers: List of header strings
            sample_data: Optional sample data rows for context
            
        Returns:
            List of ColumnInfo with detected types
        """
        if not headers:
            return []
        
        if not await self.client.is_available():
            return self._rule_based_column_detection(headers)
        
        # Build prompt
        prompt = f"""Определи тип каждой колонки по заголовку:

Заголовки: {json.dumps(headers, ensure_ascii=False)}

"""
        if sample_data:
            sample_text = "\n".join(
                " | ".join(str(c) for c in row[:len(headers)])
                for row in sample_data[:3]
            )
            prompt += f"""
Примеры данных:
{sample_text}

"""
        
        prompt += """Верни JSON массив с типами колонок:
[
  {"index": 0, "header_text": "...", "field_type": "name|price_wholesale|price_retail|sku|availability|image|description|link|unknown", "confidence": 0.0-1.0}
]"""
        
        try:
            response = await self.client.complete_json(
                prompt=prompt,
                system_prompt="Ты эксперт по анализу прайс-листов. Определи типы колонок.",
            )
            
            columns = []
            items = response if isinstance(response, list) else response.get("items", response.get("columns", []))
            
            for item in items:
                if isinstance(item, dict):
                    columns.append(ColumnInfo(
                        index=item.get("index", 0),
                        header_text=item.get("header_text", ""),
                        field_type=item.get("field_type", "unknown"),
                        confidence=float(item.get("confidence", 0.5)),
                    ))
            
            return columns
            
        except Exception as e:
            self._log.warning("column_detection_failed", error=str(e))
            return self._rule_based_column_detection(headers)
    
    async def is_metadata_row(
        self,
        row: List[str],
        context_rows: Optional[List[List[str]]] = None,
    ) -> Tuple[bool, str]:
        """Check if a row is metadata (contacts, company info, etc.).
        
        Args:
            row: Row to check
            context_rows: Surrounding rows for context
            
        Returns:
            (is_metadata, reason)
        """
        row_text = " | ".join(str(c) for c in row if c)
        
        # Quick rule-based check first
        metadata_indicators = [
            "тел", "телефон", "адрес", "email", "@", "сайт:",
            "р/с", "унп", "инн", "поставщик:", "компания",
        ]
        
        row_lower = row_text.lower()
        for indicator in metadata_indicators:
            if indicator in row_lower:
                return True, f"Contains metadata indicator: {indicator}"
        
        # Use LLM for ambiguous cases
        if not await self.client.is_available():
            return False, "LLM not available"
        
        try:
            prompt = f"""Это строка с метаданными (контакты, реквизиты компании) или строка с данными товара?

Строка: {row_text}

Ответь JSON: {{"is_metadata": true/false, "reason": "объяснение"}}"""
            
            response = await self.client.complete_json(prompt=prompt)
            return response.get("is_metadata", False), response.get("reason", "")
            
        except Exception:
            return False, "Analysis failed"
    
    def _format_rows_for_prompt(self, rows: List[List[str]]) -> str:
        """Format rows as text for LLM prompt."""
        lines = []
        for idx, row in enumerate(rows):
            # Clean and join cells
            cells = [str(c).strip() if c else "" for c in row]
            # Truncate long cells
            cells = [c[:100] + "..." if len(c) > 100 else c for c in cells]
            # Format row
            row_text = " | ".join(cells)
            lines.append(f"Строка {idx}: {row_text}")
        return "\n".join(lines)
    
    def _parse_response(
        self,
        response: Dict[str, Any],
        total_rows: int,
    ) -> HeaderAnalysisResult:
        """Parse LLM response into HeaderAnalysisResult."""
        try:
            header_row = int(response.get("header_row", 0))
            header_row_end = int(response.get("header_row_end", header_row))
            data_start_row = int(response.get("data_start_row", header_row_end + 1))
            
            # Parse columns
            columns = []
            for col_data in response.get("columns", []):
                if isinstance(col_data, dict):
                    columns.append(ColumnInfo(
                        index=int(col_data.get("index", 0)),
                        header_text=str(col_data.get("header_text", "")),
                        field_type=str(col_data.get("field_type", "unknown")),
                        confidence=float(col_data.get("confidence", 0.5)),
                    ))
            
            # Parse metadata rows
            metadata_rows = [
                int(r) for r in response.get("metadata_rows", [])
                if isinstance(r, (int, float))
            ]
            
            # Parse section rows
            section_rows = []
            for section in response.get("section_rows", []):
                if isinstance(section, dict):
                    section_rows.append((
                        int(section.get("row", 0)),
                        str(section.get("name", "")),
                    ))
                elif isinstance(section, (int, float)):
                    section_rows.append((int(section), ""))
            
            # Calculate confidence
            confidence = self._calculate_confidence(columns, header_row, total_rows)
            
            return HeaderAnalysisResult(
                header_row=header_row,
                header_row_end=header_row_end,
                data_start_row=data_start_row,
                columns=columns,
                metadata_rows=metadata_rows,
                section_rows=section_rows,
                confidence=confidence,
                llm_reasoning=response.get("reasoning"),
            )
            
        except Exception as e:
            self._log.warning("parse_response_failed", error=str(e), response=response)
            return self._empty_result()
    
    def _calculate_confidence(
        self,
        columns: List[ColumnInfo],
        header_row: int,
        total_rows: int,
    ) -> float:
        """Calculate overall confidence score."""
        if not columns:
            return 0.0
        
        # Average column confidence
        avg_confidence = sum(c.confidence for c in columns) / len(columns)
        
        # Bonus for finding key columns
        has_name = any(c.field_type == "name" for c in columns)
        has_price = any(c.field_type in ("price_wholesale", "price_retail", "price") for c in columns)
        
        confidence = avg_confidence
        if has_name:
            confidence += 0.1
        if has_price:
            confidence += 0.1
        
        # Penalty if header row is very far into the sheet
        if header_row > 10:
            confidence -= 0.1
        
        return min(max(confidence, 0.0), 1.0)
    
    async def _fallback_analysis(self, rows: List[List[str]]) -> HeaderAnalysisResult:
        """Fallback to rule-based analysis when LLM is not available."""
        from ..classification.classifier import CategoryClassifier
        from ...parsers.dynamic_header_detector import DynamicHeaderDetector
        
        try:
            detector = DynamicHeaderDetector()
            structure = detector.analyze_sheet(rows)
            
            # Convert to our result format
            columns = [
                ColumnInfo(
                    index=m.index,
                    header_text=m.header_text,
                    field_type=m.field_type.value,
                    confidence=m.confidence,
                )
                for m in structure.column_mappings
            ]
            
            return HeaderAnalysisResult(
                header_row=structure.header_rows[0] if structure.header_rows else 0,
                header_row_end=structure.header_rows[-1] if structure.header_rows else 0,
                data_start_row=structure.data_start_row,
                columns=columns,
                metadata_rows=list(structure.info_rows),
                section_rows=structure.sections,
                confidence=0.6,  # Lower confidence for rule-based
            )
            
        except Exception as e:
            self._log.error("fallback_analysis_failed", error=str(e))
            return self._empty_result()
    
    def _rule_based_column_detection(self, headers: List[str]) -> List[ColumnInfo]:
        """Rule-based column type detection."""
        from ...parsers.dynamic_header_detector import FieldPatternMatcher
        
        matcher = FieldPatternMatcher()
        columns = []
        
        for idx, header in enumerate(headers):
            field_type, confidence = matcher.match_field(header)
            columns.append(ColumnInfo(
                index=idx,
                header_text=header,
                field_type=field_type.value,
                confidence=confidence,
            ))
        
        return columns
    
    def _empty_result(self) -> HeaderAnalysisResult:
        """Return empty result for invalid input."""
        return HeaderAnalysisResult(
            header_row=0,
            header_row_end=0,
            data_start_row=1,
            columns=[],
            confidence=0.0,
        )

