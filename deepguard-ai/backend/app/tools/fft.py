"""FFT (frequency spectrum) analysis tool — detects frequency-domain anomalies."""

import os
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
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


def analyze_fft(file_path: str) -> dict[str, Any]:
    target = file_path
    tmp_path: str | None = None
    if Path(file_path).suffix.lower() in _VIDEO_EXT:
        tmp_path = _first_frame_jpeg(file_path)
        target = tmp_path
    try:
        img = cv2.imread(target, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"fft_mean": 0.0, "fft_std": 0.0, "high_freq_ratio": 0.0, "evidence": "Could not read file for FFT analysis."}
        f = np.fft.fft2(img.astype(np.float32))
        fshift = np.fft.fftshift(f)
        magnitude = np.abs(fshift)
        fft_mean = float(magnitude.mean())
        fft_std = float(magnitude.std())
        h, w = magnitude.shape
        cy, cx = h // 2, w // 2
        low_radius = min(h, w) // 8
        low_mask = np.zeros_like(magnitude, dtype=bool)
        y, x = np.ogrid[:h, :w]
        low_mask[(y - cy)**2 + (x - cx)**2 <= low_radius**2] = True
        high_freq_energy = float(magnitude[~low_mask].sum())
        total_energy = float(magnitude.sum())
        high_freq_ratio = high_freq_energy / total_energy if total_energy > 0 else 0
        evidence = f"FFT mean={fft_mean:.2f}, high-freq ratio={high_freq_ratio:.4f}."
        return {
            "fft_mean": round(fft_mean, 4),
            "fft_std": round(fft_std, 4),
            "high_freq_ratio": round(high_freq_ratio, 6),
            "evidence": evidence,
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


fft_tool = FunctionTool(func=analyze_fft)
