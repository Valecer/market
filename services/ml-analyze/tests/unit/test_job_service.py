"""
Unit Tests for Job Service
===========================

Tests for Redis-based job status management.
Uses fakeredis for isolated testing.
"""

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.job_service import (
    JobData,
    JobService,
    JobStatus,
    JobType,
    JOB_PREFIX,
    JOB_TTL_SECONDS,
)


class TestJobData:
    """Test JobData Pydantic model."""

    def test_create_job_data(self):
        """Test creating a JobData instance."""
        job_id = uuid4()
        supplier_id = uuid4()

        job = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
            supplier_id=supplier_id,
            file_url="/path/to/file.xlsx",
            file_type="excel",
        )

        assert job.job_id == job_id
        assert job.job_type == JobType.FILE_ANALYSIS
        assert job.status == JobStatus.PENDING
        assert job.progress_percentage == 0
        assert job.items_processed == 0
        assert job.items_total == 0
        assert job.errors == []
        assert job.supplier_id == supplier_id
        assert job.file_url == "/path/to/file.xlsx"
        assert job.file_type == "excel"
        assert job.started_at is None
        assert job.completed_at is None

    def test_job_data_to_json(self):
        """Test JSON serialization."""
        job_id = uuid4()
        job = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
        )

        json_str = job.to_json()

        assert isinstance(json_str, str)
        assert str(job_id) in json_str
        assert "file_analysis" in json_str

    def test_job_data_from_json(self):
        """Test JSON deserialization."""
        job_id = uuid4()
        original = JobData(
            job_id=job_id,
            job_type=JobType.BATCH_MATCH,
            status=JobStatus.PROCESSING,
            progress_percentage=50,
            items_processed=25,
            items_total=50,
        )

        json_str = original.to_json()
        restored = JobData.from_json(json_str)

        assert restored.job_id == original.job_id
        assert restored.job_type == original.job_type
        assert restored.status == original.status
        assert restored.progress_percentage == original.progress_percentage
        assert restored.items_processed == original.items_processed
        assert restored.items_total == original.items_total


