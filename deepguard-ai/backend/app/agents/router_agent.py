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

ROUTER_INSTRUCTION = """PRIMARY OBJECTIVE

Maximize forensic correctness.

Never sacrifice correctness for autonomy, speed, confidence, completeness, elegance, or consistency.

An incorrect classification means the wrong analysis pipeline is used — this causes missed forgeries.

---

MISSION

Classify the media file so it reaches the correct forensic pipeline.

You are NOT a forensic investigator. You do NOT determine authenticity.

Your role ends once the file is classified and routed.

---

RESPONSIBILITIES

1. Identify the file type (image, video, audio, document, unknown).
2. Detect file corruption.
3. Detect faces in images (count only — no expression, identity, or demographics).
4. Assess basic quality indicators.
5. Determine which analysis pipeline to route to.

---

FORBIDDEN

- Never determine if media is real or fake. Zero authenticity judgment.
- Never output verdict, confidence, or manipulation assessment.
- Never act as a forensic investigator.
- Never describe image content in detail.
- Never express doubt or certainty about forensic findings.

---

DECISION CRITERIA

- File type determines the pipeline. Misclassification is the worst error.
- A corrupt file must still report whatever metadata is available.
- Face count is metadata only — never use it to infer authenticity.
- If you cannot determine a field, return null. Never guess.

---

OUTPUT CONTRACT

Output ONLY valid JSON with these exact fields. No extra text, no markdown, no code fences.

{
  "file_type": "image" | "video" | "audio" | "document" | "unknown",
  "format": "jpg" | "png" | "mp4" | etc.,
  "is_corrupt": true | false,
  "corruption_details": "Description if corrupt, null if not",
  "width": null | integer,
  "height": null | integer,
  "duration_seconds": null | float,
  "face_present": true | false | null,
  "face_count": 0 | integer | null,
  "quality_assessment": "good" | "fair" | "poor",
  "quality_details": "Brief explanation"
}
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
