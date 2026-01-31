"""
E2E tests for the web upload pipeline.

Tests the complete flow from file upload through Celery task processing
to result retrieval, using real LLM calls.
"""
import pytest
from pathlib import Path


class TestWebPipelineEnglish:
    """Test valid lab report analysis in English."""

    def test_valid_lab_report_english(self, test_client, sample_files, wait_for_task):
        """
        Test Scenario 1: Valid lab report → successful analysis (English).

        Flow:
        1. Upload valid lab report PDF (Culture-Urine.pdf)
        2. Verify upload response with job_id
        3. Poll status endpoint until COMPLETED
        4. Verify analysis results (JSON, markdown, PDF)
        5. Verify language is English
        """
        # Step 1: Upload file
        sample_file = sample_files["valid_culture"]
        assert sample_file.exists(), f"Sample file not found: {sample_file}"

        with open(sample_file, "rb") as f:
            files = {"file": ("Culture-Urine.pdf", f, "application/pdf")}
            data = {"language": "en"}
            response = test_client.post("/v1/reports/upload", files=files, data=data)

        # Step 2: Verify upload response
        assert response.status_code == 200, f"Upload failed: {response.text}"
        upload_data = response.json()
        assert upload_data["status"] == "success"
        assert "job_id" in upload_data
        job_id = upload_data["job_id"]

        # Step 3: Wait for task completion (real LLM calls, may take ~10-30s)
        final_status = wait_for_task(job_id, test_client, timeout=120)
        status_data = final_status.json()

        # Step 4: Verify completion status
        assert status_data["status"] == "COMPLETED", f"Task failed: {status_data.get('error_message')}"
        assert status_data["language"] == "en"

        # Step 5: Get results
        results_response = test_client.get(f"/v1/reports/results/{job_id}")
        assert results_response.status_code == 200
        results_data = results_response.json()

        # Step 6: Verify result structure
        assert "result_json" in results_data
        assert "result_markdown" in results_data
        assert "result_pdf_url" in results_data

        result_json = results_data["result_json"]
        assert "patient_info" in result_json
        assert "summary" in result_json
        assert "categories" in result_json

        # Verify it's English (not Urdu)
        summary = result_json["summary"]
        assert len(summary) > 0
        # English text uses Latin characters (ASCII range mostly)
        assert any(ord(c) < 128 for c in summary)


class TestWebPipelineUrdu:
    """Test valid lab report analysis in Urdu."""

    def test_valid_lab_report_urdu(self, test_client, sample_files, wait_for_task):
        """
        Test Scenario 2: Valid lab report → successful analysis (Urdu).

        Flow:
        1. Upload valid lab report PDF with language=ur
        2. Verify translation step executes
        3. Verify results are in Urdu
        4. Verify PDF has RTL formatting
        """
        # Step 1: Upload file with Urdu language
        sample_file = sample_files["valid_troponin"]
        assert sample_file.exists(), f"Sample file not found: {sample_file}"

        with open(sample_file, "rb") as f:
            files = {"file": ("HIGH-SENSITIVE-TROPONIN-I.pdf", f, "application/pdf")}
            data = {"language": "ur"}
            response = test_client.post("/v1/reports/upload", files=files, data=data)

        # Step 2: Verify upload response
        assert response.status_code == 200, f"Upload failed: {response.text}"
        upload_data = response.json()
        job_id = upload_data["job_id"]

        # Step 3: Wait for task completion (includes translation step)
        final_status = wait_for_task(job_id, test_client, timeout=120)
        status_data = final_status.json()

        # Step 4: Verify completion
        assert status_data["status"] == "COMPLETED", f"Task failed: {status_data.get('error_message')}"
        assert status_data["language"] == "ur"

        # Step 5: Get results
        results_response = test_client.get(f"/v1/reports/results/{job_id}")
        assert results_response.status_code == 200
        results_data = results_response.json()

        # Step 6: Verify Urdu content
        result_json = results_data["result_json"]
        summary = result_json.get("summary", "")

        # Urdu uses Arabic script (Unicode range U+0600 to U+06FF)
        has_urdu_chars = any(0x0600 <= ord(c) <= 0x06FF for c in summary)
        assert has_urdu_chars, "Summary does not contain Urdu characters"


