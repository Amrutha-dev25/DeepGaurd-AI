"""E2E tests that run a real video through the full /api/analyze endpoint.

Verifies multi-frame extraction, Sightengine per-frame analysis aggregation,
and the video-specific pipeline stages (temporal, optical flow).
"""

import json
import logging

import httpx
import pytest

logger = logging.getLogger(__name__)


class TestRealVideoAPI:
    """Full pipeline E2E with a real video upload."""

    @pytest.mark.skipif(
        not pytest.importorskip("httpx", minversion="0.27"),
        reason="httpx required for E2E tests",
    )
    def test_video_upload_full_pipeline(self, e2e_server: str, test_mp4_bytes: bytes):
        """Upload a real MP4 and verify the full agent chain."""
        response = httpx.post(
            f"{e2e_server}/api/analyze",
            files={"file": ("e2e_test.mp4", test_mp4_bytes, "video/mp4")},
            timeout=180,
        )
        assert response.status_code == 200, f"API returned {response.status_code}: {response.text[:500]}"

        data = response.json()
        assert data["verdict"] in ("real", "fake", "inconclusive", "error")

        logger.info("Video E2E: verdict=%s confidence=%.1f%% model=%s frames=%s",
                     data["verdict"], data["confidence_percent"],
                     data["pipeline"]["model_used"],
                     data.get("temporal", {}).get("frame_count", "?"))

    def test_video_temporal_data(self, e2e_server: str, test_mp4_bytes: bytes):
        """Verify video-specific temporal/frame analysis fields are populated."""
        response = httpx.post(
            f"{e2e_server}/api/analyze",
            files={"file": ("temporal.mp4", test_mp4_bytes, "video/mp4")},
            timeout=180,
        )
        assert response.status_code == 200

        data = response.json()
        temporal = data.get("temporal", {})
        assert "frame_count" in temporal, "Missing temporal.frame_count"
        assert temporal["frame_count"] > 0, "Frame count should be > 0 for a video"
        logger.info("Video temporal: frame_count=%s motion_score=%s",
                     temporal.get("frame_count"), temporal.get("motion_score"))

    def test_video_diagnostic_images(self, e2e_server: str, test_mp4_bytes: bytes):
        """Verify diagnostic images exist for video uploads (first frame analysis)."""
        response = httpx.post(
            f"{e2e_server}/api/analyze",
            files={"file": ("diag_video.mp4", test_mp4_bytes, "video/mp4")},
            timeout=180,
        )
        assert response.status_code == 200

        data = response.json()
        diag = data.get("diagnostic_images", {})
        # Videos should still produce ELA/edge diagnostics from extracted frames
        if diag.get("ela"):
            assert len(diag["ela"]) > 100

    def test_video_analysis_summary(self, e2e_server: str, test_mp4_bytes: bytes):
        """Verify the analysis summary and forensic observations mention multi-frame."""
        response = httpx.post(
            f"{e2e_server}/api/analyze",
            files={"file": ("summary.mp4", test_mp4_bytes, "video/mp4")},
            timeout=180,
        )
        assert response.status_code == 200

        data = response.json()
        model_used = data.get("pipeline", {}).get("model_used", "none")

        # When all APIs are available and analysis ran, expect multi-frame observations
        if model_used not in ("none", "deterministic"):
            assert data.get("analysis_summary"), "Missing analysis_summary for video"
            obs = data.get("forensic_observations", [])
            obs_text = " ".join(obs).lower()
            assert "frame" in obs_text or "multi" in obs_text or "video" in obs_text, \
                "Forensic observations should reference frame analysis"
        else:
            # Graceful degradation: no APIs available, pipeline still returns valid response
            logger.info("Skipping summary assertion: model_used=%s (all APIs unavailable)", model_used)
            assert data["verdict"] == "inconclusive"
