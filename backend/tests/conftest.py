import os
import pytest
import time
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.db.base import Base
from app.config import get_settings


@pytest.fixture(scope="session")
def test_settings():
    """Get test settings (uses actual environment)."""
    return get_settings()


@pytest.fixture(scope="module")
def test_client():
    """FastAPI test client."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
def samples_dir():
    """Path to samples directory."""
    backend_dir = Path(__file__).parent.parent
    repo_root = backend_dir.parent
    samples = repo_root / "samples"
    assert samples.exists(), f"Samples directory not found: {samples}"
    return samples


@pytest.fixture(scope="session")
def sample_files(samples_dir):
    """Dictionary of sample file paths."""
    return {
        "valid_culture": samples_dir / "Culture-Urine.pdf",
        "valid_troponin": samples_dir / "HIGH SENSITIVE TROPONIN -I.pdf",
        "valid_urine": samples_dir / "Urine DR.pdf",
        "invalid_receipt1": samples_dir / "Lab Receipt.pdf",
        "invalid_receipt2": samples_dir / "Lab Receipt2.pdf",
    }


@pytest.fixture
def upload_file_helper(tmp_path):
    """Helper to create test files for upload."""
    def _create_test_file(filename: str, size_mb: int = 1, content: bytes = None):
        """
        Create a test file.

        Args:
            filename: Name of file to create
            size_mb: Size in MB (default 1MB)
            content: Optional custom content (overrides size_mb)
        """
        file_path = tmp_path / filename

        if content is not None:
            file_path.write_bytes(content)
        else:
            # Generate dummy content
            file_path.write_bytes(b"x" * (size_mb * 1024 * 1024))

        return file_path

    return _create_test_file


@pytest.fixture
def wait_for_task():
    """Helper to wait for Celery task completion."""
    def _wait(job_id: str, test_client: TestClient, timeout: int = 60, poll_interval: float = 2.0):
        """
        Poll the status endpoint until task completes or times out.

        Args:
            job_id: Job ID to poll
            test_client: FastAPI test client
            timeout: Maximum wait time in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Final response object

        Raises:
            TimeoutError: If task doesn't complete within timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            response = test_client.get(f"/v1/reports/status/{job_id}")

            if response.status_code != 200:
                raise Exception(f"Status check failed: {response.status_code} - {response.text}")

            data = response.json()
            status = data.get("status")

            if status in ["COMPLETED", "FAILED"]:
                return response

            time.sleep(poll_interval)

        raise TimeoutError(f"Task {job_id} did not complete within {timeout} seconds")

    return _wait


@pytest.fixture
def create_oversized_file(tmp_path):
    """Create a file larger than the allowed limit."""
    settings = get_settings()
    max_size_mb = settings.max_file_size_mb

    # Create a file 1MB larger than the limit
    oversized_file = tmp_path / "oversized.pdf"
    oversized_file.write_bytes(b"x" * ((max_size_mb + 1) * 1024 * 1024))

    return oversized_file


@pytest.fixture
def create_invalid_file_type(tmp_path):
    """Create a file with invalid file type (e.g., .txt)."""
    invalid_file = tmp_path / "test_report.txt"
    invalid_file.write_text("This is a text file, not a PDF or image.")

    return invalid_file
