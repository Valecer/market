"""
Ingestion Service
==================

Orchestrates the file parsing pipeline:
1. Select appropriate parser based on file type
2. Parse file to normalized rows
3. Insert items into supplier_items table
4. Log any errors to parsing_logs table
5. Return chunk data for embedding generation

Follows Single Responsibility: Only handles ingestion orchestration.
"""

from pathlib import Path
from typing import Any
from uuid import UUID

from src.db.connection import get_session
from src.db.repositories.parsing_logs_repo import ParsingLogsRepository
from src.db.repositories.supplier_items_repo import SupplierItemsRepository
from src.ingest.chunker import Chunker
from src.ingest.parser_factory import ParserFactory
from src.ingest.table_normalizer import ParseResult, ParserError
from src.schemas.domain import ChunkData, NormalizedRow
from src.utils.errors import ParsingError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class IngestionResult:
    """
    Result of an ingestion operation.

    Attributes:
        success: Whether ingestion completed successfully
        total_rows: Total rows found in file
        processed_rows: Rows successfully processed
        error_count: Number of errors encountered
        item_ids: List of created supplier_item IDs
        chunks: List of ChunkData for embedding generation
        errors: List of error details
    """

    def __init__(
        self,
        success: bool = True,
        total_rows: int = 0,
        processed_rows: int = 0,
        error_count: int = 0,
        item_ids: list[UUID] | None = None,
        chunks: list[ChunkData] | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        self.success = success
        self.total_rows = total_rows
        self.processed_rows = processed_rows
        self.error_count = error_count
        self.item_ids = item_ids or []
        self.chunks = chunks or []
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "total_rows": self.total_rows,
            "processed_rows": self.processed_rows,
            "error_count": self.error_count,
            "item_count": len(self.item_ids),
            "chunk_count": len(self.chunks),
        }


