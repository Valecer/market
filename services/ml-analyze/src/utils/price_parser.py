"""
Price and Currency Parser
=========================

Utility module for extracting prices and currency codes from various
string formats commonly found in supplier price lists.

Example inputs:
- "₽1 500.00" → amount=1500.00, currency_code="RUB"
- "$99.99" → amount=99.99, currency_code="USD"
- "150€" → amount=150.00, currency_code="EUR"
- "25 руб" → amount=25.00, currency_code="RUB"
- "1,234.56" → amount=1234.56, currency_code=None

Follows:
- Single Responsibility: Only handles price/currency parsing
- KISS: Regex-based extraction, no external dependencies
- Strong Typing: Pydantic dataclass for results
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Annotated, Final

from pydantic import Field
from pydantic.dataclasses import dataclass


# =============================================================================
# Currency Mapping
# =============================================================================

CURRENCY_MAP: Final[dict[str, str]] = {
    # Symbols
    "₽": "RUB",
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₴": "UAH",
    "₸": "KZT",
    "₿": "BTC",
    "元": "CNY",
    "₹": "INR",
    "₩": "KRW",
    "₦": "NGN",
    "₱": "PHP",
    "฿": "THB",
    # Russian text indicators (case-insensitive via lower())
    "руб": "RUB",
    "руб.": "RUB",
    "рубль": "RUB",
    "рублей": "RUB",
    "рубля": "RUB",
    "р.": "RUB",
    "р": "RUB",
    # English text indicators
    "rub": "RUB",
    "ruble": "RUB",
    "rubles": "RUB",
    "usd": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "gbp": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
    "jpy": "JPY",
    "yen": "JPY",
    "cny": "CNY",
    "yuan": "CNY",
    "inr": "INR",
    "rupee": "INR",
    "rupees": "INR",
    # ISO codes (redundant but useful for explicit matching)
    "RUB": "RUB",
    "USD": "USD",
    "EUR": "EUR",
    "GBP": "GBP",
    "JPY": "JPY",
    "CNY": "CNY",
}

# Retail price column indicators (case-insensitive)
RETAIL_INDICATORS: Final[frozenset[str]] = frozenset(
    {
        "розница",
        "розн",
        "розн.",
        "retail",
        "rrp",
        "msrp",
        "цена",
        "price",
        "стоимость",
        "прайс",
        "розничная",
        "рекомендуемая",
        "для клиентов",
        "конечная",
        "продажная",
    }
)

# Wholesale price column indicators (case-insensitive)
WHOLESALE_INDICATORS: Final[frozenset[str]] = frozenset(
    {
        "опт",
        "опт.",
        "оптовая",
        "оптом",
        "wholesale",
        "dealer",
        "дилер",
        "дилерская",
        "bulk",
        "trade",
        "b2b",
        "закупочная",
        "партия",
        "от 10",
        "от 50",
        "от 100",
        "оптовик",
    }
)


# =============================================================================
# Price Result Dataclass
# =============================================================================


@dataclass(frozen=True)
class PriceResult:
    """
    Result of price extraction from a string.

    Contains parsed amount and detected currency code.

    Attributes:
        amount: Numeric price value as Decimal
        currency_code: ISO 4217 currency code (e.g., "RUB", "USD", "EUR")
        raw_value: Original input string before parsing
        was_parsed: Whether the string was successfully parsed

    Example:
        Input: "₽1 500.00"
        Output:
            amount=Decimal("1500.00")
            currency_code="RUB"
            raw_value="₽1 500.00"
            was_parsed=True
    """

    amount: Annotated[
        Decimal | None,
        Field(default=None, description="Numeric price value"),
    ] = None
    currency_code: Annotated[
        str | None,
        Field(
            default=None, min_length=3, max_length=3, description="ISO 4217 currency code"
        ),
    ] = None
    raw_value: Annotated[
        str | None,
        Field(default=None, description="Original input string"),
    ] = None
    was_parsed: Annotated[
        bool,
        Field(default=False, description="Whether parsing was successful"),
    ] = False


# =============================================================================
# Currency Detection
# =============================================================================


def detect_currency(value: str) -> str | None:
    """
    Detect currency from a price string.

    Scans for currency symbols and text indicators.

    Args:
        value: Price string that may contain currency indicators

    Returns:
        ISO 4217 currency code or None if not detected

    Examples:
        >>> detect_currency("₽1500")
        'RUB'

        >>> detect_currency("99.99 USD")
        'USD'

        >>> detect_currency("150 евро")
        None  # "евро" not in map, use "euro" or "eur"

        >>> detect_currency("25 руб")
        'RUB'

        >>> detect_currency("1234.56")
        None
    """
    if not value:
        return None

    # Check for symbol match first (faster)
    for symbol in ["₽", "$", "€", "£", "¥", "₴", "₸", "₿", "₹", "₩", "₦", "₱", "฿", "元"]:
        if symbol in value:
            return CURRENCY_MAP.get(symbol)

    # Check for text indicators (case-insensitive)
    lower_value = value.lower()

    # Sort by length descending to match longer patterns first
    # e.g., "рублей" before "руб", "dollars" before "dollar"
    sorted_keys = sorted(
        (k for k in CURRENCY_MAP if k.isalpha()),
        key=len,
        reverse=True,
    )

    for indicator in sorted_keys:
        if indicator.lower() in lower_value:
            return CURRENCY_MAP[indicator]

    return None


# =============================================================================
# Price Extraction
# =============================================================================


def extract_price(value: str | int | float | Decimal | None) -> PriceResult:
    """
    Extract price amount and currency from a value.

    Handles various formats:
    - "1 500.00" → 1500.00
    - "1,500.00" → 1500.00
    - "1 234,56" → 1234.56 (European format)
    - "₽ 999" → 999 (RUB)
    - "$99.99" → 99.99 (USD)
    - 1500 → 1500.00 (int/float passthrough)

    Args:
        value: Price value (string, number, or None)

    Returns:
        PriceResult with amount and currency_code

    Examples:
        >>> result = extract_price("₽1 500.00")
        >>> result.amount
        Decimal('1500.00')
        >>> result.currency_code
        'RUB'

        >>> result = extract_price("$99.99")
        >>> result.amount
        Decimal('99.99')
        >>> result.currency_code
        'USD'

        >>> result = extract_price("150€")
        >>> result.amount
        Decimal('150')
        >>> result.currency_code
        'EUR'

        >>> result = extract_price("25 руб")
        >>> result.amount
        Decimal('25')
        >>> result.currency_code
        'RUB'

        >>> result = extract_price(1500)
        >>> result.amount
        Decimal('1500')
        >>> result.currency_code
        None
    """
    if value is None:
        return PriceResult(raw_value=None, was_parsed=False)

    # Handle numeric types directly
    if isinstance(value, (int, float, Decimal)):
        try:
            amount = Decimal(str(value))
            return PriceResult(
                amount=amount,
                currency_code=None,
                raw_value=str(value),
                was_parsed=True,
            )
        except (InvalidOperation, ValueError):
            return PriceResult(raw_value=str(value), was_parsed=False)

    if not isinstance(value, str):
        return PriceResult(raw_value=str(value), was_parsed=False)

    raw_value = value.strip()
    if not raw_value:
        return PriceResult(raw_value=raw_value, was_parsed=False)

    # Detect currency before cleaning
    currency_code = detect_currency(raw_value)

    # Clean the string for numeric extraction
    cleaned = _clean_price_string(raw_value)

    if not cleaned:
        return PriceResult(
            amount=None,
            currency_code=currency_code,
            raw_value=raw_value,
            was_parsed=False,
        )

    # Parse the numeric value
    try:
        amount = Decimal(cleaned)
        return PriceResult(
            amount=amount,
            currency_code=currency_code,
            raw_value=raw_value,
            was_parsed=True,
        )
    except (InvalidOperation, ValueError):
        return PriceResult(
            amount=None,
            currency_code=currency_code,
            raw_value=raw_value,
            was_parsed=False,
        )


def _clean_price_string(value: str) -> str:
    """
    Clean price string for numeric parsing.

    Removes currency symbols, text, and normalizes separators.

    Args:
        value: Raw price string

    Returns:
        Cleaned numeric string ready for Decimal conversion
    """
    # Remove currency symbols
    cleaned = re.sub(r"[₽$€£¥₴₸₿₹₩₦₱฿元]", "", value)

    # Remove text currency indicators
    cleaned = re.sub(
        r"(?i)\b(руб\.?|рубль|рублей|рубля|р\.?|rub|ruble|rubles|usd|dollar|dollars|"
        r"eur|euro|euros|gbp|pound|pounds|jpy|yen|cny|yuan|inr|rupee|rupees)\b",
        "",
        cleaned,
    )

    # Remove spaces (thousands separator in many locales)
    cleaned = cleaned.replace(" ", "").replace("\u00a0", "").strip()

    if not cleaned:
        return ""

    # Normalize decimal/thousands separators
    cleaned = _normalize_separators(cleaned)

    return cleaned


def _normalize_separators(value: str) -> str:
    """
    Normalize decimal and thousands separators.

    Handles various formats:
    - "1,234.56" → "1234.56" (US format)
    - "1.234,56" → "1234.56" (European format)
    - "1 234,56" → "1234.56" (Already cleaned spaces)

    Args:
        value: Partially cleaned price string

    Returns:
        String with normalized decimal separator (.)
    """
    has_comma = "," in value
    has_dot = "." in value

    if has_comma and has_dot:
        # Both present - the LAST one is the decimal separator
        last_comma = value.rfind(",")
        last_dot = value.rfind(".")

        if last_comma > last_dot:
            # Comma is decimal separator (European: 1.234,56)
            return value.replace(".", "").replace(",", ".")
        else:
            # Dot is decimal separator (US: 1,234.56)
            return value.replace(",", "")

    elif has_comma:
        # Only comma - determine if decimal or thousands
        parts = value.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Looks like decimal (e.g., "1234,56")
            return value.replace(",", ".")
        else:
            # Thousands separator (e.g., "1,234,567")
            return value.replace(",", "")

    elif has_dot:
        # Only dot - check position to determine if decimal or thousands
        parts = value.split(".")
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Looks like decimal (e.g., "1234.56" or "99.99")
            return value
        elif len(parts) > 2:
            # Multiple dots - must be thousands (e.g., "1.234.567")
            # Keep last part as decimal if <= 2 digits
            if len(parts[-1]) <= 2:
                return "".join(parts[:-1]) + "." + parts[-1]
            else:
                return "".join(parts)

    return value


# =============================================================================
# Column Classification
# =============================================================================


def classify_price_column(column_header: str) -> str | None:
    """
    Classify a column header as retail or wholesale price.

    Analyzes column header text to determine price type.

    Args:
        column_header: Column header text (e.g., "Розничная цена", "Опт")

    Returns:
        "retail", "wholesale", or None if undetermined

    Examples:
        >>> classify_price_column("Розничная цена")
        'retail'

        >>> classify_price_column("Опт")
        'wholesale'

        >>> classify_price_column("Оптовая цена")
        'wholesale'

        >>> classify_price_column("Price")
        'retail'

        >>> classify_price_column("Dealer Price")
        'wholesale'

        >>> classify_price_column("Артикул")
        None

        >>> classify_price_column("Wholesale")
        'wholesale'

        >>> classify_price_column("RRP")
        'retail'
    """
    if not column_header:
        return None

    lower_header = column_header.lower().strip()

    # Check wholesale first (more specific patterns)
    for indicator in WHOLESALE_INDICATORS:
        if indicator in lower_header:
            return "wholesale"

    # Check retail indicators
    for indicator in RETAIL_INDICATORS:
        if indicator in lower_header:
            return "retail"

    return None


def classify_price_columns(
    headers: list[str],
) -> dict[str, list[int]]:
    """
    Classify multiple column headers and return indices by type.

    Scans all headers and groups them by price type.

    Args:
        headers: List of column header strings

    Returns:
        Dict with keys "retail", "wholesale", mapping to list of column indices

    Example:
        >>> headers = ["SKU", "Name", "Retail Price", "Wholesale Price", "Stock"]
        >>> classify_price_columns(headers)
        {'retail': [2], 'wholesale': [3]}

        >>> headers = ["Артикул", "Наименование", "Цена", "Опт", "Остаток"]
        >>> classify_price_columns(headers)
        {'retail': [2], 'wholesale': [3]}
    """
    result: dict[str, list[int]] = {"retail": [], "wholesale": []}

    for idx, header in enumerate(headers):
        classification = classify_price_column(header)
        if classification == "retail":
            result["retail"].append(idx)
        elif classification == "wholesale":
            result["wholesale"].append(idx)

    return result


# =============================================================================
# Batch Extraction
# =============================================================================


def extract_prices_from_row(
    row: list[str],
    retail_columns: list[int] | None = None,
    wholesale_columns: list[int] | None = None,
    default_currency: str | None = None,
) -> tuple[Decimal | None, Decimal | None, str | None]:
    """
    Extract retail and wholesale prices from a row.

    Uses column indices to extract and parse prices.

    Args:
        row: List of cell values
        retail_columns: Column indices for retail prices
        wholesale_columns: Column indices for wholesale prices
        default_currency: Fallback currency if none detected

    Returns:
        Tuple of (retail_price, wholesale_price, currency_code)

    Example:
        >>> row = ["SKU123", "Widget", "₽1500", "₽1200"]
        >>> extract_prices_from_row(row, retail_columns=[2], wholesale_columns=[3])
        (Decimal('1500'), Decimal('1200'), 'RUB')
    """
    retail_price: Decimal | None = None
    wholesale_price: Decimal | None = None
    detected_currency: str | None = None

    # Extract retail price
    if retail_columns:
        for col_idx in retail_columns:
            if col_idx < len(row):
                result = extract_price(row[col_idx])
                if result.was_parsed and result.amount is not None:
                    retail_price = result.amount
                    if result.currency_code:
                        detected_currency = result.currency_code
                    break

    # Extract wholesale price
    if wholesale_columns:
        for col_idx in wholesale_columns:
            if col_idx < len(row):
                result = extract_price(row[col_idx])
                if result.was_parsed and result.amount is not None:
                    wholesale_price = result.amount
                    if result.currency_code and not detected_currency:
                        detected_currency = result.currency_code
                    break

    # Use default currency if none detected
    currency_code = detected_currency or default_currency

    return retail_price, wholesale_price, currency_code

