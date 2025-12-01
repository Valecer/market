"""Master Sheet Ingestor service for parsing and syncing supplier configurations.

This module implements the MasterSheetIngestor class that:
1. Reads supplier configurations from the Master Google Sheet
2. Syncs supplier records to the database (create/update/deactivate)
3. Supports dynamic column mapping with fuzzy matching
"""
from typing import List, Dict, Any, Optional, Set
from difflib import get_close_matches
import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError as PydanticValidationError

import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound, APIError
from urllib.parse import urlparse

from src.models.master_sheet_config import (
    SourceFormat,
    SupplierConfigRow,
    MasterSheetConfig,
    MasterSyncResult,
)
from src.errors.exceptions import ParserError, ValidationError
from src.config import settings
from src.db.base import async_session_maker
from src.db.models import Supplier

logger = structlog.get_logger(__name__)


class MasterSheetIngestor:
    """Ingests supplier configuration from Master Google Sheet.
    
    This class reads the Master Google Sheet containing supplier configurations,
    parses each row into SupplierConfigRow models, and syncs the data to the
    database using upsert logic.
    
    Features:
        - Service account authentication via gspread
        - Dynamic column mapping with fuzzy matching
        - Manual column mapping override support
        - Atomic database synchronization
        - Soft-delete for removed suppliers (deactivation)
    """
    
    # Column name mappings for fuzzy matching
    COLUMN_MAPPING = {
        'supplier_name': ['supplier name', 'name', 'supplier', 'company', 'vendor'],
        'source_url': ['source url', 'url', 'source', 'link', 'sheet url', 'price list'],
        'format': ['format', 'type', 'source type', 'source_type', 'file type'],
        'active': ['active', 'is_active', 'enabled', 'status'],
        'notes': ['notes', 'note', 'comments', 'description', 'memo'],
    }
    
    def __init__(self, credentials_path: Optional[str] = None):
        """Initialize Master Sheet Ingestor with Google authentication.
        
        Args:
            credentials_path: Path to service account JSON credentials file.
                            If None, uses settings.google_credentials_path.
        
        Raises:
            ParserError: If authentication fails or credentials are invalid
        """
        self.credentials_path = credentials_path or settings.google_credentials_path
        self._client: Optional[gspread.Client] = None
        
        try:
            self._client = gspread.service_account(filename=self.credentials_path)
            logger.info(
                "master_sheet_ingestor_initialized",
                credentials_path=self.credentials_path
            )
        except FileNotFoundError as e:
            raise ParserError(
                f"Google credentials file not found: {self.credentials_path}"
            ) from e
        except Exception as e:
            raise ParserError(
                f"Failed to authenticate with Google Sheets API: {e}"
            ) from e
    
    async def ingest(
        self,
        master_sheet_url: str,
        sheet_name: str = "Suppliers",
        header_row: int = 1,
        data_start_row: int = 2,
    ) -> List[SupplierConfigRow]:
        """Parse Master Sheet and return supplier configurations.
        
        Args:
            master_sheet_url: Full URL to the Master Google Sheet
            sheet_name: Name of the worksheet tab to read
            header_row: Row number containing column headers (1-indexed)
            data_start_row: Row number where data starts (1-indexed)
        
        Returns:
            List of validated SupplierConfigRow objects
        
        Raises:
            ParserError: If parsing fails due to source access issues
            ValidationError: If required columns cannot be mapped
        """
        log = logger.bind(
            sheet_url=master_sheet_url,
            sheet_name=sheet_name,
        )
        log.info("master_sheet_ingest_started")
        
        try:
            # Open spreadsheet by URL
            spreadsheet = self._open_spreadsheet(master_sheet_url, log)
            
            # Get worksheet by name
            worksheet = self._get_worksheet(spreadsheet, sheet_name, log)
            
            # Read header row
            header_row_data = worksheet.row_values(header_row)
            log.debug("header_row_read", headers=header_row_data)
            
            # Perform column mapping
            column_map = self._map_columns(header_row_data, log)
            
            # Read all data rows
            all_values = worksheet.get_all_values()
            data_rows = all_values[data_start_row - 1:]  # Convert to 0-indexed
            
            log.info(
                "data_rows_read",
                total_rows=len(data_rows),
                header_row=header_row,
                data_start_row=data_start_row,
            )
            
            # Parse rows into SupplierConfigRow objects
            configs: List[SupplierConfigRow] = []
            seen_names: Set[str] = set()
            
            for row_idx, row_data in enumerate(data_rows, start=data_start_row):
                try:
                    config = self._parse_row(
                        row_data=row_data,
                        row_number=row_idx,
                        headers=header_row_data,
                        column_map=column_map,
                        log=log,
                    )
                    
                    # Check for duplicate supplier names
                    normalized_name = config.supplier_name.lower()
                    if normalized_name in seen_names:
                        log.warning(
                            "duplicate_supplier_name",
                            row_number=row_idx,
                            supplier_name=config.supplier_name,
                        )
                        continue
                    
                    seen_names.add(normalized_name)
                    configs.append(config)
                    
                except (ValidationError, PydanticValidationError) as e:
                    log.warning(
                        "row_validation_failed",
                        row_number=row_idx,
                        error=str(e),
                        row_data=row_data,
                    )
                    continue
            
            log.info(
                "master_sheet_ingest_completed",
                total_rows=len(data_rows),
                valid_configs=len(configs),
                skipped_rows=len(data_rows) - len(configs),
            )
            
            return configs
            
        except (SpreadsheetNotFound, WorksheetNotFound) as e:
            raise ParserError(f"Sheet or worksheet not found: {e}") from e
        except APIError as e:
            raise ParserError(f"Google Sheets API error: {e}") from e
        except Exception as e:
            raise ParserError(f"Unexpected error during master sheet parsing: {e}") from e
    
    async def sync_suppliers(
        self,
        configs: List[SupplierConfigRow],
        session: Optional[AsyncSession] = None,
    ) -> MasterSyncResult:
        """Sync supplier configurations to database.
        
        Performs upsert logic:
        - Create new suppliers not in database
        - Update existing suppliers when config changes
        - Deactivate suppliers removed from Master Sheet
        
        Args:
            configs: List of supplier configurations from Master Sheet
            session: Optional database session (creates one if not provided)
        
        Returns:
            MasterSyncResult with counts and any errors
        """
        result = MasterSyncResult()
        log = logger.bind(configs_count=len(configs))
        log.info("sync_suppliers_started")
        
        # Track supplier names from Master Sheet (normalized)
        master_sheet_names: Set[str] = {
            config.supplier_name.lower() for config in configs
        }
        
        # Create session if not provided
        if session is None:
            async with async_session_maker() as session:
                async with session.begin():
                    result = await self._do_sync(
                        session=session,
                        configs=configs,
                        master_sheet_names=master_sheet_names,
                        result=result,
                        log=log,
                    )
                    await session.commit()
        else:
            result = await self._do_sync(
                session=session,
                configs=configs,
                master_sheet_names=master_sheet_names,
                result=result,
                log=log,
            )
        
        log.info(
            "sync_suppliers_completed",
            created=result.suppliers_created,
            updated=result.suppliers_updated,
            deactivated=result.suppliers_deactivated,
            skipped=result.suppliers_skipped,
            errors=len(result.errors),
        )
        
        return result
    
    async def _do_sync(
        self,
        session: AsyncSession,
        configs: List[SupplierConfigRow],
        master_sheet_names: Set[str],
        result: MasterSyncResult,
        log: Any,
    ) -> MasterSyncResult:
        """Internal sync implementation.
        
        Args:
            session: Database session
            configs: Supplier configurations
            master_sheet_names: Set of normalized supplier names from Master Sheet
            result: Result object to update
            log: Logger instance
        
        Returns:
            Updated MasterSyncResult
        """
        # Get existing suppliers
        existing_query = select(Supplier)
        existing_result = await session.execute(existing_query)
        existing_suppliers = {
            s.name.lower(): s for s in existing_result.scalars().all()
        }
        
        log.debug("existing_suppliers_loaded", count=len(existing_suppliers))
        
        # Process each config
        for config in configs:
            try:
                normalized_name = config.supplier_name.lower()
                
                if normalized_name in existing_suppliers:
                    # Update existing supplier
                    supplier = existing_suppliers[normalized_name]
                    updated = self._update_supplier(supplier, config)
                    
                    if updated:
                        session.add(supplier)
                        result.suppliers_updated += 1
                        log.debug(
                            "supplier_updated",
                            supplier_name=config.supplier_name,
                            supplier_id=str(supplier.id),
                        )
                else:
                    # Create new supplier
                    supplier = self._create_supplier(config)
                    session.add(supplier)
                    result.suppliers_created += 1
                    log.debug(
                        "supplier_created",
                        supplier_name=config.supplier_name,
                    )
                    
            except Exception as e:
                error_msg = f"Error processing supplier '{config.supplier_name}': {e}"
                result.errors.append(error_msg)
                result.suppliers_skipped += 1
                log.warning(
                    "supplier_sync_error",
                    supplier_name=config.supplier_name,
                    error=str(e),
                )
        
        # Deactivate suppliers not in Master Sheet
        for normalized_name, supplier in existing_suppliers.items():
            if normalized_name not in master_sheet_names:
                # Check if already inactive (via meta.is_active)
                meta = supplier.meta or {}
                if meta.get("is_active", True):
                    meta["is_active"] = False
                    supplier.meta = meta
                    session.add(supplier)
                    result.suppliers_deactivated += 1
                    log.debug(
                        "supplier_deactivated",
                        supplier_name=supplier.name,
                        supplier_id=str(supplier.id),
                    )
        
        return result
    
    def _create_supplier(self, config: SupplierConfigRow) -> Supplier:
        """Create a new Supplier from config.
        
        Args:
            config: Validated supplier configuration
        
        Returns:
            New Supplier model instance
        """
        # Map SourceFormat to database source_type
        source_type_map = {
            SourceFormat.GOOGLE_SHEETS: "google_sheets",
            SourceFormat.CSV: "csv",
            SourceFormat.EXCEL: "excel",
            SourceFormat.PDF: "csv",  # PDF not supported, fallback to csv
        }
        
        return Supplier(
            name=config.supplier_name,
            source_type=source_type_map.get(config.format, "csv"),
            meta={
                "source_url": str(config.source_url),
                "is_active": config.is_active,
                "notes": config.notes,
            },
        )
    
    def _update_supplier(
        self,
        supplier: Supplier,
        config: SupplierConfigRow,
    ) -> bool:
        """Update existing Supplier from config.
        
        Args:
            supplier: Existing Supplier model
            config: New configuration
        
        Returns:
            True if supplier was updated, False if no changes
        """
        # Map SourceFormat to database source_type
        source_type_map = {
            SourceFormat.GOOGLE_SHEETS: "google_sheets",
            SourceFormat.CSV: "csv",
            SourceFormat.EXCEL: "excel",
            SourceFormat.PDF: "csv",
        }
        
        new_source_type = source_type_map.get(config.format, "csv")
        new_meta = {
            "source_url": str(config.source_url),
            "is_active": config.is_active,
            "notes": config.notes,
        }
        
        # Check if anything changed
        current_meta = supplier.meta or {}
        if (
            supplier.source_type == new_source_type
            and current_meta.get("source_url") == new_meta["source_url"]
            and current_meta.get("is_active") == new_meta["is_active"]
            and current_meta.get("notes") == new_meta["notes"]
        ):
            return False
        
        supplier.source_type = new_source_type
        supplier.meta = new_meta
        return True
    
    def _open_spreadsheet(
        self,
        sheet_url: str,
        log: Any,
    ) -> gspread.Spreadsheet:
        """Open spreadsheet by URL.
        
        Args:
            sheet_url: Google Sheets URL
            log: Logger instance
        
        Returns:
            gspread.Spreadsheet object
        
        Raises:
            ParserError: If spreadsheet cannot be opened
        """
        try:
            parsed_url = urlparse(sheet_url)
            path_parts = parsed_url.path.split('/')
            
            if 'd' in path_parts:
                spreadsheet_id = path_parts[path_parts.index('d') + 1]
            else:
                raise ParserError(f"Invalid Google Sheets URL format: {sheet_url}")
            
            spreadsheet = self._client.open_by_key(spreadsheet_id)
            log.debug(
                "spreadsheet_opened",
                spreadsheet_id=spreadsheet_id,
                title=spreadsheet.title,
            )
            return spreadsheet
            
        except Exception as e:
            raise ParserError(f"Failed to open spreadsheet: {e}") from e
    
    def _get_worksheet(
        self,
        spreadsheet: gspread.Spreadsheet,
        sheet_name: str,
        log: Any,
    ) -> gspread.Worksheet:
        """Get worksheet by name.
        
        Args:
            spreadsheet: gspread.Spreadsheet object
            sheet_name: Name of worksheet tab
            log: Logger instance
        
        Returns:
            gspread.Worksheet object
        
        Raises:
            ParserError: If worksheet not found
        """
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            log.debug(
                "worksheet_found",
                sheet_name=sheet_name,
                row_count=worksheet.row_count,
            )
            return worksheet
        except WorksheetNotFound:
            available = [ws.title for ws in spreadsheet.worksheets()]
            raise ParserError(
                f"Worksheet '{sheet_name}' not found. Available: {available}"
            )
    
    def _map_columns(
        self,
        headers: List[str],
        log: Any,
    ) -> Dict[str, int]:
        """Map sheet column headers to standard field names.
        
        Args:
            headers: List of header strings from sheet
            log: Logger instance
        
        Returns:
            Dictionary mapping field names to column indices (0-indexed)
        
        Raises:
            ValidationError: If required columns cannot be mapped
        """
        column_map: Dict[str, int] = {}
        normalized_headers = [h.strip().lower() if h else "" for h in headers]
        
        for field_name, possible_names in self.COLUMN_MAPPING.items():
            found = False
            
            # Try exact match first
            for possible_name in possible_names:
                try:
                    col_idx = normalized_headers.index(possible_name.lower())
                    column_map[field_name] = col_idx
                    found = True
                    log.debug(
                        "column_mapped",
                        field=field_name,
                        header=headers[col_idx],
                        index=col_idx,
                    )
                    break
                except ValueError:
                    continue
            
            # Try fuzzy matching if exact match failed
            if not found:
                matches = get_close_matches(
                    possible_names[0],
                    normalized_headers,
                    n=1,
                    cutoff=0.6,
                )
                if matches:
                    col_idx = normalized_headers.index(matches[0])
                    column_map[field_name] = col_idx
                    found = True
                    log.debug(
                        "column_fuzzy_mapped",
                        field=field_name,
                        header=headers[col_idx],
                        index=col_idx,
                    )
        
        # Validate required fields are mapped
        required_fields = {'supplier_name', 'source_url', 'format'}
        missing_fields = required_fields - set(column_map.keys())
        if missing_fields:
            raise ValidationError(
                f"Required columns not found: {missing_fields}. "
                f"Available headers: {headers}."
            )
        
        log.info("column_mapping_complete", mapping=column_map)
        return column_map
    
    def _parse_row(
        self,
        row_data: List[str],
        row_number: int,
        headers: List[str],
        column_map: Dict[str, int],
        log: Any,
    ) -> SupplierConfigRow:
        """Parse a single row into SupplierConfigRow.
        
        Args:
            row_data: List of cell values
            row_number: Row number (1-indexed) for error reporting
            headers: List of header strings
            column_map: Mapping of field names to column indices
            log: Logger instance
        
        Returns:
            Validated SupplierConfigRow object
        
        Raises:
            ValidationError: If row data is invalid
        """
        # Extract required fields
        supplier_name = self._get_cell_value(
            row_data, column_map['supplier_name'], row_number, 'supplier_name'
        )
        source_url = self._get_cell_value(
            row_data, column_map['source_url'], row_number, 'source_url'
        )
        format_str = self._get_cell_value(
            row_data, column_map['format'], row_number, 'format'
        )
        
        # Parse format
        format_value = self._parse_format(format_str, row_number)
        
        # Extract optional fields
        is_active = True
        if 'active' in column_map:
            active_str = self._get_cell_value_optional(
                row_data, column_map['active']
            )
            if active_str:
                is_active = active_str.lower() in ('true', 'yes', '1', 'active')
        
        notes = None
        if 'notes' in column_map:
            notes = self._get_cell_value_optional(
                row_data, column_map['notes']
            )
        
        # Create and validate
        return SupplierConfigRow(
            supplier_name=supplier_name,
            source_url=source_url,
            format=format_value,
            is_active=is_active,
            notes=notes,
        )
    
    def _get_cell_value(
        self,
        row_data: List[str],
        col_idx: int,
        row_number: int,
        field_name: str,
    ) -> str:
        """Get required cell value with validation.
        
        Args:
            row_data: List of cell values
            col_idx: Column index (0-indexed)
            row_number: Row number for error messages
            field_name: Field name for error messages
        
        Returns:
            Cell value as string
        
        Raises:
            ValidationError: If value is empty or missing
        """
        if col_idx >= len(row_data):
            raise ValidationError(
                f"Row {row_number}: Column {col_idx} out of bounds"
            )
        
        value = row_data[col_idx].strip() if row_data[col_idx] else ""
        if not value:
            raise ValidationError(
                f"Row {row_number}: Required field '{field_name}' is empty"
            )
        
        return value
    
    def _get_cell_value_optional(
        self,
        row_data: List[str],
        col_idx: int,
    ) -> Optional[str]:
        """Get optional cell value.
        
        Args:
            row_data: List of cell values
            col_idx: Column index (0-indexed)
        
        Returns:
            Cell value as string or None if empty
        """
        if col_idx >= len(row_data):
            return None
        
        value = row_data[col_idx].strip() if row_data[col_idx] else ""
        return value if value else None
    
    def _parse_format(self, format_str: str, row_number: int) -> SourceFormat:
        """Parse format string to SourceFormat enum.
        
        Args:
            format_str: Format string from sheet
            row_number: Row number for error messages
        
        Returns:
            SourceFormat enum value
        
        Raises:
            ValidationError: If format is not recognized
        """
        format_map = {
            'google_sheets': SourceFormat.GOOGLE_SHEETS,
            'googlesheets': SourceFormat.GOOGLE_SHEETS,
            'google sheets': SourceFormat.GOOGLE_SHEETS,
            'gsheet': SourceFormat.GOOGLE_SHEETS,
            'csv': SourceFormat.CSV,
            'excel': SourceFormat.EXCEL,
            'xlsx': SourceFormat.EXCEL,
            'xls': SourceFormat.EXCEL,
            'pdf': SourceFormat.PDF,
        }
        
        normalized = format_str.strip().lower()
        if normalized not in format_map:
            raise ValidationError(
                f"Row {row_number}: Invalid format '{format_str}'. "
                f"Valid formats: {list(format_map.keys())}"
            )
        
        return format_map[normalized]

