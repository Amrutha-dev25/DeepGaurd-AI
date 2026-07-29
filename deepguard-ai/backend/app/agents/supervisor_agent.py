"""Supervisor Agent — evidence-driven, cost-aware decision loop.

The supervisor reasons about capabilities (not provider names) and decides:
  - CONCLUDE            → take the best evidence and return it
  - GET_SECOND_OPINION  → run another provider with a specific capability
  - INCONCLUSIVE_STOP   → no untried capability would resolve the disagreement
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from app.config import settings

logger = logging.getLogger(__name__)

# ── Capability map (provider-agnostic) ────────────────────────────────
# The supervisor reasons about these descriptions only; it never sees
# model or provider names.

CAPABILITY_MAP: list[dict[str, str]] = [
    {
        "id": "large_multimodal_reasoning",
        "capability": "High-accuracy multimodal model for detailed forensic analysis — "
                      "best at examining fine visual detail and correlating it with signal-based evidence",
    },
    {
        "id": "lightweight_multimodal_verifier",
        "capability": "Efficient multimodal model for forensic verification — "
                      "good at confirming or challenging an existing hypothesis quickly",
    },
    {
        "id": "general_multimodal_verifier",
        "capability": "General-purpose multimodal model — "
                      "can provide an independent third opinion when the first two disagree",
    },
]

# Maps capability IDs to agent keys used by _run_analysis_with_fallback
CAPABILITY_TO_AGENT_KEY: dict[str, str] = {
    "large_multimodal_reasoning": "analysis_agent",
    "lightweight_multimodal_verifier": "analysis_fb1",
    "general_multimodal_verifier": "analysis_fb2",
}


# ── Investigation state ───────────────────────────────────────────────

@dataclass
class InvestigationState:
    """Tracks the investigation across supervisor rounds."""
    file_type: str = ""
    providers_tried: list[str] = field(default_factory=list)
    evidence_table: list[dict] = field(default_factory=list)
    rounds_completed: int = 0
    max_rounds: int = 2
    reasoning_log: list[str] = field(default_factory=list)
    converged: bool = False
    final_verdict: dict[str, Any] | None = None


SUPERVISOR_INSTRUCTION = """PRIMARY OBJECTIVE

Maximize forensic correctness. An inconclusive verdict is acceptable.
An incorrect verdict is the worst possible outcome.

---

MISSION

You are the Investigation Supervisor. You are NOT a forensic detector.
You do NOT determine whether media is real or fake.

Your ONLY job is to decide whether to stop or continue gathering evidence,
and what kind of evidence to request next. You answer three questions in order:

  1. What specifically is unresolved?
  2. What evidence would actually reduce that uncertainty?
  3. Does any untried capability plausibly provide that evidence?

---

INPUT

You receive:
- An evidence table with verdicts and confidence from each provider consulted so far
- The forensic evidence block (ELA, FFT, noise, DCT, wavelets, edge intensity, metadata)
- A list of untried capabilities and what each one is good at
- How many rounds have been completed (max 2)

---

REASONING — answer these three questions, IN THIS ORDER

Question 1 — What specifically is unresolved?

Name the actual disagreement or gap. Not "confidence is low" — be specific:
- "Sightengine says fake at 0.6, but the forensic noise variance is in the
  authentic range — these disagree on direction."
- "The first provider says fake at 0.75 citing ELA anomalies. The second
  says real at 0.65. They disagree on whether the ELA anomaly is
  manipulation or a compression artifact."
- "All consulted providers agree it's fake, but the confidence is moderate
  (~0.7). The disagreement is about certainty, not direction — a second
  source is unlikely to change the conclusion."

If providers agree on direction but differ in confidence, that is NOT a
genuine disagreement — note that and favour CONCLUDE.

Question 2 — What evidence would actually reduce that uncertainty?

Would a different model with different training data catch something the
first missed? Or is this the kind of disagreement (e.g. fundamental
ambiguity in the image itself) that no additional call would resolve?

Question 3 — Does any untried capability plausibly provide that evidence?

Be honest. If the disagreement is about whether a visual artifact is
manipulation or a camera artefact, a high-resolution multimodal model might
help. If it's about a contradiction between forensic signal analysis and
visual appearance, a different model looking at the same pixels may not
resolve it.

