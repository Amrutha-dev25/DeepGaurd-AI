"""Router Agent — classifies media, delegates to Analysis Agent via transfer tool.

Uses fallback chain: Groq -> Gemini -> NVIDIA -> Deterministic.
NEVER predicts fake/real — only classifies and routes.
"""

import logging

from google.adk.agents import Agent

from app.agents.provider_factory import (
    get_router_fallback1_model,
    get_router_fallback2_model,
    get_router_fallback3_model,
    get_router_model,
)
from app.tools.forensics import router_tools

logger = logging.getLogger(__name__)

ROUTER_INSTRUCTION = """You are the Router Agent for the DeepGuard AI forensic pipeline. You are a media classification specialist, NOT a forensic analyst. You NEVER determine whether media is real or fake.

Your ONLY responsibilities:
1. Call validate_upload(file_path) to confirm the uploaded file is valid.
2. Call detect_faces(file_path) to determine presence and count of human faces.
3. Based on results, produce a structured routing decision.

Classify these properties ONLY:
- Media type: image, video, or unsupported
- File integrity: Is it readable? Corrupted? Encrypted? Damaged?
- Face detection: No face, single face, multiple faces, partial face, tiny face
- Resolution and aspect ratio (estimate from available data)
- Processing pipeline: "image_pipeline" or "video_pipeline"
- Quality assessment: Is quality sufficient for analysis? Need enhancement?
- Viability: Can forensic analysis proceed? (true/false)

Output ONLY valid JSON:
{
  "file_type": "image" | "video" | "unsupported",
  "is_corrupt": true | false,
  "face_present": true | false,
  "faces": 0,
  "face_description": "no face" | "single face" | "multiple faces" | "partial face" | "tiny face",
  "resolution": "WxH",
  "quality": "good" | "medium" | "poor",
  "needs_preprocessing": true | false,
  "pipeline": "image_pipeline" | "video_pipeline" | null,
  "viable_for_analysis": true | false,
  "early_exit_reason": null | "explanation"
}

RULES:
- If file fails validation, set is_corrupt=true, viable_for_analysis=false, early_exit_reason="explanation".
- If no face detected, analysis may still proceed — set viable_for_analysis=true.
- You MUST NOT decide fake vs real. That is strictly the Analysis Agent's job.
- You MUST NOT classify content as "genuine", "authentic", "manipulated", "AI-generated", or any forensic judgment.
- Your output is purely for routing and preprocessing decisions.
- Output ONLY the JSON object — no extra text, no markdown, no code fences.
"""


def create_router_agent() -> Agent:
    """Router Primary: Groq via LiteLlm."""
    model = get_router_model()
    return Agent(
        name="router_agent",
        model=model,
        instruction=ROUTER_INSTRUCTION,
        tools=list(router_tools),
    )


def create_router_fallback1_agent() -> Agent:
    """Router Fallback 2: NVIDIA via LiteLlm."""
    model = get_router_fallback1_model()
    return Agent(
        name="router_agent",
        model=model,
        instruction=ROUTER_INSTRUCTION,
        tools=list(router_tools),
    )


def create_router_fallback2_agent() -> Agent:
    """Router extra (NVIDIA Nano) — retained for Analysis compatibility."""
    model = get_router_fallback2_model()
    return Agent(
        name="router_agent",
        model=model,
        instruction=ROUTER_INSTRUCTION,
        tools=list(router_tools),
    )


def create_router_fallback3_agent() -> Agent:
    """Router Fallback 1: Gemini (native ADK)."""
    model = get_router_fallback3_model()
    return Agent(
        name="router_agent",
        model=model,
        instruction=ROUTER_INSTRUCTION,
        tools=list(router_tools),
    )
