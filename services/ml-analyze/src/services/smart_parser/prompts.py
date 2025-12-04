"""
LLM Prompt Templates for Semantic ETL Pipeline
==============================================

Defines prompt templates for LLM-based product extraction.
Uses LangChain's PromptTemplate for structured prompting.

Phase 9: Semantic ETL Pipeline Refactoring

Design Principles:
- Clear, unambiguous instructions
- Examples for each field
- Explicit handling of edge cases
- JSON schema enforcement
"""

from langchain_core.prompts import PromptTemplate

# System prompt for extraction context
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

# Main extraction prompt template
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

# Prompt for handling ambiguous or complex layouts
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

# Prompt for sheet selection/analysis
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

# Prompt for category extraction from context
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

# Prompt for price extraction with currency handling
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


def get_extraction_prompt(markdown_table: str, complex_layout: bool = False) -> str:
    """
    Get formatted extraction prompt for a markdown table.
    
    Args:
        markdown_table: Markdown-formatted table content
        complex_layout: Whether to use complex layout handling prompt
    
    Returns:
        Formatted prompt string ready for LLM
    """
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
    
    Args:
        sheet_info: List of sheet metadata dicts
    
    Returns:
        Formatted prompt string
    """
    sheet_info_text = "\n".join(
        f"- {s['name']}: {s['row_count']} rows, {s['col_count']} columns"
        + (" (empty)" if s.get('is_empty') else "")
        for s in sheet_info
    )
    
    return SHEET_ANALYSIS_PROMPT_TEMPLATE.format(sheet_info=sheet_info_text)