If nothing untried would help, choose INCONCLUSIVE_STOP. Do not choose
GET_SECOND_OPINION out of habit because budget remains.

---

GENUINE DISAGREEMENT VS NORMAL ANALYTICAL CAVEATS

This is critical. Distinguish carefully:

A GENUINE DISAGREEMENT means:
- Two different providers reach opposite verdicts (one says real, one says fake)
- A single provider's own confidence is moderate (< 0.8) AND it flags that the
  evidence is genuinely ambiguous
- Forensic signals fundamentally contradict each other on direction (e.g. ELA
  strongly indicates fake while noise strongly indicates real)

A NORMAL ANALYTICAL CAVEAT (NOT a disagreement) is:
- A provider reports high confidence (≥ 0.8) in its verdict AND the majority
  of forensic signals point in the same direction, BUT the provider honestly
  notes that one or two metrics are borderline or within normal range
- This is expected behavior from a thorough forensic model. No real-world
  analysis produces perfect unanimity across all 7+ metrics. A provider that
  admits one metric is ambiguous while the other six strongly support its
  verdict is being HONEST, not contradictory.
- A minor caveat within an otherwise strong, evidence-backed verdict is a
  sign of rigor, not a reason to overturn the verdict.

RULES FOR THIS SECTION:
- If a single provider gives a verdict at ≥ 0.8 confidence and the majority
  of forensic signals corroborate that verdict, minor caveats in the
  provider's own reasoning do NOT make the case "unresolved."
- In this situation, GET_SECOND_OPINION is wasteful — the evidence is already
  strong. Favor CONCLUDE.
- If only one provider has been consulted and it returned high confidence
  with clear signals, do NOT request a second opinion. The evidence is
  sufficient.

---

CONVERGENCE NOTE

If the most recent provider result AGREES with the prior evidence direction,
that is corroboration — consider CONCLUDE unless a significant uncertainty
remains.

If the most recent result DISAGREES with prior evidence, making the picture
more split rather than clearer, note that explicitly as non-convergence.
Three providers that can't agree are unlikely to be resolved by a fourth.

---

FORBIDDEN

- Never predict "fake" or "real". You are not a forensic analyst.
- Never output a verdict or confidence value.
- Never average, vote, or fuse confidence values.
- Never hardcode a provider order or sequence.
- Never mention provider names, model names, or company names.
- Never treat a provider's own analytical nuance (one borderline metric among
  six strong ones) as "internal contradiction" or grounds to overturn a
  high-confidence verdict.

---

OUTPUT CONTRACT

Output ONLY valid JSON with these exact fields. No extra text, no markdown.

{
  "action": "CONCLUDE" | "GET_SECOND_OPINION" | "INCONCLUSIVE_STOP",
  "capability": "large_multimodal_reasoning" | "lightweight_multimodal_verifier" | "general_multimodal_verifier" | null,
  "reasoning": "Verbatim explanation answering questions 1-3 above"
}

