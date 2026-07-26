# DeepGuard AI — Architecture

## Request Flow

```
User Upload (multipart POST /api/analyze)
        │
        ▼
┌──────────────────────────────────────────────────────┐
│ 1. Guardrails  (app/guardrails/)                     │
│    • validate_extension — reject .exe, .zip, .scr    │
│    • validate_path_traversal — reject ../ in filename │
│    • check_user_input — injection detection patterns  │
│    • validate_file_size — reject > MAX_FILE_SIZE_MB  │
│    • MIME detection (libmagic → PIL → extension)     │
│    • Media integrity check (cv2.VideoCapture / PIL)  │
└──────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────┐
│ 2. Preprocessing  (app/preprocessing/)               │
│    ┌─ Image: resize → CLAHE → denoise → ELA → FFT    │
│    │         → DCT → wavelet → edge maps → metadata  │
│    │         → hashing (SHA-256 + pHash)              │
│    └─ Video: adaptive frame extraction (max N frames,│
│              scene-change detection) → face tracking  │
│              → optical flow → informative frame       │
│              selection                                │
│    Output: preprocessing_result + diagnostic_images   │
│            (base64 ELA, edges, FFT, DCT, wavelet)     │
└──────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────┐
│ 3. Forensic Context  (app/tools/)                    │
│    • collect_forensic_context() calls every tool:     │
│      - ELA (Error Level Analysis)                     │
│      - EXIF metadata extraction                       │
│      - FFT (frequency domain)                         │
│      - Noise analysis (Laplacian variance)            │
│      - JPEG artifact detection                        │
│      - Clone detection (ORB keypoint matching)        │
│      - Temporal frame analysis (videos)              │
│      - Face detection (Haar cascade)                  │
│      - Compression analysis                           │
│      - Search (web lookup via Tavily, optional)       │
│    • Security checkpoint redacts PII from context     │
│    • Security checkpoint checks for injection in text │
└──────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────┐
│ 4. Router Agent  (app/agents/router_agent.py)        │
│    Classifies: file_type, face_present, viable, etc.  │
│    ┌─ Primary: Groq (llama-3.3-70b-versatile)        │
│    ├─ Fallback 1: Gemini (2.5-flash) [conditional]   │
│    ├─ Fallback 2: NVIDIA NIM (Nemotron Omni)          │
│    └─ Fallback 3: Deterministic routing               │
│    Each fallback runs in an isolated ADK session.     │
│    Non-viable files short-circuit to error response.  │
└──────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────┐
│ 5. Analysis Agent  (app/agents/analysis_agent.py)    │
│    Produces verdict: fake/real/inconclusive           │
│    ┌─ Primary: Sightengine REST API (deepfake+genai) │
│    │   • For images: single API call                 │
│    │   • For videos: 5 key frames, concurrent calls, │
│    │     worst-first aggregation                     │
│    ├─ Fallback 1: Gemini (2.5-flash) [conditional]   │
│    ├─ Fallback 2: NVIDIA NIM Omni (LLM vision)       │
│    ├─ Fallback 3: NVIDIA NIM Nano (LLM vision)       │
│    └─ Fallback 4: Hardcoded inconclusive (last resort)│
│    Confidence: provider's own calibrated score, used  │
│    directly — no heuristic fusion is applied.         │
└──────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────┐
│ 6. Report Agent  (app/agents/report_agent.py)        │
│    Generates narrative forensic report (readable      │
│    text, does NOT re-decide the verdict).             │
│    ┌─ Primary: Groq (llama-3.3-70b-versatile)        │
│    ├─ Fallback 1: Gemini (2.5-flash) [conditional]   │
│    ├─ Fallback 2: NVIDIA NIM (Nemotron Omni)          │
│    └─ Fallback 3: Deterministic template report       │
└──────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────┐
│ 7. Output Assembly  (app/runner.py + app/api.py)     │
│    • build_report_json() — structured JSON            │
│    • format_report_markdown() — human-readable MD     │
│    • generate_pdf() — PDF via fpdf2                   │
│    • write_entry() — audit log entry                  │
│    Returns: verdict + report + diagnostics + metadata │
└──────────────────────────────────────────────────────┘
```

