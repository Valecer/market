"""
LLM Prompt Templates for Semantic ETL Pipeline
==============================================

This module contains all prompt templates used for LLM-based product extraction
in the Semantic ETL pipeline (Phase 9). The prompts are designed to work with
Ollama's llama3 model (8K context window) via LangChain.

Design Principles:
------------------
1. **Explicit Instructions**: Each prompt contains clear, unambiguous rules
   to minimize LLM hallucination and ensure consistent output.

2. **Bilingual Support**: All prompts handle both English and Russian column
   headers, as supplier files come from Belarus/Russia.

3. **JSON-Only Output**: Prompts explicitly request JSON-only responses to
   facilitate structured parsing via LangChain's StructuredOutputParser.

4. **Edge Case Handling**: Prompts include guidance for common edge cases
   like missing fields, merged cells, and currency variations.

Architecture:
-------------
The prompts are used by `LangChainExtractor` in the following flow:
1. `SHEET_ANALYSIS_PROMPT_TEMPLATE` - Selects which sheets to process
2. `EXTRACTION_PROMPT_TEMPLATE` - Main extraction for standard layouts
3. `COMPLEX_LAYOUT_PROMPT_TEMPLATE` - Fallback for complex merged cells
4. `CATEGORY_CONTEXT_PROMPT_TEMPLATE` - Extracts categories when ambiguous

Token Budget Considerations:
----------------------------
- llama3 has an 8K token context window
- System prompt + guidance: ~1K tokens
- Chunk size (250 rows): ~5K tokens average
- Response buffer: ~2K tokens
- Total: ~8K tokens (fits within limit)

Usage:
------
```python
from services.smart_parser.prompts import get_extraction_prompt

prompt = get_extraction_prompt(markdown_table, complex_layout=False)
response = await llm.ainvoke(prompt)
```

Phase 9: Semantic ETL Pipeline Refactoring
See: /specs/009-semantic-etl/spec.md
See: /docs/adr/009-semantic-etl.md
"""

from langchain_core.prompts import PromptTemplate

# =============================================================================
# SYSTEM PROMPT
# =============================================================================
# This context is prepended to all extraction prompts to establish the
# LLM's role and provide consistent baseline rules.

EXTRACTION_SYSTEM_PROMPT = """You are an expert data extraction assistant specialized in parsing product catalogs from supplier files.

Your task is to extract structured product information from markdown tables representing Excel/CSV data.

IMPORTANT RULES:
1. Extract ONLY products that have at least a name AND a price
2. Prices are in Belarusian Rubles (BYN) unless explicitly marked otherwise
3. If a price has currency symbols (р., руб., BYN, $, €), remove them and keep only the number
4. If a field is missing or unclear, use null
5. Category paths should be extracted as arrays from most general to most specific
6. Do NOT invent or hallucinate data - only extract what's explicitly in the table
7. Ignore rows that appear to be headers, totals, or metadata

FIELD DEFINITIONS:
- name: Product name/title (REQUIRED) - the main identifier of the product
- description: Additional specifications, characteristics, or details
- price_opt: Wholesale/optimal price for resellers (optional)
- price_rrc: Retail recommended price for end customers (REQUIRED)
- category_path: Array of category names from general to specific, e.g., ["Electronics", "Laptops", "Gaming"]
"""

# =============================================================================
# PRICE EXTRACTION GUIDANCE
# =============================================================================
# Detailed rules for handling various price formats found in supplier files.
# Belarusian suppliers often use mixed formatting conventions.

PRICE_EXTRACTION_GUIDANCE = """
PRICE FORMATTING RULES:
- Remove currency symbols: р., руб., BYN, $, €, ₽
- Convert comma decimal separators: 1234,56 → 1234.56
- Remove thousand separators: 1 234 → 1234
- Handle ranges by taking the first price: 100-150 → 100
- If price is clearly USD/EUR, note in raw_data but DO NOT convert

COMMON PRICE COLUMN HEADERS (Russian/English):
- РРЦ, Розница, Retail, Price, Цена розничная → price_rrc
- Опт, Оптовая, Wholesale, Opt → price_opt
- Цена, Стоимость (when single price column) → price_rrc
"""

