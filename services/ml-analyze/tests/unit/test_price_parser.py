"""
Unit tests for price_parser module.

Tests currency detection, price extraction, and column classification.
"""

from decimal import Decimal

import pytest

from src.utils.price_parser import (
    CURRENCY_MAP,
    RETAIL_INDICATORS,
    WHOLESALE_INDICATORS,
    PriceResult,
    classify_price_column,
    classify_price_columns,
    detect_currency,
    extract_price,
    extract_prices_from_row,
)


class TestCurrencyMap:
    """Tests for CURRENCY_MAP constant."""

    def test_currency_map_has_common_symbols(self) -> None:
        """Currency map includes common currency symbols."""
        assert "₽" in CURRENCY_MAP
        assert "$" in CURRENCY_MAP
        assert "€" in CURRENCY_MAP
        assert "£" in CURRENCY_MAP

    def test_currency_map_has_text_indicators(self) -> None:
        """Currency map includes text indicators."""
        assert "руб" in CURRENCY_MAP
        assert "usd" in CURRENCY_MAP
        assert "eur" in CURRENCY_MAP

    def test_currency_map_returns_iso_codes(self) -> None:
        """Currency map values are ISO 4217 codes."""
        assert CURRENCY_MAP["₽"] == "RUB"
        assert CURRENCY_MAP["$"] == "USD"
        assert CURRENCY_MAP["€"] == "EUR"


class TestDetectCurrency:
    """Tests for detect_currency function."""

    def test_detect_ruble_symbol(self) -> None:
        """Detects ₽ symbol as RUB."""
        assert detect_currency("₽1500") == "RUB"
        assert detect_currency("1500₽") == "RUB"
        assert detect_currency("₽ 1500") == "RUB"

    def test_detect_dollar_symbol(self) -> None:
        """Detects $ symbol as USD."""
        assert detect_currency("$99.99") == "USD"
        assert detect_currency("99.99$") == "USD"
        assert detect_currency("$ 99.99") == "USD"

    def test_detect_euro_symbol(self) -> None:
        """Detects € symbol as EUR."""
        assert detect_currency("€150") == "EUR"
        assert detect_currency("150€") == "EUR"

    def test_detect_russian_text(self) -> None:
        """Detects Russian text indicators."""
        assert detect_currency("25 руб") == "RUB"
        assert detect_currency("25 руб.") == "RUB"
        assert detect_currency("25 рублей") == "RUB"

    def test_detect_english_text(self) -> None:
        """Detects English text indicators."""
        assert detect_currency("99 USD") == "USD"
        assert detect_currency("99 dollars") == "USD"
        assert detect_currency("99 EUR") == "EUR"
        assert detect_currency("99 euros") == "EUR"

    def test_no_currency_returns_none(self) -> None:
        """Returns None when no currency detected."""
        assert detect_currency("1234.56") is None
        assert detect_currency("1500") is None
        assert detect_currency("") is None

    def test_empty_string(self) -> None:
        """Handles empty string."""
        assert detect_currency("") is None

    def test_none_input(self) -> None:
        """Handles None input."""
        assert detect_currency(None) is None  # type: ignore[arg-type]