## Fallback Chains

Each agent stage has a complete fallback chain. A stage's failure never blocks the
pipeline — the next provider in the chain handles it.

| Stage | Primary | FB1 | FB2 | FB3 |
|-------|---------|-----|-----|-----|
| Router | Groq | NVIDIA Omni | Gemini* | Deterministic |
| Analysis | Sightengine (conf≥0.8 return, <0.8 reconcile†) | NVIDIA Omni | NVIDIA Nano | Gemini* → inconclusive |
| Report | Groq | NVIDIA Omni | Gemini* | Deterministic |

\* Gemini fallback is conditional on `ENABLE_GEMINI_FALLBACK=true` + `GOOGLE_API_KEY` set.
† Sightengine result is prepended as evidence into the LLM analysis prompt for reconciliation
  with classical forensics (ELA, FFT, noise, DCT, wavelets). The LLM produces the final verdict.

Rate-limit errors trigger immediate retry (exponential backoff, configurable count).
Non-rate-limit errors immediately advance to the next fallback.

## Sightengine Integration

The Analysis Agent's primary detector is the Sightengine REST API. Sightengine's response
is evaluated through a **confidence gate** before deciding whether LLM reconciliation is needed:

1. The image is sent to Sightengine for deepfake/genAI scoring. If the image exceeds
   2048px on its longest side, it is pre-resized using LANCZOS downsampling at JPEG
   quality 85 to stay within API limits.
2. If Sightengine responds with confidence **>= 0.8**, the verdict is returned **directly**
   — no LLM reconciliation occurs. This trusts Sightengine's calibrated commercial detector
   for clear-cut cases.
3. If Sightengine responds with confidence **< 0.8** (borderline), its result is prepended
   into the LLM analysis prompt under `=== SIGHTENGINE DEEPFAKE API RESULT ===` and the
   LLM (NVIDIA Omni → NVIDIA Nano → Gemini) reconciles it with the classical forensic
   evidence (ELA, FFT, noise, DCT, wavelets, metadata) to produce the final reconciled verdict.

This "agentic reconciliation" approach ensures:
- **Clear Sightengine verdicts are used immediately** — no unnecessary LLM calls for high-confidence results.
- **Borderline cases get human-like reasoning** — the LLM weighs Sightengine against classical forensics.
- **Contradictions are caught** — if Sightengine says "real" but classical forensics show
  anomalies, the LLM flags the conflict and adjusts confidence downward.
- **Fault tolerance** — if Sightengine fails (quota exhausted, network error, etc.), the
  LLM fallback chain proceeds without its input, using only classical forensics.
- **Multi-frame video**: For videos, 5 key frames are extracted and sent concurrently
  to Sightengine. The worst-frame (highest AI probability) dominates the Sightengine result.
  Per-frame scores are logged and included in the report.

### Parser v3 (current)

`backend/app/providers/sightengine.py` implements parser version `v3`:

1. Explicitly reads `result["deepfake"]["prob"]` and `result["genai"]["prob"]`
2. Also reads legacy `result["type"]["{key}"]` shape (numeric values)
3. Falls back to recursive JSON search only if neither known key is present
4. Returns the MAX probability across all candidates

**Known limitation**: Does NOT support the `overall` override key — reading `overall.prob`
was removed in the v3 refactor. The explicit `deepfake`/`genai` keys are authoritative.

## ADK Session Isolation

Each agent call creates its own `InMemorySessionService`, session, and Runner.
This prevents conversation-history contamination between stages.

The generator from `runner.run_async()` is explicitly `aclose()`'d in a `finally`
block to prevent OpenTelemetry context leaks when the generator is garbage-collected
in a different asyncio context.

## Forensic Tools

### What's Actually Implemented

