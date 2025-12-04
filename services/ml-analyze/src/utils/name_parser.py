"""
Composite Name Parser
=====================

Utility module for parsing composite product names that encode multiple
fields in a single cell using delimiters.

Example input: "Electric Bicycle | Shtenli Model Gt11 | Li-ion 48V 15Ah"
Output:
    - category_path: ["Electric Bicycle"]
    - name: "Shtenli Model Gt11"
    - description: "Li-ion 48V 15Ah"

Follows:
- Single Responsibility: Only handles name parsing
- KISS: Simple string splitting with delimiter support
- Strong Typing: Pydantic dataclass for results
"""

from typing import Annotated

from pydantic import Field
from pydantic.dataclasses import dataclass


@dataclass(frozen=True)
class CompositeNameResult:
    """
    Result of composite product name parsing.

    Contains parsed components from a pipe-delimited product string.

    Attributes:
        category_path: Hierarchical category path (e.g., ["Electronics", "Bikes"])
        name: Product name extracted from composite string
        description: Combined description from remaining segments
        raw_composite: Original input string before parsing
        was_parsed: Whether the string was actually parsed (had delimiters)

    Example:
        Input: "Electric Bicycle | Shtenli Model Gt11 | Li-ion 48V 15Ah"
        Output:
            category_path=["Electric Bicycle"]
            name="Shtenli Model Gt11"
            description="Li-ion 48V 15Ah"
            raw_composite="Electric Bicycle | Shtenli Model Gt11 | Li-ion 48V 15Ah"
            was_parsed=True
    """

    category_path: Annotated[
        list[str],
        Field(default_factory=list, description="Hierarchical category path"),
    ]
    name: Annotated[
        str,
        Field(description="Product name"),
    ]
    description: Annotated[
        str | None,
        Field(default=None, description="Product description from remaining segments"),
    ] = None
    raw_composite: Annotated[
        str | None,
        Field(default=None, description="Original input string"),
    ] = None
    was_parsed: Annotated[
        bool,
        Field(default=False, description="Whether composite parsing was applied"),
    ] = False


def parse_category_hierarchy(category_string: str) -> list[str]:
    """
    Parse category string into hierarchical path.

    Supports "/" and ">" as hierarchy separators.

    Args:
        category_string: Raw category string (e.g., "Electronics/Bikes/Adult")

    Returns:
        List of category levels from root to leaf

    Examples:
        >>> parse_category_hierarchy("Electronics/Bikes/Adult")
        ['Electronics', 'Bikes', 'Adult']

        >>> parse_category_hierarchy("Electronics > Bikes > Adult")
        ['Electronics', 'Bikes', 'Adult']

        >>> parse_category_hierarchy("Simple Category")
        ['Simple Category']

        >>> parse_category_hierarchy("  Spaced / Category  ")
        ['Spaced', 'Category']
    """
    if not category_string or not category_string.strip():
        return []

    category_string = category_string.strip()

    # Check for hierarchy separators
    # Priority: "/" first, then ">" (covers both path and breadcrumb styles)
    for separator in ["/", ">"]:
        if separator in category_string:
            parts = category_string.split(separator)
            # Filter empty and clean whitespace
            return [part.strip() for part in parts if part.strip()]

    # No separator found - single category
    return [category_string]


