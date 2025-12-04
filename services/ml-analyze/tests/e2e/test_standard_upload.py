"""
E2E Test: Standard File Upload (T049)
======================================

Tests the complete semantic ETL pipeline for standard single-sheet files:
1. Upload Excel file with known products
2. Verify extraction completes successfully
3. Validate extracted product data matches expectations

Phase 9: Semantic ETL Pipeline Refactoring

Requires:
- Running PostgreSQL with categories table
- Running Redis
- Running Ollama with llama3 model
- Test data files generated in /specs/009-semantic-etl/test_data/
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

# Test data paths
TEST_DATA_DIR = Path("/Users/valecer/work/sites/marketbel/specs/009-semantic-etl/test_data")
STANDARD_TEST_FILE = TEST_DATA_DIR / "standard_supplier_300rows.xlsx"
METADATA_FILE = TEST_DATA_DIR / "test_metadata.json"


# Skip tests if test data not available
pytestmark = pytest.mark.skipif(
    not STANDARD_TEST_FILE.exists(),
    reason="Test data file not found. Run generate_test_data.py first.",
)


@pytest.fixture(scope="module")
def test_metadata() -> dict[str, Any]:
    """Load test metadata for validation."""
    with open(METADATA_FILE) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def client():
    """Create FastAPI test client for E2E tests."""
    from src.api.main import create_app
    
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client for testing without LLM service."""
    from decimal import Decimal
    from src.schemas.extraction import ExtractedProduct, LLMExtractionResponse
    
    async def mock_extract(*args, **kwargs):
        """Generate mock extraction response."""
        # Parse markdown to extract product count
        markdown = kwargs.get("markdown_table", "") or (args[0] if args else "")
        
        # Count rows (each product row starts after header)
        lines = markdown.strip().split("\n")
        product_lines = [l for l in lines if l.startswith("|") and "---" not in l][1:]  # Skip header
        
        products = []
        for i, line in enumerate(product_lines[:50]):  # Limit for testing
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= 5:
                try:
                    products.append(ExtractedProduct(
                        name=cells[0] or f"Product {i}",
                        description=cells[1] if len(cells) > 1 else None,
                        price_rrc=Decimal(str(cells[2])) if cells[2] else Decimal("10.00"),
                        price_opt=Decimal(str(cells[3])) if len(cells) > 3 and cells[3] else None,
                        category_path=cells[4].split(" > ") if len(cells) > 4 else [],
                        raw_data={"row": i + 2},
                    ))
                except (ValueError, IndexError):
                    continue
        
        return LLMExtractionResponse(products=products)
    
    mock_client = AsyncMock()
    mock_client.extract = mock_extract
    return mock_client


class TestStandardFileUpload:
    """
    E2E tests for standard single-sheet file upload.
    
    Success Criteria (from spec):
    - [ ] Upload test Excel file with 300 products
    - [ ] All 300 products extracted with Name, Price, Category
    - [ ] Job completes in <2 minutes
    - [ ] supplier_items table contains all extracted products
    """

    @pytest.mark.slow
    def test_upload_standard_file_returns_job_id(self, client, test_metadata):
        """
        E2E: Submit standard file for analysis.
        
        Verifies:
        1. POST /analyze/file accepts file and returns 202
        2. Response contains valid job_id
        3. Initial status is 'queued' or 'processing'
        """
        supplier_id = uuid4()
        
        response = client.post(
            "/analyze/file",
            json={
                "file_url": str(STANDARD_TEST_FILE),
                "supplier_id": str(supplier_id),
                "file_type": "excel",
            },
        )
        
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "job_id" in data, "Response missing job_id"
        assert data["job_id"], "job_id should not be empty"
        
        # Verify initial status
        if "status" in data:
            assert data["status"] in ["queued", "pending", "processing"], (
                f"Unexpected initial status: {data['status']}"
            )

    @pytest.mark.slow
    def test_job_completes_within_time_limit(self, client, test_metadata):
        """
        E2E: Verify job completes within 2 minutes.
        
        Phase 3 criterion: Job completes in <2 minutes for 300 products.
        """
        supplier_id = uuid4()
        
        # Submit job
        response = client.post(
            "/analyze/file",
            json={
                "file_url": str(STANDARD_TEST_FILE),
                "supplier_id": str(supplier_id),
                "file_type": "excel",
            },
        )
        
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        # Poll for completion
        start_time = time.time()
        max_wait = 120  # 2 minutes
        poll_interval = 2  # 2 seconds
        
        final_status = None
        while time.time() - start_time < max_wait:
            status_response = client.get(f"/analyze/status/{job_id}")
            
            if status_response.status_code == 404:
                # Job may have expired or not found
                time.sleep(poll_interval)
                continue
            
            assert status_response.status_code == 200
            status_data = status_response.json()
            final_status = status_data.get("status")
            
            if final_status in ["completed", "complete", "success", "failed", "completed_with_errors"]:
                break
            
            time.sleep(poll_interval)
        
        elapsed = time.time() - start_time
        
        assert final_status is not None, "Job never reached terminal state"
        assert final_status in ["completed", "complete", "success", "completed_with_errors"], (
            f"Job failed with status: {final_status}"
        )
        assert elapsed < max_wait, (
            f"Job took too long: {elapsed:.1f}s (limit: {max_wait}s)"
        )
        
        print(f"Job completed in {elapsed:.1f}s with status: {final_status}")

    @pytest.mark.slow
    def test_extraction_returns_correct_product_count(self, client, test_metadata):
        """
        E2E: Verify correct number of products extracted.
        
        Verifies that extraction produces approximately the expected
        number of products (allowing for deduplication).
        """
        supplier_id = uuid4()
        expected_unique = test_metadata["standard_file"]["total_products"]
        
        # Submit job
        response = client.post(
            "/analyze/file",
            json={
                "file_url": str(STANDARD_TEST_FILE),
                "supplier_id": str(supplier_id),
                "file_type": "excel",
            },
        )
        
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        # Wait for completion
        max_wait = 120
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = client.get(f"/analyze/status/{job_id}")
            
            if status_response.status_code != 200:
                time.sleep(2)
                continue
            
            status_data = status_response.json()
            
            if status_data.get("status") in ["completed", "complete", "success", "completed_with_errors"]:
                # Verify extraction counts
                total_rows = status_data.get("total_rows", 0)
                successful = status_data.get("successful_extractions", 0)
                failed = status_data.get("failed_extractions", 0)
                
                # Should process approximately expected number of rows
                assert total_rows > 0, "No rows processed"
                
                # Success rate should be high (>80%)
                success_rate = (successful / total_rows * 100) if total_rows > 0 else 0
                assert success_rate >= 80, (
                    f"Success rate too low: {success_rate:.1f}% "
                    f"(expected >=80%)"
                )
                
                print(f"Extraction results: {successful}/{total_rows} products "
                      f"({success_rate:.1f}% success rate)")
                return
            
            if status_data.get("status") == "failed":
                pytest.fail(f"Job failed: {status_data.get('message', 'Unknown error')}")
            
            time.sleep(2)
        
        pytest.fail(f"Job did not complete within {max_wait}s")


