"""ADK orchestrator — isolated sessions per agent stage.

Pipeline:
  Deterministic: Security Layer → Preprocessing → Forensic Context
  ADK Agents:    Router (isolated, with fallback chain) → Analysis (isolated, with fallback chain) → Report (isolated, with fallback chain)
  Output:        JSON + Markdown + PDF + Audit

Each agent runs in its OWN session to prevent conversation-history contamination
across stages. Every agent stage has a full fallback chain so no single provider
failure can stop the pipeline.
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

try:
    import litellm
    litellm.suppress_debug_info = True
    litellm.set_verbose = False
except ImportError:
    pass

from app.agents.supervisor_agent import (
    CAPABILITY_MAP,
    CAPABILITY_TO_AGENT_KEY,
    InvestigationState,
    build_supervisor_context,
    create_supervisor_agent,
    create_cerebras_supervisor_agent,
    create_gemini_supervisor_agent,
    _extract_supervisor_json,
)
from app.config import settings
from app.guardrails.injection import security_checkpoint
from app.guardrails.validation import validate_file
from app.preprocessing.image_pipeline import run_image_pipeline
from app.preprocessing.video_pipeline import run_video_pipeline
from app.services.audit_service import write_entry
from app.services.report_service import build_report_json, format_report_markdown
from app.tools.forensics import collect_forensic_context

logger = logging.getLogger(__name__)
_RUNNER_FILE = os.path.abspath(__file__)


# ── Rate limit detection ──────────────────────────────────────────────

_RATE_LIMIT_PATTERNS = [
    "rate limit",
    "rate_limit",
    "429",
    "too many requests",
    "quota exceeded",
    "token exceeded",
    "request limited",
]


def _is_rate_limit_error(exc: Exception) -> bool:
    """Check if an exception is a rate-limit or quota error."""
    msg = str(exc).lower()
    for pat in _RATE_LIMIT_PATTERNS:
        if pat in msg:
            return True
    # Check exception type name
    type_name = type(exc).__name__.lower()
    if "ratelimit" in type_name or "rate limit" in type_name:
        return True
    return False


# ── Deterministic fallback functions ──────────────────────────────────


def _deterministic_routing(mime_type: str, pipeline_type: str) -> dict[str, Any]:
    """Last-resort deterministic routing when all LLM providers fail."""
    is_image = mime_type.startswith("image/")
    return {
        "file_type": "image" if is_image else "video",
        "is_corrupt": False,
        "face_present": False,
        "faces": 0,
        "face_description": "unknown (deterministic routing)",
        "resolution": "unknown",
        "quality": "unknown",
        "needs_preprocessing": True,
        "pipeline": pipeline_type,
        "viable_for_analysis": True,
        "early_exit_reason": None,
    }


_ROUTER_REQUIRED_KEYS: set[str] = {"file_type"}
_ANALYSIS_REQUIRED_KEYS: set[str] = {"verdict"}


def _router_json_valid(parsed: dict[str, Any] | None) -> bool:
    """Check that parsed router JSON has the minimum required keys.

    Prevents accepting tool-call fragments or cut-off responses as
    valid routing decisions.
    """
    if parsed is None:
        return False
    return _ROUTER_REQUIRED_KEYS.issubset(parsed.keys())


def _analysis_json_valid(parsed: dict[str, Any] | None) -> bool:
    """Check that parsed analysis JSON has the minimum required keys."""
    if parsed is None:
        return False
    return _ANALYSIS_REQUIRED_KEYS.issubset(parsed.keys())


# ── Robust isolated agent runner ──────────────────────────────────────


@dataclass
class AgentResult:
    """Explicit result from _run_agent_isolated.

    `text` contains all collected text from the agent's response.
    `success` is True only when the call completed and produced content.
    Neither field is ambiguous: success=False with empty text = failure;
    success=True with empty text = valid empty response.
    """
    text: str = ""
    success: bool = False


def _new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:16]}"


async def _run_agent_isolated(
    agent: Agent,
    text: str,
    image_bytes: bytes | None = None,
    mime_type: str = "image/jpeg",
    timeout: int = 120,
) -> AgentResult:
    """Run an agent in a fresh session — no conversation-history leakage.

    Each call creates its own InMemorySessionService, session, and Runner,
    so the agent receives ONLY its own prompt + media — nothing from prior
    stages.

    Collects text from ALL events in the stream (does not break on the first
    final event). Preserves all part types (text, function_call, inline_data,
    function_response, code_execution_result).

    Returns AgentResult with collected text and success/failure.
    Raises on errors (RateLimitError for rate limits, other exceptions propagate).
    """
    request_id = _new_request_id()
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="deepguard",
        user_id=request_id,
        state={},
    )
    runner = Runner(
        agent=agent,
        app_name="deepguard",
        session_service=session_service,
        auto_create_session=True,
    )
    parts = [genai_types.Part.from_text(text=text)]
    if image_bytes:
        parts.append(genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
    content = genai_types.Content(role="user", parts=parts)

    collected_text = ""
    collected_parts: list[dict[str, str]] = []
    events_seen = 0

    agen = runner.run_async(
        user_id=request_id,
        session_id=session.id,
        new_message=content,
    )
    try:
        async for event in agen:
            events_seen += 1
            if event.content and event.content.parts:
                for p in event.content.parts:
                    if p.text:
                        collected_text += p.text
                    # Preserve every non-None part field
                    part_fields: dict[str, str] = {}
                    for field in ("text", "inline_data", "function_call",
                                  "function_response", "code_execution_result"):
                        val = getattr(p, field, None)
                        if val is not None:
                            part_fields[field] = str(val)[:500]
                    if part_fields:
                        collected_parts.append(part_fields)
            # Do NOT break on first final event — iterate entire stream
    except (asyncio.CancelledError, GeneratorExit):
        logger.warning("Provider '%s' cancelled.", agent.name)
        raise
    except RuntimeError as exc:
        logger.warning("Provider '%s' runtime error: %s",
                       agent.name, str(exc).split('\n')[0][:200])
        if _is_rate_limit_error(exc):
            raise RateLimitError(str(exc))
        raise
    except Exception as exc:
        logger.warning("Provider '%s' failed: %s",
                       agent.name, str(exc).split('\n')[0][:200])
        if _is_rate_limit_error(exc):
            raise RateLimitError(str(exc))
        raise  # All exceptions propagate — nothing is swallowed
    finally:
        try:
            await agen.aclose()
        except GeneratorExit:
            pass

    success = bool(collected_text.strip()) or bool(collected_parts)

    # Debug dump of final result
    import json as _jd
    _model = str(getattr(getattr(agent, 'model', None), 'model', 'unknown'))
    _text_preview = collected_text[:800] + "..." if len(collected_text) > 800 else collected_text
    print(f"\n=== ADK AGENT RESULT (agent={agent.name}) ===")
    print(_jd.dumps({
        "agent": agent.name,
        "model": _model,
        "events_seen": events_seen,
        "collected_text_len": len(collected_text),
        "success": success,
        "text_preview": _text_preview,
        "part_count": len(collected_parts),
        "part_types": list({k for p in collected_parts for k in p}),
    }, indent=2, default=str))
    print("=== END ADK AGENT RESULT ===\n")

    return AgentResult(text=collected_text, success=success)


class RateLimitError(Exception):
    """Raised when a provider returns a rate-limit or quota error."""


# ── Sightengine decision thresholds (must match app/providers/sightengine.py) ──

_SIGHTENGINE_FAKE_THRESHOLD = 0.75
_SIGHTENGINE_REAL_THRESHOLD = 0.25


async def _analyze_frames_sightengine(
    frames: list[bytes],
    mime_type: str,
    timeout: int,
) -> dict[str, Any]:
    """Analyze multiple video frames via Sightengine and aggregate worst-first.

    Sends all frames concurrently, then aggregates using the highest raw AI
    probability across all frames.  If any frame is confidently fake, the
    entire video is treated as fake — a single manipulated frame is enough.
    """
    from app.providers.sightengine import analyze_with_sightengine

    tasks = [analyze_with_sightengine(f, mime_type, timeout) for f in frames]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    frame_details: list[dict] = []
    max_raw_prob = 0.0
    worst_frame_idx = -1

    for i, (frame_bytes, result) in enumerate(zip(frames, raw_results)):
        if isinstance(result, Exception):
            logger.warning("Sightengine frame %d/%d failed: %s", i + 1, len(frames), result)
            frame_details.append({
                "frame_index": i,
                "verdict": "error",
                "confidence": 0.0,
                "raw_prob": 0.5,
                "summary": f"Error: {result}",
            })
            continue
        raw_prob = result.get("raw_prob", 0.5)
        frame_details.append({
            "frame_index": i,
            "verdict": result.get("verdict", "error"),
            "confidence": result.get("confidence", 0.0),
            "raw_prob": raw_prob,
            "summary": result.get("analysis_summary", ""),
        })
        logger.info("Sightengine frame %d/%d: verdict=%s conf=%.4f raw_prob=%.4f",
                     i + 1, len(frames),
                     result.get("verdict", "?"), result.get("confidence", 0), raw_prob)
        if raw_prob > max_raw_prob:
            max_raw_prob = raw_prob
            worst_frame_idx = i

    # Worst-first decision logic
    if max_raw_prob >= _SIGHTENGINE_FAKE_THRESHOLD:
        verdict = "fake"
        confidence = max_raw_prob
    elif max_raw_prob <= _SIGHTENGINE_REAL_THRESHOLD:
        verdict = "real"
        confidence = 1.0 - max_raw_prob
    else:
        verdict = "inconclusive"
        confidence = 0.5

    logger.info(
        "Sightengine multi-frame: frames=%d max_raw_prob=%.4f "
        "worst_frame=%d verdict=%s confidence=%.4f",
        len(frames), max_raw_prob, worst_frame_idx, verdict, confidence,
    )

    frame_lines = [
        f"Frame {d['frame_index']}: {d['verdict']} (conf={d['confidence']:.2f})"
        for d in frame_details
    ]

    return {
        "verdict": verdict,
        "confidence": round(confidence, 4),
        "raw_prob": round(max_raw_prob, 4),
        "frame_analysis": frame_details,
        "analysis_summary": (
            f"Analyzed {len(frames)} video frames. "
            f"Worst-frame AI probability: {max_raw_prob:.0%}. "
            f"Overall: {verdict.upper()} (conf={confidence:.0%})."
        ),
        "visual_observations": [],
        "forensic_observations": [
            f"Multi-frame analysis: {len(frames)} frames analyzed",
            f"Worst frame: frame {worst_frame_idx} (raw_prob={max_raw_prob:.4f})",
            *frame_lines,
        ],
        "supporting_evidence": frame_lines,
        "conflicting_evidence": [],
        "limitations": (
            "Video analysis based on extracted key frames, not full frame-by-frame."
        ),
        "recommendation": (
            "Manual review recommended."
            if verdict == "inconclusive"
            else (
                "Cross-reference with original source if available."
                if verdict == "fake"
                else "No further action needed."
            )
        ),
    }


async def _run_agent_safe(
    agent: Agent,
    text: str,
    image_bytes: bytes | None = None,
    mime_type: str = "image/jpeg",
    timeout: int = 120,
    max_retries_on_rate_limit: int = 0,
) -> tuple[str, bool]:
    """Run an agent with safe error handling. Never raises.

    Returns:
        (result_text, succeeded)
    """
    for attempt in range(1 + max_retries_on_rate_limit):
        try:
            result: AgentResult = await _run_agent_isolated(
                agent, text, image_bytes, mime_type, timeout,
            )
            return result.text, result.success
        except RateLimitError:
            if attempt < max_retries_on_rate_limit:
                logger.info("Rate limited, retry %d/%d", attempt + 1, max_retries_on_rate_limit)
                await asyncio.sleep(2 ** (attempt + 1))
                continue
            return "", False
        except GeneratorExit:
            logger.warning("Provider '%s' cancelled. Continuing to next fallback.", agent.name)
            await asyncio.sleep(0)  # yield so OTel can clean up its span context
            return "", False
        except asyncio.CancelledError:
            logger.warning("Provider '%s' cancelled. Continuing to next fallback.", agent.name)
            await asyncio.sleep(0)  # yield so OTel can clean up its span context
            return "", False
        except RuntimeError:
            logger.warning("Provider '%s' failed. Continuing to next fallback.", agent.name)
            return "", False
        except BaseException:
            logger.warning("Provider '%s' failed. Continuing to next fallback.", agent.name)
            return "", False


# ── Confidence fusion (preserved) ─────────────────────────────────────

def _fuse_confidence(
    verdict: dict[str, Any],
    forensic_context: dict[str, Any],
    preprocessing: dict[str, Any],
) -> float:
    """Fuse Sightengine verdict confidence with forensic evidence agreement.

    If forensic evidence supports the verdict, confidence is boosted.
    If forensic evidence contradicts the verdict, confidence is reduced.

    Returns a fused confidence score in [0.0, 1.0].
    """
    base_conf = verdict.get("confidence", 0.5)
    v = verdict.get("verdict", "inconclusive")

    # Compute forensic evidence scores
    forensic_fake_signals = 0
    forensic_real_signals = 0
    forensic_total = 0

    # ELA: high mean diff suggests tampering
    ela = forensic_context.get("ela", {})
    ela_diff = ela.get("mean_difference")
    if ela_diff is not None:
        forensic_total += 1
        if ela_diff > 1.5:
            forensic_fake_signals += 1
        elif ela_diff < 0.5:
            forensic_real_signals += 1

    # FFT: high high-freq ratio suggests upsampling/AI artifacts
    fft = forensic_context.get("fft", {})
    fft_hf = fft.get("high_freq_ratio")
    if fft_hf is not None:
        forensic_total += 1
        if fft_hf > 0.6:
            forensic_fake_signals += 1
        elif fft_hf < 0.3:
            forensic_real_signals += 1

    # Noise: high variance can indicate artifacts
    noise = forensic_context.get("noise", {})
    noise_var = noise.get("noise_variance")
    if noise_var is not None:
        forensic_total += 1
        if noise_var > 5000:
            forensic_fake_signals += 1
        elif noise_var < 500:
            forensic_real_signals += 1

    # Compression: low quality can indicate re-encoding
    comp = forensic_context.get("compression", {})
    comp_q = comp.get("estimated_quality")
    if comp_q is not None:
        forensic_total += 1
        if comp_q < 50:
            forensic_fake_signals += 1
        elif comp_q > 90:
            forensic_real_signals += 1

    # EXIF: missing tags can indicate manipulation
    exif = forensic_context.get("exif", {})
    tag_count = exif.get("tag_count")
    if tag_count is not None:
        forensic_total += 1
        if tag_count == 0:
            forensic_fake_signals += 1
        elif tag_count > 5:
            forensic_real_signals += 1

    # Metadata: editing software detected
    editor = exif.get("editing_software", [])
    if editor:
        forensic_total += 1
        forensic_fake_signals += 1

    # Wavelet HH anomaly from preprocessing
    wavelet = preprocessing.get("wavelet", {})
    hh = wavelet.get("HH")
    if hh is not None:
        forensic_total += 1
        if hh < 0:
            forensic_fake_signals += 1
        elif hh > 5:
            forensic_real_signals += 1

    if forensic_total == 0:
        return base_conf

    # Forensic agreement ratio (0..1, where 1 = all signals agree with verdict)
    if v == "fake":
        agreement = forensic_fake_signals / max(forensic_total, 1)
    elif v == "real":
        agreement = forensic_real_signals / max(forensic_total, 1)
    else:
        # inconclusive — forensic signals can't help much
        return round(base_conf, 4)

    # Fuse: blend base confidence with forensic agreement
    # If they agree, confidence increases toward the higher of the two
    # If they disagree, confidence moves toward the midpoint
    if agreement > 0.5:
        fused = max(base_conf, agreement * 0.9 + 0.1)
    else:
        fused = base_conf * 0.5 + agreement * 0.3

    logger.info(
        "Confidence fusion: base=%.4f forensic_agreement=%.4f "
        "(fake_signals=%d real_signals=%d total=%d) => fused=%.4f",
        base_conf, agreement,
        forensic_fake_signals, forensic_real_signals, forensic_total,
        fused,
    )

    return round(min(1.0, max(0.0, fused)), 4)


def _log_forensic_summary(
    forensic_context: dict[str, Any],
    preprocessing: dict[str, Any],
) -> None:
    """Log all forensic measurements at INFO level."""
    ela = forensic_context.get("ela", {})
    fft = forensic_context.get("fft", {})
    noise = forensic_context.get("noise", {})
    comp = forensic_context.get("compression", {})
    exif = forensic_context.get("exif", {})
    jpeg = forensic_context.get("jpeg_artifacts", {})
    logger.info("=== FORENSIC SUMMARY ===")
    logger.info("ELA mean_diff=%.4f", ela.get("mean_difference", 0))
    logger.info("FFT high_freq_ratio=%.4f", fft.get("high_freq_ratio", 0))
    logger.info("Noise variance=%.2f", noise.get("noise_variance", 0))
    logger.info("Compression quality=%s", comp.get("estimated_quality", "N/A"))
    logger.info("JPEG block_boundary=%s", jpeg.get("block_boundary_ratio", "N/A"))
    logger.info("EXIF tag_count=%s", exif.get("tag_count", "N/A"))
    logger.info("EXIF editing_software=%s", exif.get("editing_software", []))
    logger.info("EXIF ai_tools=%s", exif.get("ai_generation_tools", []))
    pp_ela = preprocessing.get("ela_score")
    pp_fft = preprocessing.get("fft_mean")
    pp_dct = preprocessing.get("dct_mean")
    wavelet = preprocessing.get("wavelet", {})
    edges = preprocessing.get("edge_intensity", {})
    logger.info("Pipeline ELA_score=%s", pp_ela)
    logger.info("Pipeline FFT_mean=%s", pp_fft)
    logger.info("Pipeline DCT_mean=%s", pp_dct)
    logger.info("Wavelet LL=%.4f LH=%.4f HL=%.4f HH=%.4f",
                wavelet.get("LL", 0), wavelet.get("LH", 0),
                wavelet.get("HL", 0), wavelet.get("HH", 0))
    logger.info("Edges canny=%.4f sobel=%.4f laplacian=%.4f",
                edges.get("canny", 0), edges.get("sobel", 0),
                edges.get("laplacian", 0))
    h = forensic_context.get("hash", {})
    logger.info("SHA256=%s pHash=%s",
                h.get("sha256", "")[:16], h.get("phash", ""))
    logger.info("=== END FORENSIC SUMMARY ===")


def _new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response using bracket-counting.

    Scans forward from each `{` and takes the first substring that
    balances brackets AND parses via json.loads.  Avoids the greedy
    `.*` bug that spans from a stray `{` in reasoning text to the
    real closing `}`.
    """
    if not text or not text.strip():
        return None
    raw = text.strip()
    for i, ch in enumerate(raw):
        if ch != "{":
            continue
        depth = 0
        for j in range(i, len(raw)):
            c = raw[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidate = raw[i:j+1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
    logger.warning("No valid JSON found: %s...", raw[:200])
    return None


def _extract_key_frames(file_path: str, num_frames: int = 5) -> list[bytes]:
    import cv2
    import tempfile
    cap = cv2.VideoCapture(file_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total < 1:
        cap.release()
        return []
    step = max(1, total // num_frames)
    frames: list[bytes] = []
    for i in range(0, total, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue
        fd, tmp_name = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            cv2.imwrite(tmp_name, frame)
            with open(tmp_name, "rb") as f:
                frames.append(f.read())
        finally:
            try:
                os.unlink(tmp_name)
            except Exception:
                pass
    cap.release()
    return frames


# ── Format forensic evidence for model consumption ──────────────────────

def _format_forensic_evidence(
    forensic_context: dict[str, Any],
    preprocessing: dict[str, Any],
) -> str:
    """Convert raw forensic/preprocessing JSON into structured evidence text."""
    lines: list[str] = []
    lines.append("=== FORENSIC EVIDENCE ===\n")

    # ── ELA ──────────────────────────────────────────────────────────
    ela = forensic_context.get("ela", {})
    if ela.get("mean_difference") is not None:
        lines.append(f"ELA MEAN DIFFERENCE: {ela['mean_difference']:.4f}")
        lines.append(f"ELA SUMMARY: {ela.get('summary', 'N/A')}")
    pp_ela = preprocessing.get("ela_score")
    if pp_ela is not None:
        lines.append(f"ELA SCORE (pipeline): {pp_ela:.4f}")
    lines.append("")

    # ── FFT ──────────────────────────────────────────────────────────
    fft = forensic_context.get("fft", {})
    if fft.get("high_freq_ratio") is not None:
        lines.append(f"FFT HIGH-FREQUENCY RATIO: {fft['high_freq_ratio']:.4f}")
        lines.append(f"FFT EVIDENCE: {fft.get('evidence', 'N/A')}")
    pp_fft = preprocessing.get("fft_mean")
    if pp_fft is not None:
        lines.append(f"FFT MEAN (pipeline): {pp_fft:.2f}")
    lines.append("")

    # ── DCT ──────────────────────────────────────────────────────────
    pp_dct = preprocessing.get("dct_mean")
    if pp_dct is not None:
        lines.append(f"DCT COEFFICIENT MEAN: {pp_dct:.4f}")
    lines.append("")

    # ── Wavelet ──────────────────────────────────────────────────────
    wavelet = preprocessing.get("wavelet", {})
    if wavelet:
        lines.append("WAVELET ENERGY (Haar decomposition):")
        for band in ("LL", "LH", "HL", "HH"):
            val = wavelet.get(band)
            if val is not None:
                lines.append(f"  {band}: {val:.4f}")
    lines.append("")

    # ── Noise ────────────────────────────────────────────────────────
    noise = forensic_context.get("noise", {})
    if noise.get("noise_variance") is not None:
        lines.append(f"NOISE VARIANCE (Laplacian): {noise['noise_variance']:.2f}")
        lines.append(f"NOISE EVIDENCE: {noise.get('evidence', 'N/A')}")
    lines.append("")

    # ── JPEG / Compression ───────────────────────────────────────────
    jpeg = forensic_context.get("jpeg_artifacts", {})
    if jpeg:
        lines.append(f"JPEG BLOCK-BOUNDARY RATIO: {jpeg.get('block_boundary_ratio', 'N/A')}")
        lines.append(f"JPEG SUMMARY: {jpeg.get('summary', 'N/A')}")
    comp = forensic_context.get("compression", {})
    if comp.get("estimated_quality") is not None:
        lines.append(f"COMPRESSION ESTIMATED QUALITY: {comp['estimated_quality']}%")
        lines.append(f"COMPRESSION EVIDENCE: {comp.get('evidence', 'N/A')}")
    lines.append("")

    # ── Clone Detection ──────────────────────────────────────────────
    clones = forensic_context.get("clones", {})
    if clones:
        lines.append(f"CLONE DETECTION: {clones.get('summary', clones.get('evidence', 'N/A'))}")
    lines.append("")

    # ── Edge / Structural ────────────────────────────────────────────
    edges = preprocessing.get("edge_intensity", {})
    if edges:
        lines.append("EDGE INTENSITY:")
        for k in ("canny", "sobel", "laplacian"):
            val = edges.get(k)
            if val is not None:
                lines.append(f"  {k.upper()}: {val:.4f}")
    lines.append("")

    # ── Face Detection ───────────────────────────────────────────────
    faces = forensic_context.get("faces", {})
    if faces.get("face_count") is not None:
        lines.append(f"FACE DETECTION: {faces['face_count']} face(s) detected")
        lines.append(f"FACE EVIDENCE: {faces.get('evidence', 'N/A')}")
    lines.append("")

    # ── Metadata / EXIF ──────────────────────────────────────────────
    exif = forensic_context.get("exif", {})
    if exif:
        lines.append("EXIF / METADATA:")
        if exif.get("tag_count") is not None:
            lines.append(f"  Tag count: {exif['tag_count']}")
        if exif.get("summary"):
            lines.append(f"  Summary: {exif['summary']}")
        editor = exif.get("editing_software", [])
        if editor:
            lines.append(f"  Editing software detected: {', '.join(editor)}")
        ai_tools = exif.get("ai_generation_tools", [])
        if ai_tools:
            lines.append(f"  AI generation tools detected: {', '.join(ai_tools)}")
    pp_meta = preprocessing.get("metadata", {})
    if pp_meta:
        if pp_meta.get("camera"):
            lines.append(f"  Camera: {pp_meta['camera']}")
        if pp_meta.get("software"):
            lines.append(f"  Software: {pp_meta['software']}")
        if pp_meta.get("gps_present"):
            lines.append(f"  GPS data present: yes")
        if pp_meta.get("creation_time"):
            lines.append(f"  Creation time: {pp_meta['creation_time']}")
    lines.append("")

    # ── Hashes ───────────────────────────────────────────────────────
    h = forensic_context.get("hash", {})
    if h.get("sha256"):
        lines.append(f"SHA-256: {h['sha256']}")
    if h.get("phash"):
        lines.append(f"pHash: {h['phash']}")
    lines.append("")

    # ── Temporal / Frame info ────────────────────────────────────────
    frames_info = forensic_context.get("frames", {})
    if frames_info:
        lines.append(f"FRAME ANALYSIS: {frames_info.get('evidence', 'N/A')}")
    lines.append("")

    return "\n".join(lines)


# ── Build agents ──────────────────────────────────────────────────────

def _build_pipeline_agents() -> tuple[
    Agent, Agent, Agent, Agent,
    Agent, Agent, Agent,
    Agent, Agent, Agent, Agent,
]:
    """Build all agents for Router, Analysis, and Report (each with fallbacks)."""
    logger.info("RUNNING: %s", _RUNNER_FILE)
    logger.info("Function: _build_pipeline_agents()")
    from app.agents.router_agent import (
        create_router_agent,
        create_router_fallback1_agent,
        create_router_fallback2_agent,
        create_router_fallback3_agent,
    )
    from app.agents.analysis_agent import (
        create_analysis_agent,
        create_fallback1_agent,
        create_gemini_fallback_agent,
    )
    from app.agents.report_agent import (
        create_report_agent,
        create_report_fallback1_agent,
        create_report_fallback2_agent,
        create_report_fallback3_agent,
    )
    rtr = create_router_agent()
    rfb1 = create_router_fallback1_agent()
    rfb2 = create_router_fallback2_agent()
    rfb3 = create_router_fallback3_agent()
    ana = create_analysis_agent()
    afb1 = create_fallback1_agent()
    afb2 = create_gemini_fallback_agent()
    rep = create_report_agent()
    rpfb1 = create_report_fallback1_agent()
    rpfb2 = create_report_fallback2_agent()
    rpfb3 = create_report_fallback3_agent()
    logger.info("Router Primary: created")
    logger.info("Router FB1 (NVIDIA Omni): created")
    logger.info("Router FB2 (NVIDIA Nano): created")
    logger.info("Router FB3 (Gemini): created")
    logger.info("Analysis Agent (NVIDIA Omni): created")
    logger.info("Analysis FB1 (NVIDIA Nano): created")
    logger.info("Analysis FB2 (Gemini): created")
    logger.info("Report Primary: created")
    logger.info("Report FB1 (NVIDIA Omni): created")
    logger.info("Report FB2 (NVIDIA Nano): created")
    logger.info("Report FB3 (Gemini): created")
    return (rtr, rfb1, rfb2, rfb3, ana, afb1, afb2, rep, rpfb1, rpfb2, rpfb3)


# ── Run the router with fallback ───────────────────────────────────────

async def _run_router_with_fallback(
    router_prompt: str,
    router_agent: Agent,
    router_fb1: Agent,
    router_fb2: Agent,
    router_fb3: Agent,
    mime_type: str,
    pipeline_type: str,
) -> tuple[dict[str, Any], str, bool]:
    """Run Router Agent with Groq -> NVIDIA Omni -> Gemini -> Deterministic fallback."""
    logger.info("RUNNING: %s", _RUNNER_FILE)
    logger.info("Function: _run_router_with_fallback()")
    routing: dict[str, Any] = _deterministic_routing(mime_type, pipeline_type)
    model_used = "deterministic"
    fallback_used = False
    router_text = ""

    # Primary: Groq
    logger.info("Trying Router Primary: Groq (%s)", settings.router_model)
    try:
        router_text, ok = await _run_agent_safe(
            router_agent, router_prompt, timeout=settings.request_timeout_seconds,
        )
        if ok and router_text.strip():
            parsed = _extract_json(router_text)
            if _router_json_valid(parsed):
                routing = parsed
                model_used = settings.router_model
                logger.info("Router Primary succeeded: %s", routing)
                return routing, model_used, fallback_used
            logger.warning("Router Primary (Groq) returned invalid/missing keys: %s",
                           parsed.keys() if parsed else "None")
        logger.warning("Router Primary (Groq) FAILED")
    except Exception as exc:
        logger.warning("Router Primary (Groq) FAILED: %s", str(exc).split('\n')[0][:200])

    # Fallback 1: NVIDIA Omni
    logger.info("Trying Router Fallback 1: NVIDIA Omni (%s)", settings.router_fallback2_model)
    try:
        router_text, ok = await _run_agent_safe(
            router_fb1, router_prompt, timeout=settings.request_timeout_seconds,
        )
        if ok and router_text.strip():
            parsed = _extract_json(router_text)
            if _router_json_valid(parsed):
                routing = parsed
                model_used = settings.router_fallback2_model
                fallback_used = True
                logger.info("Router Fallback 1 (NVIDIA) succeeded: %s", routing)
                return routing, model_used, fallback_used
            logger.warning("Router Fallback 1 (NVIDIA) returned invalid/missing keys: %s",
                           parsed.keys() if parsed else "None")
        logger.warning("Router Fallback 1 (NVIDIA) FAILED")
    except Exception as exc:
        logger.warning("Router Fallback 1 (NVIDIA) FAILED: %s", str(exc).split('\n')[0][:200])

    # Fallback 2: Gemini
    if settings.enable_gemini_fallback and settings.google_api_key:
        logger.info("Trying Router Fallback 2: Gemini (%s)", settings.router_fallback1_model)
        try:
            router_text, ok = await _run_agent_safe(
                router_fb3, router_prompt, timeout=settings.request_timeout_seconds,
            )
            if ok and router_text.strip():
                parsed = _extract_json(router_text)
                if _router_json_valid(parsed):
                    routing = parsed
                    model_used = settings.router_fallback1_model
                    fallback_used = True
                    logger.info("Router Fallback 2 (Gemini) succeeded: %s", routing)
                    return routing, model_used, fallback_used
                logger.warning("Router Fallback 2 (Gemini) returned invalid/missing keys: %s",
                               parsed.keys() if parsed else "None")
            logger.warning("Router Fallback 2 (Gemini) FAILED")
        except Exception as exc:
            logger.warning("Router Fallback 2 (Gemini) FAILED: %s", str(exc).split('\n')[0][:200])
    else:
        logger.info("Router Fallback 2 (Gemini) skipped — not configured")

    # Fallback 3: Deterministic
    logger.info("Trying Router Fallback 3: Deterministic routing (last resort)")
    routing = _deterministic_routing(mime_type, pipeline_type)
    fallback_used = True
    logger.info("Router Fallback 3 succeeded: deterministic routing")
    return routing, "deterministic", fallback_used


# ── Evidence sufficiency gate ─────────────────────────────────────────

# Reference ranges (calibration anchors, from analysis_agent.py)
_AUTHENTIC_RANGES = {
    "ela_mean_difference": (0.05, 0.50),
    "noise_variance": (100, 1500),
    "fft_high_freq_ratio": (0.001, 0.05),
    "compression_quality": (75, 98),
    "dct_coefficient_mean": (0.5, 5.0),
    "wavelet_hh_energy": (0.001, 0.05),
    "edge_intensity_canny": (0.01, 0.10),
}


def _forensics_corroborate(se_verdict: dict, forensic_context: dict, preprocessing: dict) -> bool:
    """Check whether forensic evidence independently points in the same
    direction as Sightengine's verdict.

    Returns True if a majority (≥3 of available signals) sit outside
    the authentic range in the same direction as Sightengine's verdict.
    This is corroboration of an already-trusted signal, not a replacement.
    """
    se_direction = se_verdict.get("verdict")  # "real" or "fake"
    if se_direction not in ("real", "fake"):
        return False

    # Collect signals. Each is a (value, low, high) tuple meaning
    # that values below low → fake-signal, above high → fake-signal.
    # For "real" direction we invert the comparison.
    signals: list[tuple[float | None, float, float, str]] = []

    # ELA: low is normal, high ELA suggests tampering
    ela = (forensic_context or {}).get("ela", {})
    ela_val = ela.get("mean_difference")
    signals.append((ela_val, 0.05, 0.50, "ela_mean_difference"))

    # Noise: low noise (smoothing) or very high noise both suspicious
    noise = (forensic_context or {}).get("noise", {})
    noise_val = noise.get("noise_variance")
    signals.append((noise_val, 100, 1500, "noise_variance"))

    # FFT: high high-freq ratio suggests upsampling / AI artifacts
    fft = (forensic_context or {}).get("fft", {})
    fft_val = fft.get("high_freq_ratio")
    signals.append((fft_val, 0.001, 0.05, "fft_high_freq_ratio"))

    # Compression: low quality can indicate re-encoding
    comp = (forensic_context or {}).get("compression", {})
    comp_val = comp.get("estimated_quality")
    if comp_val is not None:
        try:
            comp_val = float(comp_val)
        except (TypeError, ValueError):
            comp_val = None
    signals.append((comp_val, 75, 98, "compression_quality"))

    # DCT: high coefficient mean suggests frequency-domain anomaly
    dct_val = (preprocessing or {}).get("dct_mean")
    signals.append((dct_val, 0.5, 5.0, "dct_coefficient_mean"))

    # Wavelet HH: high HH energy suggests injected high-freq noise
    wv = (preprocessing or {}).get("wavelet", {})
    hh_val = wv.get("HH")
    signals.append((hh_val, 0.001, 0.05, "wavelet_hh_energy"))

    # Edge intensity (Canny): very low (too smooth) or very high (too sharp)
    edges = (preprocessing or {}).get("edge_intensity", {})
    canny_val = edges.get("canny") if isinstance(edges, dict) else None
    signals.append((canny_val, 0.01, 0.10, "edge_intensity_canny"))

    agreeing = 0
    total = 0
    for val, low, high, name in signals:
        if val is None:
            continue
        total += 1
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue
        # For "fake" verdict: values outside authentic range agree
        # For "real" verdict:  values inside authentic range agree
        outside = val < low or val > high
        if se_direction == "fake":
            if outside:
                agreeing += 1
        else:  # real
            if not outside:
                agreeing += 1

    if total == 0:
        return False

    majority = total >= 3 and agreeing >= total * 0.6
    logger.info("Forensics corroborate: se_direction=%s signals=%d agreeing=%d majority=%s",
                se_direction, total, agreeing, majority)
    return majority


def evidence_sufficient(se_verdict: dict, forensic_context: dict, preprocessing: dict) -> bool:
    """Decide whether Sightengine evidence alone or with corroboration
    is sufficient to return a verdict without an LLM call.

    Case A: Sightengine alone is confident enough (>=0.8) — existing.
    Case B: Sightengine is moderately confident (0.55–0.8) AND forensic
            evidence independently corroborates the direction.
    """
    se_conf = se_verdict.get("confidence", 0.0)

    # Case A — existing behaviour, keep it
    if se_conf >= 0.8:
        return True

    # Case B — corroboration-extended gate
    if 0.55 <= se_conf < 0.8:
        return _forensics_corroborate(se_verdict, forensic_context, preprocessing)

    return False


def _best_evidence_entry(state: "InvestigationState") -> tuple[dict | None, str]:
    """Find the best evidence entry from the evidence table.

    Returns (entry, capability_id) of the entry with the highest
    confidence >= 0.8, or (None, "") if none qualifies.
    """
    if not state.evidence_table:
        return None, ""
    best = None
    best_conf = -1.0
    for entry in state.evidence_table:
        conf = entry.get("confidence", 0) or 0
        if conf >= 0.8 and conf > best_conf:
            best = entry
            best_conf = conf
    if best:
        return best, best.get("capability", "")
    return None, ""


def _build_verdict_from_entry(entry: dict) -> dict:
    """Build a verdict dict from an evidence table entry."""
    return {
        "verdict": entry.get("verdict", "inconclusive"),
        "confidence": entry.get("confidence", 0.5),
        "analysis_summary": entry.get("analysis_summary", ""),
        "evidence": "",
        "key_indicators": entry.get("conflicting_evidence", []),
    }


def _check_convergence(state: "InvestigationState") -> str | None:
    """Check whether multiple evidence entries agree or disagree.

    Returns 'AGREE', 'SPLIT', 'PARTIAL', or None (insufficient data).
    Does NOT return CONCLUDE/INCONCLUSIVE_STOP — that is the supervisor's job.
    Needs at least 2 entries to produce a signal.
    """
    if len(state.evidence_table) < 2:
        return None
    directions: set[str] = set()
    for entry in state.evidence_table:
        v = entry.get("verdict", "")
        if v in ("fake", "real"):
            directions.add(v)
    if len(directions) == 1:
        return "AGREE"
    if len(directions) >= 2:
        return "SPLIT"
    return "PARTIAL"


def _build_investigation_trace(state: "InvestigationState") -> dict:
    """Build the trace dict returned in the API response."""
    return {
        "rounds_completed": state.rounds_completed,
        "providers_tried": list(state.providers_tried),
        "evidence_table": [
            {
                "round": e.get("round", 0),
                "capability": e.get("capability", "unknown"),
                "verdict": e.get("verdict", "unknown"),
                "confidence": e.get("confidence", 0),
                "analysis_summary": e.get("analysis_summary", "")[:200] if e.get("analysis_summary") else "",
            }
            for e in state.evidence_table
        ],
        "reasoning_log": list(state.reasoning_log),
        "converged": state.converged,
    }


def _capability_to_model_name(capability_id: str | None) -> str:
    """Resolve a capability ID to a model name string."""
    if not capability_id:
        return "deterministic"
    cap_to_model = {
        "sightengine": "sightengine",
        "large_multimodal_reasoning": settings.primary_model,
        "lightweight_multimodal_verifier": settings.fallback1_model,
        "general_multimodal_verifier": settings.fallback2_model,
    }
    return cap_to_model.get(capability_id, "deterministic")


# ── Run supervisor with fallback chain ────────────────────────────────


async def _run_supervisor_with_fallback(
    supervisor_context: str,
    cerebras_agent: Agent | None,
    gemini_agent: Agent | None,
    timeout: int,
    max_retries: int,
) -> tuple[str, bool, str]:
    """Run supervisor with Cerebras → Gemini fallback.

    Mirrors _run_router_with_fallback pattern. Returns (text, ok, model_used).
    If all providers fail, (text="", ok=False, model_used="none") — caller
    handles best-evidence fallback.
    """
    # Primary: Cerebras
    if cerebras_agent is not None:
        logger.info("Trying Supervisor Primary: Cerebras (%s)", settings.supervisor_primary_model)
        try:
            text, ok = await _run_agent_safe(
                cerebras_agent, supervisor_context,
                timeout=timeout, max_retries_on_rate_limit=max_retries,
            )
            if ok and text.strip():
                return text, True, "cerebras"
            logger.warning("Supervisor Primary (Cerebras) returned empty")
        except Exception as exc:
            logger.warning("Supervisor Primary (Cerebras) FAILED: %s", str(exc).split('\n')[0][:200])

    # Fallback: Gemini
    if gemini_agent is not None:
        logger.info("Trying Supervisor Fallback: Gemini (%s)", settings.supervisor_fallback_model)
        try:
            text, ok = await _run_agent_safe(
                gemini_agent, supervisor_context,
                timeout=timeout, max_retries_on_rate_limit=max_retries,
            )
            if ok and text.strip():
                return text, True, "gemini"
            logger.warning("Supervisor Fallback (Gemini) returned empty")
        except Exception as exc:
            logger.warning("Supervisor Fallback (Gemini) FAILED: %s", str(exc).split('\n')[0][:200])

    return "", False, "none"


# ── Run the analysis agent with fallback chain ──────────────────────────

async def _run_analysis_with_fallback(
    analysis_prompt: str,
    image_for_analysis: bytes | None,
    analysis_mime: str,
    analysis_agent: Agent,
    analysis_fb1: Agent,
    analysis_fb2: Agent,
    analysis_frames: list[bytes] | None = None,
    forensic_context: dict[str, Any] | None = None,
    preprocessing_result: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str, bool, dict[str, Any]]:
    """Run Analysis Agent with Supervisor-driven decision loop.

    Replaces the fixed fallback chain with an evidence-driven,
    cost-aware supervisor that reasons about capabilities (not
    provider names) and decides CONCLUDE / GET_SECOND_OPINION /
    INCONCLUSIVE_STOP.

    Sightengine ≥0.8 confidence gate is preserved as a fast path.
    Max 2 supervisor rounds. Investigation trace is returned for
    surfacing in the API response.
    """
    logger.info("RUNNING: %s", _RUNNER_FILE)
    logger.info("Function: _run_analysis_with_fallback()")
    from app.providers.sightengine import analyze_with_sightengine

    verdict: dict[str, Any] = {
        "verdict": "inconclusive", "confidence": 0.0,
        "evidence": "All analysis models unavailable.", "key_indicators": [],
    }
    model_used = "none"
    fallback_used = False

    # Agent lookup by capability key
    agent_map: dict[str, Agent] = {
        "analysis_agent": analysis_agent,
        "analysis_fb1": analysis_fb1,
        "analysis_fb2": analysis_fb2,
    }

    model_name_map: dict[str, str] = {
        "analysis_agent": settings.primary_model,
        "analysis_fb1": settings.fallback1_model,
        "analysis_fb2": settings.fallback2_model,
    }

    # Create supervisor agents: Cerebras (primary) + Gemini (fallback)
    cerebras_supervisor = create_cerebras_supervisor_agent()
    gemini_supervisor = create_gemini_supervisor_agent()
    # Keep the legacy agent as a last resort if neither new one is available
    supervisor_agent = cerebras_supervisor or gemini_supervisor or create_supervisor_agent()

    # ── Investigation state ────────────────────────────────────────
    state = InvestigationState()
    state.reasoning_log = []

    # ── Sightengine REST API ──────────────────────────────────────
    sightengine_was_configured = bool(settings.sightengine_api_user and settings.sightengine_api_secret)
    se_images = analysis_frames if analysis_frames else ([image_for_analysis] if image_for_analysis else None)
    logger.info("SIGHTENGINE CHECK: sightengine_was_configured=%s se_images=%s",
                sightengine_was_configured,
                "present (%d images)" % len(se_images) if se_images else "None")
    sightengine_verdict: dict[str, Any] | None = None
    if sightengine_was_configured and se_images:
        logger.info("Trying Sightengine with %d image(s)...", len(se_images))
        try:
            if len(se_images) == 1:
                se_verdict = await analyze_with_sightengine(
                    image_bytes=se_images[0],
                    mime_type=analysis_mime,
                    timeout=settings.request_timeout_seconds,
                )
            else:
                se_verdict = await _analyze_frames_sightengine(
                    frames=se_images,
                    mime_type=analysis_mime,
                    timeout=settings.request_timeout_seconds,
                )
            logger.info("SIGHTENGINE RAW RESPONSE: %s",
                        json.dumps(se_verdict, indent=2, default=str))
            if se_verdict.get("verdict") not in ("error",):
                sightengine_verdict = se_verdict
                logger.info("Sightengine succeeded: verdict=%s confidence=%.2f frames=%d",
                            sightengine_verdict.get("verdict", "?"),
                            sightengine_verdict.get("confidence", 0),
                            len(se_images))
            else:
                logger.warning("Sightengine FAILED — returned error: %s",
                               se_verdict.get("error", "unknown"))
        except Exception as exc:
            logger.warning("Sightengine FAILED: %s", str(exc).split('\n')[0][:200])
            print(f"\n=== SIGHTENGINE FAILED (will still enter supervisor loop) ===")
    else:
        logger.info("Sightengine not configured or no image (configured=%s se_images=%s)",
                    sightengine_was_configured, bool(se_images))

    # ── Sightengine fast path: ≥0.8 confidence → return directly ──
    if sightengine_verdict is not None:
        se_confidence = sightengine_verdict.get("confidence", 0.0)
        if se_confidence >= 0.8:
            logger.info("Sightengine clear verdict (conf=%.4f >= 0.8) — returning directly",
                        se_confidence)
            state.reasoning_log.append(
                f"Sightengine returned verdict={sightengine_verdict.get('verdict')} "
                f"conf={se_confidence:.2f} (≥0.8) — returned directly, no supervisor needed"
            )
            state.final_verdict = sightengine_verdict
            state.converged = True
            state.rounds_completed = 0
            print(f"\n>>> ANALYSIS PATH: Sightengine fast path (conf={se_confidence:.2f} >= 0.8)")
            print(f">>> Returning verdict={sightengine_verdict.get('verdict')} conf={se_confidence:.2f}")
            return sightengine_verdict, "sightengine", False, {
                "rounds_completed": 0,
                "providers_tried": [],
                "evidence_table": [{
                    "round": 0, "capability": "sightengine",
                    "verdict": sightengine_verdict.get("verdict"),
                    "confidence": se_confidence,
                    "analysis_summary": sightengine_verdict.get("evidence", "Sightengine direct verdict"),
                }],
                "reasoning_log": state.reasoning_log,
                "converged": True,
            }

        # Sightengine < 0.8 — add to evidence for supervisor
        state.reasoning_log.append(
            f"Sightengine returned verdict={sightengine_verdict.get('verdict')} "
            f"conf={se_confidence:.2f} (<0.8) — will be evaluated by supervisor"
        )

    # ── Build analysis prompt with Sightengine context if present ──
    if sightengine_verdict is not None:
        print(f"\n>>> Sightengine result ({sightengine_verdict.get('verdict')}, conf={sightengine_verdict.get('confidence', 0):.2f}) prepended to analysis prompt")
        se_block = (
            "=== SIGHTENGINE DEEPFAKE API RESULT ===\n"
            f"{json.dumps(sightengine_verdict, indent=2)}\n\n"
            "=== RECONCILIATION INSTRUCTION ===\n"
            "Sightengine returned the result above using its proprietary deepfake "
            "detection model. Below you also have the classical forensic evidence "
            "(ELA, FFT, noise, DCT, wavelets, metadata) computed directly from "
            "the image signal.\n\n"
            "Your task: Review ALL sources together. Check for contradictions "
            "between Sightengine's API verdict and the signal-based forensic "
            "measurements. Produce a single reconciled verdict.\n"
            "- If they AGREE → confidence should be HIGH (>= 0.80).\n"
            "- If they CONTRADICT → note the conflict explicitly and adjust "
            "confidence DOWNWARD (0.30–0.60).\n"
            "- The forensic measurements that fall OUTSIDE authentic reference "
            "ranges should carry the most weight.\n"
        )
        analysis_prompt = se_block + analysis_prompt
        state.providers_tried.append("sightengine")
        state.evidence_table.append({
            "round": 0,
            "capability": "sightengine",
            "verdict": sightengine_verdict.get("verdict"),
            "confidence": sightengine_verdict.get("confidence", 0),
            "analysis_summary": sightengine_verdict.get("evidence", "Sightengine analysis"),
            "conflicting_evidence": sightengine_verdict.get("conflicting_evidence", []),
        })

    # ── Evidence sufficiency gate before supervisor loop ────────────
    # Case B: Sightengine 0.55–0.79 with forensic corroboration
    fcx = forensic_context or {}
    ppx = preprocessing_result or {}
    if sightengine_verdict is not None:
        se_conf = sightengine_verdict.get("confidence", 0.0)
        if 0.55 <= se_conf < 0.8 and _forensics_corroborate(sightengine_verdict, fcx, ppx):
            logger.info("Evidence gate: Sightengine conf=%.2f corroborated by forensics — returning directly",
                        se_conf)
            state.reasoning_log.append(
                f"Sightengine returned verdict={sightengine_verdict.get('verdict')} "
                f"conf={se_conf:.2f} corroborated by forensics — returned directly"
            )
            state.final_verdict = sightengine_verdict
            state.converged = True
            state.rounds_completed = 0
            print(f">>> ANALYSIS PATH: Evidence gate — Sightengine+forensics corroborated (conf={se_conf:.2f})")
            return sightengine_verdict, "sightengine", False, _build_investigation_trace(state)

    # ── Supervisor loop ───────────────────────────────────────────
    max_rounds = 2
    convergence_status: str | None = None

    for rounds_completed in range(1, max_rounds + 1):
        state.rounds_completed = rounds_completed

        # Build supervisor context (convergence_status fed as context, not override)
        supervisor_context = build_supervisor_context(
            investigation_state=state,
            sightengine_verdict=sightengine_verdict,
            forensic_context=fcx,
            preprocessing_result=ppx,
            convergence_status=convergence_status,
        )

        # === STAGE 6: SUPERVISOR INPUT ===
        print(f"\n{'='*60}")
        print(f"STAGE 6 — SUPERVISOR INPUT (round {rounds_completed})")
        print(f"{'='*60}")
        print(supervisor_context)
        print(f"{'='*60}\n")

        # ── Run supervisor with Cerebras → Gemini fallback ────
        logger.info("Running supervisor (round %d)...", rounds_completed)
        model_name = supervisor_agent.model.model if hasattr(supervisor_agent.model, 'model') else 'unknown'
        print(f"\n=== SUPERVISOR: calling model (round {rounds_completed}) ===")
        print(f"  Model: {model_name}")
        import time as _time
        _t0 = _time.time()
        supervisor_decision: dict[str, Any] | None = None
        try:
            supervisor_text, ok, supervisor_model_used = await _run_supervisor_with_fallback(
                supervisor_context,
                cerebras_supervisor,
                gemini_supervisor,
                timeout=settings.request_timeout_seconds,
                max_retries=settings.max_retries_primary,
            )
            _elapsed = _time.time() - _t0

            if supervisor_text and supervisor_text.strip():
                print(f"=== SUPERVISOR RAW OUTPUT (round {rounds_completed}, {_elapsed:.1f}s, ok={ok}, model={supervisor_model_used}) ===")
                print(supervisor_text)
                print("=== END SUPERVISOR RAW OUTPUT ===")
                logger.info("========== SUPERVISOR RAW OUTPUT (round %d) ==========", rounds_completed)
                logger.info(supervisor_text)
                logger.info("======================================================")
            else:
                print(f"=== SUPERVISOR EMPTY/FAILED (round {rounds_completed}, {_elapsed:.1f}s, ok={ok}) ===")

            if ok and supervisor_text and supervisor_text.strip():
                supervisor_decision = _extract_supervisor_json(supervisor_text)
            else:
                logger.warning("Supervisor round %d returned empty or failed (ok=%s)",
                               rounds_completed, ok)
        except Exception:
            logger.exception("Supervisor execution failed (round %d)", rounds_completed)

        # ── Infra-failure fallback: best evidence instead of INCONCLUSIVE_STOP ──
        if supervisor_decision is None:
            best_entry, best_cap = _best_evidence_entry(state)
            if best_entry:
                logger.info("Supervisor failed round %d — falling back to best evidence (cap=%s conf=%.2f)",
                            rounds_completed, best_cap, best_entry.get("confidence", 0))
                verdict = _build_verdict_from_entry(best_entry)
                model_used = _capability_to_model_name(best_cap)
                fallback_used = True
                state.final_verdict = verdict
                state.converged = True
                state.reasoning_log.append(
                    f"Round {rounds_completed}: Supervisor infra-failure — "
                    f"falling back to best evidence ({best_cap}, conf={best_entry.get('confidence', 0):.2f})"
                )
                print(f"\n>>> ANALYSIS PATH: Supervisor infra-failure — best-evidence fallback ({best_cap})")
                trace = _build_investigation_trace(state)
                return verdict, model_used, fallback_used, trace
            else:
                print(f"\n*** SUPERVISOR FAILED (round {rounds_completed}) — no fallback evidence, INCONCLUSIVE_STOP ***")
                logger.warning(
                    "Supervisor round %d: invalid output and no fallback evidence. "
                    "Stopping.", rounds_completed
                )
                supervisor_decision = {
                    "action": "INCONCLUSIVE_STOP",
                    "reasoning": "Supervisor failed or returned invalid JSON. No fallback evidence available.",
                    "capability": None,
                }
                state.reasoning_log.append(
                    f"Round {rounds_completed}: Supervisor returned invalid output. "
                    f"Pipeline safely stopped."
                )
        else:
            state.reasoning_log.append(
                f"Round {rounds_completed}: Supervisor decision: "
                f"{supervisor_decision.get('action')} "
                f"— {supervisor_decision.get('reasoning', '')[:200]}"
            )

        decision = supervisor_decision.get("action", "INCONCLUSIVE_STOP")

        if decision == "CONCLUDE":
            trusted_cap = supervisor_decision.get("capability")
            model_used = _capability_to_model_name(trusted_cap) if trusted_cap else "deterministic"
            fallback_used = rounds_completed > 1 or bool(sightengine_verdict)

            provider_entry = None
            if trusted_cap:
                for entry in reversed(state.evidence_table):
                    if entry.get("capability") == trusted_cap:
                        provider_entry = entry
                        break
            if not provider_entry and state.evidence_table:
                provider_entry = state.evidence_table[-1]
            if provider_entry:
                verdict = {
                    "verdict": provider_entry.get("verdict", "inconclusive"),
                    "confidence": provider_entry.get("confidence", 0.5),
                    "analysis_summary": provider_entry.get("analysis_summary", ""),
                    "evidence": supervisor_decision.get("reasoning", ""),
                    "key_indicators": provider_entry.get("conflicting_evidence", []),
                }
            else:
                verdict = {
                    "verdict": "inconclusive",
                    "confidence": 0.5,
                    "evidence": supervisor_decision.get("reasoning", ""),
                    "analysis_summary": "Investigation concluded without provider evidence.",
                    "key_indicators": [],
                }
            state.final_verdict = verdict
            state.converged = True
            _log_reasoning(state, rounds_completed, "CONCLUDE", (
                f"Trusted: {trusted_cap or 'none'}. "
                f"{supervisor_decision.get('reasoning', '')[:200]}"
            ))
            logger.info("Supervisor CONCLUDE: verdict=%s conf=%.2f trusted=%s",
                        verdict["verdict"], verdict["confidence"], trusted_cap)
            print(f"\n>>> ANALYSIS PATH: Supervisor CONCLUDE")
            print(f">>> trusted={trusted_cap} verdict={verdict['verdict']} conf={verdict['confidence']:.2f}")
            print(f">>> evidence_table: {[(e.get('capability'), e.get('verdict')) for e in state.evidence_table]}")
            trace = _build_investigation_trace(state)
            return verdict, model_used, fallback_used, trace

        elif decision == "GET_SECOND_OPINION":
            capability_id = supervisor_decision.get("capability", "")
            if not capability_id:
                state.reasoning_log.append(
                    f"Round {rounds_completed}: GET_SECOND_OPINION "
                    f"with no capability specified — treating as INCONCLUSIVE_STOP"
                )
                decision = "INCONCLUSIVE_STOP"
            else:
                agent_key = CAPABILITY_TO_AGENT_KEY.get(capability_id)
                if not agent_key or agent_key not in agent_map:
                    state.reasoning_log.append(
                        f"Round {rounds_completed}: GET_SECOND_OPINION "
                        f"recommended unknown capability "
                        f"'{capability_id}' — treating as INCONCLUSIVE_STOP"
                    )
                    decision = "INCONCLUSIVE_STOP"

            if decision == "GET_SECOND_OPINION":
                agent_key = CAPABILITY_TO_AGENT_KEY[capability_id]
                provider_agent = agent_map[agent_key]
                provider_model_name = model_name_map[agent_key]
                logger.info("Supervisor round %d: GET_SECOND_OPINION — running %s",
                            rounds_completed, capability_id)
                _log_reasoning(state, rounds_completed, "GET_SECOND_OPINION", (
                    f"Selected: {capability_id}. "
                    f"{supervisor_decision.get('reasoning', '')[:200]}"
                ))

                try:
                    analysis_text, ok = await _run_agent_safe(
                        provider_agent,
                        analysis_prompt, image_for_analysis, analysis_mime,
                        timeout=settings.request_timeout_seconds,
                        max_retries_on_rate_limit=settings.max_retries_primary,
                    )

                    # === STAGE 4: ANALYSIS RAW RESPONSE ===
                    print(f"\n{'='*60}")
                    print(f"STAGE 4 — ANALYSIS RAW RESPONSE ({capability_id})")
                    print(f"{'='*60}")
                    print(f"ok={ok}, text_length={len(analysis_text)}")
                    if analysis_text and analysis_text.strip():
                        print(analysis_text)
                    else:
                        print("(empty response)")
                    print(f"{'='*60}\n")

                    if ok and analysis_text.strip():
                        parsed = _extract_json(analysis_text)

                        # === STAGE 5: PARSED ANALYSIS JSON ===
                        print(f"\n{'='*60}")
                        print(f"STAGE 5 — PARSED ANALYSIS JSON ({capability_id})")
                        print(f"{'='*60}")
                        if parsed is not None:
                            print(json.dumps(parsed, indent=2))
                        else:
                            print("_extract_json returned None (invalid JSON)")
                        print(f"{'='*60}\n")

                        if _analysis_json_valid(parsed):
                            state.providers_tried.append(capability_id)
                            state.evidence_table.append({
                                "round": rounds_completed,
                                "capability": capability_id,
                                "verdict": parsed.get("verdict", "inconclusive"),
                                "confidence": parsed.get("confidence", 0),
                                "analysis_summary": parsed.get("analysis_summary", ""),
                                "conflicting_evidence": parsed.get("conflicting_evidence", []),
                            })
                            logger.info("  %s succeeded: verdict=%s conf=%.2f",
                                        capability_id,
                                        parsed.get("verdict", "?"),
                                        parsed.get("confidence", 0))
                            model_used = provider_model_name
                            fallback_used = True

                            # ── Convergence check (context only, NOT decision) ──
                            convergence_status = _check_convergence(state)
                            if convergence_status:
                                logger.info("Convergence status for round %d: %s",
                                            rounds_completed, convergence_status)
                            continue

                        logger.warning("%s returned no JSON", capability_id)
                    logger.warning("%s FAILED", capability_id)
                    state.reasoning_log.append(
                        f"Round {rounds_completed}: {capability_id} failed or returned no valid JSON"
                    )
                except Exception as exc:
                    logger.warning("%s FAILED: %s", capability_id, str(exc).split('\n')[0][:200])
                    state.reasoning_log.append(
                        f"Round {rounds_completed}: {capability_id} error: {str(exc).split(chr(10))[0][:120]}"
                    )

                if rounds_completed >= max_rounds:
                    state.reasoning_log.append(
                        f"Max rounds ({max_rounds}) reached — stopping"
                    )
                    decision = "INCONCLUSIVE_STOP"

        if decision == "INCONCLUSIVE_STOP":
            _log_reasoning(state, rounds_completed, "INCONCLUSIVE_STOP", (
                supervisor_decision.get('reasoning', 'Supervisor decided to stop')[:200]
            ))
            verdict = {
                "verdict": "inconclusive",
                "confidence": 0.5,
                "evidence": "Investigation completed: supervisor determined evidence was "
                           "insufficient or contradictory.",
                "analysis_summary": supervisor_decision.get("reasoning",
                                    "Investigation inconclusive after supervisor review."),
                "key_indicators": ["Disagreement between analysis sources"],
            }
            model_used = _capability_to_model_name(
                state.evidence_table[-1].get("capability") if state.evidence_table else None
            ) or "deterministic"
            fallback_used = True
            state.final_verdict = verdict
            state.converged = False
            logger.info("Supervisor INCONCLUSIVE_STOP after round %d", rounds_completed)
            print(f"\n>>> ANALYSIS PATH: Supervisor INCONCLUSIVE_STOP (round {rounds_completed})")
            print(f">>> evidence_table: {[(e.get('capability'), e.get('verdict')) for e in state.evidence_table]}")
            trace = _build_investigation_trace(state)
            return verdict, model_used, fallback_used, trace

    # ── Final: max rounds reached without conclusive decision ──────
    verdict = {
        "verdict": "inconclusive",
        "confidence": 0.5,
        "evidence": "All investigation rounds completed without a conclusive verdict. "
                    "Evidence was insufficient or contradictory across providers.",
        "analysis_summary": "Investigation inconclusive — exhausted all rounds.",
        "key_indicators": ["Analysis pipeline degraded — no conclusive verdict"],
    }
    model_used = _capability_to_model_name(
        state.evidence_table[-1].get("capability") if state.evidence_table else None
    ) or "deterministic"
    fallback_used = True
    state.final_verdict = verdict
    state.converged = False
    logger.info("Analysis final: inconclusive after %d rounds", state.rounds_completed)
    print(f"\n>>> ANALYSIS PATH: Max rounds reached ({state.rounds_completed}) — fallthrough")
    print(f">>> evidence_table: {[(e.get('capability'), e.get('verdict')) for e in state.evidence_table]}")
    trace = _build_investigation_trace(state)
    return verdict, model_used, fallback_used, trace


def _log_reasoning(state: InvestigationState, round_num: int, decision: str, detail: str) -> None:
    """Append a structured reasoning entry to the investigation log."""
    evidence_summary = ""
    if state.evidence_table:
        lines = []
        for e in state.evidence_table:
            cap = e.get("capability", "?")
            ver = e.get("verdict", "?")
            conf = e.get("confidence", 0)
            lines.append(f"  - {cap}: {ver} (conf={conf:.2f})")
        evidence_summary = "\n".join(lines)

    state.reasoning_log.append(
        f"Round {round_num}: {decision}\n"
        f"Evidence:\n{evidence_summary}\n"
        f"Reasoning: {detail}"
    )


# ── Run the report with fallback ───────────────────────────────────────

async def _run_report_with_fallback(
    report_prompt: str,
    report_agent: Agent,
    report_fb1: Agent,
    report_fb2: Agent,
    report_fb3: Agent,
    verdict: dict[str, Any],
    forensic_context: dict[str, Any],
    model_used: str,
    fallback_used: bool,
) -> tuple[str, str, bool]:
    """Run Report Agent with Groq -> NVIDIA Omni -> Gemini -> Deterministic fallback.

    Returns (report_text, report_model, report_degraded).
    """
    logger.info("RUNNING: %s", _RUNNER_FILE)
    logger.info("Function: _run_report_with_fallback()")
    report_text = ""
    report_model = "none"
    report_degraded = False

    # Primary: Groq
    logger.info("Trying Report Primary: Groq (%s)", settings.report_model)
    try:
        report_text, ok = await _run_agent_safe(
            report_agent, report_prompt, timeout=settings.request_timeout_seconds,
        )
        if ok and report_text.strip():
            report_model = settings.report_model
            logger.info("Report Primary succeeded: %d chars", len(report_text))
            return report_text, report_model, report_degraded
        logger.warning("Report Primary (Groq) FAILED")
    except Exception as exc:
        logger.warning("Report Primary (Groq) FAILED: %s", str(exc).split('\n')[0][:200])

    # Fallback 1: NVIDIA Omni
    logger.info("Trying Report Fallback 1: NVIDIA Omni (%s)", settings.report_fallback2_model)
    try:
        report_text, ok = await _run_agent_safe(
            report_fb1, report_prompt, timeout=settings.request_timeout_seconds,
        )
        if ok and report_text.strip():
            report_model = settings.report_fallback2_model
            report_degraded = True
            logger.info("Report Fallback 1 (NVIDIA) succeeded: %d chars", len(report_text))
            return report_text, report_model, report_degraded
        logger.warning("Report Fallback 1 (NVIDIA) FAILED")
    except Exception as exc:
        logger.warning("Report Fallback 1 (NVIDIA) FAILED: %s", str(exc).split('\n')[0][:200])

    # Fallback 2: Gemini
    if settings.enable_gemini_fallback and settings.google_api_key:
        logger.info("Trying Report Fallback 2: Gemini (%s)", settings.report_fallback1_model)
        try:
            report_text, ok = await _run_agent_safe(
                report_fb3, report_prompt, timeout=settings.request_timeout_seconds,
            )
            if ok and report_text.strip():
                report_model = settings.report_fallback1_model
                report_degraded = True
                logger.info("Report Fallback 2 (Gemini) succeeded: %d chars", len(report_text))
                return report_text, report_model, report_degraded
            logger.warning("Report Fallback 2 (Gemini) FAILED")
        except Exception as exc:
            logger.warning("Report Fallback 2 (Gemini) FAILED: %s", str(exc).split('\n')[0][:200])
    else:
        logger.info("Report Fallback 2 (Gemini) skipped — not configured")

    # Fallback 3: Deterministic report
    logger.info("Trying Report Fallback 3: Deterministic (last resort)")
    from app.agents.report_agent import generate_deterministic_report
    report_text = generate_deterministic_report(verdict, forensic_context, model_used, fallback_used)
    report_model = "deterministic"
    report_degraded = True
    logger.info("Report Fallback 3 succeeded: deterministic report (%d chars)", len(report_text))
    return report_text, report_model, report_degraded


# ── Main pipeline ──────────────────────────────────────────────────────

async def run_pipeline(
    file_path: str,
    file_bytes: bytes,
    mime_type: str,
    filename: str,
) -> dict[str, Any]:
    logger.info("RUNNING: %s", _RUNNER_FILE)
    logger.info("Function: run_pipeline()")
    request_id = _new_request_id()
    pipeline_start = time.perf_counter()
    agent_logs: list[dict] = []
    router_degraded = False
    report_degraded = False

    if not Path(file_path).exists():
        return _error_result(request_id, "File does not exist.")

    # ═══════════════════════════════════════════════════════════════
    # Deterministic Stages (no ADK agents)
    # ═══════════════════════════════════════════════════════════════

    stage_start = time.perf_counter()
    validation = validate_file(file_bytes, filename, mime_type, file_path)
    if not validation.valid:
        return _error_result(request_id, validation.error or "File validation failed")
    agent_logs.append({
        "agent": "security_layer", "valid": True,
        "latency_seconds": round(time.perf_counter() - stage_start, 3),
    })

    stage_start = time.perf_counter()
    pipeline_type = "image_pipeline"
    preprocessing_result: dict[str, Any] = {"status": "skipped"}
    try:
        if mime_type.startswith("video/"):
            pipeline_type = "video_pipeline"
            preprocessing_result = run_video_pipeline(file_path)
        else:
            preprocessing_result = run_image_pipeline(file_path)
    except Exception as exc:
        preprocessing_result = {"status": "error", "error": str(exc)}
    agent_logs.append({
        "agent": "preprocessing", "pipeline": pipeline_type,
        "status": preprocessing_result.get("status"),
        "latency_seconds": round(time.perf_counter() - stage_start, 3),
    })

    stage_start = time.perf_counter()
    forensic_context = collect_forensic_context(file_path)
    sec_result = security_checkpoint(forensic_context)
    if sec_result.get("blocked"):
        return _error_result(request_id, sec_result.get("reason", "Blocked"))
    secured_context = sec_result.get("secured_context", forensic_context)
    agent_logs.append({
        "agent": "forensic_tools", "tool_count": len(forensic_context),
        "latency_seconds": round(time.perf_counter() - stage_start, 3),
    })

    # Log forensic summary
    _log_forensic_summary(secured_context, preprocessing_result)

    # === STAGE 2: FORENSIC FEATURES ===
    print(f"\n{'='*60}")
    print("STAGE 2 — FORENSIC FEATURES (raw values)")
    print(f"{'='*60}")
    _fc = secured_context
    print(f"ELA mean_difference: {_fc.get('ela', {}).get('mean_difference', 'N/A')}")
    print(f"ELA summary: {_fc.get('ela', {}).get('summary', 'N/A')}")
    print(f"FFT high_freq_ratio: {_fc.get('fft', {}).get('high_freq_ratio', 'N/A')}")
    print(f"FFT evidence: {_fc.get('fft', {}).get('evidence', 'N/A')}")
    print(f"Noise variance (Laplacian): {_fc.get('noise', {}).get('noise_variance', 'N/A')}")
    print(f"Noise evidence: {_fc.get('noise', {}).get('evidence', 'N/A')}")
    print(f"JPEG block_boundary_ratio: {_fc.get('jpeg_artifacts', {}).get('block_boundary_ratio', 'N/A')}")
    print(f"JPEG summary: {_fc.get('jpeg_artifacts', {}).get('summary', 'N/A')}")
    print(f"Compression estimated_quality: {_fc.get('compression', {}).get('estimated_quality', 'N/A')}%")
    print(f"Compression evidence: {_fc.get('compression', {}).get('evidence', 'N/A')}")
    print(f"DCT coefficient mean: {preprocessing_result.get('dct_mean', 'N/A')}")
    _wv = preprocessing_result.get('wavelet', {})
    print(f"Wavelet LL={_wv.get('LL', 'N/A')} LH={_wv.get('LH', 'N/A')} HL={_wv.get('HL', 'N/A')} HH={_wv.get('HH', 'N/A')}")
    _ed = preprocessing_result.get('edge_intensity', {})
    print(f"Edge intensity canny={_ed.get('canny', 'N/A')} sobel={_ed.get('sobel', 'N/A')} laplacian={_ed.get('laplacian', 'N/A')}")
    print(f"Clone detection: {_fc.get('clones', {}).get('summary', _fc.get('clones', {}).get('evidence', 'N/A'))}")
    print(f"Face count: {_fc.get('faces', {}).get('face_count', 'N/A')}")
    print(f"Face evidence: {_fc.get('faces', {}).get('evidence', 'N/A')}")
    print(f"EXIF tag_count: {_fc.get('exif', {}).get('tag_count', 'N/A')}")
    print(f"EXIF editing_software: {_fc.get('exif', {}).get('editing_software', [])}")
    print(f"EXIF ai_tools: {_fc.get('exif', {}).get('ai_generation_tools', [])}")
    print(f"EXIF summary: {_fc.get('exif', {}).get('summary', 'N/A')}")
    _pp = preprocessing_result
    print(f"Pipeline ELA_score: {_pp.get('ela_score', 'N/A')}")
    print(f"Pipeline FFT_mean: {_pp.get('fft_mean', 'N/A')}")
    print(f"SHA-256: {_fc.get('hash', {}).get('sha256', 'N/A')}")
    print(f"pHash: {_fc.get('hash', {}).get('phash', 'N/A')}")
    print(f"{'='*60}\n")

    # Diagnostic images and anomaly regions from preprocessing
    diagnostic_images = preprocessing_result.get("diagnostic_images", {})
    anomaly_regions = preprocessing_result.get("anomaly_regions", [])

    # Video frame extraction
    image_for_analysis: bytes | None = file_bytes
    analysis_frames: list[bytes] | None = None
    analysis_mime = mime_type
    ext = Path(file_path).suffix.lower()
    if ext in {".mp4", ".webm", ".mov", ".avi"}:
        frames = _extract_key_frames(file_path, num_frames=5)
        if frames:
            image_for_analysis = frames[0]   # first frame for LLM fallbacks
            analysis_frames = frames          # all frames for Sightengine multi-frame
            analysis_mime = "image/jpeg"

    # ═══════════════════════════════════════════════════════════════
    # ADK Agent Chain — Each stage in its OWN isolated session
    # ═══════════════════════════════════════════════════════════════

    (router_agent, router_fb1, router_fb2, router_fb3,
     analysis_agent, analysis_fb1, analysis_fb2,
     report_agent, report_fb1, report_fb2, report_fb3) = _build_pipeline_agents()

    # ── Stage: Router Agent (with fallback chain) ────────────────
    stage_start = time.perf_counter()
    router_prompt = (
        f"Classify this media file for the deepfake pipeline.\n"
        f"Filename: {filename}\nMIME type: {mime_type}\n"
        f"File path: {file_path}\nFile size: {len(file_bytes)} bytes\n"
        f"\nCall validate_upload and detect_faces, then produce a "
        f"routing decision as JSON."
    )
    routing, router_model_used, router_fb = await _run_router_with_fallback(
        router_prompt, router_agent, router_fb1, router_fb2, router_fb3,
        mime_type, pipeline_type,
    )

    # === STAGE 1: ROUTER RESULT ===
    print(f"\n{'='*60}")
    print("STAGE 1 — ROUTER RESULT")
    print(f"{'='*60}")
    print(f"Model used: {router_model_used}")
    print(f"Fallback: {router_fb}")
    print(f"Router JSON:\n{json.dumps(routing, indent=2)}")
    print(f"{'='*60}\n")

    router_latency = time.perf_counter() - stage_start
    router_degraded = router_fb or (router_model_used == "deterministic")
    agent_logs.append({
        "agent": "router_agent",
        "model_used": router_model_used,
        "latency_seconds": round(router_latency, 3),
        "routing": routing,
        "degraded": router_degraded,
    })
    logger.info("=== PIPELINE: Router stage complete ===")
    logger.info("  model=%s degraded=%s viable=%s",
                router_model_used, router_degraded, routing.get("viable_for_analysis"))

    if not routing.get("viable_for_analysis", True):
        return _build_final_result(
            request_id=request_id, verdict={"verdict": "error",
                "error": routing.get("early_exit_reason", "Not viable")},
            routing=routing, forensic_context=secured_context,
            agent_logs=agent_logs, pipeline_start=pipeline_start,
            model_used=router_model_used, fallback_used=router_fb,
            router_degraded=router_degraded, report_degraded=False,
            diagnostic_images=diagnostic_images,
            anomaly_regions=anomaly_regions,
            preprocessing_result=preprocessing_result,
            report_text="",
        )

    # ── Stage: Analysis Agent (with fallback chain) ──────────────
    stage_start = time.perf_counter()
    forensic_evidence_block = _format_forensic_evidence(secured_context, preprocessing_result)
    analysis_prompt = (
        f"Analyze this image and the forensic evidence below to determine "
        f"if it is REAL, FAKE, or INCONCLUSIVE.\n\n"
        f"=== ROUTER SUMMARY ===\n{json.dumps(routing, indent=2)}\n\n"
        f"{forensic_evidence_block}\n"
        f"=== REFERENCE RANGES (empirically calibrated) ===\n"
        f"Use these to interpret forensic measurements:\n"
        f"  ELA mean_difference:     authentic 0.05–0.50, suspicious >1.0\n"
        f"  Noise variance:          authentic 100–1500, suspicious <50 or >3000\n"
        f"  FFT high_freq_ratio:     authentic 0.001–0.05, suspicious >0.10\n"
        f"  DCT coefficient mean:    authentic 0.5–5.0, suspicious >10.0\n"
        f"  Wavelet HH energy:       authentic 0.001–0.05, suspicious >0.10\n"
        f"  JPEG block_boundary:     authentic 0.3–0.7, suspicious <0.2 or >0.8\n"
        f"  Compression quality:     authentic 75–98%, suspicious <60% or '100%'\n"
        f"  Edge intensity (Canny):  authentic 0.01–0.10, suspicious <0.005 or >0.20\n"
        f"  Real photo anchor: ELA≈0.19, noise_variance≈470\n\n"
        f"=== INSTRUCTIONS ===\n"
        f"1. Examine the image visually for manipulation artifacts.\n"
        f"2. Review the FORENSIC EVIDENCE above — every value was computed "
        f"from this image's signal and metadata.\n"
        f"3. Compare each forensic value against the reference ranges above.\n"
        f"4. Identify any contradictions between visual appearance and "
        f"forensic measurements.\n"
        f"5. If they disagree, the forensic evidence should be weighted more heavily.\n"
        f"6. Values OUTSIDE the authentic ranges are strong indicators of manipulation, "
        f"even if the image looks realistic.\n"
        f"7. Output your verdict as JSON using the required schema."
    )
    # === STAGE 3: ANALYSIS PROMPT (fully rendered) ===
    print(f"\n{'='*60}")
    print("STAGE 3 — ANALYSIS PROMPT (fully rendered)")
    print(f"{'='*60}")
    print(analysis_prompt)
    print(f"{'='*60}\n")

    verdict, model_used, fallback_used, investigation_trace = await _run_analysis_with_fallback(
        analysis_prompt, image_for_analysis, analysis_mime,
        analysis_agent, analysis_fb1, analysis_fb2,
        analysis_frames=analysis_frames,
        forensic_context=secured_context,
        preprocessing_result=preprocessing_result,
    )

    analysis_latency = time.perf_counter() - stage_start
    agent_logs.append({
        "agent": "analysis_agent",
        "model_used": model_used,
        "fallback_used": fallback_used,
        "verdict": verdict.get("verdict", "inconclusive"),
        "latency_seconds": round(analysis_latency, 3),
    })
    logger.info("=== PIPELINE: Analysis stage complete ===")
    logger.info("  incoming verdict=%s confidence=%.4f model=%s fallback=%s",
                verdict.get("verdict", "?"), verdict.get("confidence", 0),
                model_used, fallback_used)

    # ── Stage: Report Agent (with fallback chain) ───────────────
    stage_start = time.perf_counter()
    report_prompt = (
        f"Generate a professional forensic report based on the following.\n\n"
        f"=== Analysis Verdict ===\n{json.dumps(verdict, indent=2)}\n\n"
        f"=== Supporting Tool Results ===\n{json.dumps(secured_context, indent=2)[:3000]}\n\n"
        f"=== Pipeline Info ===\n"
        f"Model used: {model_used}\n"
        f"Fallback triggered: {fallback_used}\n"
        f"File: {filename}\nFile type: {routing.get('file_type', 'unknown')}\n"
        f"Face detected: {routing.get('face_present', False)}\n"
        f"Resolution: {routing.get('resolution', 'unknown')}\n"
        f"\nYou have access to the search_web tool. Use it if the image "
        f"is notable or controversial to find external references. "
        f"Generate a structured report. Do NOT re-decide the verdict."
    )
    report_text, report_model_used, report_degraded = await _run_report_with_fallback(
        report_prompt, report_agent, report_fb1, report_fb2, report_fb3,
        verdict, secured_context, model_used, fallback_used,
    )

    report_latency = time.perf_counter() - stage_start
    agent_logs.append({
        "agent": "report_agent",
        "model_used": report_model_used,
        "latency_seconds": round(report_latency, 3),
        "degraded": report_degraded,
    })
    logger.info("=== PIPELINE: Report stage complete ===")
    logger.info("  model=%s degraded=%s", report_model_used, report_degraded)

    pipeline_latency = time.perf_counter() - pipeline_start

    # ═══════════════════════════════════════════════════════════════
    # Output Assembly
    # ═══════════════════════════════════════════════════════════════
    logger.info("=== PIPELINE: Entering output assembly ===")
    logger.info("  incoming verdict=%s confidence=%.4f",
                verdict.get("verdict", "?"), verdict.get("confidence", 0))
    return _build_final_result(
        request_id=request_id,
        verdict=verdict,
        routing=routing,
        forensic_context=secured_context,
        agent_logs=agent_logs,
        pipeline_start=pipeline_start,
        model_used=model_used,
        fallback_used=fallback_used,
        router_degraded=router_degraded,
        report_degraded=report_degraded,
        report_text=report_text,
        diagnostic_images=diagnostic_images,
        anomaly_regions=anomaly_regions,
        preprocessing_result=preprocessing_result,
        investigation_trace=investigation_trace,
    )


# ── Result builders ────────────────────────────────────────────────────

def _error_result(request_id: str, error: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "report_json": {"verdict": "error", "error": error, "recommendations": [], "timestamp": _now_utc()},
        "report_text": "", "report_markdown": "", "report_pdf": b"",
        "forensic_context": {}, "routing": {},
        "agent_logs": [],
        "degraded": False,
        "diagnostic_images": {},
        "anomaly_regions": [],
    }


def _build_final_result(
    request_id: str,
    verdict: dict[str, Any],
    routing: dict[str, Any],
    forensic_context: dict[str, Any],
    agent_logs: list[dict],
    pipeline_start: float,
    model_used: str,
    fallback_used: bool,
    router_degraded: bool,
    report_degraded: bool,
    report_text: str = "",
    diagnostic_images: dict | None = None,
    anomaly_regions: list | None = None,
    preprocessing_result: dict | None = None,
    investigation_trace: dict | None = None,
) -> dict[str, Any]:
    pipeline_latency = time.perf_counter() - pipeline_start

    # Confidence — use the provider's own calibrated value directly.
    # The fusion formula (blending Sightengine's commercial output with
    # unweighted heuristic votes from ELA/FFT/noise/etc.) has been removed
    # because it was never validated against labeled data and was actively
    # making the calibrated confidence worse.
    provider_conf = verdict.get("confidence", 0.5)
    logger.info("=== VERDICT CHAIN ===")
    logger.info("  Provider confidence: %.4f", provider_conf)
    logger.info("  Final verdict: %s (conf=%.4f)", verdict.get("verdict", "?"), provider_conf)

    # === STAGE 7: FINAL VERDICT LOGIC ===
    _investigation_trace = investigation_trace or {}
    _evidence_table = _investigation_trace.get("evidence_table", [])
    _reasoning_log = _investigation_trace.get("reasoning_log", [])
    _converged = _investigation_trace.get("converged", False)
    print(f"\n{'='*60}")
    print("STAGE 7 — FINAL VERDICT LOGIC")
    print(f"{'='*60}")
    print(f"Verdict from analysis: {json.dumps(verdict, indent=2)}")
    print(f"\nEvidence table ({len(_evidence_table)} entries):")
    for _e in _evidence_table:
        print(f"  round={_e.get('round')} cap={_e.get('capability')} verdict={_e.get('verdict')} conf={_e.get('confidence')}")
    print(f"\nReasoning log ({len(_reasoning_log)} entries):")
    for _r in _reasoning_log:
        print(f"  {_r[:200]}")
    print(f"\nConverged: {_converged}")
    print(f"Model used: {model_used}")
    print(f"Fallback used: {fallback_used}")
    # Determine which rule selected the verdict
    if _converged:
        _last_reasoning = _reasoning_log[-1] if _reasoning_log else ""
        if "Sightengine" in _last_reasoning and "returned directly" in _last_reasoning:
            print(f"Rule: Sightengine fast path (confidence >= 0.8)")
        elif "CONCLUDE" in _last_reasoning:
            print(f"Rule: Supervisor CONCLUDE — trusted provider verdict")
        else:
            print(f"Rule: Converged via supervisor investigation")
    elif _reasoning_log and any("Supervisor returned invalid" in r for r in _reasoning_log):
        print(f"Rule: Supervisor failed — safe default to INCONCLUSIVE_STOP")
    elif _reasoning_log and any("INCONCLUSIVE_STOP" in r for r in _reasoning_log):
        print(f"Rule: Supervisor INCONCLUSIVE_STOP")
    else:
        print(f"Rule: Max rounds reached or fallthrough — inconclusive")
    print(f"{'='*60}\n")

    # ── Create immutable final verdict (Req 8) ────────────────────
    # Copy the verdict so no later code can mutate the original
    final_verdict = dict(verdict)
    final_verdict["confidence"] = provider_conf

    report_json = build_report_json(
        request_id=request_id,
        verdict=final_verdict,
        routing=routing,
        forensic_context=forensic_context,
        pipeline_latency=pipeline_latency,
        model_used=model_used,
        fallback_used=fallback_used,
        investigation_trace=investigation_trace,
    )
    logger.info("Report verdict: %s (conf=%.4f)", report_json.get("verdict", "?"), report_json.get("confidence", 0))
    report_markdown = format_report_markdown(report_json, report_text)

    # Always attempt PDF — never skip, never return empty
    report_pdf = b""
    try:
        from app.services.pdf_service import generate_pdf
        report_pdf = generate_pdf(report_markdown)
        logger.info("PDF generated: %d bytes", len(report_pdf))
    except Exception as exc:
        logger.warning("PDF generation skipped: %s", exc)

    entry = {
        "request_id": request_id,
        "file_hash": forensic_context.get("hash", {}).get("sha256", "unknown"),
        "verdict": report_json["verdict"],
        "confidence": report_json["confidence"],
        "model_used": model_used,
        "fallback_used": fallback_used,
        "router_degraded": router_degraded,
        "report_degraded": report_degraded,
        "latencies_seconds": {"total": round(pipeline_latency, 3)},
    }
    try:
        write_entry(entry)
    except Exception as exc:
        logger.error("Failed to write audit entry: %s", exc)

    logger.info("API verdict: %s (conf=%.4f)", report_json.get("verdict", "?"), report_json.get("confidence", 0))
    logger.info("=== VERDICT CHAIN COMPLETE ===")

    return {
        "request_id": request_id,
        "report_json": report_json,
        "report_text": report_text,
        "report_markdown": report_markdown,
        "report_pdf": report_pdf,
        "forensic_context": forensic_context,
        "routing": routing,
        "agent_logs": agent_logs,
        "degraded": router_degraded or report_degraded,
        "diagnostic_images": diagnostic_images or {},
        "anomaly_regions": anomaly_regions or [],
        "investigation_trace": investigation_trace or {},
    }
