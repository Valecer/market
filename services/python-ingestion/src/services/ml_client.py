"""
ML-Analyze Service Client

HTTP client for inter-service communication between python-ingestion and ml-analyze.
Uses httpx for async HTTP requests with retry logic and health checks.

@see /specs/008-ml-ingestion-integration/plan.md
"""

import httpx
import structlog
from typing import Optional
from uuid import UUID
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.config import settings
from src.models.ml_models import (
    MLAnalyzeRequest,
    MLAnalyzeResponse,
    MLJobStatus,
    FileType,
)

logger = structlog.get_logger(__name__)


class MLClientError(Exception):
    """Base exception for ML client errors."""

    pass


class MLServiceUnavailableError(MLClientError):
    """Raised when ML service is unavailable after retries."""

    pass


class MLJobError(MLClientError):
    """Raised when ML job fails."""

    pass


class MLClient:
    """
    Async HTTP client for ml-analyze service communication.

    Features:
    - Health check with retry logic
    - Trigger file analysis
    - Poll job status
    - Exponential backoff on errors

    Usage:
        async with MLClient() as client:
            if await client.check_health():
                response = await client.trigger_analysis(request)
                status = await client.get_job_status(response.job_id)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """
        Initialize ML client.

        Args:
            base_url: ML-Analyze service URL (defaults to config)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for retryable errors
        """
        self.base_url = (base_url or settings.ml_analyze_url).rstrip("/")
        self.timeout = httpx.Timeout(
            connect=5.0,
            read=timeout,
            write=5.0,
            pool=5.0,
        )
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self._log = logger.bind(service="ml-analyze", base_url=self.base_url)

    async def __aenter__(self) -> "MLClient":
        """Context manager entry - create async client."""
        transport = httpx.AsyncHTTPTransport(retries=1)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=transport,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "python-ingestion/1.0",
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close async client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, raising if not initialized."""
        if self._client is None:
            raise MLClientError(
                "MLClient not initialized. Use 'async with MLClient() as client:'"
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ConnectTimeout)),
        reraise=True,
    )
    async def check_health(self) -> bool:
        """
        Check if ML-Analyze service is healthy.

        Returns:
            True if service is healthy, False otherwise

        Note:
            Retries up to 3 times with exponential backoff on connection errors.
        """
        try:
            response = await self.client.get("/health")

            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                is_healthy = status == "healthy"

                self._log.info(
                    "health_check_completed",
                    status=status,
                    healthy=is_healthy,
                    details=data,
                )
                return is_healthy

            self._log.warning(
                "health_check_failed",
                status_code=response.status_code,
                body=response.text[:200],
            )
            return False

        except httpx.TimeoutException as e:
            self._log.error("health_check_timeout", error=str(e))
            return False
        except httpx.HTTPError as e:
            self._log.error("health_check_error", error=str(e))
            return False

    async def trigger_analysis(
        self,
        file_url: str,
        supplier_id: UUID,
        file_type: FileType,
        metadata: Optional[dict] = None,
    ) -> MLAnalyzeResponse:
        """
        Trigger ML analysis for a file.

        Args:
            file_url: Local path on shared volume (e.g., /shared/uploads/file.xlsx)
            supplier_id: UUID of supplier owning the file
            file_type: Type of file (pdf, excel, csv)
            metadata: Optional additional metadata

        Returns:
            MLAnalyzeResponse with job_id for status tracking

        Raises:
            MLServiceUnavailableError: If service is unreachable
            MLClientError: On other errors
        """
        request = MLAnalyzeRequest(
            file_url=file_url,
            supplier_id=supplier_id,
            file_type=file_type,
            metadata=metadata,
        )

        self._log.info(
            "trigger_analysis_started",
            file_url=file_url,
            supplier_id=str(supplier_id),
            file_type=file_type,
        )

        try:
            response = await self.client.post(
                "/analyze/file",
                json=request.model_dump(mode="json"),
            )

            if response.status_code in (200, 201, 202):
                data = response.json()
                result = MLAnalyzeResponse(**data)

                self._log.info(
                    "trigger_analysis_success",
                    job_id=str(result.job_id),
                    status=result.status,
                )
                return result

            # Handle error responses
            if response.status_code == 400:
                error_msg = response.json().get("detail", "Bad request")
                raise MLClientError(f"Invalid request: {error_msg}")

            if response.status_code in (502, 503, 504):
                raise MLServiceUnavailableError(
                    f"ML service unavailable (HTTP {response.status_code})"
                )

            raise MLClientError(
                f"Unexpected response: HTTP {response.status_code} - {response.text[:200]}"
            )

        except httpx.ConnectError as e:
            self._log.error("trigger_analysis_connection_error", error=str(e))
            raise MLServiceUnavailableError(
                f"Failed to connect to ML service: {e}"
            ) from e
        except httpx.TimeoutException as e:
            self._log.error("trigger_analysis_timeout", error=str(e))
            raise MLServiceUnavailableError(f"ML service timeout: {e}") from e

    async def get_job_status(self, job_id: UUID) -> MLJobStatus:
        """
        Get status of an ML analysis job.

        Args:
            job_id: UUID of the job to check

        Returns:
            MLJobStatus with current job state and progress

        Raises:
            MLServiceUnavailableError: If service is unreachable
            MLClientError: On other errors
        """
        self._log.debug("get_job_status", job_id=str(job_id))

        try:
            response = await self.client.get(f"/analyze/status/{job_id}")

            if response.status_code == 200:
                data = response.json()
                status = MLJobStatus(**data)

                self._log.debug(
                    "job_status_retrieved",
                    job_id=str(job_id),
                    status=status.status,
                    progress=status.progress_percentage,
                )
                return status

            if response.status_code == 404:
                raise MLClientError(f"Job not found: {job_id}")

            if response.status_code in (502, 503, 504):
                raise MLServiceUnavailableError(
                    f"ML service unavailable (HTTP {response.status_code})"
                )

            raise MLClientError(
                f"Unexpected response: HTTP {response.status_code} - {response.text[:200]}"
            )

        except httpx.ConnectError as e:
            self._log.error("get_job_status_connection_error", error=str(e))
            raise MLServiceUnavailableError(
                f"Failed to connect to ML service: {e}"
            ) from e
        except httpx.TimeoutException as e:
            self._log.error("get_job_status_timeout", error=str(e))
            raise MLServiceUnavailableError(f"ML service timeout: {e}") from e

    async def wait_for_completion(
        self,
        job_id: UUID,
        poll_interval: Optional[int] = None,
        max_wait_seconds: int = 1800,
    ) -> MLJobStatus:
        """
        Poll job status until completion or failure.

        Args:
            job_id: UUID of the job to monitor
            poll_interval: Seconds between polls (defaults to config)
            max_wait_seconds: Maximum time to wait (default 30 minutes)

        Returns:
            Final MLJobStatus (completed or failed)

        Raises:
            MLJobError: If job fails
            MLClientError: On timeout or other errors
        """
        import asyncio

        poll_interval = poll_interval or settings.ml_poll_interval_seconds
        elapsed = 0

        self._log.info(
            "waiting_for_job_completion",
            job_id=str(job_id),
            poll_interval=poll_interval,
            max_wait=max_wait_seconds,
        )

        while elapsed < max_wait_seconds:
            status = await self.get_job_status(job_id)

            if status.status == "completed":
                self._log.info(
                    "job_completed",
                    job_id=str(job_id),
                    items_processed=status.items_processed,
                    items_total=status.items_total,
                    elapsed_seconds=elapsed,
                )
                return status

            if status.status == "failed":
                self._log.error(
                    "job_failed",
                    job_id=str(job_id),
                    errors=status.errors,
                    elapsed_seconds=elapsed,
                )
                raise MLJobError(
                    f"ML job {job_id} failed: {'; '.join(status.errors) or 'Unknown error'}"
                )

            # Still processing, wait and poll again
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise MLClientError(
            f"Job {job_id} timed out after {max_wait_seconds} seconds"
        )


# =============================================================================
# Singleton Instance
# =============================================================================


class MLClientManager:
    """
    Manager for singleton MLClient instance.

    Ensures proper lifecycle management of the async client.
    """

    _instance: Optional[MLClient] = None
    _initialized: bool = False

    @classmethod
    async def get_client(cls) -> MLClient:
        """
        Get or create the singleton ML client.

        Returns:
            Initialized MLClient instance
        """
        if cls._instance is None or not cls._initialized:
            cls._instance = MLClient()
            await cls._instance.__aenter__()
            cls._initialized = True
        return cls._instance

    @classmethod
    async def close(cls) -> None:
        """Close the singleton client."""
        if cls._instance and cls._initialized:
            await cls._instance.__aexit__(None, None, None)
            cls._instance = None
            cls._initialized = False


async def get_ml_client() -> MLClient:
    """
    Get the singleton ML client instance.

    Usage:
        client = await get_ml_client()
        if await client.check_health():
            response = await client.trigger_analysis(...)
    """
    return await MLClientManager.get_client()


# Export for convenience
ml_client = MLClientManager

