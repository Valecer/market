"""Pydantic models for file-based parser configuration (CSV, Excel)."""
from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional


class FileParserConfig(BaseModel):
    """Base configuration for file-based parsers (CSV, Excel).
    
    This model validates the source_config dictionary passed in ParseTaskMessage
    for csv and excel parser types. It defines all parser-specific settings
    including file path, column mappings, and data extraction parameters.
    """
    
    file_path: str = Field(
        ...,
        min_length=1,
        description="Path to the file to parse (uploaded or local)"
    )
    original_filename: Optional[str] = Field(
        default=None,
        description="Original filename before server-side renaming"
    )
    column_mapping: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "Manual column mapping from file headers to standard fields. "
            "Keys: 'sku', 'name', 'price'. Values: exact header names from file. "
            "If provided, overrides automatic column detection."
        )
    )
    characteristic_columns: Optional[List[str]] = Field(
        default=None,
        description=(
            "List of column names to include in characteristics JSONB. "
            "These columns will be merged into a single JSON object. "
            "If None, all non-mapped columns become characteristics."
        )
    )
    header_row: int = Field(
        default=1,
        ge=1,
        description="Row number (1-indexed) containing column headers (first header row if multiple)"
    )
    header_row_end: Optional[int] = Field(
        default=None,
        ge=1,
        description="Row number (1-indexed) of last header row if headers span multiple rows. If None, only header_row is used."
    )
    data_start_row: int = Field(
        default=2,
        ge=1,
        description="Row number (1-indexed) where data rows begin"
    )
    
    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Validate file path is not empty."""
        if not v.strip():
            raise ValueError('file_path cannot be empty or whitespace')
        return v.strip()
    
    @field_validator('column_mapping')
    @classmethod
    def validate_column_mapping_keys(cls, v: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """Validate column_mapping keys are valid field names."""
        if v is None:
            return v
        
        valid_keys = {'sku', 'name', 'price'}
        invalid_keys = set(v.keys()) - valid_keys
        if invalid_keys:
            raise ValueError(
                f"column_mapping keys must be one of {valid_keys}. "
                f"Invalid keys: {invalid_keys}"
            )
        return v
    
    @field_validator('header_row_end')
    @classmethod
    def validate_header_row_end(cls, v: Optional[int], info) -> Optional[int]:
        """Validate header_row_end is after header_row."""
        if v is None:
            return v
        header_row = info.data.get('header_row', 1)
        if v < header_row:
            raise ValueError(
                f'header_row_end ({v}) must be greater than or equal to header_row ({header_row})'
            )
        return v
    
    @field_validator('data_start_row')
    @classmethod
    def validate_data_start_after_header(cls, v: int, info) -> int:
        """Validate data_start_row is after header rows."""
        header_row = info.data.get('header_row', 1)
        header_row_end = info.data.get('header_row_end')
        # Use header_row_end if provided, otherwise use header_row
        last_header_row = header_row_end if header_row_end is not None else header_row
        if v <= last_header_row:
            raise ValueError(
                f'data_start_row ({v}) must be greater than last header row ({last_header_row})'
            )
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "file_path": "/tmp/uploads/supplier_12345.csv",
                "original_filename": "price_list_november.csv",
                "column_mapping": {
                    "sku": "Item Code",
                    "name": "Product Description",
                    "price": "Unit Price"
                },
                "characteristic_columns": ["Color", "Size", "Material"],
                "header_row": 1,
                "data_start_row": 2
            }
        }
    }


class CsvParserConfig(FileParserConfig):
    """Configuration for CSV parser.
    
    Extends FileParserConfig with CSV-specific options.
    """
    
    delimiter: str = Field(
        default=",",
        min_length=1,
        max_length=5,
        description="Field delimiter character (default: comma)"
    )
    encoding: str = Field(
        default="utf-8",
        description="File encoding (default: utf-8)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "file_path": "/tmp/uploads/supplier_12345.csv",
                "original_filename": "price_list_november.csv",
                "delimiter": ",",
                "encoding": "utf-8",
                "header_row": 1,
                "data_start_row": 2
            }
        }
    }


class ExcelParserConfig(FileParserConfig):
    """Configuration for Excel parser.
    
    Extends FileParserConfig with Excel-specific options.
    """
    
    sheet_name: str = Field(
        default="Sheet1",
        min_length=1,
        description="Name of the worksheet to parse"
    )
    
    @field_validator('sheet_name')
    @classmethod
    def validate_sheet_name(cls, v: str) -> str:
        """Validate sheet name is not empty."""
        if not v.strip():
            raise ValueError('sheet_name cannot be empty or whitespace')
        return v.strip()
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "file_path": "/tmp/uploads/supplier_12345.xlsx",
                "original_filename": "price_list_november.xlsx",
                "sheet_name": "Price List",
                "header_row": 1,
                "data_start_row": 2
            }
        }
    }

