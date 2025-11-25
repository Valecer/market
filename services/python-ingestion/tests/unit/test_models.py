"""Unit tests for Pydantic validation models.

This module tests Pydantic models for data validation, including:
- ParsedSupplierItem: Validates parsed supplier items
- ParseTaskMessage: Validates queue task messages
- GoogleSheetsConfig: Validates Google Sheets parser configuration
"""
import os

# Set environment variables BEFORE importing modules that use settings
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_PASSWORD", "test_password")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("LOG_LEVEL", "INFO")

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Any
from pydantic import ValidationError

from src.models.parsed_item import ParsedSupplierItem
from src.models.queue_message import ParseTaskMessage
from src.models.google_sheets_config import GoogleSheetsConfig


class TestParsedSupplierItem:
    """Test ParsedSupplierItem Pydantic model validation."""
    
    def test_valid_item_creates_successfully(self):
        """Verify valid ParsedSupplierItem is created successfully."""
        item = ParsedSupplierItem(
            supplier_sku="SKU-001",
            name="Test Product",
            price=Decimal("19.99"),
            characteristics={"color": "red", "size": "M"}
        )
        
        assert item.supplier_sku == "SKU-001"
        assert item.name == "Test Product"
        assert item.price == Decimal("19.99")
        assert item.characteristics == {"color": "red", "size": "M"}
    
    def test_item_requires_supplier_sku(self):
        """Verify supplier_sku is required."""
        with pytest.raises(ValidationError) as exc_info:
            ParsedSupplierItem(
                name="Test Product",
                price=Decimal("19.99")
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("supplier_sku",) for error in errors)
    
    def test_item_requires_name(self):
        """Verify name is required."""
        with pytest.raises(ValidationError) as exc_info:
            ParsedSupplierItem(
                supplier_sku="SKU-001",
                price=Decimal("19.99")
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)
    
    def test_item_requires_price(self):
        """Verify price is required."""
        with pytest.raises(ValidationError) as exc_info:
            ParsedSupplierItem(
                supplier_sku="SKU-001",
                name="Test Product"
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("price",) for error in errors)
    
    def test_item_rejects_negative_price(self):
        """Verify price must be non-negative."""
        with pytest.raises(ValidationError) as exc_info:
            ParsedSupplierItem(
                supplier_sku="SKU-001",
                name="Test Product",
                price=Decimal("-10.00")
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("price",) for error in errors)
    
    def test_item_validates_price_precision_2_decimal_places(self):
        """Verify price precision validator quantizes to 2 decimal places."""
        # Price with 3 decimal places should be quantized to 2 decimal places
        # quantize() rounds to nearest, so 19.999 becomes 20.00
        item = ParsedSupplierItem(
            supplier_sku="SKU-001",
            name="Test Product",
            price=Decimal("19.999")
        )
        
        # Should be quantized to 2 decimal places (20.00, since quantize rounds)
        assert item.price == Decimal("20.00")
        assert item.price.as_tuple().exponent >= -2
    
    def test_item_validates_price_precision_raises_error(self):
        """Verify price precision validator quantizes values with >2 decimal places."""
        # The validator quantizes values, it doesn't raise errors
        # This test verifies quantization works correctly
        item = ParsedSupplierItem(
            supplier_sku="SKU-001",
            name="Test Product",
            price=Decimal("19.999")
        )
        
        # Should be quantized to 2 decimal places (quantize rounds to nearest)
        assert item.price.as_tuple().exponent >= -2
        assert item.price == Decimal("20.00")
    
    def test_item_accepts_empty_characteristics(self):
        """Verify characteristics can be empty dict."""
        item = ParsedSupplierItem(
            supplier_sku="SKU-001",
            name="Test Product",
            price=Decimal("19.99"),
            characteristics={}
        )
        
        assert item.characteristics == {}
    
    def test_item_defaults_characteristics_to_empty_dict(self):
        """Verify characteristics defaults to empty dict if not provided."""
        item = ParsedSupplierItem(
            supplier_sku="SKU-001",
            name="Test Product",
            price=Decimal("19.99")
        )
        
        assert item.characteristics == {}
    
    def test_item_validates_characteristics_json_serializable(self):
        """Verify characteristics must be JSON serializable."""
        # Valid JSON-serializable dict
        item = ParsedSupplierItem(
            supplier_sku="SKU-001",
            name="Test Product",
            price=Decimal("19.99"),
            characteristics={"color": "red", "size": 10}
        )
        
        assert item.characteristics == {"color": "red", "size": 10}
    
    def test_item_rejects_non_serializable_characteristics(self):
        """Verify characteristics with non-serializable values are rejected."""
        # Note: Pydantic's JSON validation happens during serialization
        # For this test, we'll use a value that can't be JSON serialized
        # However, Pydantic will convert most Python types to JSON-compatible types
        # So we test with a custom object that truly can't be serialized
        
        class NonSerializable:
            pass
        
        # This should raise ValidationError during validation
        with pytest.raises(ValidationError):
            ParsedSupplierItem(
                supplier_sku="SKU-001",
                name="Test Product",
                price=Decimal("19.99"),
                characteristics={"obj": NonSerializable()}
            )
    
    def test_item_validates_supplier_sku_length(self):
        """Verify supplier_sku length constraints."""
        # Too short (empty)
        with pytest.raises(ValidationError) as exc_info:
            ParsedSupplierItem(
                supplier_sku="",
                name="Test Product",
                price=Decimal("19.99")
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("supplier_sku",) for error in errors)
        
        # Too long (>255 chars)
        long_sku = "A" * 256
        with pytest.raises(ValidationError) as exc_info:
            ParsedSupplierItem(
                supplier_sku=long_sku,
                name="Test Product",
                price=Decimal("19.99")
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("supplier_sku",) for error in errors)
    
    def test_item_validates_name_length(self):
        """Verify name length constraints."""
        # Too short (empty)
        with pytest.raises(ValidationError) as exc_info:
            ParsedSupplierItem(
                supplier_sku="SKU-001",
                name="",
                price=Decimal("19.99")
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)
        
        # Too long (>500 chars)
        long_name = "A" * 501
        with pytest.raises(ValidationError) as exc_info:
            ParsedSupplierItem(
                supplier_sku="SKU-001",
                name=long_name,
                price=Decimal("19.99")
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)


