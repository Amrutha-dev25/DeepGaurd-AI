"""
DeepGuard AI — ML Ensemble Detection Layer

Contains 4 independent detectors:
  A. HuggingFace deepfake classifier (general)
  B. DCT Frequency analysis (GAN fingerprint detection)
  C. DeepFace face consistency checker (face swap detection)
  D. Temporal consistency checker (video only)

And one ensemble verdict engine that combines all results
using weighted averaging to produce a final real probability.
"""

import os
import cv2
import gc
import numpy as np
from pathlib import Path
from typing import Any
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Ensemble weights — must sum to 1.0
_WEIGHTS = {
    "huggingface": 0.35,
    "frequency":   0.25,
    "face":        0.25,
    "temporal":    0.15,
}

# Verdict thresholds
_THRESHOLD_FAKE       = 0.65
_THRESHOLD_SUSPICIOUS = 0.40

# ---------------------------------------------------------------------------
# Helper: extract frames from video
# ---------------------------------------------------------------------------

def _extract_frames(file_path: str, max_frames: int = 10) -> list[np.ndarray]:
    """Extract up to max_frames evenly spaced frames from a video."""
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        return []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return []
    indices = np.linspace(0, total - 1, min(max_frames, total), dtype=int)
    frames = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ret, frame = cap.read()
        if ret and frame is not None:
            frames.append(frame)
    cap.release()
    return frames


def _load_image(file_path: str) -> np.ndarray | None:
    """Load an image as a numpy array."""
    return cv2.imread(file_path)


