# DeepGuard AI — Backend

The backend is a **FastAPI** application that receives media files, runs forensic analysis through a multi-stage pipeline, and returns structured reports. It uses **Google ADK** agents with fallback chains across Sightengine, Groq, NVIDIA NIM, and Gemini.

---

## Folder Layout

```
backend/
├── app/
│   ├── agents/           # ADK agent definitions
│   │   ├── router_agent.py
│   │   ├── analysis_agent.py
│   │   ├── report_agent.py
│   │   └── provider_factory.py
│   ├── guardrails/        # Input validation & security
│   │   ├── validation.py  # extension, path traversal, file size, magic bytes
│   │   ├── injection.py   # 30+ prompt injection patterns
│   │   ├── schema.py      # response schema validation
│   │   └── moderation.py
│   ├── preprocessing/     # Media processing pipelines
│   │   ├── image_pipeline.py   # resize, CLAHE, denoise, ELA, FFT, DCT, wavelet, edge maps, hashing
│   │   └── video_pipeline.py   # frame extraction, scene detection, face tracking, optical flow
│   ├── providers/         # External analysis integrations
│   │   └── sightengine.py # Sightengine REST API client (parser v3, auto-resize >2048px)
│   ├── services/          # Output generation
│   │   ├── report_service.py  # JSON + Markdown report builder
│   │   ├── pdf_service.py     # PDF generation via fpdf2
│   │   └── audit_service.py   # tamper-resistant audit logging
│   ├── tools/             # Forensic tools callable by agents
│   │   ├── ela.py, exif.py, fft.py, noise.py
│   │   ├── jpeg.py, clone.py, forensics.py
│   │   ├── security.py, search.py, temporal.py
│   ├── api.py             # FastAPI entry point (CORS, rate limiting, logging)
│   ├── config.py          # Pydantic Settings from .env
│   ├── runner.py          # ADK orchestrator with fallback chains
│   ├── results/           # (empty) runtime output directory
│   └── uploads/           # uploaded files (cleaned after processing)
├── tests/
│   ├── unit tests         # in tests/ root
│   ├── e2e/               # end-to-end API tests (conftest.py, real image/video)
│   └── eval/              # evaluation suite (LLM-as-judge, verification steps)
└── logs/                  # runtime logs
```

---

## Key Files

| File | Purpose |
|---|---|
| `app/api.py` | FastAPI entry — defines `POST /api/analyze`, sets up CORS, rate limiting (SlowAPI), logging, and delegates to `runner.py`. No business logic lives here. |
| `app/config.py` | Pydantic `Settings` class reading from `.env`. All API keys, model names, endpoints, and feature flags are configured here. |
| `app/runner.py` | ADK orchestrator. Runs deterministic preprocessing, then spins up isolated ADK sessions for Router → Analysis → Report agents, each with its own fallback chain. Writes audit entries. |

---

## Subdirectories

### `agents/`
Four ADK agent definitions. The **router** selects the analysis path, the **analysis agent** performs the forensic assessment, the **report agent** structures the output, and `provider_factory.py` constructs LiteLlm model instances with fallback configuration.

### `guardrails/`
Defense-in-depth. `validation.py` blocks dangerous uploads (path traversal, oversized files, wrong extensions, mismatched magic bytes). `injection.py` detects 30+ prompt injection patterns. `schema.py` validates LLM response structure before it reaches the user. `moderation.py` handles content policy checks.

### `preprocessing/`
Transforms raw media into analysis-ready formats. `image_pipeline.py` applies CLAHE, ELA, FFT, DCT, wavelet decomposition, edge detection, and perceptual hashing. `video_pipeline.py` extracts keyframes, detects scene changes, tracks faces, and computes optical flow.

### `providers/`
External API integrations. Currently `sightengine.py` (Sightengine REST API v3 with automatic large-image resizing). New providers can be added here and wired into the agent fallback chain via `provider_factory.py`.

### `services/`
Post-analysis output layer. `report_service.py` builds structured JSON and Markdown reports. `pdf_service.py` generates PDF via fpdf2. `audit_service.py` produces tamper-resistant audit logs (hash-chained entries).

### `tools/`
Individual forensic functions callable by ADK agents. Each tool wraps a specific algorithm (ELA, EXIF analysis, FFT, noise estimation, JPEG ghost detection, clone detection, etc.) and returns structured findings.

---

## Execution Flow

```
User uploads file
       │
       ▼
  api.py — validates extension, size, magic bytes, checks for injection
       │
       ▼
  runner.py — runs deterministic preprocessing (image/video pipeline)
       │
       ▼
  Router Agent (ADK) — classifies media type & selects analysis strategy
       │
       ▼
  Analysis Agent (ADK) — runs forensic tools + Sightengine + LLM fallback chain
       │
       ▼
  Report Agent (ADK) — structures findings into verdict, observations, recommendations
       │
       ▼
  Services — builds JSON report + Markdown + PDF, writes audit log
       │
       ▼
  Response returned to client
```

Each ADK stage has its own isolated session (no cross-contamination) and a full fallback chain so no single provider failure can stop the pipeline.

---

## Setup

```powershell
# Prerequisites: Python 3.11+, uv
cd backend
uv sync                          # install all dependencies
cp ..\.env.example ..\.env       # create env file (edit with your keys)
uv run uvicorn app.api:app --reload --port 8000
```

## Testing

```powershell
cd backend
uv run pytest tests/ -v                           # unit + integration
uv run pytest tests/e2e/ -v                       # end-to-end API tests
uv run python tests/eval/run_evaluation.py         # evaluation suite
```

---

## Dependencies

| Requirement | Notes |
|---|---|
| Python ≥3.11, <3.14 | defined in `pyproject.toml` |
| uv | fast Python package manager |
| FastAPI + uvicorn | web server |
| Google ADK | agent framework (`google-adk[gcp]`) |
| OpenCV (`opencv-python-headless`) | image/video processing |
| Pillow, numpy | imaging & numerical ops |
| aiohttp / httpx | HTTP clients (Sightengine, LiteLlm) |
| Sightengine API key | primary analysis provider |
| Groq API key | Router + Report agents |
| NVIDIA NIM API key | analysis fallback chain |
| Google/Gemini API key | optional Gemini fallback |
| fpdf2 | PDF report generation |

Full list in `pyproject.toml` under `[project.dependencies]` and `[project.optional-dependencies]`.

---

## Extension Points

| What | How |
|---|---|
| **Add a provider** | Create `app/providers/new_provider.py`, implement the analysis interface, add fallback entries in `config.py` and `provider_factory.py` |
| **Add a forensic tool** | Create `app/tools/new_tool.py`, register it in the agent's tool list (see `analysis_agent.py`) |
| **Add a guardrail** | Create a new module in `app/guardrails/`, wire it into `api.py` or `runner.py` |
| **Add an agent** | Create `app/agents/new_agent.py`, add it to the pipeline in `runner.py` |

---

> For a deep-dive on the architecture, provider fallback strategy, and evaluation methodology, see [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).
