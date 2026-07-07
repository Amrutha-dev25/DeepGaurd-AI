"""FastAPI backend for DeepGuard AI analysis.

Delegates to orchestrator_workflow in agent.py and returns populated results.
"""

import shutil
import traceback
from pathlib import Path

try:
    import magic
except Exception:
    magic = None  # Fallback if libmagic not available
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Pillow for image validation
from PIL import Image, UnidentifiedImageError

from .agent import orchestrator_workflow

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="DeepGuard AI", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Restrict CORS to known origins; wildcard kept for development but can be removed later.
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/")
async def root():
    return {"message": "DeepGuard AI API is running"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/health/ready")
async def health_ready():
    return {"status": "ready"}


@app.post("/api/analyze")
@limiter.limit("20/minute")
async def analyze(request: Request, file: UploadFile = File(...)):
    """Accept an uploaded file, run the full forensic pipeline, and return results.
    Supported formats: PNG, JPEG, JPG, WEBP.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    # Save file to temporary location
    file_location = UPLOAD_DIR / Path(file.filename).name
    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}") from exc
    finally:
        await file.close()

    # Reject empty files
    if file_location.stat().st_size == 0:
        file_location.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes).")

    # Determine MIME type with fallback chain
    mime = None
    # 1. Try python-magic if available
    if magic:
        try:
            mime = magic.from_file(str(file_location), mime=True)
        except Exception:
            mime = None
    # 2. Fallback to UploadFile's declared content_type
    if not mime:
        mime = file.content_type
    # 3. Pillow fallback to infer format when MIME still unknown
    pil_format = None
    try:
        with Image.open(file_location) as img:
            pil_format = img.format  # e.g., 'PNG', 'JPEG', etc.
    except Exception:
        pass
    if not mime and pil_format:
        pil_mime_map = {
            "PNG": "image/png",
            "JPEG": "image/jpeg",
            "JPG": "image/jpeg",
            "WEBP": "image/webp",
        }
        mime = pil_mime_map.get(pil_format)
    # Normalize MIME (some browsers may report image/jpg as image/jpeg)
    if mime == "image/jpg":
        mime = "image/jpeg"

    print(f"[DEBUG] UploadFile.content_type={file.content_type}  magic={mime}  pillow={pil_format}")

    allowed_mimes = ("image/png", "image/jpeg", "image/webp")
    if mime not in allowed_mimes:
        file_location.unlink(missing_ok=True)
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file format: {mime}. Allowed: PNG, JPEG, JPG, WEBP.",
        )

    # Additional sanity check: try opening with Pillow to catch corrupted images
    try:
        with Image.open(file_location) as img:
            img.verify()  # Verify that file is not corrupted
    except (UnidentifiedImageError, OSError):
        file_location.unlink(missing_ok=True)
        raise HTTPException(status_code=415, detail="Uploaded file is corrupted or not a valid image.")

    # Delegate to orchestrator workflow
    try:
        pipeline_result = await orchestrator_workflow(str(file_location))
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Forensic pipeline error: {exc}") from exc

    report_json = pipeline_result.get("report_json", {})
    if report_json.get("verdict") == "error":
        raise HTTPException(status_code=422, detail=report_json.get("error", "File validation failed"))

    # Log upstream model/service errors (do NOT hide them)
    for log in pipeline_result.get("agent_logs", []):
        if log.get("tool") == "error":
            res_str = str(log.get("result", ""))
            if "503" in res_str or "UNAVAILABLE" in res_str.upper():
                print(f"[WARN] Upstream error detected in agent log: {res_str}")

    results = pipeline_result.get("results", {})
    response = {
        "ela": {
            "summary": results.get("ela", {}).get("summary", results.get("ela", {}).get("error", "")),
            "diff_bbox": results.get("ela", {}).get("diff_bbox"),
        },
        "exif": {
            "summary": results.get("exif", {}).get("summary", results.get("exif", {}).get("error", "")),
            "exif": results.get("exif", {}).get("exif", {}),
        },
        "hash": {
            "sha256": results.get("hash", {}).get("sha256", results.get("hash", {}).get("error", "")),
            "phash": results.get("hash", {}).get("phash", ""),
        },
        "frames": {
            "summary": results.get("frames", {}).get("summary", results.get("frames", {}).get("error", "")),
            "frame_count": results.get("frames", {}).get("frame_count", 0),
            "average_brightness": results.get("frames", {}).get("average_brightness", 0),
        },
        "ml_ensemble": {
            "confidence_percent": results.get("ml_ensemble", {}).get("confidence_percent", 50.0),
            "verdict": results.get("ml_ensemble", {}).get("verdict", "unknown"),
            "model_results": results.get("ml_ensemble", {}).get("model_results", {}),
            "weights_used": results.get("ml_ensemble", {}).get("weights_used", {}),
        },
        "verdict": report_json.get("verdict", "inconclusive"),
        "recommendations": report_json.get("recommendations", []),
        "explanation": report_json.get("explanation", ""),
        "agent_logs": pipeline_result.get("agent_logs", []),
    }
    return response
