"""Comprehensive file validation — runs before any agent.

Checks: extension, MIME type, magic bytes, file size, empty file, corruption,
malware signatures, path traversal, and zip bomb detection.
"""

import io
import struct
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from app.config import settings

# ── Executable / script magic bytes ────────────────────────────────────
_EXEC_MAGIC_PREFIXES = {
    b"MZ",                    # PE (Windows executable)
    b"\x7fELF",               # ELF (Linux executable)
    b"#!",                    # shebang script
    b"\xca\xfe\xba\xbe",      # Java class
    b"\xcf\xfa\xed\xfe",      # Mach-O (old)
    b"\xce\xfa\xed\xfe",      # Mach-O (new)
}

# ── Suspicious MIME types that should never be uploaded ─────────────────
_BLOCKED_MIME_TYPES = {
    "application/x-executable",
    "application/x-msdownload",
    "application/x-msdos-program",
    "application/x-sh",
    "application/x-bat",
    "application/x-python-code",
    "application/x-java-applet",
    "application/x-shellscript",
    "application/vnd.microsoft.portable-executable",
}

# ── Suspicious filename patterns ───────────────────────────────────────
_SUSPICIOUS_EXTENSIONS = {
    ".exe", ".com", ".bat", ".cmd", ".sh", ".ps1", ".vbs",
    ".js", ".jse", ".vbe", ".wsf", ".wsh", ".scr", ".pif",
    ".hta", ".msi", ".msp", ".reg", ".py", ".pl", ".rb",
}

# ── Path traversal patterns ────────────────────────────────────────────
_TRAVERSAL_PATTERNS = ["..", "~", "//", "\\\\"]


class ValidationResult:
    def __init__(self, valid: bool, error: str | None = None, details: dict[str, Any] | None = None):
        self.valid = valid
        self.error = error
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "error": self.error, "details": self.details}


def validate_extension(filename: str) -> ValidationResult:
    ext = Path(filename).suffix.lower()
    if ext in _SUSPICIOUS_EXTENSIONS:
        return ValidationResult(False, f"Blocked file extension: {ext}")
    return ValidationResult(True)


def validate_path_traversal(filename: str) -> ValidationResult:
    for pattern in _TRAVERSAL_PATTERNS:
        if pattern in filename:
            return ValidationResult(False, f"Path traversal detected: {pattern}")
    return ValidationResult(True)


def validate_file_size(file_size: int) -> ValidationResult:
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if file_size == 0:
        return ValidationResult(False, "File is empty (0 bytes).")
    if file_size > max_bytes:
        return ValidationResult(False, f"File exceeds {settings.max_file_size_mb} MB limit.")
    return ValidationResult(True)


def validate_magic_bytes(file_bytes: bytes) -> ValidationResult:
    if len(file_bytes) < 4:
        return ValidationResult(True)
    for prefix in _EXEC_MAGIC_PREFIXES:
        if file_bytes[:len(prefix)] == prefix:
            return ValidationResult(False, f"Executable/script magic bytes detected: {prefix[:4].hex()}")
    return ValidationResult(True)


def _is_zip_bomb(file_bytes: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            total_ratio = 0
            file_count = 0
            for info in zf.infolist():
                if info.file_size > 0 and info.compress_size > 0:
                    ratio = info.file_size / info.compress_size
                    total_ratio += ratio
                    file_count += 1
            if file_count > 0 and (total_ratio / file_count) > 100:
                return True
    except Exception:
        pass
    return False


def validate_not_zip_bomb(file_bytes: bytes) -> ValidationResult:
    if _is_zip_bomb(file_bytes):
        return ValidationResult(False, "Zip bomb detected.")
    return ValidationResult(True)


def validate_mime_type(mime: str) -> ValidationResult:
    if mime in _BLOCKED_MIME_TYPES:
        return ValidationResult(False, f"Blocked MIME type: {mime}")
    allowed = settings.allowed_mime_types
    if allowed and mime not in allowed:
        return ValidationResult(False, f"Unsupported MIME type: {mime}. Allowed: {allowed}")
    return ValidationResult(True)


def validate_image_integrity(file_bytes: bytes) -> ValidationResult:
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()
        return ValidationResult(True)
    except (UnidentifiedImageError, OSError, struct.error) as e:
        return ValidationResult(False, f"Image corruption detected: {e}")


def validate_video_integrity(file_path: str) -> ValidationResult:
    try:
        import cv2
        cap = cv2.VideoCapture(file_path)
        ok = cap.isOpened()
        cap.release()
        if not ok:
            return ValidationResult(False, "Video file cannot be opened — may be corrupt.")
        return ValidationResult(True)
    except Exception as e:
        return ValidationResult(False, f"Video validation error: {e}")


def validate_file(file_bytes: bytes, filename: str, mime: str | None, file_path: str | None = None) -> ValidationResult:
    results: list[ValidationResult] = [
        validate_extension(filename),
        validate_path_traversal(filename),
        validate_file_size(len(file_bytes)),
        validate_magic_bytes(file_bytes),
        validate_not_zip_bomb(file_bytes),
    ]
    if mime:
        results.append(validate_mime_type(mime))
    if mime and mime.startswith("image/"):
        results.append(validate_image_integrity(file_bytes))
    if mime and mime.startswith("video/") and file_path:
        results.append(validate_video_integrity(file_path))

    for r in results:
        if not r.valid:
            return r
    return ValidationResult(True)
