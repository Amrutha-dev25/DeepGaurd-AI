"""Sightengine REST API provider — primary analysis engine for DeepGuard AI.

Calls the Sightengine deepfake + genai detection models and normalizes the
response into the verdict JSON schema expected by the downstream pipeline.

Reference: https://sightengine.com/docs/deepfake-detection
           https://sightengine.com/docs/ai-generated-image-detection
"""

import asyncio
import io
import json
import logging
import os
from typing import Any

import aiohttp
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

PARSER_VERSION = "v3"

# Startup provenance — proves the correct file is loaded at runtime
logger.info("Loaded Sightengine provider: %s", os.path.abspath(__file__))
logger.info("Parser version: %s", PARSER_VERSION)

# ── Models requested ─────────────────────────────────────────────────
# deepfake: face-swap / face-manipulation detection (real photo, tampered face)
# genai:    fully AI-generated media detection (Midjourney, Flux, SD, DALL-E, Sora, etc.)
#
# BUGFIX: previously only "deepfake" was requested. A media file that is
# entirely AI-generated (high `genai` score) but has no face-swap signal
# (low `deepfake` score) was silently scored as "real" because the genai
# score was never present in the API response to begin with — no amount
# of downstream parsing could recover a field that was never returned.
DEEPFAKE_MODELS = "deepfake,genai"

# Maximum image dimension before resizing (longest side)
MAX_IMAGE_DIMENSION = 2048
# JPEG quality for compressed uploads
COMPRESS_QUALITY = 85