class TestExtractPrice:
    """Tests for extract_price function."""

    def test_extract_ruble_price(self) -> None:
        """Extracts price with ₽ symbol."""
        result = extract_price("₽1 500.00")
        assert result.amount == Decimal("1500.00")
        assert result.currency_code == "RUB"
        assert result.was_parsed is True

    def test_extract_dollar_price(self) -> None:
        """Extracts price with $ symbol."""
        result = extract_price("$99.99")
        assert result.amount == Decimal("99.99")
        assert result.currency_code == "USD"
        assert result.was_parsed is True

    def test_extract_euro_price(self) -> None:
        """Extracts price with € symbol."""
        result = extract_price("150€")
        assert result.amount == Decimal("150")
        assert result.currency_code == "EUR"
        assert result.was_parsed is True

    def test_extract_russian_text_currency(self) -> None:
        """Extracts price with Russian text currency."""
        result = extract_price("25 руб")
        assert result.amount == Decimal("25")
        assert result.currency_code == "RUB"
        assert result.was_parsed is True

    def test_extract_no_currency(self) -> None:
        """Extracts price without currency."""
        result = extract_price("1234.56")
        assert result.amount == Decimal("1234.56")
        assert result.currency_code is None
        assert result.was_parsed is True

    def test_extract_european_format(self) -> None:
        """Handles European number format (comma as decimal)."""
        result = extract_price("1 234,56")
        assert result.amount == Decimal("1234.56")
        assert result.was_parsed is True

    def test_extract_us_format(self) -> None:
        """Handles US number format (comma as thousands)."""
        result = extract_price("1,234.56")
        assert result.amount == Decimal("1234.56")
        assert result.was_parsed is True

    def test_extract_spaces_as_thousands(self) -> None:
        """Handles spaces as thousands separator."""
        result = extract_price("1 500")
        assert result.amount == Decimal("1500")
        assert result.was_parsed is True

    def test_extract_from_int(self) -> None:
        """Handles integer input."""
        result = extract_price(1500)
        assert result.amount == Decimal("1500")
        assert result.currency_code is None
        assert result.was_parsed is True

    def test_extract_from_float(self) -> None:
        """Handles float input."""
        result = extract_price(99.99)
        assert result.amount == Decimal("99.99")
        assert result.currency_code is None
        assert result.was_parsed is True

    def test_extract_from_decimal(self) -> None:
        """Handles Decimal input."""
        result = extract_price(Decimal("150.50"))
        assert result.amount == Decimal("150.50")
        assert result.currency_code is None
        assert result.was_parsed is True

    def test_extract_none_input(self) -> None:
        """Handles None input."""
        result = extract_price(None)
        assert result.amount is None
        assert result.currency_code is None
        assert result.was_parsed is False

    def test_extract_empty_string(self) -> None:
        """Handles empty string."""
        result = extract_price("")
        assert result.amount is None
        assert result.currency_code is None
        assert result.was_parsed is False

    def test_extract_preserves_raw_value(self) -> None:
        """Preserves original input in raw_value."""
        result = extract_price("₽1 500.00")
        assert result.raw_value == "₽1 500.00"

    def test_extract_invalid_string(self) -> None:
        """Handles invalid price string."""
        result = extract_price("not a price")
        assert result.amount is None
        assert result.was_parsed is False


class TestClassifyPriceColumn:
    """Tests for classify_price_column function."""

    def test_classify_retail_russian(self) -> None:
        """Detects Russian retail indicators."""
        assert classify_price_column("Розничная цена") == "retail"
        assert classify_price_column("Розн.") == "retail"
        assert classify_price_column("Цена") == "retail"

    def test_classify_retail_english(self) -> None:
        """Detects English retail indicators."""
        assert classify_price_column("Retail Price") == "retail"
        assert classify_price_column("RRP") == "retail"
        assert classify_price_column("MSRP") == "retail"
        assert classify_price_column("Price") == "retail"

    def test_classify_wholesale_russian(self) -> None:
        """Detects Russian wholesale indicators."""
        assert classify_price_column("Оптовая цена") == "wholesale"
        assert classify_price_column("Опт") == "wholesale"
        assert classify_price_column("Дилерская цена") == "wholesale"

    def test_classify_wholesale_english(self) -> None:
        """Detects English wholesale indicators."""
        assert classify_price_column("Wholesale") == "wholesale"
        assert classify_price_column("Dealer Price") == "wholesale"
        assert classify_price_column("Bulk") == "wholesale"
        assert classify_price_column("B2B Price") == "wholesale"

    def test_classify_non_price_column(self) -> None:
        """Returns None for non-price columns."""
        assert classify_price_column("Артикул") is None
        assert classify_price_column("Наименование") is None
        assert classify_price_column("SKU") is None
        assert classify_price_column("Name") is None

    def test_classify_empty_string(self) -> None:
        """Handles empty string."""
        assert classify_price_column("") is None

    def test_classify_case_insensitive(self) -> None:
        """Classification is case-insensitive."""
        assert classify_price_column("RETAIL") == "retail"
        assert classify_price_column("WHOLESALE") == "wholesale"
        assert classify_price_column("ОПТ") == "wholesale"


