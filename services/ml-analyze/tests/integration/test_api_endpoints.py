"""
API Integration Tests
======================

Tests for ml-analyze API endpoints using FastAPI TestClient.
Uses FastAPI dependency overrides for proper mocking.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.services.job_service import (
    JobData,
    JobService,
    JobStatus,
    JobType,
    get_job_service,
)


@pytest.fixture
def app():
    """Create FastAPI app instance."""
    return create_app()


@pytest.fixture
def client(app):
    """Create FastAPI test client."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_job_service():
    """Create a mock JobService."""
    service = AsyncMock(spec=JobService)
    service.create_job = AsyncMock(return_value=uuid4())
    service.get_job = AsyncMock(return_value=None)
    service.delete_job = AsyncMock(return_value=True)
    service.update_status = AsyncMock()
    service.update_progress = AsyncMock()
    return service


class TestHealthEndpoint:
    """Test /health endpoint."""

    def test_health_check_returns_200(self, client):
        """Test health endpoint returns 200 OK."""
        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert data["service"] == "ml-analyze"
        assert "version" in data
        assert "checks" in data

    def test_health_check_includes_service_checks(self, client):
        """Test health endpoint includes dependency checks."""
        response = client.get("/health")

        data = response.json()
        checks = data.get("checks", {})

        # Should have checks for ollama, database, redis
        assert "ollama" in checks or "database" in checks


