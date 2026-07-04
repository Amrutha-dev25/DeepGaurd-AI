# ruff: noqa
"""DeepGuard AI – forensic orchestrator and sub-agents."""

import asyncio
import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from .forensics import (
        analyze_ela,
        analyze_frames,
        compute_hash,
        extract_exif,
        run_ml_ensemble,
        security_checkpoint,
        validate_file,
    )

# ---------------------------------------------------------------------------
# Helper: UTC timestamp
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.datetime.now(ZoneInfo("UTC")).isoformat()


# ---------------------------------------------------------------------------
# Helper: Determine verdict from ELA result
# ---------------------------------------------------------------------------

def _determine_verdict(ela_result: dict) -> str:
    if "error" in ela_result:
        return "unknown"
    summary = ela_result.get("summary", "").lower()
    if "manipulation detected" in summary:
        return "suspicious"
    return "ok"


# ---------------------------------------------------------------------------
# Helper: Build dynamic recommendations
# ---------------------------------------------------------------------------

def _build_recommendations(
    ela_result: dict,
    exif_result: dict,
    frames_result: dict,
    verdict: str,
) -> list[str]:
    recs = []
    ela_summary = ela_result.get("summary", "").lower()
    if "manipulation detected" in ela_summary:
        recs.append(
            "ELA detected pixel-level inconsistencies. "
            "Cross-reference with the original source file."
        )
    exif_data = exif_result.get("exif", {})
    if not exif_data:
        recs.append(
            "No EXIF metadata found. Metadata may have been stripped, "
            "which is common in manipulated files."
        )
    frame_count = frames_result.get("frame_count", 0)
    summary = frames_result.get("summary", "")
    if frame_count <= 1 or "single image" in summary.lower():
        recs.append(
            "Only one frame was analyzed. "
            "Upload a longer video clip for more thorough analysis."
        )
    if verdict == "suspicious":
        recs.append(
            "Overall verdict is suspicious. "
            "Consider submitting to a dedicated deepfake detection model."
        )
    if not recs:
        recs.append(
            "No strong indicators of manipulation found. "
            "Always verify with multiple tools before drawing conclusions."
        )
    return recs


# ---------------------------------------------------------------------------
# ADK tool functions
# ---------------------------------------------------------------------------

def ela_agent_tool(file_path: str) -> dict:
    """Run Error Level Analysis on file_path and return a dict result."""
    return analyze_ela(file_path)


def exif_agent_tool(file_path: str) -> dict:
    """Extract EXIF metadata and return a dict result."""
    return extract_exif(file_path)


def hash_agent_tool(file_path: str) -> dict:
    """Compute SHA-256 hash of the file and return a dict result."""
    return compute_hash(file_path)

def ml_ensemble_tool(file_path: str) -> dict:
    """Run ML ensemble deepfake detection on file_path."""
    return run_ml_ensemble(file_path)

def frame_agent_tool(file_path: str) -> dict:
    """Run OpenCV frame-level analysis on a video or image."""
    return analyze_frames(file_path)


# ---------------------------------------------------------------------------
# ADK root agent
# ---------------------------------------------------------------------------

root_agent = Agent(
    name="deepguard_orchestrator",
    model="gemini-2.5-flash",
    instruction=(
        "You are a forensic orchestrator. "
        "When given a file path, call all five tools: "
        "ela_agent_tool, exif_agent_tool, hash_agent_tool, "
        "frame_agent_tool, ml_ensemble_tool. "
        "Call each tool exactly once with the file path provided. "
        "Do not skip any tool."
    ),
    tools=[ela_agent_tool, exif_agent_tool, hash_agent_tool, frame_agent_tool, ml_ensemble_tool],
)


# ---------------------------------------------------------------------------
# ADK Runner: runs root_agent and collects logs
# ---------------------------------------------------------------------------

async def _run_agent_async(file_path: str) -> tuple[dict, list[dict]]:
    """Run root_agent via ADK Runner and collect tool results and logs."""
    session_id = f"session_{datetime.datetime.now(ZoneInfo('UTC')).timestamp()}"
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="deepguard",
        user_id="user",
        session_id=session_id,
    )
    runner = Runner(
        agent=root_agent,
        app_name="deepguard",
        session_service=session_service,
    )
    logs = []
    tool_results = {}
    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=f"Analyze this file: {file_path}")],
    )
    async for event in runner.run_async(
        user_id="user",
        session_id=session_id,
        new_message=message,
    ):
        if not event.content or not event.content.parts:
            continue
        for part in event.content.parts:
            if hasattr(part, "function_response") and part.function_response:
                tool_name = part.function_response.name
                tool_result = dict(part.function_response.response)
                tool_results[tool_name] = tool_result
                logs.append({
                    "agent": "deepguard_orchestrator",
                    "tool": tool_name,
                    "result": str(tool_result)[:300],
                    "timestamp": _now_utc(),
                })
            elif hasattr(part, "text") and part.text:
                logs.append({
                    "agent": "deepguard_orchestrator",
                    "tool": "model_response",
                    "result": part.text[:300],
                    "timestamp": _now_utc(),
                })
    return tool_results, logs

