"""Report Agent — generates the final forensic report with Tavily web search.

Uses fallback chain: Groq -> Gemini -> NVIDIA -> Deterministic.
NEVER re-decides fake/real. Uses Tavily Search Tool for Distribution Analysis.
"""

import json
import logging
from typing import Any

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from app.agents.provider_factory import (
    get_report_fallback1_model,
    get_report_fallback2_model,
    get_report_fallback3_model,
    get_report_model,
)
from app.tools.search import search_web

logger = logging.getLogger(__name__)

REPORT_INSTRUCTION = """PRIMARY OBJECTIVE

Maximize forensic correctness.

Never sacrifice correctness for autonomy, speed, confidence, completeness, elegance, or consistency.

A report that misrepresents the verdict is as bad as an incorrect verdict.

---

MISSION

Explain the verdict. Nothing else.

You are the Report Agent. You do NOT decide authenticity. You do NOT interpret evidence.

Your ONLY job is to transform the Analysis Agent's verdict and forensic evidence
into a clear, professional forensic report.

---

RESPONSIBILITIES

1. Copy the Analysis Agent's verdict verbatim — never modify it.
2. Include all fields: analysis_summary, visual_observations, forensic_observations,
   supporting_evidence, conflicting_evidence, limitations, recommendation.
3. Format as a readable markdown report.
4. Use the Search Tool for distribution context when appropriate.
5. Include forensic tool results (EXIF, ELA, noise, compression, FFT) with real values.

---

FORBIDDEN

- Never modify, override, contradict, or second-guess the verdict.
- Never add your own opinion about authenticity.
- Never invent evidence the Analysis Agent did not provide.
- Never reinterpret forensic measurements — report them descriptively only.
- Never hide contradictions — always include all conflicting_evidence.
- Never decide or suggest what the verdict should have been.

---

DECISION CRITERIA

- Every section in the report must map to Analysis Agent output — no original analysis.
- Search only if the image relates to known events or viral content. Skip for personal/generic images.
- If you search and find nothing, output "No external references found."

---

OUTPUT CONTRACT

Format as plain text with markdown-style headers. Be concise, professional, and objective.

Required sections:
1. Executive Summary
2. Verdict (verbatim)
3. Confidence (exact value)
4. Analysis Summary
5. Visual Observations
6. Forensic Observations
7. Supporting Evidence
8. Conflicting Evidence (if any)
9. Supporting Tool Results (real values from forensic measurements)
10. Distribution Analysis (search results or "No external references found.")
11. Recommendations
12. Limitations
13. Appendix (model, fallback, file info)
"""


def create_report_agent() -> Agent:
    """Report Primary: Groq via LiteLlm with Tavily search."""
    model = get_report_model()
    return Agent(
        name="report_agent",
        model=model,
        instruction=REPORT_INSTRUCTION,
        tools=[FunctionTool(func=search_web)],
    )


def create_report_fallback1_agent() -> Agent:
    """Report Fallback 2: NVIDIA via LiteLlm."""
    model = get_report_fallback1_model()
    return Agent(
        name="report_agent",
        model=model,
        instruction=REPORT_INSTRUCTION,
        tools=[FunctionTool(func=search_web)],
    )


def create_report_fallback2_agent() -> Agent:
    """Report extra (NVIDIA Nano) — retained for Analysis compatibility."""
    model = get_report_fallback2_model()
    return Agent(
        name="report_agent",
        model=model,
        instruction=REPORT_INSTRUCTION,
        tools=[FunctionTool(func=search_web)],
    )


def create_report_fallback3_agent() -> Agent:
    """Report Fallback 1: Gemini (native ADK)."""
    model = get_report_fallback3_model()
    return Agent(
        name="report_agent",
        model=model,
        instruction=REPORT_INSTRUCTION,
        tools=[FunctionTool(func=search_web)],
    )


