"""
Parsing Logs Repository
========================

Data access layer for the parsing_logs table.
Records errors and events during file parsing.

Follows Repository Pattern: Abstracts database operations.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.logger import get_logger

logger = get_logger(__name__)


# Error severity levels
ErrorSeverity = Literal["debug", "info", "warning", "error", "critical"]

# Error types
ErrorType = Literal[
    "validation",
    "parsing",
    "embedding",
    "matching",
    "database",
    "network",
    "unknown",
]


class ParsingLogsRepository:
    """
    Repository for parsing_logs table operations.

    The parsing_logs table stores structured error information
    for debugging and monitoring parsing operations.

    Table Schema (actual):
        id: UUID (PK)
        task_id: varchar(255) (job reference as string)
        supplier_id: UUID (FK → suppliers)
        error_type: varchar(100)
        error_message: text
        row_number: int | None
        row_data: JSONB (context data)
        created_at: datetime
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository with async session.

        Args:
            session: SQLAlchemy async session
        """
        self._session = session

    async def log_error(
        self,
        supplier_id: UUID,
        error_type: ErrorType,
        message: str,
        severity: ErrorSeverity = "error",
        job_id: UUID | None = None,
        context: dict[str, Any] | None = None,
    ) -> UUID:
        """
        Log a parsing error to the database.

        Args:
            supplier_id: Reference to supplier
            error_type: Category of error
            message: Human-readable error message
            severity: Error severity level
            job_id: Optional reference to job
            context: Additional context (row data, file info, etc.)

        Returns:
            Created log entry UUID
        """
        import json

        query = text("""
            INSERT INTO parsing_logs (
                task_id, supplier_id, error_type,
                error_message, row_data, created_at
            ) VALUES (
                :task_id, :supplier_id, :error_type,
                :error_message, CAST(:row_data AS jsonb), NOW()
            )
            RETURNING id
        """)

        result = await self._session.execute(
            query,
            {
                "task_id": str(job_id) if job_id else f"ml-{supplier_id}",
                "supplier_id": str(supplier_id),
                "error_type": error_type,
                "error_message": f"[{severity}] {message}",
                "row_data": json.dumps(context) if context else None,
            },
        )

        log_id = result.scalar_one()
        logger.debug(
            "Parsing error logged",
            log_id=str(log_id),
            error_type=error_type,
            severity=severity,
        )
        return log_id

    async def log_batch(
        self,
        supplier_id: UUID,
        errors: list[dict[str, Any]],
        job_id: UUID | None = None,
    ) -> list[UUID]:
        """
        Log multiple errors in a batch.

        Args:
            supplier_id: Reference to supplier
            errors: List of error dicts with keys:
                - error_type: ErrorType
                - message: str
                - severity: ErrorSeverity (optional, default 'error')
                - context: dict (optional)
            job_id: Optional reference to job

        Returns:
            List of created log entry UUIDs
        """
        if not errors:
            return []

        import json

        task_id = str(job_id) if job_id else f"ml-{supplier_id}"
        values = []
        for err in errors:
            severity = err.get("severity", "error")
            message = err.get("message", "Unknown error")
            values.append({
                "task_id": task_id,
                "supplier_id": str(supplier_id),
                "error_type": err.get("error_type", "unknown"),
                "error_message": f"[{severity}] {message}",
                "row_data": json.dumps(err.get("context")) if err.get("context") else None,
            })

        query = text("""
            INSERT INTO parsing_logs (
                task_id, supplier_id, error_type,
                error_message, row_data, created_at
            )
            SELECT
                v->>'task_id',
                (v->>'supplier_id')::uuid,
                v->>'error_type',
                v->>'error_message',
                (v->>'row_data')::jsonb,
                NOW()
            FROM jsonb_array_elements(CAST(:values AS jsonb)) AS v
            RETURNING id
        """)

        result = await self._session.execute(query, {"values": json.dumps(values)})
        ids = [row[0] for row in result.fetchall()]

        logger.info("Batch errors logged", count=len(ids), supplier_id=str(supplier_id))
        return ids

    async def log_low_confidence_match(
        self,
        supplier_id: UUID,
        item_id: UUID,
        confidence: float,
        candidates: list[dict[str, Any]],
        job_id: UUID | None = None,
    ) -> UUID:
        """
        Log a low-confidence match result (confidence < 70%).

        These are rejected matches that need investigation.

        Args:
            supplier_id: Reference to supplier
            item_id: Supplier item that failed to match
            confidence: Highest confidence score
            candidates: Top match candidates with scores
            job_id: Optional reference to job

        Returns:
            Created log entry UUID
        """
        context = {
            "item_id": str(item_id),
            "confidence": confidence,
            "candidates": candidates,
            "action": "rejected",
        }

        return await self.log_error(
            supplier_id=supplier_id,
            error_type="matching",
            message=f"Low confidence match ({confidence:.2%}), no action taken",
            severity="info",
            job_id=job_id,
            context=context,
        )

    async def get_recent_errors(
        self,
        supplier_id: UUID | None = None,
        limit: int = 100,
        severity_filter: list[ErrorSeverity] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get recent parsing errors.

        Args:
            supplier_id: Optional filter by supplier
            limit: Maximum entries to return
            severity_filter: Optional filter by severity levels

        Returns:
            List of log entry dicts
        """
        params: dict[str, Any] = {"limit": limit}
        conditions = ["1=1"]

        if supplier_id:
            conditions.append("supplier_id = :supplier_id")
            params["supplier_id"] = str(supplier_id)

        if severity_filter:
            # Use ANY for array comparison
            conditions.append("severity = ANY(:severities)")
            params["severities"] = severity_filter

        where_clause = " AND ".join(conditions)

        query = text(f"""
            SELECT id, supplier_id, job_id, error_type, severity,
                   message, context, created_at
            FROM parsing_logs
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit
        """)

        result = await self._session.execute(query, params)
        return [dict(row) for row in result.mappings().fetchall()]

    async def get_errors_by_job(
        self,
        job_id: UUID,
    ) -> list[dict[str, Any]]:
        """
        Get all errors for a specific job.

        Args:
            job_id: Job UUID

        Returns:
            List of log entry dicts
        """
        query = text("""
            SELECT id, supplier_id, error_type, severity,
                   message, context, created_at
            FROM parsing_logs
            WHERE job_id = :job_id
            ORDER BY created_at ASC
        """)

        result = await self._session.execute(query, {"job_id": str(job_id)})
        return [dict(row) for row in result.mappings().fetchall()]

    async def count_by_type(
        self,
        supplier_id: UUID | None = None,
        since: datetime | None = None,
    ) -> dict[str, int]:
        """
        Count errors by type.

        Args:
            supplier_id: Optional filter by supplier
            since: Optional filter by date

        Returns:
            Dict mapping error_type to count
        """
        params: dict[str, Any] = {}
        conditions = ["1=1"]

        if supplier_id:
            conditions.append("supplier_id = :supplier_id")
            params["supplier_id"] = str(supplier_id)

        if since:
            conditions.append("created_at >= :since")
            params["since"] = since

        where_clause = " AND ".join(conditions)

        query = text(f"""
            SELECT error_type, COUNT(*) as count
            FROM parsing_logs
            WHERE {where_clause}
            GROUP BY error_type
        """)

        result = await self._session.execute(query, params)
        return {row["error_type"]: row["count"] for row in result.mappings().fetchall()}

    async def delete_old_logs(
        self,
        days: int = 30,
    ) -> int:
        """
        Delete logs older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of deleted rows
        """
        query = text("""
            DELETE FROM parsing_logs
            WHERE created_at < NOW() - INTERVAL ':days days'
        """)

        result = await self._session.execute(query, {"days": days})
        deleted = result.rowcount

        logger.info("Old logs deleted", days=days, deleted_count=deleted)
        return deleted

