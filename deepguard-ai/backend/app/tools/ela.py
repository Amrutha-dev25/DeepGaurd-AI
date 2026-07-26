"""Error Level Analysis tool — measures JPEG recompression artifacts."""

import io
import os
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from google.adk.tools import FunctionTool
from PIL import Image, ImageChops

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


def analyze_ela(file_path: str) -> dict[str, Any]:
    target = file_path
    tmp_path: str | None = None
    if Path(file_path).suffix.lower() in _VIDEO_EXT:
        tmp_path = _first_frame_jpeg(file_path)
        target = tmp_path
    try:
        img = Image.open(target).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        buf.seek(0)
        compressed = Image.open(buf)
        diff = ImageChops.difference(img, compressed)
        arr = np.array(diff)
        mean_diff = float(arr.mean())
        max_diff = float(arr.max())
        bbox = diff.getbbox()
        evidence = f"ELA mean difference {mean_diff:.3f}, max {max_diff:.3f}." if mean_diff > 1.8 else f"Compression artifacts are uniform (mean diff {mean_diff:.3f})."
        return {
            "mean_difference": round(mean_diff, 4),
            "max_difference": round(max_diff, 4),
            "diff_bbox": list(bbox) if bbox else None,
            "evidence": evidence,
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


ela_tool = FunctionTool(func=analyze_ela)