# =============================================================================
# MAIN EXTRACTION PROMPT
# =============================================================================
# This is the primary prompt used for standard Excel files with clear structure.
# It assumes the markdown table has identifiable column headers.

EXTRACTION_PROMPT_TEMPLATE = PromptTemplate.from_template(
    """Extract all products from the following markdown table.

{system_context}

MARKDOWN TABLE:
```
{markdown_table}
```

EXTRACTION GUIDELINES:
- Each row typically represents one product
- Price columns may be labeled: "Цена", "Price", "РРЦ", "Опт", "Розница", "Стоимость"
- Category may be in a separate column or merged cells spanning multiple rows
- Name columns may be labeled: "Название", "Наименование", "Name", "Товар", "Product"
- Description may include specifications like dimensions, weight, material

Extract each valid product with all available fields. Return a JSON array of products.

IMPORTANT: Return ONLY valid JSON. No explanations or additional text."""
)

# =============================================================================
# COMPLEX LAYOUT PROMPT
# =============================================================================
# Used when the MarkdownConverter detects merged cells or non-standard layouts.
# This prompt includes additional guidance for handling ambiguous structures.
#
# Trigger conditions:
# - Merged cells spanning multiple rows/columns
# - Composite fields (e.g., "Category | Name | Specs" in one column)
# - Mixed formatting within columns

COMPLEX_LAYOUT_PROMPT_TEMPLATE = PromptTemplate.from_template(
    """This markdown table has a complex layout. Analyze the structure carefully.

{system_context}

MARKDOWN TABLE:
```
{markdown_table}
```

LAYOUT HINTS:
- Merged cells may repeat values across multiple rows (same category for multiple products)
- Some columns may contain composite data (e.g., "Category | Name | Specs")
- Price columns might have mixed formatting (1234.56, 1 234,56, 1234.56 р.)

For composite fields like "Category | Name | Specs":
- Split by | or / delimiter
- First part is usually category
- Second part is usually name
- Remaining parts are description

Extract all products and return as JSON array."""
)

# =============================================================================
# SHEET ANALYSIS PROMPT
# =============================================================================
# Used by SheetSelector to determine which sheets in a multi-sheet Excel file
# contain product data. This allows skipping instruction/config sheets.
#
# Priority logic:
# 1. Exact match on priority names → process only that sheet
# 2. No priority match → process all sheets except skip list
# 3. Sheets with <10 rows are considered metadata and skipped

SHEET_ANALYSIS_PROMPT_TEMPLATE = PromptTemplate.from_template(
    """Analyze the following list of sheet names and their metadata to identify which sheets contain product data.

SHEET INFORMATION:
{sheet_info}

PRIORITY SHEET NAMES (if any match exactly, select only that sheet):
- "Upload to site"
- "Загрузка на сайт"
- "Products"
- "Товары"
- "Catalog"
- "Каталог"
- "Export"
- "Экспорт"

SHEETS TO SKIP (metadata/configuration):
- "Instructions", "Инструкции"
- "Settings", "Настройки"
- "Config", "Конфигурация"
- "Template", "Шаблон"
- "Example", "Пример"

Based on the sheet names and row/column counts, return a JSON object with:
{{
  "selected_sheets": ["sheet_name1", "sheet_name2"],
  "skipped_sheets": ["sheet_name3"],
  "reasoning": "Brief explanation of selection"
}}

Select sheets that likely contain product data for upload."""
)

# =============================================================================
# CATEGORY CONTEXT PROMPT
# =============================================================================
# Used when category cannot be determined from the main extraction.
# This prompt examines surrounding context (merged cells, section headers)
# to infer category hierarchy.
#
# Use cases:
# - Category in merged cells above product rows
# - Category embedded in product name (e.g., "Electronics / Laptop X")
# - Category in section headers rather than columns

