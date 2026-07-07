# ruff: noqa
"""DeepGuard AI – forensic orchestrator and sub-agents."""

import asyncio
import datetime
import hashlib
import json
import os
import pathlib
from pathlib import Path
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.tools import AgentTool
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

BASE_DIR = pathlib.Path(__file__).parent.resolve()
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

from .config import config
from .forensics import (
        analyze_ela,
        analyze_noise,
        analyze_jpeg_artifacts,
        detect_clones,
        detect_faces,
        analyze_compression,
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
# ADK tool functions (Primitives)
# ---------------------------------------------------------------------------

def perform_ela_tool(file_path: str) -> dict:
    return analyze_ela(file_path)

def extract_exif_tool(file_path: str) -> dict:
    return extract_exif(file_path)

def compute_hash_tool(file_path: str) -> dict:
    return compute_hash(file_path)

def ml_ensemble_tool(file_path: str) -> dict:
    return run_ml_ensemble(file_path)

def analyze_frames_tool(file_path: str) -> dict:
    return analyze_frames(file_path)

def analyze_noise_tool(file_path: str) -> dict:
    return analyze_noise(file_path)

def analyze_jpeg_artifacts_tool(file_path: str) -> dict:
    return analyze_jpeg_artifacts(file_path)

def detect_clones_tool(file_path: str) -> dict:
    return detect_clones(file_path)

def detect_faces_tool(file_path: str) -> dict:
    return detect_faces(file_path)

def analyze_compression_tool(file_path: str) -> dict:
    return analyze_compression(file_path)

# ---------------------------------------------------------------------------
# Specialized Sub-Agents (True Multi-Agent Design)
# ---------------------------------------------------------------------------

image_video_agent = Agent(
    name="image_video_analysis_agent",
    model=config.model,
    instruction=(
        "You are the Image & Video Analysis Agent. Your responsibility is to analyze "
        "visual inconsistencies in media files. Use perform_ela_tool for image pixel "
        "compression analysis (ELA), analyze_frames_tool for video frame/brightness analysis, "
        "analyze_noise_tool to measure local noise variance, analyze_jpeg_artifacts_tool for "
        "grid discrepancies, and detect_clones_tool to search for duplicate regions."
    ),
    tools=[perform_ela_tool, analyze_frames_tool, analyze_noise_tool, analyze_jpeg_artifacts_tool, detect_clones_tool]
)

metadata_agent = Agent(
    name="metadata_agent",
    model=config.model,
    instruction=(
        "You are the Metadata Agent. Your responsibility is to extract EXIF data, "
        "compute cryptographic hashes, and estimate compression quality. "
        "Use extract_exif_tool, compute_hash_tool, and analyze_compression_tool. "
        "Call these tools given the file path and return the findings."
    ),
    tools=[extract_exif_tool, compute_hash_tool, analyze_compression_tool]
)

ml_analysis_agent = Agent(
    name="ml_analysis_agent",
    model=config.model,
    instruction=(
        "You are the Machine Learning Analysis Agent. Your responsibility is to run the "
        "ML ensemble detector on the file using the ml_ensemble_tool, and detect face "
        "regions using detect_faces_tool. Call these tools given the file path and report."
    ),
    tools=[ml_ensemble_tool, detect_faces_tool]
)

# ---------------------------------------------------------------------------
# ADK Root Coordinator Agent
# ---------------------------------------------------------------------------

root_agent = Agent(
    name="deepguard_coordinator",
    model=config.model,
    instruction=(
        "You are the DeepGuard Coordinator Agent. You manage a team of specialized sub-agents "
        "to perform deepfake forensics on a given file. "
        "You must call the following agent tools exactly once with the file path: "
        "1. image_video_analysis_agent_tool "
        "2. metadata_agent_tool "
        "3. ml_analysis_agent_tool "
        "Do not skip any agent tools. Wait for their results."
    ),
    tools=[
        AgentTool(agent=image_video_agent),
        AgentTool(agent=metadata_agent),
        AgentTool(agent=ml_analysis_agent)
    ],
)

# ---------------------------------------------------------------------------
# Workflow Execution
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

    # Generate cache key based on file hash to ensure uniqueness
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        hasher.update(f.read())
    file_hash = hasher.hexdigest()
    
    final_cache_path = RESULTS_DIR / f"{file_hash}_final.json"
    inter_cache_path = RESULTS_DIR / f"{file_hash}_intermediate.json"

    if final_cache_path.exists():
        print("Cache Hit: Loading final result")
        with open(final_cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Execute agents via Runner
    agent_logs = []
    aggregated = {}
    
    if inter_cache_path.exists():
        print("Cache Hit: Loading intermediate forensic data")
        with open(inter_cache_path, "r", encoding="utf-8") as f:
            aggregated = json.load(f)
            
    if not aggregated:
        async def run_pipeline(model_name=None):
            if model_name:
                root_agent.model = model_name
                image_video_agent.model = model_name
                metadata_agent.model = model_name
                ml_analysis_agent.model = model_name

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
            message = genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=f"Analyze this file comprehensively: {file_path}")],
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
                        res_dict = dict(part.function_response.response)
                        
                        mapping = {
                            "perform_ela_tool": "ela",
                            "extract_exif_tool": "exif",
                            "compute_hash_tool": "hash",
                            "analyze_frames_tool": "frames",
                            "ml_ensemble_tool": "ml_ensemble",
                            "analyze_noise_tool": "noise",
                            "analyze_jpeg_artifacts_tool": "jpeg_artifacts",
                            "detect_clones_tool": "clones",
                            "detect_faces_tool": "faces",
                            "analyze_compression_tool": "compression"
                        }
                        if tool_name in mapping:
                            aggregated[mapping[tool_name]] = res_dict

                        agent_logs.append({
                            "agent": "sub_agent",
                            "tool": tool_name,
                            "result": str(res_dict)[:300],
                            "timestamp": _now_utc(),
                        })
                    elif hasattr(part, "text") and part.text:
                        agent_logs.append({
                            "agent": "deepguard_coordinator",
                            "tool": "model_response",
                            "result": part.text[:300],
                            "timestamp": _now_utc(),
                        })

        try:
            # Wrap runner call with a retry on rate limit / 503
            await run_pipeline()
        except Exception as e:
            is_503 = getattr(e, "code", None) == 503 or "503" in str(e) or "UNAVAILABLE" in str(e).upper()
            if is_503:
                agent_logs.append({
                    "agent": "deepguard_coordinator",
                    "tool": "fallback",
                    "result": "Primary model unavailable. Retrying with secondary Flash model.",
                    "timestamp": _now_utc(),
                })
                try:
                    await run_pipeline(model_name="gemini-2.5-flash")
                except Exception as inner_e:
                    # Both models unavailable — fall through to direct tool calls
                    agent_logs.append({
                        "agent": "deepguard_coordinator",
                        "tool": "fallback",
                        "result": f"Flash model also unavailable ({inner_e}). Using direct tool execution.",
                        "timestamp": _now_utc(),
                    })
            else:
                agent_logs.append({
                    "agent": "deepguard_coordinator",
                    "tool": "error",
                    "result": str(e),
                    "timestamp": _now_utc(),
                })

    # Intelligent Fallback: only call tools if data is missing from agent runs
    if "ela" not in aggregated:
        aggregated["ela"] = perform_ela_tool(file_path)
    if "exif" not in aggregated:
        aggregated["exif"] = extract_exif_tool(file_path)
    if "hash" not in aggregated:
        aggregated["hash"] = compute_hash_tool(file_path)
    if "frames" not in aggregated:
        aggregated["frames"] = analyze_frames_tool(file_path)
    if "ml_ensemble" not in aggregated:
        aggregated["ml_ensemble"] = ml_ensemble_tool(file_path)
    if "noise" not in aggregated:
        aggregated["noise"] = analyze_noise_tool(file_path)
    if "jpeg_artifacts" not in aggregated:
        aggregated["jpeg_artifacts"] = analyze_jpeg_artifacts_tool(file_path)
    if "clones" not in aggregated:
        aggregated["clones"] = detect_clones_tool(file_path)
    if "faces" not in aggregated:
        aggregated["faces"] = detect_faces_tool(file_path)
    if "compression" not in aggregated:
        aggregated["compression"] = analyze_compression_tool(file_path)
        
    # Save intermediate cache
    with open(inter_cache_path, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, indent=2)

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
    
    # Verdict logic uses robust state machine pattern
    ml_res = aggregated.get("ml_ensemble", {})
    if not ml_res or "error" in ml_res or ml_res.get("status") == "failed":
        verdict = "inconclusive"
    else:
        verdict = ml_res.get("verdict", "inconclusive")

    # Data Integrity Check: Ensure at least 5 out of 10 analysis metrics were successfully generated
    success_count = sum(1 for tool in ["ela", "exif", "hash", "frames", "ml_ensemble", "noise", "jpeg_artifacts", "clones", "faces", "compression"] 
                        if tool in aggregated and "error" not in aggregated[tool] and aggregated[tool].get("status") != "failed")
    if success_count < 5:
        verdict = "inconclusive"

    # Confidence Filtering: Force inconclusive if < 30%
    confidence = ml_res.get("confidence_percent", 0.0)
    if confidence < 30.0:
        verdict = "inconclusive"

    if verdict not in ["real", "fake", "inconclusive"]:
        verdict = "inconclusive"

    # Build recommendations and explanation dynamically
    recs = []
    explanations = []
    
    # ELA
    ela_res = aggregated.get("ela", {})
    if ela_res.get("status") == "success":
        mean_diff = ela_res.get("measurements", {}).get("mean_difference", 0.0)
        if mean_diff > 1.8:
            explanations.append(f"ELA detected localized compression anomalies (mean difference of {mean_diff:.2f}).")
            recs.append("Cross-reference ELA anomalies with the original source image structure.")
        else:
            explanations.append(f"ELA indicated relatively uniform compression level differences across the frame (mean difference of {mean_diff:.2f}).")
            
    # EXIF
    exif_res = aggregated.get("exif", {})
    if exif_res.get("status") == "success":
        tag_count = exif_res.get("measurements", {}).get("tag_count", 0)
        software_modified = exif_res.get("measurements", {}).get("software_modified", False)
        if tag_count == 0:
            explanations.append("Metadata was removed or was not present in the uploaded media.")
            recs.append("Metadata has been stripped. Check external sources for original capture logs.")
        elif software_modified:
            explanations.append("EXIF metadata indicates image editing/processing software was used.")
            recs.append("EXIF tags verify editing software usage. Inspect software metadata signatures.")
        else:
            explanations.append(f"EXIF metadata was found containing {tag_count} active tags.")
            
    # JPEG artifacts
    ja_res = aggregated.get("jpeg_artifacts", {})
    if ja_res.get("status") == "success":
        ratio = ja_res.get("measurements", {}).get("block_boundary_ratio", 1.0)
        if ratio > 1.2 or ratio < 0.8:
            explanations.append(f"JPEG block boundary artifacts indicate inconsistent encoding (ratio {ratio:.2f}).")
        else:
            explanations.append(f"JPEG block artifacts are consistent with standard single-generation encoding (ratio {ratio:.2f}).")
            
    # Clones
    clone_res = aggregated.get("clones", {})
    if clone_res.get("status") == "success":
        matches = clone_res.get("measurements", {}).get("clone_matches_count", 0)
        if matches > 5:
            explanations.append(f"Clone detection identified {matches} duplicated regions inside the image.")
            recs.append("Spliced duplicate patches detected. Check for copy-paste manipulation.")
        else:
            explanations.append("No copy-move cloning or identical duplicate regions were found.")
            
    # Faces
    face_res = aggregated.get("faces", {})
    if face_res.get("status") == "success":
        fc = face_res.get("measurements", {}).get("face_count", 0)
        if fc > 0:
            explanations.append(f"Face detector identified {fc} face regions in the media.")
        else:
            explanations.append("No face regions were found in the analyzed frame.")
            
    # Compression
    comp_res = aggregated.get("compression", {})
    if comp_res.get("status") == "success":
        qf = comp_res.get("measurements", {}).get("quality_factor", 100)
        explanations.append(f"Quantization grid analysis estimates compression quality factor at {qf}%.")

    # Noise
    noise_res = aggregated.get("noise", {})
    if noise_res.get("status") == "success":
        var = noise_res.get("measurements", {}).get("noise_variance", 0.0)
        explanations.append(f"Estimated noise variance across the analyzed frame is {var:.2f}.")

    # ML
    if ml_res.get("status") != "disabled" and "error" not in ml_res:
        fake_prob = ml_res.get("fake_probability", 0.5)
        if verdict == "fake":
            explanations.append(f"Machine learning ensemble model computed a deepfake probability of {fake_prob:.2%}.")
        elif verdict == "suspicious":
            explanations.append(f"ML models flagged potential structural inconsistencies with {fake_prob:.2%} confidence.")
        else:
            explanations.append(f"ML models indicated standard authenticity signatures with low deepfake probability ({fake_prob:.2%}).")

    if not recs:
        recs.append("No critical digital manipulation indicators found.")

    explanation_text = " ".join(explanations)

    report_text = (
        "DeepGuard AI Forensic Report\n"
        "================================\n"
        f"Generated on: {_now_utc()}\n\n"
        "=== Analysis Summary ===\n"
        f"Verdict : {verdict}\n"
        f"Explanation: {explanation_text}\n"
        "\n=== Recommendations ===\n"
        + "\n".join(f"- {r}" for r in recs)
    )

    report_json = {
        "timestamp": _now_utc(),
        "results": secured,
        "verdict": verdict,
        "recommendations": recs,
        "explanation": explanation_text
    }

    final_result = {
        "results": secured,
        "report_text": report_text,
        "report_json": report_json,
        "agent_logs": agent_logs,
        "activity_log_path": log_path,
    }
    
    # Save final cache
    with open(final_cache_path, "w", encoding="utf-8") as f:
        json.dump(final_result, f, indent=2)

    return final_result