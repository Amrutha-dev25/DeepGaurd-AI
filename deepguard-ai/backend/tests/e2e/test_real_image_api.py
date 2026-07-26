"""E2E tests that run a real image through the full /api/analyze endpoint.

Requires real API keys in .env (SIGHTENGINE_API_USER/SECRET, GROQ_API_KEY, etc.).
If Sightengine is unconfigured, the pipeline tests the fallback chain instead.
"""

import json
import logging

import httpx
import pytest

logger = logging.getLogger(__name__)


def _check_response_shape(response: dict) -> None:
    """Assert the API response has all required fields with valid shapes."""
    # Top-level fields
    assert "verdict" in response, "Missing verdict"
    assert response["verdict"] in ("real", "fake", "inconclusive", "error"), \
        f"Unexpected verdict: {response['verdict']}"
    assert "confidence_percent" in response
    assert isinstance(response["confidence_percent"], (int, float))
    assert 0 <= response["confidence_percent"] <= 100

    # Forensic context sections
    for section in ("ela", "exif", "hash", "noise", "compression", "fft"):
        assert section in response, f"Missing {section}"

    # Diagnostic images
    assert "diagnostic_images" in response
    diag = response["diagnostic_images"]
    for key in ("ela", "edges_canny", "fft"):
        if diag.get(key):
            # If present, must be valid base64
            assert isinstance(diag[key], str)
            assert len(diag[key]) > 0

    # Anomaly regions
    assert "anomaly_regions" in response
    assert isinstance(response["anomaly_regions"], list)

    # Pipeline info
    assert "pipeline" in response
    pipe = response["pipeline"]
    assert "model_used" in pipe
    assert "pipeline_time_seconds" in pipe
    assert isinstance(pipe["pipeline_time_seconds"], (int, float))

    # Agent logs
    assert "agent_logs" in response
    assert isinstance(response["agent_logs"], list)
    for log_entry in response["agent_logs"]:
        assert "agent" in log_entry
        assert "latency_seconds" in log_entry

    # Analysis fields
    assert "analysis_summary" in response
    assert isinstance(response["analysis_summary"], str)
    assert "forensic_observations" in response
    assert isinstance(response["forensic_observations"], list)

    # Report text (optional but should exist for successful analysis)
    if response["verdict"] != "error":
        assert "report_text" in response, "Missing report_text"
        assert "report_markdown" in response, "Missing report_markdown"


class TestRealImageAPI:
    """Full pipeline E2E with a real image upload via the live API."""

    @pytest.mark.skipif(
        not pytest.importorskip("httpx", minversion="0.27"),
        reason="httpx required for E2E tests",
    )
    def test_image_upload_full_pipeline(self, e2e_server: str, test_jpeg_bytes: bytes):
        """Upload a real JPEG and verify the full agent chain produces correct output."""
        response = httpx.post(
            f"{e2e_server}/api/analyze",
            files={"file": ("e2e_test.jpg", test_jpeg_bytes, "image/jpeg")},
            timeout=120,
        )
        assert response.status_code == 200, f"API returned {response.status_code}: {response.text[:500]}"

        data = response.json()
        _check_response_shape(data)

        logger.info("Image E2E: verdict=%s confidence=%.1f%% model=%s",
                     data["verdict"], data["confidence_percent"],
                     data["pipeline"]["model_used"])

    def test_health_endpoint(self, e2e_server: str):
        """Verify the health endpoint works."""
        r = httpx.get(f"{e2e_server}/health", timeout=5)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_ready(self, e2e_server: str):
        """Verify the readiness endpoint works."""
        r = httpx.get(f"{e2e_server}/health/ready", timeout=5)
        assert r.status_code == 200
        assert r.json()["status"] == "ready"

    def test_invalid_file_rejected(self, e2e_server: str):
        """Verify that a .exe file is rejected by guardrails."""
        response = httpx.post(
            f"{e2e_server}/api/analyze",
            files={"file": ("virus.exe", b"MZ\x90\x00" * 100, "application/x-msdownload")},
            timeout=10,
        )
        assert response.status_code == 400

    def test_diagnostic_images_present(self, e2e_server: str, test_jpeg_bytes: bytes):
        """Verify diagnostic_images contain base64 data for a real upload."""
        response = httpx.post(
            f"{e2e_server}/api/analyze",
            files={"file": ("diag_test.jpg", test_jpeg_bytes, "image/jpeg")},
            timeout=120,
        )
        assert response.status_code == 200
        data = response.json()
        diag = data.get("diagnostic_images", {})
        # At minimum, ELA diagnostic should be present
        assert "ela" in diag, "ELA diagnostic missing"
        if diag["ela"]:
            assert len(diag["ela"]) > 100, "ELA base64 suspiciously short"
            assert diag["ela"] != "not_applicable", "ELA should be computed, not hardcoded"