class TestParseTaskMessage:
    """Test ParseTaskMessage Pydantic model validation."""
    
    def test_valid_message_creates_successfully(self):
        """Verify valid ParseTaskMessage is created successfully."""
        message = ParseTaskMessage(
            task_id="task-001",
            parser_type="google_sheets",
            supplier_name="Test Supplier",
            source_config={"sheet_url": "https://example.com/sheet"}
        )
        
        assert message.task_id == "task-001"
        assert message.parser_type == "google_sheets"
        assert message.supplier_name == "Test Supplier"
        assert message.retry_count == 0
        assert message.max_retries == 3
        assert isinstance(message.enqueued_at, datetime)
    
    def test_message_requires_task_id(self):
        """Verify task_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            ParseTaskMessage(
                parser_type="google_sheets",
                supplier_name="Test Supplier",
                source_config={}
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("task_id",) for error in errors)
    
    def test_message_validates_task_id_not_empty(self):
        """Verify task_id cannot be empty or whitespace."""
        with pytest.raises(ValidationError) as exc_info:
            ParseTaskMessage(
                task_id="   ",
                parser_type="google_sheets",
                supplier_name="Test Supplier",
                source_config={}
            )
        
        errors = exc_info.value.errors()
        assert any("task_id" in str(error["loc"]) for error in errors)
    
    def test_message_validates_parser_type_literal(self):
        """Verify parser_type must be one of allowed values."""
        with pytest.raises(ValidationError) as exc_info:
            ParseTaskMessage(
                task_id="task-001",
                parser_type="invalid_parser",
                supplier_name="Test Supplier",
                source_config={}
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("parser_type",) for error in errors)
    
    def test_message_validates_supplier_name_not_empty(self):
        """Verify supplier_name cannot be empty or whitespace."""
        with pytest.raises(ValidationError) as exc_info:
            ParseTaskMessage(
                task_id="task-001",
                parser_type="google_sheets",
                supplier_name="   ",
                source_config={}
            )
        
        errors = exc_info.value.errors()
        assert any("supplier_name" in str(error["loc"]) for error in errors)
    
    def test_message_validates_source_config_not_empty_for_real_parsers(self):
        """Verify source_config cannot be empty for non-test parsers."""
        with pytest.raises(ValidationError) as exc_info:
            ParseTaskMessage(
                task_id="task-001",
                parser_type="google_sheets",
                supplier_name="Test Supplier",
                source_config={}
            )
        
        errors = exc_info.value.errors()
        # The error is raised by model_validator, so it's at the root level
        # Check for the error message or type
        assert any(
            "source_config" in str(error.get("msg", "")).lower() or 
            error.get("type") == "value_error" 
            for error in errors
        )
    
    def test_message_allows_empty_source_config_for_test_parsers(self):
        """Verify source_config can be empty for test parsers."""
        message = ParseTaskMessage(
            task_id="task-001",
            parser_type="stub",
            supplier_name="Test Supplier",
            source_config={}
        )
        
        assert message.source_config == {}
    
    def test_message_defaults_retry_count_to_zero(self):
        """Verify retry_count defaults to 0."""
        message = ParseTaskMessage(
            task_id="task-001",
            parser_type="stub",
            supplier_name="Test Supplier",
            source_config={}
        )
        
        assert message.retry_count == 0
    
    def test_message_validates_retry_count_non_negative(self):
        """Verify retry_count must be >= 0."""
        with pytest.raises(ValidationError) as exc_info:
            ParseTaskMessage(
                task_id="task-001",
                parser_type="stub",
                supplier_name="Test Supplier",
                source_config={},
                retry_count=-1
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("retry_count",) for error in errors)
    
    def test_message_defaults_max_retries_to_three(self):
        """Verify max_retries defaults to 3."""
        message = ParseTaskMessage(
            task_id="task-001",
            parser_type="stub",
            supplier_name="Test Supplier",
            source_config={}
        )
        
        assert message.max_retries == 3
    
    def test_message_validates_max_retries_range(self):
        """Verify max_retries must be between 1 and 10."""
        # Too low
        with pytest.raises(ValidationError) as exc_info:
            ParseTaskMessage(
                task_id="task-001",
                parser_type="stub",
                supplier_name="Test Supplier",
                source_config={},
                max_retries=0
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("max_retries",) for error in errors)
        
        # Too high
        with pytest.raises(ValidationError) as exc_info:
            ParseTaskMessage(
                task_id="task-001",
                parser_type="stub",
                supplier_name="Test Supplier",
                source_config={},
                max_retries=11
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("max_retries",) for error in errors)
    
    def test_message_defaults_enqueued_at_to_current_time(self):
        """Verify enqueued_at defaults to current UTC time."""
        before = datetime.now(timezone.utc)
        message = ParseTaskMessage(
            task_id="task-001",
            parser_type="stub",
            supplier_name="Test Supplier",
            source_config={}
        )
        after = datetime.now(timezone.utc)
        
        assert before <= message.enqueued_at <= after
    
    def test_message_defaults_priority_to_normal(self):
        """Verify priority defaults to 'normal'."""
        message = ParseTaskMessage(
            task_id="task-001",
            parser_type="stub",
            supplier_name="Test Supplier",
            source_config={}
        )
        
        assert message.priority == "normal"
    
    def test_message_validates_priority_literal(self):
        """Verify priority must be one of allowed values."""
        with pytest.raises(ValidationError) as exc_info:
            ParseTaskMessage(
                task_id="task-001",
                parser_type="stub",
                supplier_name="Test Supplier",
                source_config={},
                priority="invalid"
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("priority",) for error in errors)


class TestGoogleSheetsConfig:
    """Test GoogleSheetsConfig Pydantic model validation."""
    
    def test_valid_config_creates_successfully(self):
        """Verify valid GoogleSheetsConfig is created successfully."""
        config = GoogleSheetsConfig(
            sheet_url="https://docs.google.com/spreadsheets/d/abc123/edit"
        )
        
        # HttpUrl objects need to be compared as strings
        assert str(config.sheet_url) == "https://docs.google.com/spreadsheets/d/abc123/edit"
        assert config.sheet_name == "Sheet1"  # Default
        assert config.header_row == 1  # Default
        assert config.data_start_row == 2  # Default
    
    def test_config_requires_sheet_url(self):
        """Verify sheet_url is required."""
        with pytest.raises(ValidationError) as exc_info:
            GoogleSheetsConfig()
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("sheet_url",) for error in errors)
    
    def test_config_validates_sheet_url_is_valid_http_url(self):
        """Verify sheet_url must be a valid HTTP/HTTPS URL."""
        with pytest.raises(ValidationError) as exc_info:
            GoogleSheetsConfig(
                sheet_url="not-a-valid-url"
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("sheet_url",) for error in errors)
    
    def test_config_defaults_sheet_name_to_sheet1(self):
        """Verify sheet_name defaults to 'Sheet1'."""
        config = GoogleSheetsConfig(
            sheet_url="https://docs.google.com/spreadsheets/d/abc123/edit"
        )
        
        assert config.sheet_name == "Sheet1"
    
    def test_config_validates_sheet_name_not_empty(self):
        """Verify sheet_name cannot be empty or whitespace."""
        with pytest.raises(ValidationError) as exc_info:
            GoogleSheetsConfig(
                sheet_url="https://docs.google.com/spreadsheets/d/abc123/edit",
                sheet_name="   "
            )
        
        errors = exc_info.value.errors()
        assert any("sheet_name" in str(error["loc"]) for error in errors)
    
    def test_config_validates_column_mapping_keys(self):
        """Verify column_mapping keys must be 'sku', 'name', or 'price'."""
        # Valid keys
        config = GoogleSheetsConfig(
            sheet_url="https://docs.google.com/spreadsheets/d/abc123/edit",
            column_mapping={
                "sku": "Product Code",
                "name": "Description",
                "price": "Unit Price"
            }
        )
        
        assert config.column_mapping is not None
        
        # Invalid key
        with pytest.raises(ValidationError) as exc_info:
            GoogleSheetsConfig(
                sheet_url="https://docs.google.com/spreadsheets/d/abc123/edit",
                column_mapping={
                    "invalid_key": "Column Name"
                }
            )
        
        errors = exc_info.value.errors()
        assert any("column_mapping" in str(error["loc"]) for error in errors)
    
    def test_config_defaults_header_row_to_one(self):
        """Verify header_row defaults to 1."""
        config = GoogleSheetsConfig(
            sheet_url="https://docs.google.com/spreadsheets/d/abc123/edit"
        )
        
        assert config.header_row == 1
    
    def test_config_validates_header_row_positive(self):
        """Verify header_row must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            GoogleSheetsConfig(
                sheet_url="https://docs.google.com/spreadsheets/d/abc123/edit",
                header_row=0
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("header_row",) for error in errors)
    
    def test_config_defaults_data_start_row_to_two(self):
        """Verify data_start_row defaults to 2."""
        config = GoogleSheetsConfig(
            sheet_url="https://docs.google.com/spreadsheets/d/abc123/edit"
        )
        
        assert config.data_start_row == 2
    
    def test_config_validates_data_start_row_after_header_row(self):
        """Verify data_start_row must be > header_row."""
        with pytest.raises(ValidationError) as exc_info:
            GoogleSheetsConfig(
                sheet_url="https://docs.google.com/spreadsheets/d/abc123/edit",
                header_row=2,
                data_start_row=1  # Must be > header_row
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("data_start_row",) for error in errors)
    
    def test_config_validates_data_start_row_minimum(self):
        """Verify data_start_row must be >= 2."""
        with pytest.raises(ValidationError) as exc_info:
            GoogleSheetsConfig(
                sheet_url="https://docs.google.com/spreadsheets/d/abc123/edit",
                data_start_row=1
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("data_start_row",) for error in errors)
    
    def test_config_accepts_characteristic_columns_list(self):
        """Verify characteristic_columns can be a list of column names."""
        config = GoogleSheetsConfig(
            sheet_url="https://docs.google.com/spreadsheets/d/abc123/edit",
            characteristic_columns=["Color", "Size", "Material"]
        )
        
        assert config.characteristic_columns == ["Color", "Size", "Material"]
    
    def test_config_accepts_none_characteristic_columns(self):
        """Verify characteristic_columns can be None."""
        config = GoogleSheetsConfig(
            sheet_url="https://docs.google.com/spreadsheets/d/abc123/edit",
            characteristic_columns=None
        )
        
        assert config.characteristic_columns is None

