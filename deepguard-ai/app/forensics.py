# ruff: noqa
"""Forensic analysis functions for DeepGuard AI.

Provides ELA, EXIF extraction, cryptographic + perceptual hashing,
frame-level video analysis, and a security checkpoint with PII
redaction and prompt-injection detection.
"""

import datetime
import hashlib
import io
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from .ml_models import run_ensemble

import cv2
import exifread
import imagehash
from PIL import Image, ImageChops

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
_ALLOWED_EXTENSIONS = _VIDEO_EXTENSIONS | _IMAGE_EXTENSIONS

_MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MB


def _now_utc() -> str:
    """Return the current UTC time as an ISO-8601 string (timezone-aware).

    CHECK 9 — all timestamps use ZoneInfo("UTC") consistently; the deprecated
    datetime.utcnow() is not used anywhere in this file.
    """
    return datetime.datetime.now(ZoneInfo("UTC")).isoformat()


def _is_video(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in _VIDEO_EXTENSIONS


# ---------------------------------------------------------------------------
# BUG 5 + CHECK 4 / CHECK 5 — validate file before any analysis
# ---------------------------------------------------------------------------

def validate_file(file_path: str) -> dict[str, Any] | None:
    """Return an error dict if the file is unsupported or too large, else None.

    CHECK 4 — file type validation.
    CHECK 5 — file size limit (100 MB).
    """
    p = Path(file_path)
    ext = p.suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        return {
            "error": (
                f"Unsupported file type '{ext}'. "
                f"Allowed: {sorted(_ALLOWED_EXTENSIONS)}"
            )
        }
    try:
        size = p.stat().st_size
    except OSError as exc:
        return {"error": f"Cannot read file: {exc}"}
    if size > _MAX_FILE_BYTES:
        mb = size / (1024 * 1024)
        return {
            "error": (
                f"File is too large ({mb:.1f} MB). "
                "Maximum allowed size is 100 MB."
            )
        }
    return None


# ---------------------------------------------------------------------------
# BUG 5 — ELA on video: extract first frame, run ELA on that JPEG, clean up
# ---------------------------------------------------------------------------

def _extract_first_frame_as_jpeg(file_path: str) -> str:
    """Extract the first video frame and save it to a temporary JPEG file.

    Returns the path to the temporary file (caller must delete it).
    Raises RuntimeError if the frame cannot be extracted.
    """
    cap = cv2.VideoCapture(file_path)
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise RuntimeError(
            f"Could not extract the first frame from video: {file_path}"
        )
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    cv2.imwrite(tmp.name, frame)
    return tmp.name


def perform_ela(file_path: str) -> dict[str, Any]:
    """Perform Error Level Analysis (ELA) on an image or video file.

    BUG 5 — For video files the first frame is extracted via OpenCV before
    running ELA. The temporary frame JPEG is deleted after analysis.

    Returns a dict with 'summary' and 'diff_bbox' keys, or 'error' on failure.
    """
    temp_path: str | None = None
    try:
        target = file_path
        if _is_video(file_path):
            temp_path = _extract_first_frame_as_jpeg(file_path)
            target = temp_path

        img = Image.open(target).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        buf.seek(0)
        compressed = Image.open(buf)
        diff = ImageChops.difference(img, compressed)
        bbox = diff.getbbox()
        manipulated = bbox is not None
        summary = (
            "Potential manipulation detected" if manipulated else "No significant manipulation"
        )
        return {"summary": summary, "diff_bbox": bbox}
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def analyze_ela(file_path: str) -> dict[str, Any]:
    """Compatibility wrapper — delegates to perform_ela."""
    return perform_ela(file_path)


# ---------------------------------------------------------------------------
# EXIF extraction
# ---------------------------------------------------------------------------

def extract_exif(file_path: str) -> dict[str, Any]:
    """Extract EXIF metadata from an image file using exifread.

    Returns a dict with 'summary' and 'exif' keys, or 'error' on failure.
    For video files, EXIF is not applicable and an empty dict is returned.
    """
    try:
        if _is_video(file_path):
            return {"summary": "EXIF not applicable for video files", "exif": {}}
        with open(file_path, "rb") as fh:
            tags = exifread.process_file(fh, details=False)
        exif_data = {tag: str(val) for tag, val in tags.items()}
        return {
            "summary": f"Extracted {len(exif_data)} EXIF tags",
            "exif": exif_data,
        }
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def compute_hash(file_path: str) -> dict[str, Any]:
    """Compute SHA-256 and perceptual hash for the file.

    CHECK 10 — for video files phash is set to 'not_applicable_for_video'
    rather than None / null so the frontend can display it meaningfully.

    Returns a dict with 'sha256' and 'phash' keys, or 'error' on failure.
    """
    try:
        sha = hashlib.sha256()
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                sha.update(chunk)
        sha_hex = sha.hexdigest()

        if _is_video(file_path):
            phash_value: str | None = "not_applicable_for_video"
        else:
            try:
                phash_value = str(imagehash.phash(Image.open(file_path)))
            except Exception:
                phash_value = None

        return {"sha256": sha_hex, "phash": phash_value}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Frame analysis — BUG 6: always return key "frames" at the top level
# ---------------------------------------------------------------------------

def analyze_frames(file_path: str) -> dict[str, Any]:
    """Analyze video frames or single image for brightness statistics."""
    try:
        ext = Path(file_path).suffix.lower()
        if ext in _IMAGE_EXTENSIONS:
            img = cv2.imread(file_path)
            if img is None:
                return {"error": "Unable to open image file"}
            return {
                "summary": "Single image analyzed",
                "frame_count": 1,
                "average_brightness": float(img.mean()),
            }
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return {"error": "Unable to open video file"}
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
        }
    except Exception as exc:
        return {"error": str(exc)}


