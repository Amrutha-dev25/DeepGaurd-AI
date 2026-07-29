"""FastAPI layer — thin, no business logic.  Delegates to ADK Runner via app.runner."""

import logging
import os
import shutil
import sys
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.guardrails.injection import check_user_input
from app.guardrails.validation import validate_extension, validate_path_traversal, validate_file_size
from app.runner import run_pipeline

logger = logging.getLogger(__name__)

_log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.basicConfig(level=_log_level, stream=sys.stdout, format="%(levelname)s:%(name)s:%(message)s")

# Suppress noisy third-party tracebacks at provider-failure granularity
# litellm prints full stack traces on API errors (429, 503, etc.)
for _lib in ("litellm", "LiteLLM"):
    logging.getLogger(_lib).setLevel(logging.CRITICAL)
# google_adk prints "Node execution failed with exception" + full traceback
# at ERROR level every time a provider call fails and the pipeline falls back
logging.getLogger("google_adk").setLevel(logging.CRITICAL)


def _validate_api_keys():
    """Validate required API keys at startup. Prints warning on missing keys without SystemExit."""
    missing: list[str] = []
    if not settings.sightengine_api_user or not settings.sightengine_api_secret:
        missing.append("SIGHTENGINE_API_USER / SIGHTENGINE_API_SECRET (Analysis Primary — will fall back to NVIDIA)")
    if not settings.primary_api_key:
        missing.append("PRIMARY_API_KEY (needed for Analysis Fallback 1 — NVIDIA Nemotron Omni)")
    if not settings.groq_api_key:
        missing.append("GROQ_API_KEY (needed for Router and Report Agent)")
    if not settings.fallback1_api_key:
        missing.append("FALLBACK1_API_KEY (needed for Analysis Fallback 2 — NVIDIA Nemotron Nano 12B VL)")
    if settings.enable_gemini_fallback and not settings.google_api_key:
        missing.append("GOOGLE_API_KEY (needed because ENABLE_GEMINI_FALLBACK=true)")
    if missing:
        logger.warning("DeepGuard AI — missing API key(s). Pipeline will degrade gracefully:")
        for k in missing:
            logger.warning("  - %s", k)
    else:
        logger.info("All required API keys are present.")

    # Provider configuration logging — shows actual execution order
    logger.info("=== DeepGuard AI Provider Configuration ===")
    logger.info("Router Primary: Groq (%s)", settings.router_model)
    logger.info("Router Fallback 1: NVIDIA Omni (%s)", settings.router_fallback2_model)
    logger.info("Router Fallback 2: Gemini (%s) — %s", settings.router_fallback1_model,
                 "ENABLED" if settings.enable_gemini_fallback else "DISABLED (set ENABLE_GEMINI_FALLBACK=true)")
    logger.info("Router Fallback 3: Deterministic routing (last resort)")
    logger.info("Analysis Primary: Sightengine REST API (deepfake detection — used as evidence for LLM reconciliation)")
    logger.info("Analysis Fallback 1: NVIDIA Nemotron Omni (%s)", settings.primary_model)
    logger.info("Analysis Fallback 2: NVIDIA Nemotron Nano 12B VL (%s)", settings.fallback1_model)
    logger.info("Analysis Fallback 3: Gemini (%s) — %s", settings.fallback2_model,
                 "ENABLED" if settings.enable_gemini_fallback else "DISABLED (set ENABLE_GEMINI_FALLBACK=true)")
    logger.info("Analysis Fallback 4: Last-resort fallthrough (no LLM available)")
    logger.info("Report Primary: Groq (%s)", settings.report_model)
    logger.info("Report Fallback 1: NVIDIA Omni (%s)", settings.report_fallback2_model)
    logger.info("Report Fallback 2: Gemini (%s) — %s", settings.report_fallback1_model,
                 "ENABLED" if settings.enable_gemini_fallback else "DISABLED (set ENABLE_GEMINI_FALLBACK=true)")
    logger.info("Report Fallback 3: Deterministic report generator (last resort)")
    logger.info("Supervisor: Gemini (%s) — %s", settings.supervisor_model or "gemini-2.5-flash",
                 "ENABLED" if settings.google_api_key else "DISABLED (set GOOGLE_API_KEY)")
    logger.info("Gemini Fallback Toggle: %s", "ENABLED" if settings.enable_gemini_fallback else "DISABLED")


limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(application: FastAPI):
    _validate_api_keys()
    yield


app = FastAPI(title="DeepGuard AI", version="3.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
# Add production frontend domain from env (set to Vercel URL in Cloud Run)
if settings.frontend_url:
    origins.append(settings.frontend_url)
# CORS_ORIGINS can add extra origins (comma-separated)
if settings.cors_origins:
    for o in settings.cors_origins.split(","):
        o = o.strip()
        if o and o not in origins:
            origins.append(o)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "video/mp4"}
SUPPORTED_FORMATS_MSG = "PNG, JPEG, WEBP, MP4"


@app.get("/")
async def root():
    return {"message": "DeepGuard AI API is running", "version": "3.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    return {"status": "ready"}


# Cloud Run standard probe endpoints (alias for /health)
@app.get("/livez")
async def livez():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    return {"status": "ready"}


@app.post("/api/analyze")
@limiter.limit("20/minute")
async def analyze(request: Request, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    # ── Guardrails: validate filename ──────────────────────────
    filename = file.filename

    ext_check = validate_extension(filename)
    if not ext_check.valid:
        raise HTTPException(status_code=400, detail=ext_check.error)

    trav_check = validate_path_traversal(filename)
    if not trav_check.valid:
        raise HTTPException(status_code=400, detail=trav_check.error)

    # ── Guardrails: check user input for injection ─────────────
    inj_check = check_user_input(filename)
    if inj_check.get("blocked"):
        raise HTTPException(status_code=400, detail=inj_check.get("reason"))

    # ── Save upload ────────────────────────────────────────────
    file_location = UPLOAD_DIR / Path(filename).name
    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}") from exc
    finally:
        await file.close()

    # ── Guardrails: file size check ────────────────────────────
    file_bytes = b""
    try:
        file_bytes = file_location.read_bytes()
    except Exception as exc:
        file_location.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to read file: {exc}") from exc

    size_check = validate_file_size(len(file_bytes))
    if not size_check.valid:
        file_location.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=size_check.error)

    # ── MIME detection ─────────────────────────────────────────
    mime = _detect_mime(file_location, file.content_type)
    if not mime:
        file_location.unlink(missing_ok=True)
        raise HTTPException(status_code=415, detail=f"Could not determine file type. Supported: {SUPPORTED_FORMATS_MSG}.")
    if mime not in ALLOWED_MIME_TYPES:
        file_location.unlink(missing_ok=True)
        raise HTTPException(status_code=415, detail=f"Unsupported format '{mime}'. Allowed: {SUPPORTED_FORMATS_MSG}.")

    # ── Integrity check ────────────────────────────────────────
    if not _is_valid_media(file_location, mime):
        file_location.unlink(missing_ok=True)
        raise HTTPException(status_code=415, detail="File is corrupted or not a valid media file.")

    # ── Run pipeline ──────────────────────────────────────────
    try:
        result = await run_pipeline(
            file_path=str(file_location),
            file_bytes=file_bytes,
            mime_type=mime,
            filename=filename,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc
    finally:
        try:
            file_location.unlink(missing_ok=True)
        except Exception:
            pass

    # ── Build response ─────────────────────────────────────────
    report_json = result.get("report_json", {})
    fc = result.get("forensic_context", {})

    response = {
        "ela": {
            "summary": fc.get("ela", {}).get("evidence", ""),
            "diff_bbox": fc.get("ela", {}).get("diff_bbox"),
            "mean_difference": fc.get("ela", {}).get("mean_difference"),
        },
        "exif": {
            "summary": fc.get("exif", {}).get("evidence", ""),
            "exif": fc.get("exif", {}).get("tags", {}),
            "editing_software": fc.get("exif", {}).get("editing_software", []),
            "ai_generation_tools": fc.get("exif", {}).get("ai_generation_tools", []),
        },
        "hash": {
            "sha256": fc.get("hash", {}).get("sha256", ""),
            "phash": fc.get("hash", {}).get("phash", ""),
        },
        "noise": {
            "noise_variance": fc.get("noise", {}).get("noise_variance"),
            "evidence": fc.get("noise", {}).get("evidence", ""),
        },
        "compression": {
            "estimated_quality": fc.get("compression", {}).get("estimated_quality"),
            "evidence": fc.get("compression", {}).get("evidence", ""),
        },
        "fft": {
            "high_freq_ratio": fc.get("fft", {}).get("high_freq_ratio"),
            "evidence": fc.get("fft", {}).get("evidence", ""),
        },
        "temporal": {
            "frame_count": fc.get("frames", {}).get("frame_count", 0),
            "motion_score": fc.get("frames", {}).get("motion_score"),
            "evidence": fc.get("frames", {}).get("evidence", ""),
        },
        "verdict": report_json.get("verdict", "inconclusive"),
        "confidence": report_json.get("confidence", 0),
        "confidence_percent": report_json.get("confidence_percent", 0),
        "recommendations": report_json.get("recommendations", []),
        "explanation": report_json.get("evidence", ""),
        "key_indicators": report_json.get("key_indicators", []),
        "analysis_summary": report_json.get("analysis_summary", ""),
        "visual_observations": report_json.get("visual_observations", []),
        "forensic_observations": report_json.get("forensic_observations", []),
        "frame_analysis": report_json.get("frame_analysis"),
        "raw_prob": report_json.get("raw_prob"),
        "supporting_evidence": report_json.get("supporting_evidence", []),
        "conflicting_evidence": report_json.get("conflicting_evidence", []),
        "limitations": report_json.get("limitations", ""),
        "diagnostic_images": result.get("diagnostic_images", {}),
        "anomaly_regions": result.get("anomaly_regions", []),
        "pipeline": {
            "routing": result.get("routing", {}),
            "model_used": report_json.get("model_used", "unknown"),
            "pipeline_time_seconds": report_json.get("pipeline_time_seconds", 0),
            "fallback_triggered": report_json.get("fallback_triggered", False),
            "degraded": result.get("degraded", False),
        },
        "agent_logs": result.get("agent_logs", []),
        "request_id": result.get("request_id", ""),
    }

    if result.get("report_text"):
        response["report_text"] = result["report_text"]
    if result.get("report_markdown"):
        response["report_markdown"] = result["report_markdown"]

    return response


# ── Helpers ───────────────────────────────────────────────────────────

def _detect_mime(file_location: Path, content_type: str | None) -> str | None:
    # Priority 1: libmagic (magic bytes detection)
    magic_mime = None
    try:
        import magic
        magic_mime = magic.from_file(str(file_location), mime=True)
    except Exception:
        pass
    if magic_mime and magic_mime in ALLOWED_MIME_TYPES:
        return magic_mime

    # Priority 2: HTTP Content-Type header
    if content_type and content_type in ALLOWED_MIME_TYPES:
        return content_type

    # Priority 3: PIL image format detection
    try:
        with Image.open(file_location) as img:
            fmt = img.format
        _MAP = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
        m = _MAP.get(fmt)
        if m:
            return m
    except Exception:
        pass

    # Priority 4: Extension-based fallback
    ext = file_location.suffix.lower()
    _EXT_MAP = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".mp4": "video/mp4", ".webm": "video/webm",
        ".mov": "video/quicktime", ".avi": "video/x-msvideo",
    }
    return _EXT_MAP.get(ext)


def _is_valid_media(file_location: Path, mime: str) -> bool:
    if mime.startswith("video/"):
        import cv2
        cap = cv2.VideoCapture(str(file_location))
        ok = cap.isOpened()
        cap.release()
        return ok
    try:
        with Image.open(file_location) as img:
            img.verify()
        return True
    except (UnidentifiedImageError, OSError):
        return False
