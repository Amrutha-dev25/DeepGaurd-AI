# ruff: noqa
"""Forensic analysis functions for DeepGuard AI.

Provides standard forensic tools (ELA, EXIF, hashing, noise, JPEG artifacts,
clone detection, face detection, compression analysis) returning execution details.
"""

from app.ml_models import run_ml_ensemble
import datetime
import hashlib
import io
import json
import os
import re
import tempfile
import time
from functools import wraps
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import cv2
import exifread
import imagehash
import numpy as np
from PIL import Image, ImageChops

# ---------------------------------------------------------------------------
# Constants & Helpers
# ---------------------------------------------------------------------------

_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_ALLOWED_EXTENSIONS = _VIDEO_EXTENSIONS | _IMAGE_EXTENSIONS
_MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MB


def _now_utc() -> str:
    return datetime.datetime.now(ZoneInfo("UTC")).isoformat()


def _is_video(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in _VIDEO_EXTENSIONS


def validate_file(file_path: str) -> dict[str, Any] | None:
    """Return an error dict if the file is unsupported, corrupted, empty, or too large."""
    p = Path(file_path)
    if not p.exists():
        return {"error": "File does not exist."}
    if p.stat().st_size == 0:
        return {"error": "File is empty."}
    
    ext = p.suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        return {
            "error": (
                f"Unsupported file type '{ext}'. "
                f"Allowed: {sorted(_ALLOWED_EXTENSIONS)}"
            )
        }
    
    # Try basic readability check
    if _is_video(file_path):
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            cap.release()
            return {"error": "Video file is corrupted or unreadable."}
        cap.release()
    else:
        try:
            with Image.open(file_path) as img:
                img.verify()
        except Exception as exc:
            return {"error": f"Image file is corrupted or unreadable: {exc}"}

    size = p.stat().st_size
    if size > _MAX_FILE_BYTES:
        mb = size / (1024 * 1024)
        return {
            "error": (
                f"File is too large ({mb:.1f} MB). "
                "Maximum allowed size is 100 MB."
            )
        }
    return None


def run_tool_safely(name: str):
    """Decorator to standardise return structure and measure execution time."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                exec_time = time.perf_counter() - start_time
                if "status" not in result:
                    result["status"] = "success"
                result["execution_time"] = round(exec_time, 4)
                return result
            except Exception as e:
                exec_time = time.perf_counter() - start_time
                return {
                    "status": "failed",
                    "execution_time": round(exec_time, 4),
                    "measurements": {},
                    "confidence": 0.0,
                    "evidence": f"Error running {name}: {str(e)}",
                }
        return wrapper
    return decorator


def _extract_first_frame_as_jpeg(file_path: str) -> str:
    """Extract the first frame of a video for image-based analyses."""
    cap = cv2.VideoCapture(file_path)
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise RuntimeError(f"Could not extract frame from video: {file_path}")
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    cv2.imwrite(tmp.name, frame)
    return tmp.name


# ---------------------------------------------------------------------------
# Core Forensic Tools
# ---------------------------------------------------------------------------

@run_tool_safely("Metadata extraction")
def extract_exif(file_path: str) -> dict[str, Any]:
    """1. Extract EXIF metadata tags."""
    if _is_video(file_path):
        return {
            "status": "success",
            "measurements": {"tag_count": 0},
            "confidence": 0.5,
            "evidence": "EXIF metadata not applicable for video files.",
            "exif": {}
        }
    
    with open(file_path, "rb") as fh:
        tags = exifread.process_file(fh, details=False)
    exif_data = {tag: str(val) for tag, val in tags.items()}
    
    has_software_edit = any(
        k in exif_data and ("photoshop" in exif_data[k].lower() or "gimp" in exif_data[k].lower())
        for k in ["Image Software", "Software", "Image Processing"]
    )
    confidence = 0.9 if has_software_edit else 0.5
    evidence = (
        "EXIF metadata indicates image editing software was used."
        if has_software_edit else f"Extracted {len(exif_data)} EXIF tags."
    )
    
    return {
        "measurements": {"tag_count": len(exif_data), "software_modified": has_software_edit},
        "confidence": confidence,
        "evidence": evidence,
        "exif": exif_data
    }


@run_tool_safely("Error Level Analysis")
def analyze_ela(file_path: str) -> dict[str, Any]:
    """2. ELA analysis."""
    temp_path = None
    target = file_path
    if _is_video(file_path):
        temp_path = _extract_first_frame_as_jpeg(file_path)
        target = temp_path
        
    try:
        img = Image.open(target).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        buf.seek(0)
        compressed = Image.open(buf)
        diff = ImageChops.difference(img, compressed)
        
        # Calculate statistics
        diff_arr = np.array(diff)
        mean_diff = float(diff_arr.mean())
        max_diff = float(diff_arr.max())
        bbox = diff.getbbox()
        
        manipulated = mean_diff > 1.8
        confidence = round(min(0.5 + (mean_diff / 5.0), 0.95), 2) if manipulated else 0.4
        evidence = (
            f"Potential pixel-level compression anomalies detected (mean diff: {mean_diff:.2f})."
            if manipulated else "Compression level differences are uniform."
        )
        
        return {
            "measurements": {
                "mean_difference": round(mean_diff, 4),
                "max_difference": round(max_diff, 4),
                "diff_bbox": bbox
            },
            "confidence": confidence,
            "evidence": evidence,
            "summary": evidence,  # compatibility
            "diff_bbox": bbox
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def perform_ela(file_path: str) -> dict[str, Any]:
    return analyze_ela(file_path)


@run_tool_safely("Noise analysis")
def analyze_noise(file_path: str) -> dict[str, Any]:
    """3. Noise analysis using Laplacian operator variance."""
    target = file_path
    temp_path = None
    if _is_video(file_path):
        temp_path = _extract_first_frame_as_jpeg(file_path)
        target = temp_path
        
    try:
        img = cv2.imread(target, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError("Could not read image for noise analysis")
        
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        var = float(laplacian.var())
        
        # Spliced images often show regions of mismatched high-frequency noise variance
        evidence = f"Noise variance (Laplacian) is {var:.2f}."
        
        return {
            "measurements": {"noise_variance": round(var, 2)},
            "confidence": 0.7,
            "evidence": evidence
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@run_tool_safely("JPEG artifact analysis")
def analyze_jpeg_artifacts(file_path: str) -> dict[str, Any]:
    """4. JPEG grid artifact estimation."""
    target = file_path
    temp_path = None
    if _is_video(file_path):
        temp_path = _extract_first_frame_as_jpeg(file_path)
        target = temp_path
        
    try:
        img = cv2.imread(target, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError("Could not read image for JPEG artifact analysis")
        
        # Analyze blockiness along 8x8 boundaries
        h, w = img.shape
        block_diff = 0.0
        non_block_diff = 0.0
        count_block = 0
        count_non_block = 0
        
        for y in range(8, h - 8, 8):
            for x in range(8, w - 8, 8):
                # Diff across boundary vs internal diff
                block_diff += abs(float(img[y, x]) - float(img[y - 1, x]))
                non_block_diff += abs(float(img[y + 1, x]) - float(img[y, x]))
                count_block += 1
                count_non_block += 1
                
        ratio = block_diff / (non_block_diff + 1e-8)
        evidence = f"Block grid boundary difference ratio is {ratio:.3f}."
        
        return {
            "measurements": {"block_boundary_ratio": round(ratio, 4)},
            "confidence": 0.65,
            "evidence": evidence
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@run_tool_safely("Clone detection")
def detect_clones(file_path: str) -> dict[str, Any]:
    """5. Copy-move clone detection using ORB descriptor matching."""
    target = file_path
    temp_path = None
    if _is_video(file_path):
        temp_path = _extract_first_frame_as_jpeg(file_path)
        target = temp_path
        
    try:
        img = cv2.imread(target, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError("Could not read image for clone detection")
        
        # Downscale for performance
        if img.shape[0] > 1024 or img.shape[1] > 1024:
            img = cv2.resize(img, (1024, 1024))
            
        orb = cv2.ORB_create(nfeatures=500)
        kp, des = orb.detectAndCompute(img, None)
        
        clone_matches = 0
        if des is not None and len(des) > 10:
            # Match descriptors against themselves
            bf = cv2.BFMatcher(cv2.NORM_HAMMING)
            matches = bf.knnMatch(des, des, k=3)
            
            for m in matches:
                if len(m) >= 2:
                    m1, m2 = m[0], m[1]
                    # Exclude self matches and ensure high similarity
                    if m1.distance < 0.3 * m2.distance and m1.queryIdx != m1.trainIdx:
                        pt1 = kp[m1.queryIdx].pt
                        pt2 = kp[m1.trainIdx].pt
                        # Must be far apart to be considered clones
                        dist = np.sqrt((pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2)
                        if dist > 35:
                            clone_matches += 1
                            
        evidence = (
            f"Detected {clone_matches} suspicious duplicate keypoint matches (clones)."
            if clone_matches > 5 else "No significant duplicate regions detected."
        )
        
        return {
            "measurements": {"clone_matches_count": clone_matches},
            "confidence": 0.8 if clone_matches > 5 else 0.5,
            "evidence": evidence
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@run_tool_safely("Face detection")
def detect_faces(file_path: str) -> dict[str, Any]:
    """6. Face detection using OpenCV Haar Cascades."""
    target = file_path
    temp_path = None
    if _is_video(file_path):
        temp_path = _extract_first_frame_as_jpeg(file_path)
        target = temp_path
        
    try:
        img = cv2.imread(target)
        if img is None:
            raise ValueError("Could not read image for face detection")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        face_cascade = cv2.CascadeClassifier(cascade_path)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)
        
        evidence = f"Detected {len(faces)} faces in the media frame."
        
        return {
            "measurements": {"face_count": len(faces), "faces_bbox": [list(map(int, f)) for f in faces]},
            "confidence": 0.9,
            "evidence": evidence
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@run_tool_safely("Compression analysis")
def analyze_compression(file_path: str) -> dict[str, Any]:
    """7. Estimate compression profile and JPEG quality factor."""
    target = file_path
    temp_path = None
    if _is_video(file_path):
        temp_path = _extract_first_frame_as_jpeg(file_path)
        target = temp_path
        
    try:
        img = Image.open(target)
        # Check image format details
        q_estimate = 90
        if img.format == "JPEG":
            # Quantization tables are usually available in JPEG
            quant = getattr(img, "quantization", None)
            if quant:
                # Estimate QF based on quantization table sum
                tbl_sum = sum(quant.get(0, [100]*64))
                q_estimate = int(max(1, min(100, 100 - tbl_sum / 25)))
                
        evidence = f"Estimated compression/quality factor: {q_estimate}%."
        
        return {
            "measurements": {"quality_factor": q_estimate},
            "confidence": 0.8,
            "evidence": evidence
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@run_tool_safely("Hash generation")
def compute_hash(file_path: str) -> dict[str, Any]:
    """8. Cryptographic and perceptual hashing."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            sha.update(chunk)
    sha_hex = sha.hexdigest()

    if _is_video(file_path):
        phash_value = "not_applicable_for_video"
    else:
        try:
            phash_value = str(imagehash.phash(Image.open(file_path)))
        except Exception:
            phash_value = "error_computing_phash"

    return {
        "measurements": {"sha256": sha_hex, "phash": phash_value},
        "confidence": 1.0,
        "evidence": f"SHA-256: {sha_hex}. Perceptual Hash: {phash_value}",
        "sha256": sha_hex,  # compatibility
        "phash": phash_value
    }


# ---------------------------------------------------------------------------
# Frame brightness analysis
# ---------------------------------------------------------------------------

@run_tool_safely("Frame analysis")
def analyze_frames(file_path: str) -> dict[str, Any]:
    """Analyze video frames or single image for brightness statistics."""
    ext = Path(file_path).suffix.lower()
    if ext in _IMAGE_EXTENSIONS:
        img = cv2.imread(file_path)
        if img is None:
            raise ValueError("Unable to open image file")
        brightness = float(img.mean())
        return {
            "summary": "Single image analyzed",
            "frame_count": 1,
            "average_brightness": brightness,
            "measurements": {"frame_count": 1, "average_brightness": brightness},
            "confidence": 0.8,
            "evidence": f"Image brightness average is {brightness:.2f}."
        }
        
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        raise ValueError("Unable to open video file")
    
    frame_count_reported = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    total_brightness = 0.0
    frames_read = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        total_brightness += float(frame.mean())
        frames_read += 1
    cap.release()
    avg = total_brightness / frames_read if frames_read else 0.0
    
    return {
        "summary": f"Analyzed {frames_read} frames",
        "frame_count": frame_count_reported,
        "average_brightness": avg,
        "measurements": {"frame_count": frames_read, "average_brightness": avg},
        "confidence": 0.9,
        "evidence": f"Video analyzed ({frames_read} frames). Average brightness: {avg:.2f}."
    }


# ---------------------------------------------------------------------------
# Security checkpoint
# ---------------------------------------------------------------------------

def security_checkpoint(
    aggregated: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Scrub PII, detect prompt injection, and write an audit log entry."""
    try:
        username = os.getlogin()
    except Exception:
        username = os.environ.get("USERNAME") or os.environ.get("USER") or "unknown_user"

    _FS_ROOTS = (
        "/home/", "/var/", "/tmp/", "/usr/", "/root/", "/mnt/",
        "/uploads/", "/proc/", "/etc/",
    )
    _WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s]*")
    _UNIX_PATH_RE = re.compile(
        r"(?:" + "|".join(re.escape(r) for r in _FS_ROOTS) + r")[^\s]*"
    )
    _EMAIL_RE = re.compile(r"[\w.\-]+@[\w.\-]+")
    _USER_RE = re.compile(re.escape(username)) if username != "unknown_user" else None

    def redact_value(val: Any) -> Any:
        if isinstance(val, str):
            val = _WINDOWS_PATH_RE.sub("[REDACTED_PATH]", val)
            val = _UNIX_PATH_RE.sub("[REDACTED_PATH]", val)
            val = _EMAIL_RE.sub("[REDACTED_EMAIL]", val)
            if _USER_RE:
                val = _USER_RE.sub("[REDACTED_USER]", val)
            return val
        if isinstance(val, dict):
            return {k: redact_value(v) for k, v in val.items()}
        if isinstance(val, list):
            return [redact_value(v) for v in val]
        return val

    secured = redact_value(aggregated)

    _SUSPICIOUS = [
        "DROP TABLE", "--exec", "sudo", "rm -rf",
        "ignore previous instructions", "system prompt",
        "__import__", "eval(", "exec(",
    ]

    def contains_suspicious(val: Any) -> bool:
        if isinstance(val, str):
            low = val.lower()
            return any(s.lower() in low for s in _SUSPICIOUS)
        if isinstance(val, dict):
            return any(contains_suspicious(v) for v in val.values())
        if isinstance(val, list):
            return any(contains_suspicious(v) for v in val)
        return False

    violation = contains_suspicious(secured)

    audit: dict[str, Any] = {
        "timestamp": _now_utc(),
        "action": "security_checkpoint",
        "severity": "warning" if violation else "info",
        "blocked": violation,
        "result": secured,
    }

    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "audit_log.json"
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(audit) + "\n")

    if violation:
        return {}, audit
    return secured, audit

run_ensemble = run_ml_ensemble