"""Forensic tool collector — imports from separate tool modules and provides the unified context.

Each tool module exports a raw function and a FunctionTool.
This module re-exports them all for backward compatibility.
"""

import hashlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import cv2
import imagehash
from google.adk.tools import FunctionTool
from PIL import Image

from .clone import clone_tool, detect_clones
from .ela import ela_tool, analyze_ela
from .exif import exif_tool, extract_exif
from .fft import fft_tool, analyze_fft
from .jpeg import compression_tool, jpeg_artifact_tool, analyze_compression, analyze_jpeg_artifacts
from .noise import noise_tool, analyze_noise
from .temporal import temporal_tool, analyze_temporal

logger = logging.getLogger(__name__)

_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _is_video(path: Path) -> bool:
    return path.suffix.lower() in _VIDEO_EXTENSIONS


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


def validate_upload(file_path: str) -> dict[str, Any]:
    p = Path(file_path)
    if not p.exists():
        return {"valid": False, "error": "File does not exist."}
    if p.stat().st_size == 0:
        return {"valid": False, "error": "File is empty (0 bytes)."}
    ext = p.suffix.lower()
    if ext not in _VIDEO_EXTENSIONS and ext not in _IMAGE_EXTENSIONS:
        return {"valid": False, "error": f"Unsupported file extension '{ext}'."}
    if _is_video(p):
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            cap.release()
            return {"valid": False, "error": "Video file is corrupted or unreadable."}
        cap.release()
    else:
        try:
            Image.open(file_path).verify()
        except Exception as exc:
            return {"valid": False, "error": f"Image file is corrupted: {exc}"}
    from app.config import settings
    size_mb = p.stat().st_size / (1024 * 1024)
    if size_mb > settings.max_file_size_mb:
        return {"valid": False, "error": f"File too large ({size_mb:.1f} MB; limit {settings.max_file_size_mb} MB)."}
    return {"valid": True}


def detect_faces(file_path: str) -> dict[str, Any]:
    target = file_path
    tmp_path: str | None = None
    if _is_video(Path(file_path)):
        tmp_path = _first_frame_jpeg(file_path)
        target = tmp_path
    try:
        img = cv2.imread(target)
        if img is None:
            return {"face_count": 0, "evidence": "Could not read file for face detection."}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)
        count = len(faces)
        return {"face_count": count, "face_locations": [list(map(int, f)) for f in faces], "evidence": f"Detected {count} face(s) in the media."}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def compute_hash(file_path: str) -> dict[str, Any]:
    sha = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            sha.update(chunk)
    sha_hex = sha.hexdigest()
    path = Path(file_path)
    if _is_video(path):
        phash_val = "n/a (video)"
    else:
        try:
            phash_val = str(imagehash.phash(Image.open(file_path)))
        except Exception:
            phash_val = "error"
    return {"sha256": sha_hex, "phash": phash_val, "evidence": f"SHA-256: {sha_hex[:16]}...  pHash: {phash_val}"}


router_tools = [
    FunctionTool(func=validate_upload),
    FunctionTool(func=detect_faces),
]

all_forensic_tools = [
    exif_tool,
    ela_tool,
    noise_tool,
    jpeg_artifact_tool,
    clone_tool,
    compression_tool,
    fft_tool,
    temporal_tool,
]


def collect_forensic_context(file_path: str) -> dict[str, Any]:
    _cached_frame: str | None = None
    try:
        if _is_video(Path(file_path)):
            _cached_frame = _first_frame_jpeg(file_path)
            fp = _cached_frame
            logger.info("Video frame extracted once to %s, shared across %d tools", fp, 6)
        else:
            fp = file_path
        return {
            "exif": extract_exif(fp),
            "ela": analyze_ela(fp),
            "noise": analyze_noise(fp),
            "jpeg_artifacts": analyze_jpeg_artifacts(fp),
            "clones": detect_clones(fp),
            "faces": detect_faces(fp),
            "compression": analyze_compression(fp),
            "hash": compute_hash(file_path),
            "frames": analyze_temporal(file_path),
            "fft": analyze_fft(fp),
        }
    finally:
        if _cached_frame and os.path.exists(_cached_frame):
            try:
                os.unlink(_cached_frame)
            except Exception:
                pass
