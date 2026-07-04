"""FastAPI backend for DeepGuard AI analysis.

All forensic analysis is now delegated to orchestrator_workflow in agent.py,
which runs the ADK root_agent through the Runner and returns populated
agent_logs, a dynamic verdict, and dynamic recommendations.

BUG 1  Verdict is now derived from ELA result inside orchestrator_workflow.
BUG 6  'frames' key is used consistently from orchestrator through this response.
CHECK 2  agent_logs are returned from the orchestrator and surfaced in the response.
CHECK 4  File-type validation is performed inside orchestrator_workflow.
CHECK 5  File-size validation is performed inside orchestrator_workflow.
"""

import shutil
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .agent import orchestrator_workflow

app = FastAPI(title="DeepGuard AI", version="1.0.0")

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
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


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    """Accept an uploaded file, run the full forensic pipeline, and return results."""
    file_location = UPLOAD_DIR / file.filename
    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to save file: {exc}"
        ) from exc
    finally:
        await file.close()

    # Delegate entirely to orchestrator_workflow which runs the ADK agent
    try:
        pipeline_result = await orchestrator_workflow(str(file_location))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Forensic pipeline error: {exc}"
        ) from exc

    # Surface a validation/pipeline error to the caller
    report_json = pipeline_result.get("report_json", {})
    if report_json.get("verdict") == "error":
        raise HTTPException(
            status_code=422,
            detail=report_json.get("error", "File validation failed"),
        )

    results = pipeline_result.get("results", {})
    ela_result = results.get("ela", {})
    exif_result = results.get("exif", {})
    hash_result = results.get("hash", {})
    frames_result = results.get("frames", {})  # BUG 6: consistent "frames" key
    ml_result = results.get("ml_ensemble", {})

    response = {
        "ela": {
            "summary": ela_result.get("summary", ela_result.get("error", "")),
            "diff_bbox": ela_result.get("diff_bbox"),
        },
        "exif": {
            "summary": exif_result.get("summary", exif_result.get("error", "")),
            "exif": exif_result.get("exif", {}),
        },
        "hash": {
            "sha256": hash_result.get("sha256", hash_result.get("error", "")),
            "phash": hash_result.get("phash", ""),
        },
        "frames": {  # BUG 6: consistent "frames" key
            "summary": frames_result.get("summary", frames_result.get("error", "")),
            "frame_count": frames_result.get("frame_count", 0),
            "average_brightness": frames_result.get("average_brightness", 0),
        },
        "ml_ensemble": {         # ADD THIS
            "confidence_percent": ml_result.get("confidence_percent", 50.0),
            "verdict": ml_result.get("verdict", "unknown"),
            "model_results": ml_result.get("model_results", {}),
            "weights_used": ml_result.get("weights_used", {}),
        },
       # BUG 1: verdict now comes from orchestrator_workflow (ELA-driven)
        "verdict": report_json.get("verdict", "ok"),
        # CHECK 1: dynamic recommendations from orchestrator_workflow
        "recommendations": report_json.get("recommendations", []),
        # CHECK 2: agent_logs populated from ADK Runner events
        "agent_logs": pipeline_result.get("agent_logs", []),
    }
    return response