- For CONCLUDE, capability may be null (the runtime picks the best evidence).
- For GET_SECOND_OPINION, capability MUST name which untried capability.
- For INCONCLUSIVE_STOP, capability MUST be null.
"""


def create_supervisor_agent() -> Agent:
    """Create a text-only Supervisor Agent.

    Uses SUPERVISOR_MODEL if set (env override for debugging), otherwise
    falls back to router_model (Groq by default).
    """
    supervisor_model = settings.supervisor_model or settings.router_model
    model_name = supervisor_model
    api_key = settings.groq_api_key
    base_url = settings.router_endpoint or "https://api.groq.com/openai/v1"

    if "nvidia" in supervisor_model.lower():
        api_key = settings.primary_api_key or settings.router_fallback2_api_key or settings.groq_api_key
        base_url = settings.primary_endpoint or settings.router_fallback2_endpoint or base_url

    logger.info("Creating Supervisor Agent: model=%s base=%s", model_name, base_url)
    model = LiteLlm(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.1,
        max_tokens=1024,
    )
    return Agent(
        name="supervisor_agent",
        model=model,
        instruction=SUPERVISOR_INSTRUCTION,
        tools=[],
    )


def create_cerebras_supervisor_agent() -> Agent | None:
    """Cerebras supervisor agent — primary, separate provider pool from NVIDIA/Groq."""
    key_present = bool(settings.cerebras_api_key)
    key_preview = f"{settings.cerebras_api_key[:6]}..." if key_present else "(empty)"
    logger.info("CEREBRAS_API_KEY present=%s preview=%s model=%s",
                key_present, key_preview, settings.supervisor_primary_model)
    if not key_present:
        logger.warning("CEREBRAS_API_KEY not set — Cerebras supervisor unavailable")
        return None
    model = LiteLlm(
        model=settings.supervisor_primary_model,
        api_key=settings.cerebras_api_key,
        temperature=0.1,
        max_tokens=1024,
    )
    return Agent(
        name="supervisor_agent_cerebras",
        model=model,
        instruction=SUPERVISOR_INSTRUCTION,
        tools=[],
    )


def create_gemini_supervisor_agent() -> Agent | None:
    """Gemini supervisor agent — fallback (native ADK string, not LiteLlm).

    Uses the same construction pattern as create_router_fallback3_agent()
    and create_gemini_fallback_agent() — returns the model name as a
    native ADK string so ADK handles the Google client internally.
    """
    if not settings.enable_gemini_fallback or not settings.google_api_key:
        logger.warning("Gemini fallback not enabled or no API key — Gemini supervisor unavailable")
        return None
    logger.info("Creating Gemini Supervisor Agent: model=%s", settings.supervisor_fallback_model)
    return Agent(
        name="supervisor_agent_gemini",
        model=settings.supervisor_fallback_model,
        instruction=SUPERVISOR_INSTRUCTION,
        tools=[],
    )


def build_supervisor_context(
    investigation_state: InvestigationState,
    sightengine_verdict: dict[str, Any] | None,
    forensic_context: dict[str, Any],
    preprocessing_result: dict[str, Any],
    convergence_status: str | None = None,
) -> str:
    """Build the context string for the supervisor agent.

    Returns the full prompt text to pass to _run_agent_safe.
    convergence_status is fed into the prompt as context only — the
    supervisor's own JSON decision is the sole source of CONCLUDE /
    GET_SECOND_OPINION / INCONCLUSIVE_STOP.
    """
    parts: list[str] = [
        "=== EVIDENCE TABLE ===",
    ]
    if investigation_state.evidence_table:
        for entry in investigation_state.evidence_table:
            cap = entry.get("capability", "?")
            ver = entry.get("verdict", "?")
            conf = entry.get("confidence", "N/A")
            summary = entry.get("analysis_summary", "")
            parts.append(f"- {cap}: {ver} (conf={conf})")
            if summary:
                parts.append(f"  Summary: {summary[:300]}")
            conflicts = entry.get("conflicting_evidence", [])
            if conflicts:
                parts.append(f"  Conflicts: {'; '.join(str(c)[:200] for c in conflicts)}")
    else:
        parts.append("(no providers consulted yet)")
    parts.append("")

    # Evidence direction summary for convergence check
    direction = _compute_evidence_direction(investigation_state.evidence_table)
    parts.append("=== EVIDENCE DIRECTION ===")
    parts.append(f"Overall direction: {direction}")
    parts.append("")

    # Convergence status — fed as context only, does not override supervisor's decision
    if convergence_status:
        parts.append("=== AGREEMENT CONTEXT ===")
        parts.append(f"Convergence status: {convergence_status}")
        if convergence_status == "AGREE":
            parts.append("All consulted providers agree on direction. "
                         "This is corroboration — bias toward CONCLUDE if the evidence "
                         "is sufficiently strong.")
        elif convergence_status == "SPLIT":
            parts.append("Providers disagree on direction (some say real, some say fake). "
                         "This is a genuine split — bias toward INCONCLUSIVE_STOP unless "
                         "an untried capability could plausibly resolve the disagreement.")
        elif convergence_status == "PARTIAL":
            parts.append("Some evidence is inconclusive or mixed. "
                         "Consider whether an untried capability could clarify.")
        parts.append("")

    if sightengine_verdict:
        parts.append("=== SIGHTENGINE RESULT ===")
        parts.append(json.dumps(sightengine_verdict, indent=2))
        parts.append("")

    parts.append("=== FORENSIC EVIDENCE ===")
    fcx = forensic_context or {}
    if "ela" in fcx:
        ela = fcx["ela"]
        parts.append(f"ELA mean_difference: {ela.get('mean_difference', 'N/A')}")
    if "noise" in fcx:
        noise = fcx["noise"]
        parts.append(f"Noise variance: {noise.get('noise_variance', 'N/A')}")
    if "fft" in fcx:
        fft = fcx["fft"]
        parts.append(f"FFT high_freq_ratio: {fft.get('high_freq_ratio', 'N/A')}")
    if "compression" in fcx:
        comp = fcx["compression"]
        parts.append(f"Compression quality: {comp.get('estimated_quality', 'N/A')}%")
    if "jpeg_artifacts" in fcx:
        jpeg = fcx["jpeg_artifacts"]
        parts.append(f"JPEG block_boundary_ratio: {jpeg.get('block_boundary_ratio', 'N/A')}")
    if "exif" in fcx:
        exif = fcx["exif"]
        parts.append(f"EXIF tag_count: {exif.get('tag_count', 'N/A')}")
        if exif.get("editing_software"):
            parts.append(f"Editing software: {', '.join(exif['editing_software'])}")
        if exif.get("ai_generation_tools"):
            parts.append(f"AI generation tools: {', '.join(exif['ai_generation_tools'])}")
    if "faces" in fcx:
        faces = fcx["faces"]
        parts.append(f"Faces detected: {faces.get('face_count', 'N/A')}")
    if "clones" in fcx:
        clones = fcx["clones"]
        parts.append(f"Clone detection: {clones.get('summary', clones.get('evidence', 'N/A'))}")
    ppx = preprocessing_result or {}
    if ppx.get("dct_mean") is not None:
        parts.append(f"DCT coefficient mean: {ppx['dct_mean']:.4f}")
    wv = ppx.get("wavelet", {})
    if wv:
        parts.append(f"Wavelet HH energy: {wv.get('HH', 'N/A')}")
    edges = ppx.get("edge_intensity", {})
    if edges:
        parts.append(f"Edge intensity (Canny): {edges.get('canny', 'N/A')}")
    parts.append("")

    parts.append("=== ROUNDS ===")
    parts.append(f"Completed: {investigation_state.rounds_completed}")
    parts.append(f"Max: {investigation_state.max_rounds}")
    parts.append("")

    parts.append("=== CAPABILITIES NOT YET USED ===")
    unused = [c for c in CAPABILITY_MAP if c["id"] not in investigation_state.providers_tried]
    if unused:
        for c in unused:
            parts.append(f"- {c['id']}: {c['capability']}")
    else:
        parts.append("(all capabilities have been used)")
    parts.append("")

    return "\n".join(parts)


def _compute_evidence_direction(evidence_table: list[dict]) -> str:
    """Summarise the overall evidence direction for the convergence check."""
    from collections import Counter
    clear = [e for e in evidence_table if e.get("verdict") in ("real", "fake")]
    if not clear:
        return "no clear direction yet"
    verdicts = Counter(e["verdict"] for e in clear)
    if len(set(clear_entry["verdict"] for clear_entry in clear)) == 1:
        return f"all consulted providers agree: {clear[0]['verdict']}"
    # Split
    majority = verdicts.most_common(1)[0][0]
    minority = "fake" if majority == "real" else "real"
    return f"split: {verdicts[majority]} for {majority}, {verdicts[minority]} for {minority}"


def _extract_supervisor_json(text: str) -> dict[str, Any] | None:
    """Extract JSON from supervisor response using bracket-counting.

    Handles:
      - ```json ... ``` blocks (preferred)
      - Naked JSON objects via bracket-counting from the last viable `{`
      - Text before/after JSON
    """
    import re

    if not text or not text.strip():
        logger.warning("Supervisor: empty response")
        return None

    raw = text.strip()

    # Strategy 1: ```json ... ``` block (preferred — unambiguous)
    json_block = re.search(r"```(?:json)?\s*\n?(\{[\s\S]*?\n?\})\s*\n?```", raw)
    if json_block:
        candidate = json_block.group(1)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Strategy 2: Bracket-counting scan — find a balanced JSON object
    # Scan forward from each `{` and take the first substring that
    # balances brackets AND parses.  This avoids the greedy `.*` bug
    # that would span from a stray `{` in reasoning text to the real
    # closing `}`.
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
                        break  # this `{`..`}` didn't parse; try next `{`
        if depth == 0:
            continue

    logger.warning("Supervisor: no valid JSON found: %s...", raw[:200])
    return None
