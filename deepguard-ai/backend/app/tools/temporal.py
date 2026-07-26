"""Temporal analysis tool — video frame consistency, brightness, and motion analysis."""

from pathlib import Path
from typing import Any

import cv2
from google.adk.tools import FunctionTool

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi"}


def analyze_temporal(file_path: str) -> dict[str, Any]:
    ext = Path(file_path).suffix.lower()
    if ext in _IMAGE_EXTENSIONS:
        img = cv2.imread(file_path)
        if img is None:
            return {"frame_count": 0, "average_brightness": 0.0, "motion_score": 0.0, "evidence": "Could not read image."}
        brightness = float(img.mean())
        return {
            "frame_count": 1,
            "average_brightness": round(brightness, 2),
            "motion_score": 0.0,
            "evidence": f"Single image — average brightness {brightness:.2f}.",
        }
    if ext not in _VIDEO_EXTENSIONS:
        return {"frame_count": 0, "average_brightness": 0.0, "motion_score": 0.0, "evidence": f"Unsupported format: {ext}"}
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        return {"frame_count": 0, "average_brightness": 0.0, "motion_score": 0.0, "evidence": "Could not open video."}
    total_brightness = 0.0
    count = 0
    prev_gray = None
    motion_scores: list[float] = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        total_brightness += float(frame.mean())
        count += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray).mean()
            motion_scores.append(float(diff))
        prev_gray = gray
    cap.release()
    avg_brightness = total_brightness / count if count else 0.0
    motion_score = float(sum(motion_scores)) / len(motion_scores) if motion_scores else 0.0
    return {
        "frame_count": count,
        "average_brightness": round(avg_brightness, 2),
        "motion_score": round(motion_score, 4),
        "evidence": f"Video — {count} frame(s), brightness={avg_brightness:.2f}, motion={motion_score:.2f}.",
    }


temporal_tool = FunctionTool(func=analyze_temporal)
