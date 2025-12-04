"""
Prompt Templates
==================

LangChain prompt templates for LLM-based product matching.

Follows:
- DRY: Centralized prompt templates
- KISS: Simple, clear prompts with explicit JSON output format
- Single Responsibility: Only handles prompt construction
"""

from typing import Any

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

# =============================================================================
# Product Matching Prompt
# =============================================================================

MATCH_SYSTEM_MESSAGE = """You are a product matching expert for a procurement system.
Your task is to determine if a supplier item matches any of the candidate products.

IMPORTANT RULES:
1. Only match products that are TRULY the same product, not just similar
2. Consider brand, specifications, and characteristics carefully
3. Return valid JSON only - no markdown, no explanations outside JSON
4. If no match is found, return an empty array []
5. Confidence should reflect certainty: 0.9+ = certain match, 0.7-0.9 = likely match, <0.7 = uncertain"""

MATCH_USER_TEMPLATE = """Analyze the following supplier item and find matches from the candidates.

## Supplier Item to Match:
Name: {item_name}
Description: {item_description}
SKU: {item_sku}
Category: {item_category}
Brand: {item_brand}
Characteristics: {item_characteristics}

## Candidate Products (Top {top_k} by semantic similarity):
{candidates_text}

## Instructions:
Compare the supplier item with each candidate. For matches, return a JSON array:
[
  {{
    "product_id": "<uuid of matched product>",
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation of why they match>"
  }}
]

If NO candidates match, return: []

Respond ONLY with valid JSON, no other text."""

# ChatPromptTemplate for structured chat-based LLM calls
MATCH_PROMPT = ChatPromptTemplate.from_messages([
    ("system", MATCH_SYSTEM_MESSAGE),
    ("human", MATCH_USER_TEMPLATE),
])

# =============================================================================
# Helper function to format candidates
# =============================================================================

def format_candidates_text(candidates: list[dict[str, Any]]) -> str:
    """
    Format candidate products for the prompt.

    Args:
        candidates: List of candidate dicts with product_id, name, similarity, etc.

    Returns:
        Formatted text for prompt insertion
    """
    if not candidates:
        return "No candidates available."

    lines = []
    for i, candidate in enumerate(candidates, 1):
        product_id = candidate.get("product_id", "unknown")
        name = candidate.get("name", "Unknown")
        similarity = candidate.get("similarity", 0.0)
        characteristics = candidate.get("characteristics", {})

        char_str = ", ".join(f"{k}: {v}" for k, v in characteristics.items()) if characteristics else "none"

        lines.append(
            f"{i}. Product ID: {product_id}\n"
            f"   Name: {name}\n"
            f"   Similarity Score: {similarity:.3f}\n"
            f"   Characteristics: {char_str}"
        )

    return "\n\n".join(lines)


