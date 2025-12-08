"""
LLM Prompt Templates for Semantic ETL Pipeline (v2)
====================================================

This module contains all prompt templates used for LLM-based product extraction
in the Semantic ETL pipeline (Phase 9).

VERSION 2 CHANGES:
------------------
- Proper separation of SystemMessage and HumanMessage content
- Removed redundant instructions (extract command appeared twice in v1)
- Functions return structured message lists for ChatOllama
- Cleaner token budget with ~15% reduction

Design Principles:
------------------
1. **Message Separation**: System context is distinct from user requests
2. **No Redundancy**: Each instruction appears exactly once
3. **Bilingual Support**: Handles English and Russian column headers
4. **JSON-Only Output**: ChatOllama's format="json" handles this; prompts reinforce

Architecture:
-------------
Prompts return List[BaseMessage] for proper ChatModel usage:
1. `get_extraction_messages()` - Main extraction (SystemMessage + HumanMessage)
2. `get_sheet_analysis_messages()` - Sheet selection
3. `get_category_context_messages()` - Category inference

Token Budget (llama3 8K context):
---------------------------------
- System message: ~800 tokens
- User message overhead: ~200 tokens
- Chunk data (250 rows): ~5K tokens
- Response buffer: ~2K tokens
- Total: ~8K tokens (fits within limit)

Phase 9: Semantic ETL Pipeline Refactoring
See: /specs/009-semantic-etl/spec.md
"""

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

__version__ = "2.0.0"

# =============================================================================
# SYSTEM MESSAGE CONTENT
# =============================================================================
# This establishes the LLM's role and provides consistent baseline rules.
# Sent as SystemMessage to ChatOllama.

EXTRACTION_SYSTEM_CONTENT = """You are an expert data extraction assistant specialized in parsing product catalogs from supplier files.

EXTRACTION RULES:
1. Extract ONLY products that have at least a name AND a price
2. Prices are in Belarusian Rubles (BYN) unless explicitly marked otherwise
3. If a field is missing or unclear, use null
4. Do NOT invent or hallucinate data - only extract what's explicitly present
5. Ignore rows that are headers, totals, subtotals, or metadata

CATEGORY RULES:
- Categories are product TYPE classifications (e.g., "Электро транспорт", "Велосипеды")
- Categories are NOT brands/manufacturers (e.g., "Shtenli", "Xiaomi" are BRANDS)
- If you see a brand name in a category column, exclude it from category_path
- Build category_path using ONLY generic product type names

PRICE FORMATTING:
- Remove currency symbols: р., руб., BYN, $, €, ₽
- Convert comma decimals: 1234,56 → 1234.56
- Remove thousand separators: 1 234 → 1234
- Handle ranges by taking first value: 100-150 → 100

VARIANT ATTRIBUTES (Phase 10):
Extract structured specifications that differentiate product variants:
- voltage: Battery voltage (e.g., "48V", "60V", "36V")
- capacity: Battery capacity in Ah (e.g., "20Ah", "12A", "7.8A")
- power: Motor power in watts (e.g., "250W", "500W")
- storage: Storage capacity (e.g., "256GB", "512GB", "1TB")
- ram: RAM size (e.g., "8GB", "16GB")
- color: Product color (e.g., "Black", "Черный", "White")
- size: Size designation (e.g., "M", "L", "XL", "42")

VARIANT EXTRACTION RULES:
- Look for specs in product name, e.g., "Shtenli GT15 48V20A" → {"voltage": "48V", "capacity": "20A"}
- Look for specs in dedicated columns (e.g., "АКБ", "Батарея", "Память")
- Normalize units: "7,8А" → "7.8A", "48в" → "48V"
- Only extract attributes that ARE PRESENT - don't guess or invent

COMMON COLUMN HEADERS (Russian/English):
- РРЦ, Розница, Retail, Price, Цена → price_rrc (retail price)
- Опт, Оптовая, Wholesale → price_opt (wholesale price)
- Название, Наименование, Name, Товар → name
- Категория, Category → category_path
- АКБ, Батарея, Battery → look for voltage/capacity
- Память, Storage, Флеш → look for storage
- Цвет, Color → look for color

OUTPUT SCHEMA:
Each product must have:
- name: string (REQUIRED) - product title
- description: string | null - specifications, characteristics
- price_opt: number | null - wholesale price
- price_rrc: number (REQUIRED) - retail price
- category_path: string[] - array from general to specific, e.g., ["Electronics", "Laptops"]
- variant_attributes: object - structured specs, e.g., {"voltage": "48V", "capacity": "20Ah"}"""


# =============================================================================
# USER MESSAGE TEMPLATES
# =============================================================================
# These are the actual requests sent as HumanMessage.
# They reference the data without repeating system rules.

EXTRACTION_USER_TEMPLATE = """Extract products from this markdown table:

```
{markdown_table}
```

Return a JSON array of products. Each product object must include:
- name (required)
- price_rrc (required)
- description (optional)
- price_opt (optional)
- category_path (optional)
- variant_attributes (optional) - extract voltage, capacity, storage, color, size, etc. from the product name or dedicated columns"""


COMPLEX_LAYOUT_USER_TEMPLATE = """This table has complex layout with merged cells or composite fields. Analyze carefully:

```
{markdown_table}
```

LAYOUT HINTS:
- Merged cells may repeat values across rows (same category for multiple products)
- Composite fields like "Category | Name | Specs" should be split by | or / delimiter
- Price columns might have mixed formatting
- Battery specs (АКБ) may contain voltage and capacity together, e.g., "48V 20Ah" or "АКБ LI-ION"
- Extract variant_attributes from product names like "Model GT17 36V7.8A" → {"voltage": "36V", "capacity": "7.8A"}

Return a JSON array of products with variant_attributes where applicable."""


