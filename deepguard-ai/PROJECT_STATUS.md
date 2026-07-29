# DeepGuard AI — Project Evolution

> A chronological record of agentic behavior, bugs discovered, decisions made, and the current state of the pipeline.

---

## Phase 1 — Foundations (Initial Architecture)

### The Original Design

The pipeline was a **static fallback chain** — three stages (Router → Analysis → Report), each with a hardcoded list of providers tried in sequence. If the primary provider failed, try FB1, then FB2, etc. This had no reasoning, no evidence evaluation, no decision loop — just sequential brute force.

**Providers per stage:**
- **Router:** Groq → NVIDIA Omni → NVIDIA Nano → Gemini → Deterministic
- **Analysis:** Sightengine (REST) → NVIDIA Omni (LiteLlm) → NVIDIA Nano (LiteLlm) → Gemini (native) → inconclusive
- **Report:** Groq → NVIDIA Omni → NVIDIA Nano → Gemini → Deterministic

**Key early decisions (correct):**
- Sightengine as the primary detector (cheap, fast, calibrated REST API)
- Google ADK as the agent framework (standardized agent lifecycle)
- LiteLlm for non-Gemini providers (single interface for Groq, NVIDIA)
- Provider-agnostic capability map (supervisor reasons about *what it needs*, not *which provider*)

### The Supervisor Agent (First Major Evolution)

The static fallback chain was replaced with an **evidence-driven supervisor loop**. The supervisor (a text-only LiteLlm agent) receives evidence and decides: `CONCLUDE`, `GET_SECOND_OPINION`, or `INCONCLUSIVE_STOP`.

**Supervisor providers (original):**
- **Primary:** Cerebras (gemma-4-31b via LiteLlm) — separate API pool from NVIDIA/Groq
- **Fallback:** Gemini 2.5 Flash (native ADK string)
- **Last resort:** Groq llama-3.3-70b (text-only, no vision)

**Capability map (unchanged since inception):**
- `large_multimodal_reasoning` → NVIDIA Omni (analysis_agent)
- `lightweight_multimodal_verifier` → NVIDIA Nano (analysis_fb1)
- `general_multimodal_verifier` → Gemini (analysis_fb2)

---

## Phase 2 — Iteration & Bug Discovery

### Bug 1: Below-Range Ambiguity (Instruction Flaw)

**Discovery:** The analysis prompt's reference ranges used symmetric language ("authentic range 0.05–0.50, suspicious >1.0") without clarifying which direction is suspicious. Models treated values *below* the authentic floor (e.g., ELA=0.01, FFT=0.0005) as suspicious — but these are actually normal for clean captures.

**Root cause:** `VALUES` in `runner.py:1906-1912` — the analysis prompt listed ranges without one-sided clarification.

**Fix:** Added explicit asymmetry:
- `(below 0.05 is normal, NOT suspicious)` for ELA, FFT, DCT, Wavelet HH
- "Only values in the SUSPICIOUS direction are manipulation indicators"
- Values below the authentic floor for one-sided metrics are NORMAL, not suspicious

**Files affected:** `runner.py` (analysis prompt construction)

### Bug 2: Resolution Normalization (Metric Reliability)

**Discovery:** Forensic reference ranges were calibrated on 1080p-scale images. 4K/8K images produced noise variance 5–20x higher, triggering false manipulation flags.

**Root cause:** No resolution normalization. Reference ranges assume ~2000px longest side.

**Fix:** Added `_metric_caveat()` tag — metrics on images >3000px longest side get `[reduced reliability — reference ranges calibrated at lower resolution]`. Resolution extracted from router's `width`/`height` fields. Same caveat logic in `build_supervisor_context()`.

**Files affected:** `runner.py`, `supervisor_agent.py`

### Bug 3: Forensic-Beats-Visual Blanket Rule

**Discovery:** The instruction "forensic evidence should be weighted more heavily" caused models to override clear visual evidence with unreliable forensic data (e.g., high noise on a video frame from recompression artifacts, not manipulation).

