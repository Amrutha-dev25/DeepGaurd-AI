# ruff: noqa
"""
ml_models.py — ML Ensemble Deepfake Detection for DeepGuard AI
===============================================================

This module provides a resilient, multi-model ensemble for deepfake and
media authenticity detection.  Each detector is wrapped in its own
try/except so that a missing GPU, unavailable model weight, or optional
dependency does NOT crash the entire pipeline — the detector simply
contributes a neutral 0.5 score and records an error note.

Exported symbol:
    run_ensemble(file_path: str) -> dict
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np

# Optional heavy deps — imported lazily so the module loads even when they
# are unavailable (e.g., in a lightweight test environment).
try:
    from PIL import Image as _PILImage
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".avi"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def _is_video(path: str) -> bool:
    return Path(path).suffix.lower() in _VIDEO_EXTS


def _load_image_array(file_path: str) -> np.ndarray | None:
    """Return a BGR ndarray for images; first frame for videos. None on failure."""
    if _is_video(file_path):
        cap = cv2.VideoCapture(file_path)
        ret, frame = cap.read()
        cap.release()
        return frame if ret else None
    img = cv2.imread(file_path)
    return img


def _array_to_pil(arr: np.ndarray):
    """Convert BGR ndarray to PIL RGB Image."""
    if not _PIL_OK:
        return None
    rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    return _PILImage.fromarray(rgb)


# ─────────────────────────────────────────────────────────────────────────────
# Individual detectors
# Each returns a float in [0.0, 1.0] where 1.0 = "definitely deepfake"
# ─────────────────────────────────────────────────────────────────────────────


def _detect_ela_score(file_path: str) -> tuple[float, str | None]:
    """
    ELA-based detector: re-compress at low quality and measure normalised diff.
    A larger diff → higher manipulation probability.
    """
    try:
        arr = _load_image_array(file_path)
        if arr is None:
            return 0.5, "could not load image"
        if not _PIL_OK:
            return 0.5, "Pillow not available"
        pil = _array_to_pil(arr)
        buf = io.BytesIO()
        pil.save(buf, format="JPEG", quality=75)
        buf.seek(0)
        compressed = _PILImage.open(buf).convert("RGB")
        orig_arr = np.array(pil, dtype=np.float32)
        comp_arr = np.array(compressed, dtype=np.float32)
        diff = np.abs(orig_arr - comp_arr)
        # Normalise: max possible diff per channel = 255
        score = float(np.mean(diff) / 255.0)
        # Clamp to [0, 1] and scale to make moderate diffs more visible
        score = min(1.0, score * 10.0)
        return score, None
    except Exception as exc:
        return 0.5, str(exc)


def _detect_frequency_anomaly(file_path: str) -> tuple[float, str | None]:
    """
    DCT/FFT frequency-domain detector.
    GAN-generated images often have characteristic high-frequency artefacts.
    """
    try:
        arr = _load_image_array(file_path)
        if arr is None:
            return 0.5, "could not load image"
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        # 2D FFT magnitude spectrum
        fft = np.fft.fft2(gray)
        fft_shift = np.fft.fftshift(fft)
        magnitude = np.abs(fft_shift)
        # Compare high-frequency energy to low-frequency energy
        h, w = magnitude.shape
        cy, cx = h // 2, w // 2
        radius = min(h, w) // 8
        y, x = np.ogrid[:h, :w]
        mask_low = (y - cy) ** 2 + (x - cx) ** 2 <= radius ** 2
        low_energy = float(magnitude[mask_low].mean())
        high_energy = float(magnitude[~mask_low].mean())
        if low_energy == 0:
            return 0.5, "zero low-frequency energy"
        ratio = high_energy / (low_energy + 1e-9)
        # Typical natural images: ratio ~ 0.1–0.5; GAN images often > 0.6
        score = min(1.0, ratio / 1.2)
        return score, None
    except Exception as exc:
        return 0.5, str(exc)


def _detect_noise_inconsistency(file_path: str) -> tuple[float, str | None]:
    """
    Noise pattern inconsistency detector.
    Splice edits and GAN faces often have localised noise variance mismatches.
    """
    try:
        arr = _load_image_array(file_path)
        if arr is None:
            return 0.5, "could not load image"
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        # Local variance map using a sliding window via integral images
        blur = cv2.GaussianBlur(gray, (7, 7), 0)
        residual = gray - blur
        h, w = residual.shape
        # Divide into 4×4 blocks and measure variance per block
        block_h, block_w = max(1, h // 4), max(1, w // 4)
        variances = []
        for row in range(4):
            for col in range(4):
                patch = residual[
                    row * block_h:(row + 1) * block_h,
                    col * block_w:(col + 1) * block_w,
                ]
                variances.append(float(np.var(patch)))
        if not variances:
            return 0.5, "no patches"
        var_array = np.array(variances)
        # Coefficient of variation of block variances
        mean_var = float(var_array.mean())
        std_var = float(var_array.std())
        cv = std_var / (mean_var + 1e-9)
        # High CV → inconsistent noise → suspicious
        score = min(1.0, cv / 3.0)
        return score, None
    except Exception as exc:
        return 0.5, str(exc)


def _detect_face_asymmetry(file_path: str) -> tuple[float, str | None]:
    """
    Facial symmetry detector using OpenCV Haar cascade.
    Many deepfakes exhibit unnatural facial asymmetry.
    Falls back to neutral score if no face is detected.
    """
    try:
        arr = _load_image_array(file_path)
        if arr is None:
            return 0.5, "could not load image"
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        if len(faces) == 0:
            return 0.5, "no face detected"
        # Use the largest face
        x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        face_region = gray[y:y + fh, x:x + fw]
        if face_region.size == 0:
            return 0.5, "empty face region"
        # Compare left half to mirrored right half
        mid = fw // 2
        left = face_region[:, :mid].astype(np.float32)
        right = np.fliplr(face_region[:, mid:mid + mid]).astype(np.float32)
        min_w = min(left.shape[1], right.shape[1])
        diff = np.abs(left[:, :min_w] - right[:, :min_w])
        asymmetry = float(diff.mean()) / 255.0
        # Scale: > 0.3 asymmetry is highly suspicious
        score = min(1.0, asymmetry / 0.3)
        return score, None
    except Exception as exc:
        return 0.5, str(exc)


def _detect_compression_artifacts(file_path: str) -> tuple[float, str | None]:
    """
    JPEG block-artifact detector.
    Edited/generated images often have inconsistent 8×8 DCT block boundaries.
    """
    try:
        arr = _load_image_array(file_path)
        if arr is None:
            return 0.5, "could not load image"
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        h, w = gray.shape
        # Compute horizontal and vertical differences at 8-pixel boundaries
        block_size = 8
        h_diffs, v_diffs = [], []
        for col in range(block_size, w, block_size):
            diff = np.abs(gray[:, col].astype(float) - gray[:, col - 1].astype(float))
            h_diffs.append(float(diff.mean()))
        for row in range(block_size, h, block_size):
            diff = np.abs(gray[row, :].astype(float) - gray[row - 1, :].astype(float))
            v_diffs.append(float(diff.mean()))
        if not h_diffs or not v_diffs:
            return 0.5, "image too small for block analysis"
        boundary_mean = np.mean(h_diffs + v_diffs)
        # Interior pixel differences (non-boundary)
        interior_diff = float(np.abs(np.diff(gray, axis=1)).mean())
        if interior_diff == 0:
            return 0.5, "zero interior variance"
        ratio = boundary_mean / (interior_diff + 1e-9)
        # High ratio → strong block boundaries → suspicious
        score = min(1.0, max(0.0, (ratio - 1.0) / 2.0))
        return score, None
    except Exception as exc:
        return 0.5, str(exc)


# ─────────────────────────────────────────────────────────────────────────────
# DeepFace wrapper (optional — heavyweight dependency)
# ─────────────────────────────────────────────────────────────────────────────


def _detect_with_deepface(file_path: str) -> tuple[float, str | None]:
    """
    Use DeepFace face attribute analysis as a proxy signal.
    A real face with normal attributes → lower score.
    Falls back to 0.5 if DeepFace is not installed or fails.
    """
    try:
        import deepface.DeepFace as DeepFace  # type: ignore
        result = DeepFace.analyze(
            img_path=file_path,
            actions=["emotion", "age", "gender"],
            enforce_detection=False,
            silent=True,
        )
        if isinstance(result, list):
            result = result[0]
        # Use dominant emotion confidence as a proxy — deepfakes often look "neutral"
        emotions = result.get("emotion", {})
        if emotions:
            neutral_pct = float(emotions.get("neutral", 0))
            # Extremely high neutral % is a weak deepfake signal
            score = min(1.0, neutral_pct / 100.0 * 0.6)
        else:
            score = 0.5
        return score, None
    except ImportError:
        return 0.5, "deepface not installed"
    except Exception as exc:
        return 0.5, str(exc)


# ─────────────────────────────────────────────────────────────────────────────
# Ensemble aggregator
# ─────────────────────────────────────────────────────────────────────────────

# Detector name → (function, weight)
_DETECTORS: dict[str, tuple[Any, float]] = {
    "ela":                  (_detect_ela_score,             0.30),
    "frequency_anomaly":    (_detect_frequency_anomaly,     0.20),
    "noise_inconsistency":  (_detect_noise_inconsistency,   0.20),
    "face_asymmetry":       (_detect_face_asymmetry,        0.15),
    "compression_artifacts":(_detect_compression_artifacts, 0.10),
    "deepface":             (_detect_with_deepface,         0.05),
}


def run_ensemble(file_path: str) -> dict[str, Any]:
    """
    Run all ML detectors on *file_path* and return a combined verdict dict.

    Returns
    -------
    dict with keys:
        final_confidence   float  — weighted ensemble score in [0.0, 1.0]
        confidence_percent float  — same score scaled to 0–100
        verdict            str    — 'real' | 'suspicious' | 'fake' | 'unknown'
        model_results      dict   — per-detector {'score': float, 'error': str|None}
        weights_used       dict   — per-detector weight
        error              str    — present only if ALL detectors failed
    """
    if not os.path.isfile(file_path):
        return {
            "final_confidence": 0.5,
            "confidence_percent": 50.0,
            "verdict": "unknown",
            "model_results": {},
            "weights_used": {},
            "error": f"File not found: {file_path}",
        }

    model_results: dict[str, dict] = {}
    weights_used: dict[str, float] = {}
    weighted_sum = 0.0
    total_weight = 0.0
    all_failed = True

    for name, (fn, weight) in _DETECTORS.items():
        score, err = fn(file_path)
        model_results[name] = {"score": round(score, 4), "error": err}
        weights_used[name] = weight
        if err is None:
            all_failed = False
        weighted_sum += score * weight
        total_weight += weight

    final_confidence = weighted_sum / total_weight if total_weight > 0 else 0.5

    if all_failed:
        verdict = "unknown"
    elif final_confidence >= 0.65:
        verdict = "fake"
    elif final_confidence >= 0.40:
        verdict = "suspicious"
    else:
        verdict = "real"

    result: dict[str, Any] = {
        "final_confidence": round(final_confidence, 4),
        "confidence_percent": round(final_confidence * 100, 2),
        "verdict": verdict,
        "model_results": model_results,
        "weights_used": weights_used,
    }
    if all_failed:
        result["error"] = "All detectors failed — scores are neutral defaults"
    return result