def _determine_verdict_with_ml(ml_result: dict) -> str:
        """Determine verdict using real ML ensemble confidence score."""
        if "error" in ml_result and not ml_result.get("model_results"):
            return "unknown"
        verdict = ml_result.get("verdict", "unknown")
        if verdict in ("fake", "suspicious", "real", "unknown"):
            return verdict
        confidence = ml_result.get("final_confidence", 0.5)
        if confidence >= 0.65:
            return "fake"
        elif confidence >= 0.40:
            return "suspicious"
        return "real"
        
# ---------------------------------------------------------------------------
# Main orchestrator workflow
# ---------------------------------------------------------------------------

async def orchestrator_workflow(file_path: str) -> dict:
    """Execute the full forensic pipeline."""

    if not os.path.isabs(file_path):
        uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        file_path = os.path.join(uploads_dir, file_path)

    validation = validate_file(file_path)
    if validation and "error" in validation:
        return {
            "results": {},
            "report_text": f"Validation failed: {validation['error']}",
            "report_json": {
                "verdict": "error",
                "error": validation["error"],
                "recommendations": [],
                "timestamp": _now_utc(),
            },
            "agent_logs": [],
            "activity_log_path": "",
        }

    try:
        tool_results, agent_logs = await _run_agent_async(file_path)
    except Exception as e:
        agent_logs = [{
            "agent": "deepguard_orchestrator",
            "tool": "error",
            "result": str(e),
            "timestamp": _now_utc(),
        }]
        tool_results = {}

    ela_res = tool_results.get("ela_agent_tool") or ela_agent_tool(file_path)
    exif_res = tool_results.get("exif_agent_tool") or exif_agent_tool(file_path)
    hash_res = tool_results.get("hash_agent_tool") or hash_agent_tool(file_path)
    frames_res = tool_results.get("frame_agent_tool") or frame_agent_tool(file_path)
    ml_res = tool_results.get("ml_ensemble_tool") or ml_ensemble_tool(file_path)

    aggregated = {
        "ela": ela_res,
        "exif": exif_res,
        "hash": hash_res,
        "frames": frames_res,
        "ml_ensemble": ml_res,
    }

    secured, audit = security_checkpoint(aggregated)

    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "activity_log.json")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("--- SESSION ---\n")
        json.dump(audit, f, indent=2)
        f.write("\n")

    if audit.get("blocked"):
        return {
            "results": {},
            "report_text": "Security checkpoint blocked this request.",
            "report_json": {
                "verdict": "blocked",
                "recommendations": [
                    "Investigate potential prompt injection or malicious input."
                ],
                "timestamp": _now_utc(),
            },
            "agent_logs": agent_logs,
            "activity_log_path": log_path,
        }
    
    verdict = _determine_verdict_with_ml(secured.get("ml_ensemble", ml_res))
    verdict = _determine_verdict(secured.get("ela", ela_res))
    recommendations = _build_recommendations(
        ela_result=secured.get("ela", ela_res),
        exif_result=secured.get("exif", exif_res),
        frames_result=secured.get("frames", frames_res),
        verdict=verdict,
    )

    report_text = (
        "DeepGuard AI Forensic Report\n"
        "================================\n"
        f"Generated on: {_now_utc()}\n\n"
        "=== Analysis Summary ===\n"
        f"ELA     : {secured.get('ela', {}).get('summary', 'N/A')}\n"
        f"EXIF    : {secured.get('exif', {}).get('summary', 'N/A')}\n"
        f"SHA-256 : {secured.get('hash', {}).get('sha256', 'N/A')}\n"
        f"Frames  : {secured.get('frames', {}).get('summary', 'N/A')}\n"
        f"Verdict : {verdict}\n"
        "\n=== Recommendations ===\n"
        + "\n".join(f"- {r}" for r in recommendations)
    )

    report_json = {
        "timestamp": _now_utc(),
        "results": secured,
        "verdict": verdict,
        "recommendations": recommendations,
    }

    return {
        "results": secured,
        "report_text": report_text,
        "report_json": report_json,
        "agent_logs": agent_logs,
        "activity_log_path": log_path,
    }