def _is_video(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in _VIDEO_EXTENSIONS


# ---------------------------------------------------------------------------
# MODEL A — HuggingFace Deepfake Classifier
# ---------------------------------------------------------------------------

_hf_pipeline = None

def _get_hf_pipeline():
    """Lazy-load the HuggingFace pipeline once with CPU fallback and reuse it."""
    global _hf_pipeline
    if _hf_pipeline is None:
        try:
            import torch
            from transformers import pipeline
            device = 0 if torch.cuda.is_available() else -1
            try:
                _hf_pipeline = pipeline(
                    "image-classification",
                    model="prithivMLmods/Deep-Fake-Detector-v2-Model",
                    device=device,
                )
            except Exception as e:
                logger.warning(f"Could not load HuggingFace model on device {device}: {e}. Retrying on CPU.")
                _hf_pipeline = pipeline(
                    "image-classification",
                    model="prithivMLmods/Deep-Fake-Detector-v2-Model",
                    device=-1,
                )
        except Exception as e:
            logger.error(f"Failed to load HuggingFace model: {e}")
            _hf_pipeline = None
    return _hf_pipeline


def _hf_score_frame(frame_bgr: np.ndarray) -> float:
    """Score a single frame. Returns probability of being fake (0.0-1.0)."""
    pipe = _get_hf_pipeline()
    if pipe is None:
        raise RuntimeError("HuggingFace model pipeline is unavailable.")

    from PIL import Image
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(frame_rgb)
    results = pipe(pil_img)
    # Find the fake label score
    for r in results:
        label = r["label"].lower()
        if "fake" in label or "deepfake" in label or "manipulated" in label:
            return float(r["score"])
    # If no fake label found, return 1 - real score
    for r in results:
        label = r["label"].lower()
        if "real" in label or "authentic" in label:
            return 1.0 - float(r["score"])
    return 0.5


def detect_huggingface(file_path: str) -> dict[str, Any]:
    """Run HuggingFace deepfake classifier."""
    try:
        if _is_video(file_path):
            frames = _extract_frames(file_path, max_frames=5)
            if not frames:
                return {"confidence": 0.5, "signal": "Could not extract video frames", "model": "huggingface", "disabled": True}
            scores = [_hf_score_frame(f) for f in frames]
            avg_score = float(np.mean(scores))
            return {
                "confidence": avg_score,
                "signal": f"Analyzed {len(frames)} frames. Average fake probability: {avg_score:.2%}",
                "model": "huggingface",
                "frame_scores": [round(s, 3) for s in scores],
            }
        else:
            img = _load_image(file_path)
            if img is None:
                return {"confidence": 0.5, "signal": "Could not load image", "model": "huggingface", "disabled": True}
            score = _hf_score_frame(img)
            return {
                "confidence": score,
                "signal": f"Deepfake classifier probability: {score:.2%}",
                "model": "huggingface",
            }
    except Exception as e:
        logger.warning(f"HuggingFace detection disabled: {e}")
        return {"confidence": 0.5, "signal": f"HuggingFace model disabled: {str(e)}", "model": "huggingface", "disabled": True}


# ---------------------------------------------------------------------------
# MODEL B — DCT Frequency Analysis (GAN Fingerprint Detection)
# ---------------------------------------------------------------------------

def _dct_fake_score(frame_bgr: np.ndarray) -> float:
    """Compute a GAN detection score using DCT frequency analysis."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray = cv2.resize(gray, (256, 256))
    dct = cv2.dct(gray)
    dct_abs = np.abs(dct)
    dct_norm = dct_abs / (dct_abs.max() + 1e-8)

    h, w = dct_norm.shape
    low_freq  = dct_norm[:h//4,  :w//4]
    mid_freq  = dct_norm[h//4:h//2, w//4:w//2]
    high_freq = dct_norm[h//2:,  w//2:]

    mid_energy  = float(mid_freq.mean())
    high_energy = float(high_freq.mean())

    ratio = high_energy / (mid_energy + 1e-8)
    high_variance = float(np.var(high_freq))

    ratio_score = min(ratio / 0.8, 1.0)
    variance_score = min(high_variance * 50, 1.0)

    final_score = (ratio_score * 0.7) + (variance_score * 0.3)
    return float(np.clip(final_score, 0.0, 1.0))


def detect_frequency(file_path: str) -> dict[str, Any]:
    """Run DCT frequency analysis to detect GAN fingerprints."""
    try:
        if _is_video(file_path):
            frames = _extract_frames(file_path, max_frames=5)
            if not frames:
                return {"confidence": 0.5, "signal": "Could not extract frames", "model": "frequency", "disabled": True}
            scores = [_dct_fake_score(f) for f in frames]
            avg_score = float(np.mean(scores))
            return {
                "confidence": avg_score,
                "signal": f"Frequency analysis across {len(frames)} frames. GAN artifact score: {avg_score:.2%}",
                "model": "frequency",
            }
        else:
            img = _load_image(file_path)
            if img is None:
                return {"confidence": 0.5, "signal": "Could not load image", "model": "frequency", "disabled": True}
            score = _dct_fake_score(img)
            return {
                "confidence": score,
                "signal": f"DCT frequency GAN artifact score: {score:.2%}",
                "model": "frequency",
            }
    except Exception as e:
        return {"confidence": 0.5, "signal": f"Error: {str(e)}", "model": "frequency", "disabled": True}


# ---------------------------------------------------------------------------
# MODEL C — DeepFace Face Consistency Checker
# ---------------------------------------------------------------------------

def _analyze_face_frame(frame_bgr: np.ndarray) -> dict[str, Any]:
    """Analyze facial landmarks and geometry in a single frame using DeepFace."""
    try:
        from deepface import DeepFace
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = DeepFace.analyze(
            frame_rgb,
            actions=["emotion"],
            enforce_detection=True,
            silent=True,
        )
        if isinstance(result, list):
            result = result[0]
        region = result.get("region", {})
        face_w = region.get("w", 0)
        face_h = region.get("h", 0)
        return {"found": True, "face_w": face_w, "face_h": face_h}
    except Exception:
        return {"found": False}


def detect_face_consistency(file_path: str) -> dict[str, Any]:
    """Check face consistency across frames (video) or geometry (image)."""
    try:
        import deepface
    except ImportError:
        return {"confidence": 0.5, "signal": "DeepFace package not installed", "model": "face", "disabled": True}

    try:
        if _is_video(file_path):
            frames = _extract_frames(file_path, max_frames=5)
            if not frames:
                return {"confidence": 0.5, "signal": "Could not extract frames", "model": "face", "disabled": True}

            face_results = [_analyze_face_frame(f) for f in frames]
            found_faces = [r for r in face_results if r.get("found")]

            if len(found_faces) < 2:
                return {
                    "confidence": 0.4,
                    "signal": "Insufficient faces detected for consistency check",
                    "model": "face",
                }

            widths = [r["face_w"] for r in found_faces if r["face_w"] > 0]
            if len(widths) < 2:
                return {"confidence": 0.4, "signal": "Face region data incomplete", "model": "face"}

            width_variance = float(np.var(widths))
            mean_width = float(np.mean(widths))
            normalized_variance = width_variance / (mean_width ** 2 + 1e-8)

            score = float(np.clip(normalized_variance / 0.05, 0.0, 1.0))
            return {
                "confidence": score,
                "signal": f"Face size variance across {len(found_faces)} frames: {normalized_variance:.4f}",
                "model": "face",
            }
        else:
            img = _load_image(file_path)
            if img is None:
                return {"confidence": 0.5, "signal": "Could not load image", "model": "face", "disabled": True}
            face_result = _analyze_face_frame(img)
            if not face_result.get("found"):
                return {
                    "confidence": 0.3,
                    "signal": "No face detected in image",
                    "model": "face",
                }
            return {
                "confidence": 0.35,
                "signal": "Face detected. Single image — no temporal consistency check possible.",
                "model": "face",
            }
    except Exception as e:
        return {"confidence": 0.5, "signal": f"Error: {str(e)}", "model": "face", "disabled": True}


# ---------------------------------------------------------------------------
# MODEL D — Temporal Consistency (Video Only)
# ---------------------------------------------------------------------------

def detect_temporal_consistency(file_path: str) -> dict[str, Any]:
    """Analyze optical flow between consecutive video frames."""
    try:
        if not _is_video(file_path):
            return {
                "confidence": 0.5,
                "signal": "Temporal analysis not applicable to single images.",
                "model": "temporal",
                "skipped": True,
            }

        frames = _extract_frames(file_path, max_frames=8)
        if len(frames) < 2:
            return {
                "confidence": 0.5,
                "signal": "Not enough frames for temporal analysis",
                "model": "temporal",
                "disabled": True
            }

        flow_scores = []
        for i in range(len(frames) - 1):
            gray1 = cv2.cvtColor(frames[i],   cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frames[i+1], cv2.COLOR_BGR2GRAY)
            flow = cv2.calcOpticalFlowFarneback(
                gray1, gray2, None,
                pyr_scale=0.5, levels=3, winsize=15,
                iterations=3, poly_n=5, poly_sigma=1.2,
                flags=0,
            )
            magnitude = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
            flow_scores.append(float(magnitude.mean()))

        if not flow_scores:
            return {"confidence": 0.5, "signal": "Optical flow computation failed", "model": "temporal", "disabled": True}

        mean_flow = float(np.mean(flow_scores))
        std_flow  = float(np.std(flow_scores))

        variance_score = float(np.clip(std_flow / 5.0, 0.0, 1.0))

        return {
            "confidence": variance_score,
            "signal": (
                f"Optical flow analysis across {len(frames)} frames. "
                f"Mean flow: {mean_flow:.2f}, Variance: {std_flow:.2f}"
            ),
            "model": "temporal",
        }
    except Exception as e:
        return {"confidence": 0.5, "signal": f"Error: {str(e)}", "model": "temporal", "disabled": True}


# ---------------------------------------------------------------------------
# ENSEMBLE VERDICT ENGINE
# ---------------------------------------------------------------------------

def run_ml_ensemble(file_path: str) -> dict[str, Any]:
    """Run active models and combine results using dynamically redistributed weights."""
    is_video = _is_video(file_path)

    # Run all models
    results = {
        "huggingface": detect_huggingface(file_path),
        "frequency":   detect_frequency(file_path),
        "face":        detect_face_consistency(file_path),
        "temporal":    detect_temporal_consistency(file_path),
    }

    # Build weights — filter out skipped or disabled models
    weights = dict(_WEIGHTS)
    
    # Filter skipped temporal for images
    if not is_video or results["temporal"].get("skipped"):
        weights.pop("temporal", None)
        
    # Filter disabled models
    active_models = []
    for model_name in list(weights.keys()):
        if results[model_name].get("disabled"):
            weights.pop(model_name)
        else:
            active_models.append(model_name)

    if not weights:
        # Fallback: if everything is disabled, return inconclusive
        return {
            "fake_probability": 0.5,
            "confidence_percent": 50.0,
            "verdict": "inconclusive",
            "model_results": results,
            "weights_used": {},
            "is_video": is_video,
        }

    # Redistribute weights to sum to 1.0
    total_weight = sum(weights.values())
    for k in weights:
        weights[k] = weights[k] / total_weight

    # Compute weighted average
    fake_probability = 0.0
    for model_name, weight in weights.items():
        model_confidence = results[model_name].get("confidence", 0.5)
        fake_probability += model_confidence * weight

    fake_probability = float(np.clip(fake_probability, 0.0, 1.0))

    # Determine verdict
    if fake_probability >= _THRESHOLD_FAKE:
        verdict = "fake"
    elif fake_probability >= _THRESHOLD_SUSPICIOUS:
        verdict = "suspicious"
    else:
        verdict = "real"

    # Cleanup resources (Phase 7 - REMOVE RESOURCE EXHAUSTION)
    global _hf_pipeline
    if _hf_pipeline is not None:
        del _hf_pipeline
        _hf_pipeline = None
        
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    return {
        "fake_probability": round(fake_probability, 4),
        "confidence_percent": round(fake_probability * 100, 1),
        "verdict": verdict,
        "model_results": results,
        "weights_used": {k: round(v, 4) for k, v in weights.items()},
        "is_video": is_video,
    }