def format_item_for_prompt(
    name: str,
    description: str | None = None,
    sku: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    characteristics: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Format supplier item data for prompt variables.

    Args:
        name: Item name
        description: Optional description
        sku: Optional SKU
        category: Optional category
        brand: Optional brand
        characteristics: Optional characteristics dict

    Returns:
        Dict of prompt variables
    """
    char_str = ", ".join(f"{k}: {v}" for k, v in (characteristics or {}).items()) if characteristics else "none"

    return {
        "item_name": name,
        "item_description": description or "Not provided",
        "item_sku": sku or "Not provided",
        "item_category": category or "Not provided",
        "item_brand": brand or "Not provided",
        "item_characteristics": char_str,
    }


# =============================================================================
# Batch Analysis Prompt (for future batch processing)
# =============================================================================

BATCH_MATCH_SYSTEM_MESSAGE = """You are a product matching expert analyzing multiple items.
Return matches for each item as a JSON object with item indices as keys."""

BATCH_MATCH_USER_TEMPLATE = """Match the following supplier items to candidate products.

## Supplier Items:
{items_text}

## Candidate Products:
{candidates_text}

Return JSON object with item indices as keys:
{{
  "0": [{{"product_id": "...", "confidence": 0.95, "reasoning": "..."}}],
  "1": [],
  "2": [{{"product_id": "...", "confidence": 0.85, "reasoning": "..."}}]
}}"""

BATCH_MATCH_PROMPT = ChatPromptTemplate.from_messages([
    ("system", BATCH_MATCH_SYSTEM_MESSAGE),
    ("human", BATCH_MATCH_USER_TEMPLATE),
])

# =============================================================================
# Prompt for low-confidence explanation (future use)
# =============================================================================

NO_MATCH_EXPLANATION_TEMPLATE = """Explain why the following supplier item could not be matched.

Item: {item_name}
Candidates examined: {candidate_count}
Best similarity score: {best_similarity}

Provide a brief explanation for why no match was found."""

NO_MATCH_PROMPT = PromptTemplate.from_template(NO_MATCH_EXPLANATION_TEMPLATE)


# =============================================================================
# Phase 10: Two-Stage Parsing Prompts
# =============================================================================

# -----------------------------------------------------------------------------
# Stage A: Structure Analysis
# -----------------------------------------------------------------------------

STRUCTURE_ANALYSIS_SYSTEM = """You are a document structure analyzer for supplier price lists.
Your task is to analyze tabular data and identify the document structure.

IMPORTANT RULES:
1. Identify header rows (may be single or multi-row headers)
2. Find where product data starts and ends
3. Map columns to their purpose (name, price, SKU, category, etc.)
4. Detect currency symbols or indicators if present
5. Return valid JSON only - no markdown, no explanations outside JSON
6. All row indices are 0-based (first row = 0)
7. Use -1 for data_end_row if data continues to the end of document
8. Confidence should reflect certainty: 0.9+ = clear structure, 0.7-0.9 = likely correct, <0.7 = uncertain"""

STRUCTURE_ANALYSIS_USER = """Analyze the structure of this document sample.

## Document Sample (first {sample_rows} rows):
{document_sample}

## Instructions:
Identify the document structure and return JSON:
{{
  "header_rows": [<list of header row indices, 0-based>],
  "data_start_row": <first row with product data, 0-based>,
  "data_end_row": <last row with product data, -1 if until end>,
  "column_mapping": {{
    "name_column": <column index for product name or null>,
    "sku_column": <column index for SKU/article or null>,
    "retail_price_column": <column index for retail price or null>,
    "wholesale_price_column": <column index for wholesale/dealer price or null>,
    "category_column": <column index for category or null>,
    "unit_column": <column index for unit of measure or null>,
    "description_column": <column index for description or null>,
    "brand_column": <column index for brand or null>
  }},
  "confidence": <0.0-1.0>,
  "detected_currency": "<ISO 4217 code or null>",
  "has_merged_cells": <true/false>,
  "notes": "<optional notes about structure>"
}}

Look for:
- Headers often contain: "Наименование", "Артикул", "Цена", "Name", "SKU", "Price", "Опт", "Розница"
- Price columns may have currency symbols (₽, $, €) or text (руб, USD)
- Wholesale indicators: "опт", "дилер", "wholesale", "dealer"
- Retail indicators: "розница", "retail", "RRP", "цена"

Respond ONLY with valid JSON, no other text."""

# -----------------------------------------------------------------------------
# Stage B: Data Extraction
# -----------------------------------------------------------------------------

EXTRACTION_SYSTEM = """You are a data extractor for supplier price lists.
Your task is to extract product data from rows using a known column structure.

IMPORTANT RULES:
1. Extract only the fields that have column mappings
2. Clean and normalize values (trim whitespace, remove extra characters)
3. Preserve numeric precision for prices
4. Return valid JSON array only - no markdown, no explanations
5. Each row becomes one object in the array
6. Skip rows that appear to be totals, subtotals, or empty
7. For composite names (with | delimiter), keep the full string - post-processing will split it"""

EXTRACTION_USER = """Extract product data from these rows using the column structure.

## Column Structure (from structure analysis):
{column_mapping}

## Rows to Extract (indices {start_row} to {end_row}):
{data_rows}

## Instructions:
For each row, extract fields based on column mapping and return JSON array:
[
  {{
    "row_index": <original row index>,
    "name": "<product name>",
    "sku": "<SKU/article or null>",
    "retail_price": "<retail price as string or null>",
    "wholesale_price": "<wholesale price as string or null>",
    "category": "<category or null>",
    "unit": "<unit of measure or null>",
    "description": "<description or null>",
    "brand": "<brand or null>",
    "raw_data": {{<original cell values keyed by column index>}}
  }},
  ...
]

Guidelines:
- Extract price as string to preserve formatting (post-processing will parse)
- Include currency symbols if present in the cell
- Skip obviously empty or total rows
- If a cell has composite data ("|" separated), keep it as-is

Respond ONLY with valid JSON array, no other text."""


# =============================================================================
# Phase 10: ChatPromptTemplates
# =============================================================================

STRUCTURE_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", STRUCTURE_ANALYSIS_SYSTEM),
    ("human", STRUCTURE_ANALYSIS_USER),
])

EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", EXTRACTION_SYSTEM),
    ("human", EXTRACTION_USER),
])


# =============================================================================
# Phase 10: Helper Functions for Two-Stage Parsing
# =============================================================================

def format_document_sample(rows: list[list[str]], max_rows: int = 20) -> str:
    """
    Format document rows for the structure analysis prompt.

    Args:
        rows: Raw table data as list of lists
        max_rows: Maximum rows to include in sample

    Returns:
        Formatted text representation of rows
    """
    if not rows:
        return "No data available."

    sample = rows[:max_rows]
    lines = []

    for idx, row in enumerate(sample):
        # Format each cell, truncate long values
        cells = []
        for col_idx, cell in enumerate(row):
            cell_str = str(cell).strip() if cell else ""
            if len(cell_str) > 50:
                cell_str = cell_str[:47] + "..."
            cells.append(f"[{col_idx}]{cell_str}")

        lines.append(f"Row {idx}: {' | '.join(cells)}")

    return "\n".join(lines)


def format_column_mapping_for_prompt(column_mapping: dict[str, int | None]) -> str:
    """
    Format column mapping for the extraction prompt.

    Args:
        column_mapping: Dict of field names to column indices

    Returns:
        Formatted text representation
    """
    lines = []
    for field, col_idx in column_mapping.items():
        if col_idx is not None:
            lines.append(f"- {field}: Column {col_idx}")

    return "\n".join(lines) if lines else "No columns mapped."


def format_data_rows_for_prompt(
    rows: list[list[str]],
    start_row: int,
    end_row: int,
) -> str:
    """
    Format data rows for the extraction prompt.

    Args:
        rows: Full table data as list of lists
        start_row: Starting row index (inclusive)
        end_row: Ending row index (inclusive, or -1 for end)

    Returns:
        Formatted text representation of data rows
    """
    if not rows:
        return "No data available."

    # Handle -1 as end of document
    actual_end = len(rows) if end_row == -1 else min(end_row + 1, len(rows))
    data_slice = rows[start_row:actual_end]

    lines = []
    for rel_idx, row in enumerate(data_slice):
        abs_idx = start_row + rel_idx
        # Format row with cell indices
        cells = [f"[{i}]{str(cell).strip() if cell else ''}" for i, cell in enumerate(row)]
        lines.append(f"Row {abs_idx}: {' | '.join(cells)}")

    return "\n".join(lines)