| Tool | File | What It Checks | Notes |
|------|------|---------------|-------|
| **ELA** | `tools/ela.py` | JPEG recompression error (mean_diff > 1.8 threshold) | Hardcoded threshold |
| **EXIF** | `tools/exif.py` | Camera make/model, editing software, GPS, timestamps | Videos return empty (correct — no EXIF) |
| **FFT** | `tools/fft.py` | High-frequency energy ratio — upsampling artifacts | |
| **Noise** | `tools/noise.py` | Laplacian variance — inconsistent noise patterns | |
| **JPEG** | `tools/jpeg.py` | Block boundary artifact ratio, quantization estimation | |
| **Clone** | `tools/clone.py` | ORB keypoint matching — copy-move forgery | Hardcoded 35px distance, 5-match thresholds |
| **Face** | `tools/forensics.py` | Haar cascade face count | |
| **Hash** | `tools/forensics.py` | SHA-256 + pHash | Video pHash returns "n/a (video)" |
| **Search** | `tools/search.py` | Tavily web search (optional) | |
| **Temporal** | `tools/temporal.py` | Video frame diff, motion score, scene changes | |

### What's NOT Implemented

- No ML ensemble or classifier fusion (the `_fuse_confidence` function was removed — see
  `runner.py` history)
- No EXIF-based AI tool detection is data-driven (it checks known software names, not
  actual algorithmic detection)

## Guardrails (What They Actually Check)

| Guardrail | File | What It Checks | Returns |
|-----------|------|---------------|---------|
| Extension | `validation.py` | `.exe`, `.bat`, `.cmd`, `.com`, `.scr`, `.zip` blocked | `ValidationResult` |
| Path traversal | `validation.py` | `../`, `..\\`, absolute paths in filename | `ValidationResult` |
| File size | `validation.py` | Bytes > `MAX_FILE_SIZE_MB` | `ValidationResult` |
| Magic bytes | `validation.py` | PNG/JPEG/WEBP/MP4 headers vs claimed extension | `bool` |
| Zip bomb | `validation.py` | Tiny file with huge compression ratio | `bool` |
| Injection | `injection.py` | 30+ prompt injection patterns (case-insensitive) | `{"blocked": bool, "reason": str}` |
| Schema | `schema.py` | Router/Agent JSON responses match expected schema | `bool` + error |

## Environment Variables (Full Reference)

See `backend/app/config.py:Settings` class for the full authoritative list. All are
loaded from `.env` file via `pydantic-settings`. Key groups:

```
# Required
SIGHTENGINE_API_USER, SIGHTENGINE_API_SECRET  — Analysis primary
GROQ_API_KEY                                   — Router + Report primary

# Strongly recommended
PRIMARY_API_KEY — NVIDIA NIM (Analysis fallback 2 + Router/Report fallback 2)

# Optional
GOOGLE_API_KEY                 — Gemini fallback (all 3 agents)
ENABLE_GEMINI_FALLBACK         — must be "true" to enable Gemini
TAVILY_API_KEY                 — Web search tool
FALLBACK1_API_KEY              — NVIDIA Nano (Analysis fallback 3)

# Preprocessing defaults (all settable)
IMAGE_TARGET_SIZE=384
CLAHE_CLIP_LIMIT=2.0
DENOISE_STRENGTH=10
ELA_QUALITY=95
VIDEO_MAX_FRAMES=30
VIDEO_INFORMATIVE_FRAMES=10

# Pipeline
MAX_RETRIES_PRIMARY=2
REQUEST_TIMEOUT_SECONDS=240
MAX_FILE_SIZE_MB=100
RATE_LIMIT_PER_MINUTE=20
LOG_LEVEL=INFO
```

## Deployment

### Docker

```bash
cd deepguard-ai
docker build -t deepguard-ai .
docker run -p 8000:8000 --env-file .env deepguard-ai
```

## Testing

```
backend/tests/
├── test_pipeline.py          # 47 unit tests (forensics, guardrails, agents, config, services)
├── test_sightengine_parser.py  # 7 parser schema tests
├── e2e_verify_all.py         # Offline pipeline verification (no API calls)
└── e2e/                      # Live-API tests (requires .env keys)
    ├── conftest.py           # Test server + image/video factories
    ├── test_real_image_api.py
    └── test_real_video_api.py

frontend/tests/e2e/           # Playwright tests (requires npm install @playwright/test)
    ├── upload-and-verify.spec.ts
    └── test_fixtures/sample.jpg
```