CATEGORY_CONTEXT_PROMPT_TEMPLATE = PromptTemplate.from_template(
    """Given the following context from a supplier file, extract the category hierarchy.

CONTEXT:
- Product name: {product_name}
- Surrounding rows (for context):
{surrounding_rows}

The category may be:
1. In a dedicated "Category" column
2. In merged cells above the product
3. Embedded in the product name (e.g., "Electronics / Laptops / Gaming Laptop X")
4. Inferred from section headers

Return the category as a JSON array from most general to most specific:
["Level 1 Category", "Level 2 Category", "Level 3 Category"]

If no category can be determined, return an empty array: []"""
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_extraction_prompt(markdown_table: str, complex_layout: bool = False) -> str:
    """
    Get formatted extraction prompt for a markdown table.
    
    This is the main entry point for generating extraction prompts. It combines
    the system context with the appropriate template based on layout complexity.
    
    Args:
        markdown_table: Markdown-formatted table content from MarkdownConverter.
                       Should include headers and data rows in pipe-delimited format.
        complex_layout: If True, uses the complex layout prompt with additional
                       guidance for merged cells and composite fields.
                       Set by MarkdownConverter when it detects anomalies.
    
    Returns:
        Formatted prompt string ready for LLM invocation.
    
    Example:
        >>> prompt = get_extraction_prompt(markdown_chunk, complex_layout=False)
        >>> response = await llm.ainvoke(prompt)
        >>> products = json.loads(response)
    
    Token estimation:
        - System context: ~600 tokens
        - Price guidance: ~200 tokens  
        - Template overhead: ~200 tokens
        - User content: varies by markdown_table length
        - Total overhead: ~1000 tokens (leaving ~5K for data, ~2K for response)
    """
    # Combine system prompt with price extraction rules
    system_context = EXTRACTION_SYSTEM_PROMPT + "\n\n" + PRICE_EXTRACTION_GUIDANCE
    
    if complex_layout:
        return COMPLEX_LAYOUT_PROMPT_TEMPLATE.format(
            system_context=system_context,
            markdown_table=markdown_table,
        )
    
    return EXTRACTION_PROMPT_TEMPLATE.format(
        system_context=system_context,
        markdown_table=markdown_table,
    )


def get_sheet_analysis_prompt(sheet_info: list[dict]) -> str:
    """
    Get formatted prompt for sheet analysis/selection.
    
    Used by SheetSelector to determine which sheets in a multi-sheet Excel
    file contain product data. The LLM analyzes sheet names and metadata
    to make intelligent selection decisions.
    
    Args:
        sheet_info: List of sheet metadata dictionaries, each containing:
            - name (str): Sheet name
            - row_count (int): Number of rows in sheet
            - col_count (int): Number of columns in sheet
            - is_empty (bool, optional): True if sheet has no data
    
    Returns:
        Formatted prompt string ready for LLM invocation.
    
    Example:
        >>> sheets = [
        ...     {"name": "Products", "row_count": 500, "col_count": 10},
        ...     {"name": "Instructions", "row_count": 20, "col_count": 3},
        ... ]
        >>> prompt = get_sheet_analysis_prompt(sheets)
        >>> response = await llm.ainvoke(prompt)
        >>> selection = json.loads(response)  # {"selected_sheets": ["Products"], ...}
    
    Note:
        The response JSON includes 'reasoning' field for debugging/logging
        sheet selection decisions.
    """
    # Format sheet info as human-readable list
    sheet_info_text = "\n".join(
        f"- {s['name']}: {s['row_count']} rows, {s['col_count']} columns"
        + (" (empty)" if s.get('is_empty') else "")
        for s in sheet_info
    )
    
    return SHEET_ANALYSIS_PROMPT_TEMPLATE.format(sheet_info=sheet_info_text)


def get_category_context_prompt(product_name: str, surrounding_rows: str) -> str:
    """
    Get formatted prompt for category extraction from context.
    
    Used when the main extraction cannot determine category from column data.
    This prompt examines the product name and surrounding rows to infer
    the category hierarchy.
    
    Args:
        product_name: The extracted product name to find category for.
        surrounding_rows: Markdown representation of rows above/below the product,
                         which may contain category information in merged cells
                         or section headers.
    
    Returns:
        Formatted prompt string ready for LLM invocation.
    
    Example:
        >>> prompt = get_category_context_prompt(
        ...     "Gaming Laptop X500",
        ...     "| Computers / Electronics |\\n| Gaming Laptop X500 | 1500 |"
        ... )
        >>> response = await llm.ainvoke(prompt)
        >>> categories = json.loads(response)  # ["Computers", "Electronics"]
    """
    return CATEGORY_CONTEXT_PROMPT_TEMPLATE.format(
        product_name=product_name,
        surrounding_rows=surrounding_rows,
    )