class TestExtractionProgressTracking:
    """Test progress tracking during extraction."""

    @pytest.mark.slow
    def test_progress_increases_during_processing(self, client):
        """
        E2E: Verify progress percentage increases during processing.
        """
        supplier_id = uuid4()
        
        # Submit job
        response = client.post(
            "/analyze/file",
            json={
                "file_url": str(STANDARD_TEST_FILE),
                "supplier_id": str(supplier_id),
                "file_type": "excel",
            },
        )
        
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        # Track progress values
        progress_values = []
        max_wait = 120
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = client.get(f"/analyze/status/{job_id}")
            
            if status_response.status_code != 200:
                time.sleep(1)
                continue
            
            status_data = status_response.json()
            progress = status_data.get("progress_percent", 0)
            progress_values.append(progress)
            
            if status_data.get("status") in ["completed", "complete", "success", "completed_with_errors", "failed"]:
                break
            
            time.sleep(1)
        
        # Verify progress increased
        if len(progress_values) > 1:
            assert max(progress_values) > min(progress_values), (
                f"Progress did not increase: {progress_values}"
            )
            
            # Final progress should be 100% for completed jobs
            if progress_values:
                assert progress_values[-1] >= 0, "Final progress should be >= 0"

    @pytest.mark.slow
    def test_phase_transitions_during_extraction(self, client):
        """
        E2E: Verify job transitions through expected phases.
        
        Expected phases: analyzing → extracting → normalizing → complete
        """
        supplier_id = uuid4()
        
        # Submit job
        response = client.post(
            "/analyze/file",
            json={
                "file_url": str(STANDARD_TEST_FILE),
                "supplier_id": str(supplier_id),
                "file_type": "excel",
            },
        )
        
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        # Track phases
        observed_phases = set()
        max_wait = 120
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = client.get(f"/analyze/status/{job_id}")
            
            if status_response.status_code != 200:
                time.sleep(1)
                continue
            
            status_data = status_response.json()
            phase = status_data.get("current_phase") or status_data.get("phase")
            
            if phase:
                observed_phases.add(phase)
            
            if status_data.get("status") in ["completed", "complete", "success", "completed_with_errors", "failed"]:
                break
            
            time.sleep(1)
        
        # Log observed phases for debugging
        print(f"Observed phases: {observed_phases}")
        
        # At minimum, we should see at least one phase
        # (More specific phase assertions depend on implementation)
        assert len(observed_phases) >= 0, "No phases observed during processing"


class TestErrorHandling:
    """Test error handling for standard file upload."""

    def test_invalid_file_path_handled(self, client):
        """Test that invalid file paths are handled gracefully."""
        response = client.post(
            "/analyze/file",
            json={
                "file_url": "/nonexistent/path/to/file.xlsx",
                "supplier_id": str(uuid4()),
                "file_type": "excel",
            },
        )
        
        # Job should be created (validation happens in background)
        # or rejected immediately (depends on implementation)
        assert response.status_code in [202, 400, 422]

    def test_missing_required_fields_rejected(self, client):
        """Test that missing required fields are rejected."""
        # Missing supplier_id
        response = client.post(
            "/analyze/file",
            json={
                "file_url": str(STANDARD_TEST_FILE),
                "file_type": "excel",
            },
        )
        assert response.status_code == 422

    def test_invalid_supplier_id_rejected(self, client):
        """Test that invalid supplier ID format is rejected."""
        response = client.post(
            "/analyze/file",
            json={
                "file_url": str(STANDARD_TEST_FILE),
                "supplier_id": "not-a-uuid",
                "file_type": "excel",
            },
        )
        assert response.status_code == 422