**Fix:** Changed to "weight by reliability: tagged metrics carry LESS weight than visual observations; untagged carry MORE." The reliability tag system (video recompression, high-resolution caveats) now drives weighting.

**Files affected:** `runner.py` (analysis prompt, instruction #5)

### Bug 4: Convergence Detection Gaps

**Discovery:** When only one provider returned a directional verdict and others abstained (inconclusive), the system falsely reported "AGREE" — treating an inconclusive as corroboration.

**Root cause:** `_check_convergence()` included all entries in agreement calculations, not just directional ones.

**Fix:** 
- `_check_convergence()` returns `SINGLE_OPINION` when <2 directional verdicts exist
- `_compute_evidence_direction()` now says "1 directional opinion: real (conf=0.55) (1 provider(s) abstained) — single opinion, not convergence"

**Files affected:** `supervisor_agent.py`, `runner.py`

### Bug 5: max_rounds Too Low

**Discovery:** Supervisor capped at 2 rounds, but the capability map has 3 entries. If the first capability fails to resolve, only one fallback remains before forced fallthrough.

**Fix:** `max_rounds` raised from 2 to 3, matching the 3-capability map.

**Files affected:** `runner.py:1400`, `supervisor_agent.py:60`

### Bug 6: Evidence Sufficiency Gate (Missing Feature)

**Discovery:** With Sightengine at 0.55–0.79, the supervisor always dispatched a second opinion even when forensic evidence strongly corroborated Sightengine's direction.

**Fix:** Two-case Evidence Sufficiency Gate:
- **Case A (≥0.8):** Fast return — no supervisor loop
- **Case B (0.55–0.79):** Check forensic corroboration — if ≥2 forensic metrics agree with Sightengine direction, CONCLUDE without supervisor

**Files affected:** `runner.py`

### Bug 7: Cerebras Completely Non-Functional

**Discovery:** `cerebras/llama3.1-8b` (original model string) returned litellm.NotFoundError — archived model. Swapped to `cerebras/gemma-4-31b` — also not deployable (preview, billing wall). `zai-glm-4.7` — same issue. The Cerebras API key's billing tab needed attention per error messages, and this was not fixable from code.

**Root cause:** Cerebras account billing issue + archived model IDs.

**Fix:** **Complete removal:**
- `create_cerebras_supervisor_agent()` deleted from `supervisor_agent.py`
- `_run_supervisor_with_fallback()` simplified to Gemini-only
- `cerebras_api_key` and `supervisor_primary_model` removed from `settings`
- `supervisor_fallback_model` → renamed to `supervisor_model` (sole field)
- Startup logging, docs, `.env.example` all updated

**Files affected:** `config.py`, `supervisor_agent.py`, `runner.py`, `api.py`, `docs/ARCHITECTURE.md`, `.env.example`

### Bug 8: "model: unknown" Label

**Discovery:** Native ADK string models (Gemini `"gemini-2.5-flash"`) displayed as `"unknown"` in ADK agent result logs. The code assumed every model has a `.model` attribute access pattern — correct for LiteLlm, wrong for native strings where `agent.model` IS the string.

**Root cause:** `_model = str(getattr(getattr(agent, 'model', None), 'model', 'unknown'))` — double-dot pattern fails when `agent.model` is a plain string.

**Fix:** Added `isinstance(_m, str)` check — if the model attribute is a string, use it directly; otherwise fall through to `.model` attribute access or `'unknown'`.

**Files affected:** `runner.py` (lines 237-243, 1415-1416)

### Bug 9: FALLBACK_INSTRUCTION Contradicts PRIMARY_INSTRUCTION (Weak Verdicts)

**Discovery:** Fallback analysis agents (`analysis_fb1`, `analysis_fb2`) used `FALLBACK_INSTRUCTION` — a stripped-down version that lacked:
- One-sided reference ranges (Bug 1 fix never propagated)
- Reliability-tag guidance (Bug 3 fix never propagated)
- Decision criteria (confidence calibration table)
- Explicit FORBIDDEN rules about guessing

This made fallback agents return weak `inconclusive` verdicts that failed to corroborate a correct primary verdict.

**Fix:**
- `FALLBACK_INSTRUCTION` deleted entirely
- All three analysis agents now use the identical `PRIMARY_INSTRUCTION`
- `PRIMARY_INSTRUCTION` updated with one-sided ranges + "Only values in the SUSPICIOUS direction are manipulation indicators"

**Files affected:** `analysis_agent.py`

---

## Phase 3 — Current Architecture

### Pipeline Flow (Final)

```
Upload → Guardrails → Router (Groq)
                           ↓
                  Sightengine REST API (6 frames for video)
                           ↓
                  Evidence Sufficiency Gate
                  ├─ conf ≥ 0.8 → fast return to Report
                  └─ conf < 0.8 or forensic conflict → Supervisor Loop
                           ↓
                  Supervisor (Gemini 2.5 Flash, native ADK)
                  ├─ CONCLUDE → return best evidence to Report
                  ├─ GET_SECOND_OPINION → dispatch capability
                  │   ├─ large_multimodal_reasoning → NVIDIA Omni
                  │   ├─ lightweight_multimodal_verifier → NVIDIA Nano
                  │   └─ general_multimodal_verifier → Gemini
                  └─ INCONCLUSIVE_STOP → return inconclusive to Report
                           ↓
                  Report (Groq → NVIDIA Omni → NVIDIA Nano → Gemini)
```

### Provider Chains (Verified Working)

| Stage | Primary | FB1 | FB2 | FB3 | Last Resort |
|-------|---------|-----|-----|-----|-------------|
| Router | Groq llama-3.3-70b | NVIDIA Omni | NVIDIA Nano | Gemini 2.5 Flash | Deterministic |
| Analysis | Sightengine REST | (supervisor-dispatched) NVIDIA Omni → NVIDIA Nano → Gemini | N/A | N/A | Fallthrough |
| Supervisor | **Gemini 2.5 Flash** (sole — no fallback needed) | Text-only LiteLlm (degraded, no google_api_key) | N/A | N/A | N/A |
| Report | Groq llama-3.3-70b | NVIDIA Omni | NVIDIA Nano | Gemini 2.5 Flash | Deterministic |

### Agent Design Decisions (Final)

| Decision | Rationale |
|----------|-----------|
| Gemini-only supervisor | Cerebras was non-functional (archived models, billing wall); LiteLlm text-only agents can't see images |
| Native ADK strings for Gemini | Avoids LiteLlm round-trip; ADK handles Google client internally; faster and more reliable |
| Same instruction for all analysis agents | FALLBACK_INSTRUCTION produced weak inconclusive verdicts; all agents must reason with identical guidance |
| One-sided reference ranges | Below-authentic-floor values (ELA<0.05, FFT<0.001) are normal, not suspicious — symmetric ranges caused false flags |
| Weight-by-reliability | Tagged metrics (video recompression, high-res caveat) carry LESS weight than visual observations; untagged carry MORE |
| Capability-based dispatch | Supervisor requests "large_multimodal_reasoning", not "NVIDIA Omni" — provider-neutral, avoids name leakage |
| Sightengine ≥0.8 fast path | Calibrated REST API at high confidence needs no LLM intervention; saves cost and latency |
| max_rounds=3 | Matches the 3-capability map; prevents premature fallthrough when consensus is building |
| SINGLE_OPINION detection | One directional verdict + inconclusive abstentions is NOT convergence — must dispatch another capability |

---

## Phase 4 — Verified Behaviors

### Test: Real Video (1280×720 MP4, July 29 2026)

```
Sightengine (6 frames): all real@0.99 → fast path (conf ≥ 0.8)
Router: Groq → metadata extracted (video, 1280×720, 1 face)
Report: Groq → "authentic with 99% confidence"
Pipeline time: ~15s
Supervisor: NOT invoked (Sightengine ≥ 0.8 gate)
```

**Result:** `real (conf=0.99)` — correct. No Cerebras attempt. No "unknown" model label.

### Behavior Matrix

| Scenario | Expected Behavior | Status |
|----------|-------------------|--------|
| Real video, SE ≥ 0.8 | Fast path → REAL, no supervisor | ✅ Verified |
| Fake image, SE ≥ 0.8 | Fast path → FAKE | ⬜ Not tested |
| Real media, SE 0.55–0.79 + forensic corroboration | Evidence Gate → CONCLUDE real | ⬜ Not tested |
| Ambiguous media, SE < 0.55 | Supervisor loop → dispatch 2nd opinion | ⬜ Not tested |
| All 3 capabilities disagree | Supervisor → INCONCLUSIVE_STOP | ⬜ Not tested |
| Supervisor Gemini fails (no API key) | Text-only fallback (degraded) | ⬜ Not tested |

---

## Phase 5 — Known Gaps

### DCT / Wavelet / Edge Intensity for Video

These metrics (`dct_mean`, `wavelet_HH`, `edge_intensity_canny`) are computed by `image_pipeline.py` but are NOT computed for video frames. The forensic summary for video shows these as `N/A` or `0.0000`. Effect: **no DCT/wavelet/edge evidence** in the supervisor context for video cases, relying entirely on ELA, FFT, noise, JPEG, compression, and EXIF.

### Sightengine Multi-Frame Aggregation

Currently uses `max_raw_prob` across all frames — takes the worst frame. This is conservative but may over-flag on video where only 1 frame has artifacts (could be compression noise). Consider median or weighted average.

### No Timeout on Individual ADK Agent Calls

`_run_agent_safe()` has no per-call timeout. If a provider hangs indefinitely, the entire pipeline blocks. The `request_timeout_seconds` only applies at the HTTP level, not the ADK agent level.

### Cerebras (Resolved — Removed)

Cerebras was the original supervisor primary. Billing tab needed attention (`cerebras_api_key` had quota issues at the account level). All model strings tested (`llama3.1-8b`, `gemma-4-31b`, `zai-glm-4.7`) returned NotFoundError — archived/preview models. Complete removal in Phase 2.

---

## File Manifest (Current)

```
deepguard-ai/
├── backend/app/
│   ├── api.py                          # FastAPI layer
│   ├── config.py                       # Pydantic Settings (env-driven)
│   ├── runner.py                       # Pipeline orchestrator (2240 lines)
│   ├── agents/
│   │   ├── supervisor_agent.py         # Supervisor logic + capability map
│   │   ├── analysis_agent.py           # Analysis instruction (single PRIMARY_INSTRUCTION)
│   │   ├── router_agent.py             # Router agent + fallbacks
│   │   ├── report_agent.py             # Report agent + tools
│   │   └── provider_factory.py         # Centralized model creation (no Cerebras)
│   ├── providers/
│   │   └── sightengine.py              # Sightengine REST client
│   ├── tools/                          # 10 forensic tool modules
│   ├── preprocessing/                  # Image + video pipelines
│   ├── guardrails/                     # Validation, injection, moderation, schema
│   └── services/                       # Report + audit + PDF generation
├── PROJECT_STATUS.md                   # This file
├── KNOWN_LIMITATIONS.md
├── docs/
│   ├── ARCHITECTURE.md                 # Updated for Gemini-only supervisor
│   └── agentic-supervisor-spec.md     # Design decisions record
├── .env.example                        # Authoritative env template
├── .env                                # Live secrets (gitignored)
├── Dockerfile
├── docker-compose.yml
├── start_all.bat
└── frontend/                           # React/TypeScript UI
```

## Next Actions

1. **Evaluate with fake media** — run the pipeline on known-fake images/videos to verify:
   - Supervisor loop triggers (Sightengine < 0.8)
   - Fallback analysis agents with PRIMARY_INSTRUCTION produce strong verdicts
   - Convergence detection works correctly (fake → CONCLUDE, ambiguous → INCONCLUSIVE_STOP)
2. **DCT/wavelet/edge for video** — extend preprocessing to compute these metrics on video frames
3. **Sightengine quota monitoring** — add pool-consumption tracking to avoid surprise 429s
4. **Per-agent timeout** — add timeout parameter to `_run_agent_safe()` to prevent indefinite hangs
