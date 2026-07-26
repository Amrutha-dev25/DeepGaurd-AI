"""Clone detection tool — detects copy-move forgeries using ORB keypoint matching."""

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


def detect_clones(file_path: str) -> dict[str, Any]:
    target = file_path
    tmp_path: str | None = None
    if Path(file_path).suffix.lower() in _VIDEO_EXT:
        tmp_path = _first_frame_jpeg(file_path)
        target = tmp_path
    try:
        img = cv2.imread(target, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"clone_match_count": 0, "evidence": "Could not read file for clone detection."}
        if img.shape[0] > 1024 or img.shape[1] > 1024:
            img = cv2.resize(img, (1024, 1024))
        orb = cv2.ORB_create(nfeatures=500)
        kp, des = orb.detectAndCompute(img, None)
        matches = 0
        if des is not None and len(des) > 10:
            bf = cv2.BFMatcher(cv2.NORM_HAMMING)
            raw = bf.knnMatch(des, des, k=3)
            for m in raw:
                if len(m) >= 2 and m[0].distance < 0.3 * m[1].distance and m[0].queryIdx != m[0].trainIdx:
                    pt1, pt2 = kp[m[0].queryIdx].pt, kp[m[0].trainIdx].pt
                    if np.sqrt((pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2) > 35:
                        matches += 1
        evidence = f"Found {matches} suspicious duplicate keypoint match(es)." if matches > 5 else "No significant duplicate regions detected."
        return {"clone_match_count": matches, "evidence": evidence}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


clone_tool = FunctionTool(func=detect_clones)