class TestJobService:
    """Test JobService class."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.setex = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def job_service(self, mock_redis):
        """Create JobService with mock Redis."""
        return JobService(mock_redis)

    @pytest.mark.asyncio
    async def test_create_job(self, job_service, mock_redis):
        """Test creating a new job."""
        supplier_id = uuid4()

        job_id = await job_service.create_job(
            job_type=JobType.FILE_ANALYSIS,
            supplier_id=supplier_id,
            file_url="/path/to/file.xlsx",
            file_type="excel",
            items_total=100,
        )

        assert isinstance(job_id, UUID)
        mock_redis.setex.assert_called_once()

        # Verify the call arguments
        call_args = mock_redis.setex.call_args
        key = call_args[0][0]
        ttl = call_args[0][1]
        data = call_args[0][2]

        assert key.startswith(JOB_PREFIX)
        assert ttl == JOB_TTL_SECONDS
        assert str(job_id) in data

    @pytest.mark.asyncio
    async def test_get_job_found(self, job_service, mock_redis):
        """Test retrieving an existing job."""
        job_id = uuid4()
        job_data = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
            status=JobStatus.PROCESSING,
        )

        mock_redis.get = AsyncMock(return_value=job_data.to_json())

        result = await job_service.get_job(job_id)

        assert result is not None
        assert result.job_id == job_id
        assert result.status == JobStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, job_service, mock_redis):
        """Test retrieving a non-existent job."""
        job_id = uuid4()
        mock_redis.get = AsyncMock(return_value=None)

        result = await job_service.get_job(job_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_status_to_processing(self, job_service, mock_redis):
        """Test updating job status to processing."""
        job_id = uuid4()
        job_data = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
            status=JobStatus.PENDING,
        )

        mock_redis.get = AsyncMock(return_value=job_data.to_json())

        result = await job_service.update_status(job_id, JobStatus.PROCESSING)

        assert result.success is True
        assert result.job_id == job_id
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_to_completed(self, job_service, mock_redis):
        """Test updating job status to completed."""
        job_id = uuid4()
        job_data = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
            status=JobStatus.PROCESSING,
            started_at=datetime.now(timezone.utc),
        )

        mock_redis.get = AsyncMock(return_value=job_data.to_json())

        result = await job_service.update_status(job_id, JobStatus.COMPLETED)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_update_status_job_not_found(self, job_service, mock_redis):
        """Test updating status of non-existent job."""
        job_id = uuid4()
        mock_redis.get = AsyncMock(return_value=None)

        result = await job_service.update_status(job_id, JobStatus.PROCESSING)

        assert result.success is False
        assert result.error == "Job not found"

    @pytest.mark.asyncio
    async def test_update_progress(self, job_service, mock_redis):
        """Test updating job progress."""
        job_id = uuid4()
        job_data = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
            status=JobStatus.PROCESSING,
            items_total=100,
        )

        mock_redis.get = AsyncMock(return_value=job_data.to_json())

        result = await job_service.update_progress(
            job_id,
            items_processed=50,
        )

        assert result.success is True

        # Verify setex was called with updated data
        call_args = mock_redis.setex.call_args
        stored_json = call_args[0][2]
        stored_job = JobData.from_json(stored_json)

        assert stored_job.items_processed == 50
        assert stored_job.progress_percentage == 50

    @pytest.mark.asyncio
    async def test_update_progress_with_total(self, job_service, mock_redis):
        """Test updating progress with new total."""
        job_id = uuid4()
        job_data = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
            status=JobStatus.PROCESSING,
        )

        mock_redis.get = AsyncMock(return_value=job_data.to_json())

        result = await job_service.update_progress(
            job_id,
            items_processed=25,
            items_total=100,
        )

        assert result.success is True

        call_args = mock_redis.setex.call_args
        stored_json = call_args[0][2]
        stored_job = JobData.from_json(stored_json)

        assert stored_job.items_total == 100
        assert stored_job.items_processed == 25
        assert stored_job.progress_percentage == 25

    @pytest.mark.asyncio
    async def test_update_progress_with_errors(self, job_service, mock_redis):
        """Test updating progress with error messages."""
        job_id = uuid4()
        job_data = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
            status=JobStatus.PROCESSING,
            items_total=100,
        )

        mock_redis.get = AsyncMock(return_value=job_data.to_json())

        result = await job_service.update_progress(
            job_id,
            items_processed=10,
            errors=["Error 1", "Error 2"],
        )

        assert result.success is True

        call_args = mock_redis.setex.call_args
        stored_json = call_args[0][2]
        stored_job = JobData.from_json(stored_json)

        assert len(stored_job.errors) == 2
        assert "Error 1" in stored_job.errors
        assert "Error 2" in stored_job.errors

    @pytest.mark.asyncio
    async def test_mark_started(self, job_service, mock_redis):
        """Test marking job as started."""
        job_id = uuid4()
        job_data = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
            status=JobStatus.PENDING,
        )

        mock_redis.get = AsyncMock(return_value=job_data.to_json())

        result = await job_service.mark_started(job_id)

        assert result.success is True

        call_args = mock_redis.setex.call_args
        stored_json = call_args[0][2]
        stored_job = JobData.from_json(stored_json)

        assert stored_job.status == JobStatus.PROCESSING
        assert stored_job.started_at is not None

    @pytest.mark.asyncio
    async def test_mark_completed(self, job_service, mock_redis):
        """Test marking job as completed."""
        job_id = uuid4()
        job_data = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
            status=JobStatus.PROCESSING,
            items_total=100,
            items_processed=50,
        )

        mock_redis.get = AsyncMock(return_value=job_data.to_json())

        result = await job_service.mark_completed(job_id, items_processed=100)

        assert result.success is True

        call_args = mock_redis.setex.call_args
        stored_json = call_args[0][2]
        stored_job = JobData.from_json(stored_json)

        assert stored_job.status == JobStatus.COMPLETED
        assert stored_job.progress_percentage == 100
        assert stored_job.items_processed == 100
        assert stored_job.completed_at is not None

    @pytest.mark.asyncio
    async def test_mark_failed(self, job_service, mock_redis):
        """Test marking job as failed."""
        job_id = uuid4()
        job_data = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
            status=JobStatus.PROCESSING,
        )

        mock_redis.get = AsyncMock(return_value=job_data.to_json())

        result = await job_service.mark_failed(job_id, "Processing error occurred")

        assert result.success is True

        call_args = mock_redis.setex.call_args
        stored_json = call_args[0][2]
        stored_job = JobData.from_json(stored_json)

        assert stored_job.status == JobStatus.FAILED
        assert "Processing error occurred" in stored_job.errors

    @pytest.mark.asyncio
    async def test_delete_job_found(self, job_service, mock_redis):
        """Test deleting an existing job."""
        job_id = uuid4()
        mock_redis.delete = AsyncMock(return_value=1)

        result = await job_service.delete_job(job_id)

        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_job_not_found(self, job_service, mock_redis):
        """Test deleting a non-existent job."""
        job_id = uuid4()
        mock_redis.delete = AsyncMock(return_value=0)

        result = await job_service.delete_job(job_id)

        assert result is False

    def test_job_key_format(self):
        """Test job key generation."""
        job_id = uuid4()
        key = JobService._job_key(job_id)

        assert key == f"{JOB_PREFIX}{job_id}"


class TestJobStatus:
    """Test JobStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.PROCESSING.value == "processing"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"


class TestJobType:
    """Test JobType enum."""

    def test_type_values(self):
        """Test all type values exist."""
        assert JobType.FILE_ANALYSIS.value == "file_analysis"
        assert JobType.BATCH_MATCH.value == "batch_match"
        assert JobType.VISION.value == "vision"

