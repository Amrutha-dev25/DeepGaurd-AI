"""JPEG artifact and compression analysis tools."""

import os
import tempfile
from pathlib import Path
from typing import Any

import cv2
from google.adk.tools import FunctionTool
from PIL import Image

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


def analyze_jpeg_artifacts(file_path: str) -> dict[str, Any]:
    target = file_path
    tmp_path: str | None = None
    if Path(file_path).suffix.lower() in _VIDEO_EXT:
        tmp_path = _first_frame_jpeg(file_path)
        target = tmp_path
    try:
        img = cv2.imread(target, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"block_boundary_ratio": 0.0, "evidence": "Could not read file for JPEG artifact analysis."}
        h, w = img.shape
        block_sum = 0.0
        non_block_sum = 0.0
        n = 0
        for y in range(8, h - 8, 8):
            for x in range(8, w - 8, 8):
                block_sum += abs(float(img[y, x]) - float(img[y - 1, x]))
                non_block_sum += abs(float(img[y + 1, x]) - float(img[y, x]))
                n += 1
        ratio = block_sum / (non_block_sum + 1e-8) if n else 1.0
        return {"block_boundary_ratio": round(ratio, 4), "evidence": f"JPEG block-boundary ratio is {ratio:.3f}."}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def analyze_compression(file_path: str) -> dict[str, Any]:
    target = file_path
    tmp_path: str | None = None
    if Path(file_path).suffix.lower() in _VIDEO_EXT:
        tmp_path = _first_frame_jpeg(file_path)
        target = tmp_path
    try:
        img = Image.open(target)
        q = 90
        if img.format == "JPEG":
            quant = getattr(img, "quantization", None)
            if quant:
                tbl_sum = sum(quant.get(0, [100] * 64))
                q = int(max(1, min(100, 100 - tbl_sum / 25)))
        return {"estimated_quality": q, "evidence": f"Estimated compression quality: {q}%."}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


jpeg_artifact_tool = FunctionTool(func=analyze_jpeg_artifacts)
compression_tool = FunctionTool(func=analyze_compression)
