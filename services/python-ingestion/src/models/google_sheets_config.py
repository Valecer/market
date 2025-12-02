"""Pydantic models for Google Sheets parser configuration."""
from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import Dict, List, Optional


class GoogleSheetsConfig(BaseModel):
    """Configuration for Google Sheets parser.
    
    This model validates the source_config dictionary passed in ParseTaskMessage
    for the google_sheets parser type. It defines all parser-specific settings
    including sheet URL, column mappings, and data extraction parameters.
    """
    
    sheet_url: HttpUrl = Field(
        ...,
        description="Google Sheets URL (must be a valid HTTP/HTTPS URL)"
    )
    sheet_name: str = Field(
        default="Sheet1",
        min_length=1,
        description="Name of the worksheet tab to parse"
    )
    column_mapping: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "Manual column mapping from sheet headers to standard fields. "
            "Keys: 'sku', 'name', 'price'. Values: exact header names from sheet. "
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
        ge=2,
        description="Row number (1-indexed) where data rows begin"
    )
    
    @field_validator('sheet_name')
    @classmethod
    def validate_sheet_name(cls, v: str) -> str:
        """Validate sheet name is not empty."""
        if not v.strip():
            raise ValueError('sheet_name cannot be empty or whitespace')
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
                "sheet_url": "https://docs.google.com/spreadsheets/d/1abc123xyz/edit",
                "sheet_name": "November 2025 Price List",
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

