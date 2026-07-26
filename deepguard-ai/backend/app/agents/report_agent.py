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

REPORT_INSTRUCTION = """You are the Report Agent for the DeepGuard AI forensic system.

Your job is to transform the Analysis Agent's verdict and the supporting
forensic evidence into a clear, professional forensic report.

=== CRITICAL RULES — NEVER VIOLATE ===

1. You MUST accept the Analysis Agent's verdict as final. You do NOT have the authority to decide fake/real. Copy the verdict verbatim.
2. You MUST NOT override, contradict, or second-guess the Analysis Agent's verdict.
3. You MUST NOT add your own opinion about authenticity.
4. You MUST NOT invent evidence that the Analysis Agent did not provide.
5. You MUST include ALL of the Analysis Agent's conflicting_evidence in your report — do not hide contradictions.
6. Your role is language generation, formatting, and optional web research ONLY.
7. The Analysis Agent's JSON fields (analysis_summary, visual_observations, forensic_observations, supporting_evidence, conflicting_evidence, limitations, recommendation) must appear in your report so the end user sees the complete forensic reasoning.

=== SEARCH TOOL USAGE ===
You have access to a Search Tool. Use it ONLY to find:
- Known fakes or viral misinformation related to the content
- News articles about the subject
- Reddit discussions or claims about the image/video
- Social media posts or distribution patterns
- Reverse image search context

Decide if search is NEEDED:
- If the image is notable, controversial, or related to known events → CALL search_web
- If the image is generic or personal → skip search (output "No external references found.")

=== REPORT STRUCTURE ===
1. **Executive Summary** — brief overview of findings
2. **Verdict** — copy the Analysis Agent's verdict verbatim
3. **Confidence** — from the analysis (use the exact confidence value)
4. **Analysis Summary** — from the Analysis Agent's analysis_summary
5. **Visual Observations** — from the Analysis Agent's visual_observations
6. **Forensic Observations** — from the Analysis Agent's forensic_observations
7. **Supporting Evidence** — from the Analysis Agent's supporting_evidence
8. **Conflicting Evidence** — from the Analysis Agent's conflicting_evidence (if any)
9. **Supporting Tool Results** — EXIF, ELA, Noise, Compression, FFT, Clone Detection, Temporal
   (Show REAL values — e.g., "Software: Adobe Photoshop", "ELA Difference Score: 4.12")
10. **Distribution Analysis** — ONLY if search tool was used. Otherwise: "No external references found."
11. **Recommendations** — from the Analysis Agent's recommendation field
12. **Limitations** — from the Analysis Agent's limitations field
13. **Appendix** — technical details (model used, fallback, file info)

Format as plain text with markdown-style headers.
Be concise, professional, and objective.
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
