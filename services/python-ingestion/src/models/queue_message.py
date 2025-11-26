"""Pydantic models for queue messages."""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Self
from typing import Dict, Any, Literal
from datetime import datetime, timezone


class ParseTaskMessage(BaseModel):
    """Message schema for enqueuing data parsing tasks in Redis queue.
    
    This model matches the JSON schema defined in contracts/queue-message.schema.json
    and is used to validate task messages before enqueuing them to Redis.
    """
    
    task_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique identifier for this parse task"
    )
    parser_type: Literal["google_sheets", "csv", "excel", "stub"] = Field(
        ...,
        description="Type of parser to use for data extraction"
    )
    supplier_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the supplier providing the data"
    )
    source_config: Dict[str, Any] = Field(
        ...,
        description="Parser-specific configuration (schema varies by parser_type)"
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Current retry attempt number"
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of retry attempts before moving to DLQ"
    )
    enqueued_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="ISO 8601 timestamp when task was enqueued"
    )
    priority: Literal["low", "normal", "high"] = Field(
        default="normal",
        description="Task priority for queue processing"
    )
    
    @field_validator('task_id')
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        """Validate task_id format."""
        if not v.strip():
            raise ValueError('task_id cannot be empty or whitespace')
        return v.strip()
    
    @field_validator('supplier_name')
    @classmethod
    def validate_supplier_name(cls, v: str) -> str:
        """Validate supplier_name format."""
        if not v.strip():
            raise ValueError('supplier_name cannot be empty or whitespace')
        return v.strip()
    
    @model_validator(mode='after')
    def validate_source_config_not_empty(self) -> Self:
        """Validate source_config is not empty (except for test parsers).
        
        For most parsers, config should not be empty. However, the stub parser
        accepts empty config for testing purposes.
        """
        # Allow empty config for stub parser (used for testing)
        if self.parser_type == 'stub':
            return self
        
        # For other parsers, config should not be empty
        if not self.source_config:
            raise ValueError('source_config cannot be empty (except for stub parser)')
        return self
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "task-2025-11-23-001",
                "parser_type": "google_sheets",
                "supplier_name": "Acme Wholesale",
                "source_config": {
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
                },
                "retry_count": 0,
                "max_retries": 3,
                "enqueued_at": "2025-11-23T10:30:00Z",
                "priority": "normal"
            }
        }
    }

