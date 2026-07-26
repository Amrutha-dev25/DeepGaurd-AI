"""Noise analysis tool — measures Laplacian variance as noise indicator."""

import os
import tempfile
from pathlib import Path
from typing import Any

import cv2
from google.adk.tools import FunctionTool

_VIDEO_EXT = {".mp4", ".webm", ".mov", ".avi"}


def _first_frame_jpeg(file_path: str) -> str:
    cap = cv2.VideoCapture(file_path)
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise RuntimeError(f"Could not extract frame from video: {file_path}")
    fd, tmp_name = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    cv2.imwrite(tmp_name, frame)
    return tmp_name


def analyze_noise(file_path: str) -> dict[str, Any]:
    target = file_path
    tmp_path: str | None = None
    if Path(file_path).suffix.lower() in _VIDEO_EXT:
        tmp_path = _first_frame_jpeg(file_path)
        target = tmp_path
    try:
        img = cv2.imread(target, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"noise_variance": 0.0, "evidence": "Could not read file for noise analysis."}
        var = float(cv2.Laplacian(img, cv2.CV_64F).var())
        return {"noise_variance": round(var, 2), "evidence": f"Noise variance (Laplacian) is {var:.2f}."}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


noise_tool = FunctionTool(func=analyze_noise)