class TestClassifyPriceColumns:
    """Tests for classify_price_columns function."""

    def test_classify_multiple_columns(self) -> None:
        """Classifies multiple column headers."""
        headers = ["SKU", "Name", "Retail Price", "Wholesale Price", "Stock"]
        result = classify_price_columns(headers)
        assert result["retail"] == [2]
        assert result["wholesale"] == [3]

    def test_classify_russian_headers(self) -> None:
        """Classifies Russian column headers."""
        headers = ["Артикул", "Наименование", "Цена", "Опт", "Остаток"]
        result = classify_price_columns(headers)
        assert result["retail"] == [2]
        assert result["wholesale"] == [3]

    def test_classify_no_price_columns(self) -> None:
        """Returns empty lists when no price columns found."""
        headers = ["SKU", "Name", "Description"]
        result = classify_price_columns(headers)
        assert result["retail"] == []
        assert result["wholesale"] == []

    def test_classify_multiple_retail_columns(self) -> None:
        """Handles multiple retail price columns."""
        headers = ["Name", "Retail Price", "RRP"]
        result = classify_price_columns(headers)
        assert len(result["retail"]) == 2


class TestExtractPricesFromRow:
    """Tests for extract_prices_from_row function."""

    def test_extract_both_prices(self) -> None:
        """Extracts both retail and wholesale prices."""
        row = ["SKU123", "Widget", "₽1500", "₽1200"]
        retail, wholesale, currency = extract_prices_from_row(
            row, retail_columns=[2], wholesale_columns=[3]
        )
        assert retail == Decimal("1500")
        assert wholesale == Decimal("1200")
        assert currency == "RUB"

    def test_extract_with_default_currency(self) -> None:
        """Uses default currency when not detected."""
        row = ["SKU123", "Widget", "1500", "1200"]
        retail, wholesale, currency = extract_prices_from_row(
            row,
            retail_columns=[2],
            wholesale_columns=[3],
            default_currency="USD",
        )
        assert retail == Decimal("1500")
        assert wholesale == Decimal("1200")
        assert currency == "USD"

    def test_extract_missing_columns(self) -> None:
        """Handles missing column indices."""
        row = ["SKU123", "Widget"]
        retail, wholesale, currency = extract_prices_from_row(
            row, retail_columns=[2], wholesale_columns=[3]
        )
        assert retail is None
        assert wholesale is None
        assert currency is None

    def test_extract_none_columns(self) -> None:
        """Handles None column lists."""
        row = ["SKU123", "Widget", "₽1500"]
        retail, wholesale, currency = extract_prices_from_row(
            row, retail_columns=None, wholesale_columns=None
        )
        assert retail is None
        assert wholesale is None
        assert currency is None


class TestPriceResultDataclass:
    """Tests for PriceResult dataclass."""

    def test_price_result_defaults(self) -> None:
        """PriceResult has correct default values."""
        result = PriceResult()
        assert result.amount is None
        assert result.currency_code is None
        assert result.raw_value is None
        assert result.was_parsed is False

    def test_price_result_is_frozen(self) -> None:
        """PriceResult is immutable."""
        result = PriceResult(amount=Decimal("100"), currency_code="USD")
        with pytest.raises(AttributeError):
            result.amount = Decimal("200")  # type: ignore[misc]


class TestIndicatorSets:
    """Tests for indicator constants."""

    def test_retail_indicators_is_frozenset(self) -> None:
        """RETAIL_INDICATORS is a frozenset."""
        assert isinstance(RETAIL_INDICATORS, frozenset)

    def test_wholesale_indicators_is_frozenset(self) -> None:
        """WHOLESALE_INDICATORS is a frozenset."""
        assert isinstance(WHOLESALE_INDICATORS, frozenset)

    def test_no_overlap_between_indicators(self) -> None:
        """No overlap between retail and wholesale indicators."""
        overlap = RETAIL_INDICATORS & WHOLESALE_INDICATORS
        assert len(overlap) == 0, f"Unexpected overlap: {overlap}"

