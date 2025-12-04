"""
Analyze Routes Integration Tests
================================

Tests for POST /analyze/file endpoint with semantic ETL (Phase 9).
Tests SmartParserService integration and job status tracking.

@see /specs/009-semantic-etl/tasks.md - T043
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.schemas.extraction import ExtractionResult, ExtractedProduct
from src.services.job_service import (
    JobData,
    JobPhase,
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
    service.update_job_status = AsyncMock()
    return service


@pytest.fixture
def temp_excel_file():
    """Create a temporary Excel file for testing."""
    import openpyxl
    
    # Create a temporary directory and file
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test_products.xlsx"
        
        # Create a simple Excel file
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Upload to site"
        
        # Add headers
        ws.append(["Name", "Price", "Category"])
        
        # Add some test data
        ws.append(["Test Product 1", "100.00", "Electronics"])
        ws.append(["Test Product 2", "200.00", "Furniture"])
        ws.append(["Test Product 3", "150.00", "Electronics"])
        
        wb.save(file_path)
        
        yield str(file_path)


class TestSemanticETLEndpoint:
    """Tests for POST /analyze/file with semantic ETL."""
    
    def test_analyze_file_semantic_etl_request(self, app, mock_job_service, temp_excel_file):
        """Test file analysis with semantic ETL enabled."""
        app.dependency_overrides[get_job_service] = lambda: mock_job_service
        
        with TestClient(app) as client:
            response = client.post(
                "/analyze/file",
                json={
                    "file_url": temp_excel_file,
                    "supplier_id": str(uuid4()),
                    "file_type": "excel",
                    "use_semantic_etl": True,
                },
            )
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert "semantic etl" in data["message"].lower()
        
        app.dependency_overrides.clear()
    
    def test_analyze_file_with_priority_sheet(self, app, mock_job_service, temp_excel_file):
        """Test file analysis with priority sheet specified."""
        app.dependency_overrides[get_job_service] = lambda: mock_job_service
        
        with TestClient(app) as client:
            response = client.post(
                "/analyze/file",
                json={
                    "file_url": temp_excel_file,
                    "supplier_id": str(uuid4()),
                    "file_type": "excel",
                    "use_semantic_etl": True,
                    "priority_sheet": "Upload to site",
                },
            )
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        
        app.dependency_overrides.clear()
    
    def test_analyze_file_nonexistent_file(self, app, mock_job_service):
        """Test file analysis with non-existent file returns 400."""
        app.dependency_overrides[get_job_service] = lambda: mock_job_service
        
        with TestClient(app) as client:
            response = client.post(
                "/analyze/file",
                json={
                    "file_url": "/shared/uploads/nonexistent_file.xlsx",
                    "supplier_id": str(uuid4()),
                    "file_type": "excel",
                },
            )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not found" in response.json()["detail"].lower()
        
        app.dependency_overrides.clear()
    
    def test_analyze_file_http_url_accepted(self, app, mock_job_service):
        """Test file analysis with HTTP URL is accepted."""
        app.dependency_overrides[get_job_service] = lambda: mock_job_service
        
        with TestClient(app) as client:
            response = client.post(
                "/analyze/file",
                json={
                    "file_url": "https://example.com/files/test.xlsx",
                    "supplier_id": str(uuid4()),
                    "file_type": "excel",
                },
            )
        
        # HTTP URLs don't get local file validation
        assert response.status_code == status.HTTP_202_ACCEPTED
        
        app.dependency_overrides.clear()


class TestSemanticETLJobStatus:
    """Tests for job status with semantic ETL metrics."""
    
    def test_get_status_with_semantic_etl_metrics(self, app):
        """Test job status includes semantic ETL metrics."""
        job_id = uuid4()
        job_data = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
            status=JobStatus.PROCESSING,
            phase=JobPhase.EXTRACTING,
            progress_percentage=50,
            items_processed=150,
            items_total=300,
            successful_extractions=145,
            failed_extractions=5,
            duplicates_removed=3,
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
        
        # Verify semantic ETL metrics are included
        assert data["phase"] == "extracting"
        assert data["successful_extractions"] == 145
        assert data["failed_extractions"] == 5
        assert data["duplicates_removed"] == 3
        
        app.dependency_overrides.clear()
    
    def test_get_status_completed_with_errors(self, app):
        """Test job status with completed_with_errors status."""
        job_id = uuid4()
        job_data = JobData(
            job_id=job_id,
            job_type=JobType.FILE_ANALYSIS,
            status=JobStatus.COMPLETED_WITH_ERRORS,
            phase=JobPhase.COMPLETED_WITH_ERRORS,
            progress_percentage=100,
            items_processed=280,
            items_total=300,
            successful_extractions=280,
            failed_extractions=20,
            duplicates_removed=5,
            errors=["Row 45: Missing price field", "Row 122: Invalid category"],
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        
        mock_service = AsyncMock(spec=JobService)
        mock_service.get_job = AsyncMock(return_value=job_data)
        
        app.dependency_overrides[get_job_service] = lambda: mock_service
        
        with TestClient(app) as client:
            response = client.get(f"/analyze/status/{job_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "completed_with_errors"
        assert data["phase"] == "completed_with_errors"
        assert len(data["errors"]) == 2
        
        app.dependency_overrides.clear()
    
    def test_get_status_all_phases(self, app):
        """Test job status for all semantic ETL phases."""
        phases = [
            (JobPhase.PENDING, "pending"),
            (JobPhase.DOWNLOADING, "downloading"),
            (JobPhase.ANALYZING, "analyzing"),
            (JobPhase.EXTRACTING, "extracting"),
            (JobPhase.NORMALIZING, "normalizing"),
            (JobPhase.COMPLETE, "complete"),
            (JobPhase.FAILED, "failed"),
        ]
        
        for phase_enum, phase_str in phases:
            job_id = uuid4()
            job_data = JobData(
                job_id=job_id,
                job_type=JobType.FILE_ANALYSIS,
                status=JobStatus.PROCESSING,
                phase=phase_enum,
                progress_percentage=50,
                created_at=datetime.now(timezone.utc),
            )
            
            mock_service = AsyncMock(spec=JobService)
            mock_service.get_job = AsyncMock(return_value=job_data)
            
            app.dependency_overrides[get_job_service] = lambda: mock_service
            
            with TestClient(app) as client:
                response = client.get(f"/analyze/status/{job_id}")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["phase"] == phase_str, f"Phase mismatch for {phase_str}"
            
            app.dependency_overrides.clear()


class TestRequestValidation:
    """Tests for request schema validation (T042)."""
    
    def test_use_semantic_etl_default_true(self, app, mock_job_service, temp_excel_file):
        """Test use_semantic_etl defaults to True."""
        app.dependency_overrides[get_job_service] = lambda: mock_job_service
        
        with TestClient(app) as client:
            response = client.post(
                "/analyze/file",
                json={
                    "file_url": temp_excel_file,
                    "supplier_id": str(uuid4()),
                    "file_type": "excel",
                    # use_semantic_etl not specified - should default to True
                },
            )
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        # Should use semantic ETL by default
        assert "semantic etl" in response.json()["message"].lower()
        
        app.dependency_overrides.clear()
    
    def test_priority_sheet_optional(self, app, mock_job_service, temp_excel_file):
        """Test priority_sheet is optional."""
        app.dependency_overrides[get_job_service] = lambda: mock_job_service
        
        # Without priority_sheet
        with TestClient(app) as client:
            response = client.post(
                "/analyze/file",
                json={
                    "file_url": temp_excel_file,
                    "supplier_id": str(uuid4()),
                    "file_type": "excel",
                },
            )
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        
        app.dependency_overrides.clear()
    
    def test_invalid_file_type_rejected(self, client):
        """Test invalid file type is rejected."""
        response = client.post(
            "/analyze/file",
            json={
                "file_url": "/shared/uploads/test.docx",
                "supplier_id": str(uuid4()),
                "file_type": "docx",  # Invalid type
            },
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_invalid_supplier_id_rejected(self, client):
        """Test invalid supplier_id format is rejected."""
        response = client.post(
            "/analyze/file",
            json={
                "file_url": "/shared/uploads/test.xlsx",
                "supplier_id": "not-a-uuid",  # Invalid UUID
                "file_type": "excel",
            },
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