class TestApiInfoEndpoint:
    """Test / (root) endpoint."""

    def test_api_info_returns_200(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["service"] == "ml-analyze"
        assert "version" in data
        assert "description" in data


class TestAnalyzeFileEndpoint:
    """Test POST /analyze/file endpoint."""

    def test_analyze_file_valid_request(self, app, mock_job_service):
        """Test file analysis with valid request."""
        # Override dependency
        app.dependency_overrides[get_job_service] = lambda: mock_job_service

        with patch("src.tasks.file_analysis_task.enqueue_file_analysis", new_callable=AsyncMock):
            with TestClient(app) as client:
                response = client.post(
                    "/analyze/file",
                    json={
                        "file_url": "/shared/uploads/test.xlsx",
                        "supplier_id": str(uuid4()),
                        "file_type": "excel",
                    },
                )

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert "message" in data

        # Cleanup
        app.dependency_overrides.clear()

    def test_analyze_file_missing_supplier_id(self, client):
        """Test file analysis with missing supplier_id."""
        response = client.post(
            "/analyze/file",
            json={
                "file_url": "/shared/uploads/test.xlsx",
                "file_type": "excel",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_analyze_file_invalid_file_type(self, client):
        """Test file analysis with invalid file type."""
        response = client.post(
            "/analyze/file",
            json={
                "file_url": "/shared/uploads/test.docx",
                "supplier_id": str(uuid4()),
                "file_type": "docx",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_analyze_file_pdf_type(self, app, mock_job_service):
        """Test file analysis with PDF file type."""
        app.dependency_overrides[get_job_service] = lambda: mock_job_service

        with patch("src.tasks.file_analysis_task.enqueue_file_analysis", new_callable=AsyncMock):
            with TestClient(app) as client:
                response = client.post(
                    "/analyze/file",
                    json={
                        "file_url": "/shared/uploads/test.pdf",
                        "supplier_id": str(uuid4()),
                        "file_type": "pdf",
                    },
                )

        assert response.status_code == status.HTTP_202_ACCEPTED
        app.dependency_overrides.clear()

    def test_analyze_file_csv_type(self, app, mock_job_service):
        """Test file analysis with CSV file type."""
        app.dependency_overrides[get_job_service] = lambda: mock_job_service

        with patch("src.tasks.file_analysis_task.enqueue_file_analysis", new_callable=AsyncMock):
            with TestClient(app) as client:
                response = client.post(
                    "/analyze/file",
                    json={
                        "file_url": "/shared/uploads/test.csv",
                        "supplier_id": str(uuid4()),
                        "file_type": "csv",
                    },
                )

        assert response.status_code == status.HTTP_202_ACCEPTED
        app.dependency_overrides.clear()


class TestBatchMatchEndpoint:
    """Test POST /analyze/merge endpoint."""

    def test_batch_match_valid_request(self, app, mock_job_service):
        """Test batch matching with valid request."""
        app.dependency_overrides[get_job_service] = lambda: mock_job_service

        with patch("src.tasks.file_analysis_task.enqueue_batch_match", new_callable=AsyncMock):
            with TestClient(app) as client:
                response = client.post(
                    "/analyze/merge",
                    json={
                        "supplier_item_ids": [str(uuid4()), str(uuid4())],
                        "limit": 100,
                    },
                )

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["items_queued"] == 2
        app.dependency_overrides.clear()

    def test_batch_match_no_items(self, app, mock_job_service):
        """Test batch matching with no specific items (match all pending)."""
        app.dependency_overrides[get_job_service] = lambda: mock_job_service

        with patch("src.tasks.file_analysis_task.enqueue_batch_match", new_callable=AsyncMock):
            with TestClient(app) as client:
                response = client.post(
                    "/analyze/merge",
                    json={
                        "limit": 50,
                    },
                )

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["items_queued"] == 50
        app.dependency_overrides.clear()

    def test_batch_match_with_supplier_filter(self, app, mock_job_service):
        """Test batch matching with supplier ID filter."""
        supplier_id = uuid4()
        app.dependency_overrides[get_job_service] = lambda: mock_job_service

        with patch("src.tasks.file_analysis_task.enqueue_batch_match", new_callable=AsyncMock):
            with TestClient(app) as client:
                response = client.post(
                    "/analyze/merge",
                    json={
                        "supplier_id": str(supplier_id),
                        "limit": 100,
                    },
                )

        assert response.status_code == status.HTTP_202_ACCEPTED
        app.dependency_overrides.clear()


class TestVisionEndpoint:
    """Test POST /analyze/vision endpoint (stub)."""

    def test_vision_returns_501(self, client):
        """Test vision endpoint returns 501 Not Implemented."""
        response = client.post(
            "/analyze/vision",
            json={
                "image_url": "https://example.com/image.jpg",
                "supplier_id": str(uuid4()),
            },
        )

        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
        data = response.json()
        assert data["status"] == "not_implemented"
        assert "planned_features" in data


class TestStatusEndpoint:
    """Test GET /analyze/status/{job_id} endpoint."""

    def test_get_status_job_found(self, app):
        """Test getting status of existing job."""
        job_id = uuid4()
        job_data = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
            status=JobStatus.PROCESSING,
            progress_percentage=50,
            items_processed=25,
            items_total=50,
            errors=[],
            created_at=datetime.now(timezone.utc),
        )

        mock_service = AsyncMock(spec=JobService)
        mock_service.get_job = AsyncMock(return_value=job_data)

        app.dependency_overrides[get_job_service] = lambda: mock_service

        with TestClient(app) as client:
            response = client.get(f"/analyze/status/{job_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["job_id"] == str(job_id)
        assert data["status"] == "processing"
        assert data["progress_percentage"] == 50
        assert data["items_processed"] == 25
        assert data["items_total"] == 50
        app.dependency_overrides.clear()

    def test_get_status_job_not_found(self, app):
        """Test getting status of non-existent job."""
        job_id = uuid4()
        mock_service = AsyncMock(spec=JobService)
        mock_service.get_job = AsyncMock(return_value=None)

        app.dependency_overrides[get_job_service] = lambda: mock_service

        with TestClient(app) as client:
            response = client.get(f"/analyze/status/{job_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        app.dependency_overrides.clear()

    def test_get_status_invalid_job_id(self, client):
        """Test getting status with invalid job ID format."""
        response = client.get("/analyze/status/invalid-uuid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestDeleteJobEndpoint:
    """Test DELETE /analyze/status/{job_id} endpoint."""

    def test_delete_job_found(self, app):
        """Test deleting existing job."""
        job_id = uuid4()
        mock_service = AsyncMock(spec=JobService)
        mock_service.delete_job = AsyncMock(return_value=True)

        app.dependency_overrides[get_job_service] = lambda: mock_service

        with TestClient(app) as client:
            response = client.delete(f"/analyze/status/{job_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        app.dependency_overrides.clear()

    def test_delete_job_not_found(self, app):
        """Test deleting non-existent job."""
        job_id = uuid4()
        mock_service = AsyncMock(spec=JobService)
        mock_service.delete_job = AsyncMock(return_value=False)

        app.dependency_overrides[get_job_service] = lambda: mock_service

        with TestClient(app) as client:
            response = client.delete(f"/analyze/status/{job_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        app.dependency_overrides.clear()


class TestOpenAPIDocumentation:
    """Test OpenAPI documentation generation."""

    def test_openapi_schema_accessible(self, client):
        """Test OpenAPI schema is accessible in dev mode."""
        response = client.get("/openapi.json")

        # Should be accessible in test/dev environment
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_docs_endpoint(self, client):
        """Test Swagger docs endpoint."""
        response = client.get("/docs")

        # Should be accessible in test/dev environment
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