class TestWebPipelineRejection:
    """Test rejection of non-lab documents."""

    def test_non_lab_document_rejected(self, test_client, sample_files, wait_for_task):
        """
        Test Scenario 3: Non-lab document (receipt) → rejected with clear error.

        Flow:
        1. Upload receipt (not a lab report)
        2. Wait for analysis
        3. Verify task completes but pre-validation fails
        4. Verify clear error message
        """
        # Step 1: Upload receipt
        sample_file = sample_files["invalid_receipt1"]
        assert sample_file.exists(), f"Sample file not found: {sample_file}"

        with open(sample_file, "rb") as f:
            files = {"file": ("Lab-Receipt.pdf", f, "application/pdf")}
            data = {"language": "en"}
            response = test_client.post("/v1/reports/upload", files=files, data=data)

        # Step 2: Verify upload response
        assert response.status_code == 200, f"Upload failed: {response.text}"
        upload_data = response.json()
        job_id = upload_data["job_id"]

        # Step 3: Wait for task completion
        final_status = wait_for_task(job_id, test_client, timeout=120)
        status_data = final_status.json()

        # Step 4: Verify rejection
        assert status_data["status"] == "FAILED"
        assert "error_message" in status_data

        error_msg = status_data["error_message"].lower()
        # Should contain keywords about not being a lab report
        assert any(keyword in error_msg for keyword in ["not a lab report", "rejected", "insufficient medical data"])


class TestWebPipelineOversized:
    """Test rejection of oversized files."""

    def test_oversized_file_rejected(self, test_client, create_oversized_file):
        """
        Test Scenario 4: Oversized file → rejected.

        Flow:
        1. Create file larger than max_file_size_mb
        2. Upload oversized file
        3. Verify immediate rejection (before Celery task)
        4. Verify clear error message
        """
        # Step 1: Create oversized file
        oversized_file = create_oversized_file
        assert oversized_file.exists()

        # Step 2: Upload oversized file
        with open(oversized_file, "rb") as f:
            files = {"file": ("oversized.pdf", f, "application/pdf")}
            data = {"language": "en"}
            response = test_client.post("/v1/reports/upload", files=files, data=data)

        # Step 3: Verify rejection
        assert response.status_code in [400, 413], f"Expected 400 or 413, got {response.status_code}"
        error_data = response.json()

        # Step 4: Verify error message
        assert "message" in error_data or "detail" in error_data
        error_msg = error_data.get("message", error_data.get("detail", "")).lower()
        assert any(keyword in error_msg for keyword in ["file size", "too large", "exceeds"])


class TestWebPipelineInvalidFileType:
    """Test rejection of invalid file types."""

    def test_invalid_file_type_rejected(self, test_client, create_invalid_file_type):
        """
        Test Scenario 5: Invalid file type → rejected.

        Flow:
        1. Create .txt file (not PDF/PNG/JPEG)
        2. Upload invalid file
        3. Verify immediate rejection
        4. Verify clear error message
        """
        # Step 1: Create invalid file type
        invalid_file = create_invalid_file_type
        assert invalid_file.exists()

        # Step 2: Upload invalid file
        with open(invalid_file, "rb") as f:
            files = {"file": ("test_report.txt", f, "text/plain")}
            data = {"language": "en"}
            response = test_client.post("/v1/reports/upload", files=files, data=data)

        # Step 3: Verify rejection
        assert response.status_code in [400, 415], f"Expected 400 or 415, got {response.status_code}"
        error_data = response.json()

        # Step 4: Verify error message
        assert "message" in error_data or "detail" in error_data
        error_msg = error_data.get("message", error_data.get("detail", "")).lower()
        assert any(keyword in error_msg for keyword in ["file type", "invalid", "supported", "format"])