# =============================================================================
# SHEET ANALYSIS PROMPTS
# =============================================================================

SHEET_ANALYSIS_SYSTEM_CONTENT = """You are an expert at analyzing Excel file structures to identify product data sheets."""


SHEET_ANALYSIS_USER_TEMPLATE = """Analyze these sheet names and metadata to identify which contain product data:

{sheet_info}

PRIORITY SHEETS (if any match exactly, select ONLY that sheet):
- "Upload to site", "Загрузка на сайт"
- "Products", "Товары"
- "Catalog", "Каталог"
- "Export", "Экспорт"

SKIP THESE (metadata/configuration):
- "Instructions", "Инструкции", "Settings", "Настройки"
- "Config", "Template", "Example", "Пример"

Return JSON:
{{
  "selected_sheets": ["sheet_name1", "sheet_name2"],
  "skipped_sheets": ["sheet_name3"],
  "reasoning": "Brief explanation"
}}"""


# =============================================================================
# CATEGORY CONTEXT PROMPTS
# =============================================================================

CATEGORY_CONTEXT_SYSTEM_CONTENT = """You are an expert at inferring product categories from context clues in supplier files."""


CATEGORY_CONTEXT_USER_TEMPLATE = """Determine the category hierarchy for this product:

Product name: {product_name}

Surrounding context:
{surrounding_rows}

The category may be:
1. In a dedicated "Category" column
2. In merged cells above the product
3. Embedded in the product name (e.g., "Electronics / Laptops / Gaming Laptop X")
4. Inferred from section headers

Return the category as a JSON array from most general to most specific:
["Level 1", "Level 2", "Level 3"]

If no category can be determined, return: []"""


# =============================================================================
# MESSAGE BUILDER FUNCTIONS
# =============================================================================

def get_extraction_messages(
    markdown_table: str,
    complex_layout: bool = False,
) -> list[BaseMessage]:
    """
    Build extraction messages for ChatOllama.
    
    Returns a list of [SystemMessage, HumanMessage] for proper chat model usage.
    This replaces the v1 `get_extraction_prompt()` which returned a single string.
    
    Args:
        markdown_table: Markdown-formatted table content from MarkdownConverter.
        complex_layout: If True, uses complex layout template with additional hints.
    
    Returns:
        List of BaseMessage objects ready for ChatOllama.ainvoke()
    
    Example:
        >>> messages = get_extraction_messages(markdown_chunk, complex_layout=False)
        >>> response = await llm.ainvoke(messages)
        >>> products = json.loads(response.content)
    
    Token estimation (v2):
        - System message: ~800 tokens (vs ~1000 in v1)
        - User message overhead: ~100 tokens
        - User content: varies by markdown_table length
    """
    system_message = SystemMessage(content=EXTRACTION_SYSTEM_CONTENT)
    
    if complex_layout:
        user_content = COMPLEX_LAYOUT_USER_TEMPLATE.format(
            markdown_table=markdown_table,
        )
    else:
        user_content = EXTRACTION_USER_TEMPLATE.format(
            markdown_table=markdown_table,
        )
    
    user_message = HumanMessage(content=user_content)
    
    return [system_message, user_message]


def get_sheet_analysis_messages(sheet_info: list[dict]) -> list[BaseMessage]:
    """
    Build sheet analysis messages for ChatOllama.
    
    Used by SheetSelector to determine which sheets contain product data.
    
    Args:
        sheet_info: List of sheet metadata dictionaries, each containing:
            - name (str): Sheet name
            - row_count (int): Number of rows
            - col_count (int): Number of columns
            - is_empty (bool, optional): True if sheet has no data
    
    Returns:
        List of BaseMessage objects ready for ChatOllama.ainvoke()
    
    Example:
        >>> sheets = [{"name": "Products", "row_count": 500, "col_count": 10}]
        >>> messages = get_sheet_analysis_messages(sheets)
        >>> response = await llm.ainvoke(messages)
    """
    # Format sheet info as human-readable list
    sheet_info_text = "\n".join(
        f"- {s['name']}: {s['row_count']} rows, {s['col_count']} columns"
        + (" (empty)" if s.get('is_empty') else "")
        for s in sheet_info
    )
    
    system_message = SystemMessage(content=SHEET_ANALYSIS_SYSTEM_CONTENT)
    user_message = HumanMessage(
        content=SHEET_ANALYSIS_USER_TEMPLATE.format(sheet_info=sheet_info_text)
    )
    
    return [system_message, user_message]


def get_category_context_messages(
    product_name: str,
    surrounding_rows: str,
) -> list[BaseMessage]:
    """
    Build category context messages for ChatOllama.
    
    Used when category cannot be determined from main extraction.
    Examines product name and surrounding context to infer category.
    
    Args:
        product_name: The extracted product name to find category for.
        surrounding_rows: Markdown representation of surrounding rows.
    
    Returns:
        List of BaseMessage objects ready for ChatOllama.ainvoke()
    """
    system_message = SystemMessage(content=CATEGORY_CONTEXT_SYSTEM_CONTENT)
    user_message = HumanMessage(
        content=CATEGORY_CONTEXT_USER_TEMPLATE.format(
            product_name=product_name,
            surrounding_rows=surrounding_rows,
        )
    )
    
    return [system_message, user_message]