def parse_composite_name(
    value: str,
    delimiter: str = "|",
) -> CompositeNameResult:
    """
    Parse a composite product string into structured components.

    The composite format follows this convention:
    - Segment 1: Category (may contain "/" or ">" for hierarchy)
    - Segment 2: Product name
    - Segment 3+: Description/specifications (concatenated with spaces)

    Args:
        value: The composite product string to parse
        delimiter: Character used to separate fields (default: "|")

    Returns:
        CompositeNameResult with parsed components

    Examples:
        >>> result = parse_composite_name("Electric Bicycle | Shtenli Model Gt11 | Li-ion 48V 15Ah")
        >>> result.category_path
        ['Electric Bicycle']
        >>> result.name
        'Shtenli Model Gt11'
        >>> result.description
        'Li-ion 48V 15Ah'

        >>> result = parse_composite_name("Electronics/Bikes | Mountain Pro | 27.5 inch | Shimano")
        >>> result.category_path
        ['Electronics', 'Bikes']
        >>> result.name
        'Mountain Pro'
        >>> result.description
        '27.5 inch Shimano'

        >>> result = parse_composite_name("Simple Product Name")
        >>> result.was_parsed
        False
        >>> result.name
        'Simple Product Name'

        >>> result = parse_composite_name("Category Only | ")
        >>> result.category_path
        ['Category Only']
        >>> result.name
        ''

        >>> result = parse_composite_name(" | Name Only")
        >>> result.category_path
        []
        >>> result.name
        'Name Only'
    """
    if not value:
        return CompositeNameResult(
            category_path=[],
            name="",
            raw_composite=value,
            was_parsed=False,
        )

    original = value.strip()

    # Check if delimiter is present
    if delimiter not in original:
        # No composite structure - return as-is for name
        return CompositeNameResult(
            category_path=[],
            name=original,
            raw_composite=None,  # Not a composite, no need to store
            was_parsed=False,
        )

    # Split by delimiter and filter empty segments
    segments = original.split(delimiter)
    cleaned_segments = [seg.strip() for seg in segments]

    # Handle edge cases
    if not any(cleaned_segments):
        return CompositeNameResult(
            category_path=[],
            name="",
            raw_composite=original,
            was_parsed=True,
        )

    # Parse according to position
    category_path: list[str] = []
    name: str = ""
    description: str | None = None

    # First segment → category (with hierarchy parsing)
    if len(cleaned_segments) >= 1 and cleaned_segments[0]:
        category_path = parse_category_hierarchy(cleaned_segments[0])

    # Second segment → product name
    if len(cleaned_segments) >= 2 and cleaned_segments[1]:
        name = cleaned_segments[1]

    # Third+ segments → description (concatenated)
    if len(cleaned_segments) >= 3:
        desc_parts = [seg for seg in cleaned_segments[2:] if seg]
        if desc_parts:
            description = " ".join(desc_parts)

    # Handle case where first segment was category but second was empty
    # In this case, treat first non-empty segment as name
    if not name and not category_path:
        # Find first non-empty segment
        for seg in cleaned_segments:
            if seg:
                name = seg
                break

    # Handle case: only category provided (e.g., "Category | ")
    # Keep category, name stays empty
    if not name and category_path and len(cleaned_segments) >= 2:
        # This is intentional - category-only entry
        pass

    # Handle case: "| Name" - empty first segment
    if not category_path and len(cleaned_segments) >= 2 and cleaned_segments[1]:
        name = cleaned_segments[1]

    return CompositeNameResult(
        category_path=category_path,
        name=name,
        description=description,
        raw_composite=original,
        was_parsed=True,
    )


def parse_composite_name_with_fallback(
    value: str,
    delimiter: str = "|",
    fallback_to_name: bool = True,
) -> CompositeNameResult:
    """
    Parse composite name with intelligent fallback handling.

    When parsing fails or produces unexpected results, this function
    provides sensible defaults.

    Args:
        value: The composite product string to parse
        delimiter: Character used to separate fields
        fallback_to_name: If True, unparseable strings become the name

    Returns:
        CompositeNameResult with parsed or fallback components

    Examples:
        >>> result = parse_composite_name_with_fallback("")
        >>> result.name
        ''
        >>> result.was_parsed
        False

        >>> result = parse_composite_name_with_fallback("|||")
        >>> result.name
        ''
        >>> result.was_parsed
        True
    """
    if not value or not value.strip():
        return CompositeNameResult(
            category_path=[],
            name="",
            raw_composite=value if value else None,
            was_parsed=False,
        )

    result = parse_composite_name(value, delimiter)

    # If we parsed but got no useful data, use original as name
    if result.was_parsed and not result.name and not result.category_path:
        if fallback_to_name:
            return CompositeNameResult(
                category_path=[],
                name=value.strip(),
                raw_composite=value,
                was_parsed=False,  # Mark as not successfully parsed
            )

    return result

