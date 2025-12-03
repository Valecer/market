"""
Prompt Templates
==================

LangChain prompt templates for LLM-based product matching.

Follows:
- DRY: Centralized prompt templates
- KISS: Simple, clear prompts with explicit JSON output format
- Single Responsibility: Only handles prompt construction
"""

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

def format_candidates_text(candidates: list[dict]) -> str:
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
    characteristics: dict | None = None,
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