def _resize_large_image(image_bytes: bytes, mime_type: str) -> bytes:
    """Downsize images whose longest side exceeds MAX_IMAGE_DIMENSION.

    Resizing reduces Sightengine upload/processing time for large photos
    (e.g. 4032x3024 smartphone captures) without meaningfully affecting
    deepfake/genai detection accuracy.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        if max(w, h) <= MAX_IMAGE_DIMENSION:
            return image_bytes  # already small enough
        ratio = MAX_IMAGE_DIMENSION / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        fmt = "JPEG" if "jpeg" in mime_type or "jpg" in mime_type else "PNG"
        img.save(buf, format=fmt, quality=COMPRESS_QUALITY, optimize=True)
        reduced = buf.getvalue()
        logger.info("Resized image %dx%d -> %dx%d (%d -> %d bytes)",
                    w, h, new_size[0], new_size[1], len(image_bytes), len(reduced))
        return reduced
    except Exception as exc:
        logger.warning("Image resize failed (%s) — sending original", exc)
        return image_bytes

# ── Thresholds for verdict mapping ──────────────────────────────────────
# Both deepfake.prob and genai.prob are "probability this media IS
# manipulated/AI-generated". We take the MAX of the two as the operative
# signal: either one firing high is sufficient evidence of fakery — a
# face-swap deepfake with low genai score is still fake, and a fully
# AI-generated image with low deepfake-specific score is still fake.

_FAKE_THRESHOLD = 0.75
_REAL_THRESHOLD = 0.25

# ── Known irrelevant model keys to exclude from fallback score search ──
_IRRELEVANT_MODEL_KEYS = {
    "weapon", "nudity", "alcohol", "drugs", "offensive",
    "gore", "self-harm", "text", "ocr", "face-attributes",
}

# ── Known relevant model key prefixes (fallback recursive search only) ─
_RELEVANT_MODEL_PREFIXES = {
    "deepfake", "genai", "face", "manipulation", "synthetic",
    "ai", "fake", "gan",
}


def _recursive_find_scores(
    obj: Any,
    path: str = "",
    depth: int = 0,
    max_depth: int = 8,
) -> list[dict[str, Any]]:
    """Recursively search any nested JSON structure for probability/score/confidence fields.

    This is a FALLBACK path used only when the known top-level `deepfake`
    and `genai` keys (handled explicitly in `_extract_score`) are absent —
    e.g. an older API version, or a models list that included something
    unexpected. It should rarely fire in normal operation.
    """
    results: list[dict[str, Any]] = []
    if depth > max_depth:
        return results

    current_key = path.split(".")[0] if path else ""
    if current_key in _IRRELEVANT_MODEL_KEYS:
        return results

    if isinstance(obj, dict):
        prob_val = None
        for score_key in ("prob", "score", "confidence"):
            v = obj.get(score_key)
            if v is not None and isinstance(v, (int, float)):
                prob_val = float(v)
                break
        if prob_val is not None:
            type_val = obj.get("type")
            label_val = obj.get("label")
            results.append({
                "prob": prob_val,
                "type": str(type_val) if type_val is not None else (path.split(".")[0] if path else "unknown"),
                "label": str(label_val) if label_val is not None else None,
                "path": path or "(root)",
                "source": path.split(".")[-1] if path else "root",
            })

        for k, v in obj.items():
            if isinstance(v, (int, float)):
                k_lower = k.lower()
                is_relevant = any(prefix in k_lower for prefix in _RELEVANT_MODEL_PREFIXES)
                if is_relevant:
                    results.append({
                        "prob": float(v),
                        "type": k_lower,
                        "label": None,
                        "path": f"{path}.{k}" if path else k,
                        "source": k,
                    })

        for k, v in obj.items():
            if not isinstance(v, (int, float)):
                child_path = f"{path}.{k}" if path else k
                results.extend(_recursive_find_scores(v, child_path, depth + 1, max_depth))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            child_path = f"{path}[{i}]"
            results.extend(_recursive_find_scores(item, child_path, depth + 1, max_depth))
    return results


def _extract_score(result: dict[str, Any]) -> tuple[float, str, list[str]]:
    """Extract the operative AI/manipulation probability from a Sightengine response.

    Explicitly reads the two known top-level model keys:
        result["deepfake"]["prob"]  — face-swap / manipulation probability
        result["genai"]["prob"]     — fully-AI-generated probability

    Returns max(deepfake_prob, genai_prob) as the operative score, with
    `type` reflecting whichever model produced the higher (winning) score.
    Falls back to recursive search only if neither known key is present
    (e.g. unexpected API response shape).

    Returns:
        (probability, type_label, supporting_evidence_list)
    """
    supporting: list[str] = []
    candidates: list[dict[str, Any]] = []

    logger.info("=== _extract_score TRACE (parser v3) ===")

    # ── Explicit known-key extraction ───────────────────────────────
    deepfake_block = result.get("deepfake")
    if isinstance(deepfake_block, dict) and isinstance(deepfake_block.get("prob"), (int, float)):
        candidates.append({
            "prob": float(deepfake_block["prob"]),
            "type": "deepfake",
            "path": "deepfake.prob",
        })

    genai_block = result.get("genai")
    if isinstance(genai_block, dict) and isinstance(genai_block.get("prob"), (int, float)):
        candidates.append({
            "prob": float(genai_block["prob"]),
            "type": "genai",
            "path": "genai.prob",
        })

    # Legacy shape support: {"type": {"deepfake": 0.07}}
    legacy_type = result.get("type")
    if isinstance(legacy_type, dict):
        for k, v in legacy_type.items():
            if isinstance(v, (int, float)):
                candidates.append({
                    "prob": float(v),
                    "type": k.lower(),
                    "path": f"type.{k}",
                })

    for c in candidates:
        logger.info("  Known-key candidate: type=%s prob=%.4f path=%s",
                     c["type"], c["prob"], c["path"])

    # ── Fallback to recursive search if nothing found via known keys ──
    if not candidates:
        logger.warning("No known deepfake/genai keys found — falling back to recursive search")
        found_scores = _recursive_find_scores(result)
        for s in found_scores:
            logger.info("  Fallback candidate: type=%s prob=%s path=%s",
                         s.get("type"), s.get("prob"), s.get("path"))
        candidates = found_scores

    if not candidates:
        logger.warning(
            "Sightengine response contains NO probability fields anywhere: %s",
            list(result.keys())
        )
        logger.info("=== _extract_score TRACE END: returning 0.5/uncertain (no candidates) ===")
        return 0.5, "uncertain", ["No confidence score found in Sightengine response"]

    # ── Take MAX across all candidates — either signal firing is fake ─
    selected = max(candidates, key=lambda c: c["prob"])
    prob = selected["prob"]
    verdict_type = selected["type"]

    logger.info("SELECTED (max): prob=%.4f type=%s path=%s", prob, verdict_type, selected.get("path", "?"))

    for c in candidates:
        supporting.append(f"Sightengine [{c['path']}] — prob={c['prob']:.4f}, type={c['type']}")

    prob = max(0.0, min(1.0, prob))

    logger.info("FINAL SCORE from _extract_score: prob=%.4f type=%s", prob, verdict_type)
    logger.info("=== _extract_score TRACE END ===")

    return prob, verdict_type, supporting


def _normalize_verdict(sightengine_result: dict[str, Any]) -> dict[str, Any]:
    """Convert Sightengine API response into DeepGuard verdict JSON."""
    prob, df_type, supporting = _extract_score(sightengine_result)

    if prob >= _FAKE_THRESHOLD:
        verdict = "fake"
    elif prob <= _REAL_THRESHOLD:
        verdict = "real"
    else:
        verdict = "inconclusive"

    if verdict == "fake":
        confidence = prob
    elif verdict == "real":
        confidence = 1.0 - prob
    else:
        confidence = 0.5

    logger.info("========== PARSER TRACE ==========")
    logger.info("Raw JSON:\n%s", json.dumps(sightengine_result, indent=2, default=str))
    for i, s in enumerate(supporting):
        logger.info("Candidate %d: %s", i + 1, s)
    logger.info("Selected (max): %s", df_type)
    logger.info("Probability: %.4f", prob)
    logger.info("Threshold: %s (FAKE>=%.2f, REAL<=%.2f)",
                 "FAKE" if prob >= _FAKE_THRESHOLD else "REAL" if prob <= _REAL_THRESHOLD else "INCONCLUSIVE",
                 _FAKE_THRESHOLD, _REAL_THRESHOLD)
    logger.info("Verdict: %s", verdict)
    logger.info("Confidence: %.4f", confidence)
    logger.info("=================================")

    forensic_obs: list[str] = list(supporting) if supporting else [
        f"Sightengine probability: {prob:.4f}, type: {df_type}"
    ]

    media_info = sightengine_result.get("media", {})
    if isinstance(media_info, dict):
        w = media_info.get("width")
        h = media_info.get("height")
        if w and h:
            forensic_obs.append(f"Media dimensions: {w}x{h}")

    if verdict == "fake":
        summary = (
            f"Sightengine classified this media as AI-generated or manipulated "
            f"with {prob:.0%} confidence (strongest signal: {df_type}). "
            f"The forensic indicators support this classification."
        )
    elif verdict == "real":
        summary = (
            f"Sightengine classified this media as authentic "
            f"with {1-prob:.0%} confidence (max AI/manipulation probability={prob:.2f})."
        )
    else:
        summary = (
            f"Sightengine returned an inconclusive result "
            f"(max AI/manipulation probability={prob:.2f}, type={df_type}). "
            f"Confidence is insufficient for a definitive classification. "
            f"Manual review recommended."
        )

    normalized = {
        "verdict": verdict,
        "confidence": round(confidence, 4),
        "raw_prob": round(prob, 4),
        "analysis_summary": summary,
        "visual_observations": [],
        "forensic_observations": forensic_obs,
        "supporting_evidence": supporting,
        "conflicting_evidence": [],
        "raw_result_keys": list(sightengine_result.keys()),
        "deepfake_prob": round(float(sightengine_result.get("deepfake", {}).get("prob", 0)), 4),
        "genai_prob": round(float(sightengine_result.get("genai", {}).get("prob", 0)), 4),
        "limitations": (
            "Sightengine analysis combines deepfake (face-swap) and genai "
            "(fully-generated) model scores from a single API call. "
            "Results should be cross-referenced with additional forensic tools."
        ),
        "recommendation": (
            "Manual expert review recommended."
            if verdict == "inconclusive"
            else (
                "Cross-reference with original source if available."
                if verdict == "fake"
                else "No further action needed."
            )
        ),
    }

    logger.info("FINAL SCORE from _normalize_verdict: prob=%.4f type=%s verdict=%s confidence=%.4f",
                prob, df_type, verdict, confidence)
    logger.info("=== SIGHTENGINE NORMALIZED VERDICT ===\n%s",
                json.dumps(normalized, indent=2))
    return normalized


async def analyze_with_sightengine(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    timeout: int = 30,
) -> dict[str, Any]:
    """Send image to Sightengine deepfake+genai APIs and return normalized verdict."""
    logger.info("Parser version=%s", PARSER_VERSION)
    api_user = settings.sightengine_api_user
    api_secret = settings.sightengine_api_secret

    if not api_user or not api_secret:
        logger.warning("Sightengine API credentials not configured — skipping")
        return {
            "verdict": "error",
            "confidence": 0.0,
            "error": "Sightengine credentials not configured",
        }

    # Resize large images before sending to reduce upload/processing time
    resized_bytes = _resize_large_image(image_bytes, mime_type)

    url = settings.sightengine_api_url
    data = aiohttp.FormData()
    data.add_field("media", resized_bytes, filename="image", content_type=mime_type)
    data.add_field("models", DEEPFAKE_MODELS)
    data.add_field("api_user", api_user)
    data.add_field("api_secret", api_secret)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data=data,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                body = await resp.text()
                logger.info("SIGHTENGINE HTTP RESPONSE: status=%d body_preview=%s",
                            resp.status, body[:1000])
                if resp.status != 200:
                    # Parse error details for clearer logging
                    error_detail = body[:500]
                    try:
                        err_json = json.loads(body)
                        err_type = err_json.get("error", {}).get("type", "unknown")
                        err_msg = err_json.get("error", {}).get("message", body[:300])
                        error_detail = f"{err_type}: {err_msg}"
                        if err_type == "usage_limit":
                            logger.error(
                                "SIGHTENGINE QUOTA EXCEEDED: %s — all requests will fall through to LLM fallbacks "
                                "until quota resets or plan is upgraded.", err_msg
                            )
                    except json.JSONDecodeError:
                        pass
                    logger.warning("Sightengine returned HTTP %d: %s", resp.status, error_detail)
                    return {
                        "verdict": "error",
                        "confidence": 0.0,
                        "error": error_detail,
                    }
                result = json.loads(body)
                if result.get("status") != "success":
                    logger.warning(
                        "Sightengine returned non-success status: %s",
                        result.get("status", body[:200]),
                    )
                    return {
                        "verdict": "error",
                        "confidence": 0.0,
                        "error": f"Sightengine status: {result.get('status')}",
                    }
                return _normalize_verdict(result)
    except asyncio.TimeoutError:
        logger.warning("Sightengine request timed out after %ds", timeout)
        return {"verdict": "error", "confidence": 0.0, "error": "Sightengine timeout"}
    except Exception as exc:
        logger.warning("Sightengine request failed: %s", exc)
        return {
            "verdict": "error",
            "confidence": 0.0,
            "error": f"Sightengine exception: {exc}",
        }