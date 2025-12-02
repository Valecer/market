"""Pydantic models for Master Sheet configuration.

This module defines the data models for parsing and validating
supplier configurations from the Master Google Sheet.
"""
from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, List
from enum import Enum


class SourceFormat(str, Enum):
    """Supported data source formats for supplier price lists."""
    GOOGLE_SHEETS = "google_sheets"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"  # Noted but not parsed in current implementation


class SupplierConfigRow(BaseModel):
    """Single row from Master Google Sheet representing a supplier configuration.
    
    Attributes:
        supplier_name: Unique identifier for the supplier
        source_url: URL to the supplier's price list
        format: Data source format type
        is_active: Whether the supplier is active for syncing
        notes: Optional administrative notes
    """
    supplier_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique identifier for the supplier"
    )
    source_url: HttpUrl = Field(
        ...,
        description="URL to the supplier's price list (Google Sheet, CSV endpoint, etc.)"
    )
    format: SourceFormat = Field(
        ...,
        description="Data source format type"
    )
    is_active: bool = Field(
        default=True,
        description="Whether the supplier is active for syncing"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional administrative notes"
    )
    
    @field_validator('supplier_name')
    @classmethod
    def validate_supplier_name(cls, v: str) -> str:
        """Strip whitespace from supplier name."""
        return v.strip()
    
    @field_validator('notes')
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from notes if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class MasterSheetConfig(BaseModel):
    """Configuration for reading the Master Google Sheet.
    
    Attributes:
        sheet_url: Full URL to the Master Google Sheet
        sheet_name: Name of the worksheet tab to read
        header_row: Row number containing column headers (1-indexed)
        data_start_row: Row number where data starts (1-indexed)
    """
    sheet_url: HttpUrl = Field(
        ...,
        description="Full URL to the Master Google Sheet"
    )
    sheet_name: str = Field(
        default="Suppliers",
        min_length=1,
        max_length=100,
        description="Name of the worksheet tab to read"
    )
    header_row: int = Field(
        default=1,
        ge=1,
        description="Row number containing column headers (1-indexed)"
    )
    data_start_row: int = Field(
        default=2,
        ge=2,
        description="Row number where data starts (1-indexed)"
    )
    
    @field_validator('sheet_name')
    @classmethod
    def validate_sheet_name(cls, v: str) -> str:
        """Strip whitespace from sheet name."""
        return v.strip()


class MasterSyncResult(BaseModel):
    """Result of master sheet sync operation.
    
    Attributes:
        suppliers_created: Number of new suppliers created
        suppliers_updated: Number of existing suppliers updated
        suppliers_deactivated: Number of suppliers marked inactive
        suppliers_skipped: Number of rows skipped due to errors
        errors: List of error messages encountered
    """
    suppliers_created: int = Field(
        default=0,
        ge=0,
        description="Number of new suppliers created"
    )
    suppliers_updated: int = Field(
        default=0,
        ge=0,
        description="Number of existing suppliers updated"
    )
    suppliers_deactivated: int = Field(
        default=0,
        ge=0,
        description="Number of suppliers marked inactive"
    )
    suppliers_skipped: int = Field(
        default=0,
        ge=0,
        description="Number of rows skipped due to errors"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of error messages encountered"
    )
    
    @property
    def total_processed(self) -> int:
        """Total number of suppliers processed (created + updated)."""
        return self.suppliers_created + self.suppliers_updated
    
    @property
    def has_errors(self) -> bool:
        """Whether any errors occurred during sync."""
        return len(self.errors) > 0