class IngestionService:
    """
    Service for orchestrating file ingestion.

    Workflow:
        1. Validate file exists and type is supported
        2. Create parser strategy based on file type
        3. Parse file to NormalizedRow objects
        4. Insert rows into supplier_items table
        5. Generate chunks for embedding
        6. Log any errors encountered

    Usage:
        service = IngestionService()
        result = await service.ingest_file(
            file_path="/path/to/file.xlsx",
            supplier_id=uuid,
            job_id=uuid,
        )

        # Check result
        if result.success:
            print(f"Processed {result.processed_rows} rows")
            for chunk in result.chunks:
                # Generate embeddings...
    """

    def __init__(
        self,
        chunker: Chunker | None = None,
    ) -> None:
        """
        Initialize ingestion service.

        Args:
            chunker: Optional custom Chunker instance
        """
        self._chunker = chunker or Chunker()
        logger.debug("IngestionService initialized")

    async def ingest_file(
        self,
        file_path: str | Path,
        supplier_id: UUID,
        job_id: UUID | None = None,
        file_type: str | None = None,
        parser_kwargs: dict[str, Any] | None = None,
    ) -> IngestionResult:
        """
        Ingest a file and create supplier items.

        Args:
            file_path: Path to file to ingest
            supplier_id: Supplier ID for created items
            job_id: Optional job ID for tracking
            file_type: Optional explicit file type (auto-detected if None)
            parser_kwargs: Optional arguments for parser

        Returns:
            IngestionResult with processing details

        Raises:
            ParsingError: If file cannot be parsed
            FileNotFoundError: If file doesn't exist
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path

        logger.info(
            "Starting file ingestion",
            file_path=str(path),
            supplier_id=str(supplier_id),
            job_id=str(job_id) if job_id else None,
        )

        # Validate file exists
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        errors: list[dict[str, Any]] = []

        try:
            # Create parser
            kwargs = parser_kwargs or {}
            if file_type:
                parser = ParserFactory.create(file_type, **kwargs)
            else:
                parser = ParserFactory.from_file_path(path, **kwargs)

            # Parse file
            logger.debug("Parsing file", parser=type(parser).__name__)
            rows = await parser.parse(path, supplier_id)

            if not rows:
                logger.warning("No rows parsed from file", file_path=str(path))
                return IngestionResult(
                    success=True,
                    total_rows=0,
                    processed_rows=0,
                )

            # Insert into database
            async with get_session() as session:
                items_repo = SupplierItemsRepository(session)
                logs_repo = ParsingLogsRepository(session)

                # Create supplier items
                item_ids = await items_repo.create_batch(
                    supplier_id=supplier_id,
                    rows=rows,
                    source_type="ml_analyzed",
                )

                # Generate chunks for embedding
                chunks = self._chunker.chunk_batch(rows, item_ids)

                # Log any errors
                if errors:
                    await logs_repo.log_batch(
                        supplier_id=supplier_id,
                        errors=errors,
                        job_id=job_id,
                    )

            logger.info(
                "File ingestion complete",
                file_path=str(path),
                total_rows=len(rows),
                items_created=len(item_ids),
                chunks_generated=len(chunks),
            )

            return IngestionResult(
                success=True,
                total_rows=len(rows),
                processed_rows=len(item_ids),
                error_count=len(errors),
                item_ids=item_ids,
                chunks=chunks,
                errors=errors,
            )

        except ParsingError as e:
            logger.error(
                "Parsing error during ingestion",
                file_path=str(path),
                error=e.message,
            )
            # Log to database
            try:
                async with get_session() as session:
                    logs_repo = ParsingLogsRepository(session)
                    await logs_repo.log_error(
                        supplier_id=supplier_id,
                        error_type="parsing",
                        message=e.message,
                        severity="error",
                        job_id=job_id,
                        context=e.details,
                    )
            except Exception as log_error:
                logger.warning("Failed to log error", error=str(log_error))

            return IngestionResult(
                success=False,
                error_count=1,
                errors=[{"type": "parsing", "message": e.message, "details": e.details}],
            )

        except Exception as e:
            logger.exception(
                "Unexpected error during ingestion",
                file_path=str(path),
                error=str(e),
            )
            return IngestionResult(
                success=False,
                error_count=1,
                errors=[{"type": "unknown", "message": str(e)}],
            )

    async def parse_only(
        self,
        file_path: str | Path,
        file_type: str | None = None,
        parser_kwargs: dict[str, Any] | None = None,
    ) -> list[NormalizedRow]:
        """
        Parse a file without inserting into database.

        Useful for previewing file contents or testing parsers.

        Args:
            file_path: Path to file
            file_type: Optional explicit file type
            parser_kwargs: Optional arguments for parser

        Returns:
            List of NormalizedRow objects
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        kwargs = parser_kwargs or {}
        if file_type:
            parser = ParserFactory.create(file_type, **kwargs)
        else:
            parser = ParserFactory.from_file_path(path, **kwargs)

        return await parser.parse(path)

    async def validate_file(
        self,
        file_path: str | Path,
        file_type: str | None = None,
    ) -> bool:
        """
        Validate that a file can be parsed.

        Args:
            file_path: Path to file
            file_type: Optional explicit file type

        Returns:
            True if file can be parsed
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path

        if not path.exists():
            return False

        try:
            if file_type:
                parser = ParserFactory.create(file_type)
            else:
                parser = ParserFactory.from_file_path(path)
            return await parser.validate_file(path)
        except Exception:
            return False


# Convenience function for simple ingestion
async def ingest_file(
    file_path: str | Path,
    supplier_id: UUID,
    job_id: UUID | None = None,
    **kwargs,
) -> IngestionResult:
    """
    Convenience function to ingest a file.

    Args:
        file_path: Path to file
        supplier_id: Supplier ID
        job_id: Optional job ID
        **kwargs: Additional arguments for parser

    Returns:
        IngestionResult
    """
    service = IngestionService()
    return await service.ingest_file(
        file_path=file_path,
        supplier_id=supplier_id,
        job_id=job_id,
        parser_kwargs=kwargs,
    )