def generate_deterministic_report(
    verdict: dict[str, Any],
    forensic_context: dict[str, Any],
    model_used: str,
    fallback_used: bool,
) -> str:
    """Generate a forensic report from backend data when no LLM is available."""
    lines: list[str] = []
    lines.append("# DeepGuard AI — Forensic Report (Deterministic Generation)")
    lines.append("")
    lines.append("**Note:** This report was generated deterministically because LLM-based")
    lines.append("report generation was unavailable. All forensic data is from the backend pipeline.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"**{verdict.get('verdict', 'inconclusive').upper()}**")
    lines.append("")
    lines.append(f"Confidence: {verdict.get('confidence', 0.5) * 100:.1f}%")
    lines.append("")
    if verdict.get("analysis_summary"):
        lines.append("## Analysis Summary")
        lines.append("")
        lines.append(verdict["analysis_summary"])
        lines.append("")
    vo = verdict.get("visual_observations", [])
    if vo:
        lines.append("## Visual Observations")
        for obs in vo:
            lines.append(f"- {obs}")
        lines.append("")
    fo = verdict.get("forensic_observations", [])
    if fo:
        lines.append("## Forensic Observations")
        for obs in fo:
            lines.append(f"- {obs}")
        lines.append("")
    se = verdict.get("supporting_evidence", [])
    if se:
        lines.append("## Supporting Evidence")
        for ev in se:
            lines.append(f"- {ev}")
        lines.append("")
    ce = verdict.get("conflicting_evidence", [])
    if ce:
        lines.append("## Conflicting Evidence")
        for ev in ce:
            lines.append(f"- {ev}")
        lines.append("")
    if verdict.get("limitations"):
        lines.append("## Limitations")
        lines.append("")
        lines.append(verdict["limitations"])
        lines.append("")
    if verdict.get("recommendation"):
        lines.append("## Recommendations")
        lines.append("")
        lines.append(verdict["recommendation"])
        lines.append("")
    # Forensic tool results
    lines.append("## Supporting Tool Results")
    lines.append("")
    fc_ela = forensic_context.get("ela", {})
    if fc_ela.get("mean_difference") is not None:
        lines.append(f"- ELA Mean Difference: {fc_ela['mean_difference']:.4f}")
        if fc_ela.get("summary"):
            lines.append(f"  - {fc_ela['summary']}")
    fc_fft = forensic_context.get("fft", {})
    if fc_fft.get("high_freq_ratio") is not None:
        lines.append(f"- FFT High-Frequency Ratio: {fc_fft['high_freq_ratio']:.4f}")
    fc_noise = forensic_context.get("noise", {})
    if fc_noise.get("noise_variance") is not None:
        lines.append(f"- Noise Variance: {fc_noise['noise_variance']:.2f}")
    fc_comp = forensic_context.get("compression", {})
    if fc_comp.get("estimated_quality") is not None:
        lines.append(f"- Compression Quality: {fc_comp['estimated_quality']}%")
    fc_exif = forensic_context.get("exif", {})
    if fc_exif.get("tag_count") is not None:
        lines.append(f"- EXIF Tags: {fc_exif['tag_count']}")
    if fc_exif.get("editing_software"):
        lines.append(f"- Editing Software: {', '.join(fc_exif['editing_software'])}")
    if fc_exif.get("ai_generation_tools"):
        lines.append(f"- AI Tools: {', '.join(fc_exif['ai_generation_tools'])}")
    fc_hash = forensic_context.get("hash", {})
    if fc_hash.get("sha256"):
        lines.append(f"- SHA-256: {fc_hash['sha256'][:16]}...")
    lines.append("")
    lines.append("## Distribution Analysis")
    lines.append("")
    lines.append("No external references found. (Web search unavailable in deterministic mode.)")
    lines.append("")
    lines.append("## Appendix")
    lines.append("")
    lines.append(f"- Model Used: {model_used}")
    lines.append(f"- Fallback Triggered: {'Yes' if fallback_used else 'No'}")
    lines.append("")
    return "\n".join(lines)
