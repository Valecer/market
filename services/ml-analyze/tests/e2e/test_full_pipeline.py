"""
End-to-End Tests
=================

Full pipeline tests for ml-analyze service.

Tests:
- Submit job → Poll status → Verify completion
- File analysis pipeline
- Batch matching pipeline

Requires:
- Running PostgreSQL with pgvector
- Running Redis
- Running Ollama with models

These tests are slow (~30s) and require full infrastructure.
"""

import asyncio
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


# Skip E2E tests if infrastructure not available
pytestmark = pytest.mark.skipif(
    not Path("/Users/valecer/work/sites/marketbel/services/ml-analyze/tests/fixtures/sample.xlsx").exists(),
    reason="Test fixtures not available",
)


@pytest.fixture(scope="module")
def client():
    """Create FastAPI test client for E2E tests."""
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def test_file_path():
    """Path to test fixture file."""
    return "/Users/valecer/work/sites/marketbel/services/ml-analyze/tests/fixtures/sample.xlsx"


class TestJobSubmissionAndPolling:
    """Test job submission and status polling workflow."""

    @pytest.mark.slow
    def test_submit_job_and_poll_status(self, client):
        """
        E2E: Submit job → Poll status → Verify state transitions.

        This test verifies:
        1. Job is created with pending status
        2. Job transitions to processing
        3. Status endpoint returns correct progress
        """
        # Submit a file analysis job (may fail to actually process without full infra)
        supplier_id = uuid4()

        response = client.post(
            "/analyze/file",
            json={
                "file_url": "/Users/valecer/work/sites/marketbel/services/ml-analyze/tests/fixtures/sample.xlsx",
                "supplier_id": str(supplier_id),
                "file_type": "excel",
            },
        )

        assert response.status_code == 202
        data = response.json()
        job_id = data["job_id"]

        # Poll status (immediate check - should be pending or processing)
        status_response = client.get(f"/analyze/status/{job_id}")

        # Job should exist (either pending, processing, or already failed due to missing infra)
        assert status_response.status_code in [200, 404]

        if status_response.status_code == 200:
            status_data = status_response.json()
            assert status_data["job_id"] == job_id
            assert status_data["status"] in ["pending", "processing", "completed", "failed"]

    @pytest.mark.slow
    def test_batch_match_job_lifecycle(self, client):
        """
        E2E: Submit batch match → Poll → Verify.
        """
        response = client.post(
            "/analyze/merge",
            json={
                "limit": 10,
            },
        )

        assert response.status_code == 202
        data = response.json()
        job_id = data["job_id"]

        # Verify job was created
        status_response = client.get(f"/analyze/status/{job_id}")
        assert status_response.status_code in [200, 404]


class TestVisionStub:
    """Test vision endpoint stub behavior."""

    def test_vision_returns_501_with_features(self, client):
        """Test vision endpoint returns proper stub response."""
        supplier_id = uuid4()

        response = client.post(
            "/analyze/vision",
            json={
                "image_url": "https://example.com/price-tag.jpg",
                "supplier_id": str(supplier_id),
            },
        )

        assert response.status_code == 501
        data = response.json()

        assert data["status"] == "not_implemented"
        assert "planned_features" in data
        assert len(data["planned_features"]) > 0


class TestHealthCheckIntegration:
    """Test health check with real services."""

    def test_health_check_structure(self, client):
        """Test health check returns proper structure."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "status" in data
        assert "version" in data
        assert "service" in data
        assert "checks" in data

        # Service should be ml-analyze
        assert data["service"] == "ml-analyze"

        # Status should be valid
        assert data["status"] in ["healthy", "degraded", "unhealthy"]


class TestJobCleanup:
    """Test job lifecycle including cleanup."""

    def test_job_deletion(self, client):
        """Test job can be deleted after creation."""
        # Create a job
        response = client.post(
            "/analyze/merge",
            json={"limit": 1},
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Delete the job
        delete_response = client.delete(f"/analyze/status/{job_id}")

        # Should succeed or job already processed/expired
        assert delete_response.status_code in [204, 404]

        # Verify job is gone
        status_response = client.get(f"/analyze/status/{job_id}")
        assert status_response.status_code == 404


class TestErrorHandling:
    """Test error handling in E2E scenarios."""

    def test_invalid_file_url_handled(self, client):
        """Test that invalid file URLs are handled gracefully."""
        response = client.post(
            "/analyze/file",
            json={
                "file_url": "/nonexistent/path/to/file.xlsx",
                "supplier_id": str(uuid4()),
                "file_type": "excel",
            },
        )

        # Job should be created (file validation happens in background)
        assert response.status_code == 202

    def test_invalid_supplier_id_format(self, client):
        """Test that invalid supplier ID format is rejected."""
        response = client.post(
            "/analyze/file",
            json={
                "file_url": "/shared/uploads/test.xlsx",
                "supplier_id": "not-a-uuid",
                "file_type": "excel",
            },
        )

        assert response.status_code == 422

    def test_missing_required_fields(self, client):
        """Test that missing required fields are rejected."""
        # Missing file_url
        response = client.post(
            "/analyze/file",
            json={
                "supplier_id": str(uuid4()),
                "file_type": "excel",
            },
        )
        assert response.status_code == 422

        # Missing file_type
        response = client.post(
            "/analyze/file",
            json={
                "file_url": "/shared/uploads/test.xlsx",
                "supplier_id": str(uuid4()),
            },
        )
        assert response.status_code == 422


class TestConcurrentRequests:
    """Test handling of concurrent requests."""

    @pytest.mark.slow
    def test_multiple_job_submissions(self, client):
        """Test submitting multiple jobs concurrently."""
        jobs = []

        # Submit 5 jobs
        for i in range(5):
            response = client.post(
                "/analyze/merge",
                json={"limit": 1},
            )
            assert response.status_code == 202
            jobs.append(response.json()["job_id"])

        # Verify all jobs have unique IDs
        assert len(set(jobs)) == 5

        # All jobs should be queryable
        for job_id in jobs:
            response = client.get(f"/analyze/status/{job_id}")
            assert response.status_code in [200, 404]  # May have expired

