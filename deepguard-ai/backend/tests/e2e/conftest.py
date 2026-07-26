"""E2E test fixtures — starts a live test server and provides test images/videos."""

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest

logger = logging.getLogger(__name__)

SERVER_PORT = 18800
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"
_BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
_PROJECT_DIR = _BASE_DIR.parent  # deepguard-ai/


def _make_test_jpeg(width: int = 640, height: int = 480) -> bytes:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = (128, 128, 128)
    cv2.rectangle(img, (50, 50), (width - 50, height - 50), (200, 100, 50), -1)
    cv2.putText(img, "E2E TEST", (width // 3, height // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    ret, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buf.tobytes()


def _make_test_mp4(duration_sec: int = 3, fps: int = 10, width: int = 320, height: int = 240) -> bytes:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    out = cv2.VideoWriter(tmp_path, fourcc, fps, (width, height))
    for i in range(duration_sec * fps):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        color = (i * 20 % 256, i * 30 % 256, i * 40 % 256)
        frame[:, :] = color
        cv2.putText(frame, f"frame{i}", (10, height // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255 - color[0], 255 - color[1], 255 - color[2]), 1)
        out.write(frame)
    out.release()
    with open(tmp_path, "rb") as f:
        data = f.read()
    os.unlink(tmp_path)
    return data


@pytest.fixture(scope="session")
def test_jpeg_bytes() -> bytes:
    return _make_test_jpeg()


@pytest.fixture(scope="session")
def test_mp4_bytes() -> bytes:
    return _make_test_mp4()


@pytest.fixture(scope="session")
def e2e_server():
    """Start the FastAPI server on a random port for the test session."""
    env = os.environ.copy()
    env["LOG_LEVEL"] = "WARNING"

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.api:app",
         "--host", "127.0.0.1", "--port", str(SERVER_PORT),
         "--log-level", "warning"],
        cwd=str(_BASE_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for server to be ready
    for attempt in range(30):
        try:
            r = httpx.get(f"{SERVER_URL}/health", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        proc.terminate()
        proc.wait()
        raise RuntimeError("E2E test server failed to start")

    yield SERVER_URL

    proc.terminate()
    proc.wait(timeout=5)