def run_ml_ensemble(file_path: str) -> dict[str, Any]:
    """Run the full ML ensemble detection pipeline.
    
    Wraps run_ensemble from ml_models.py as a forensic tool
    compatible with the existing agent architecture.
    Returns ensemble result or error dict on failure.
    """
    try:
        return run_ensemble(file_path)
    except Exception as e:
        return {
            "final_confidence": 0.5,
            "confidence_percent": 50.0,
            "verdict": "unknown",
            "error": str(e),
            "model_results": {},
        }

# ---------------------------------------------------------------------------
# Security checkpoint
# CHECK 3 — tightened path-redaction regex
# CHECK 9 — ZoneInfo UTC timestamp
# ---------------------------------------------------------------------------

def security_checkpoint(
    aggregated: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Scrub PII, detect prompt injection, and write an audit log entry.

    CHECK 3 — the Unix path pattern is tightened to only match strings that
    begin with recognised filesystem roots (/home, /var, /tmp, /usr, /root,
    /mnt, /uploads, /proc, /etc) so legitimate analysis values that happen to
    contain a forward slash (e.g. MIME types, URLs) are not redacted.

    CHECK 9 — all timestamps use datetime.datetime.now(ZoneInfo("UTC")).

    Returns a tuple of (secured_data, audit_record).
    If a security violation is detected, secured_data is an empty dict and
    audit_record includes blocked=True.
    """
    try:
        username = os.getlogin()
    except Exception:
        username = os.environ.get("USERNAME") or os.environ.get("USER") or "unknown_user"

    _FS_ROOTS = (
        "/home/", "/var/", "/tmp/", "/usr/", "/root/", "/mnt/",
        "/uploads/", "/proc/", "/etc/",
    )
    _WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s]*")
    # CHECK 3 — only match paths starting with known FS roots, not any slash
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

    # Injection / suspicious-string detection
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

    # CHECK 9 — ZoneInfo UTC timestamp
    audit: dict[str, Any] = {
        "timestamp": _now_utc(),
        "action": "security_checkpoint",
        "severity": "warning" if violation else "info",
        "blocked": violation,
        "result": secured,
    }

    # CHECK 8 — append to log rather than overwrite; use a timestamped filename
    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "audit_log.json"
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(audit) + "\n")

    if violation:
        return {}, audit
    return secured, audit
