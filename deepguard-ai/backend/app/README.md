# `app/` — FastAPI Backend Application

The core Python package that contains all backend logic — API layer, ADK agents, forensic tools, providers, guardrails, preprocessing, and services.

## Layout

```
app/
├── api.py              # FastAPI entry point (routes, CORS, rate limiting, logging)
├── config.py           # Pydantic Settings from .env (all runtime config)
├── runner.py           # ADK orchestrator (pipeline + fallback chains)
├── agents/             # ADK agent definitions + provider factory
├── guardrails/         # Input validation, injection detection, schema enforcement
├── preprocessing/      # Image/video computer vision pipelines
├── providers/          # Sightengine REST API client
├── services/           # Report builder, PDF generator, audit logger
├── tools/              # Forensic analysis tools (10 tools)
├── results/            # Generated report output directory
└── uploads/            # Uploaded media files (temporary)
```

## Key Files

| File | Role |
|------|------|
| `api.py` | Thin FastAPI layer — no business logic. Routes, CORS, rate limiting, logging setup. |
| `config.py` | Single source of truth for all environment configuration via `pydantic-settings`. |
| `runner.py` | ADK orchestrator — runs the 3-agent pipeline with full fallback chains per stage. |

## Execution Flow

```
POST /api/analyze
  → api.py (validate, check injection)
    → runner.run_pipeline()
      → Security Layer → Preprocessing → Forensic Context
        → Router Agent (classify media)
          → Analysis Agent (Sightengine + LLM fallback → verdict)
            → Report Agent (generate narrative report)
              → Output Assembly (JSON + Markdown + PDF + audit)
```

## Dependencies

- **Framework**: FastAPI, Uvicorn, SlowAPI (rate limiting)
- **ADK**: google-adk (3 agents with session isolation)
- **Computer Vision**: OpenCV, Pillow, NumPy
- **Forensics**: exifread, imagehash, python-magic
- **PDF**: fpdf2
- **HTTP**: aiohttp (Sightengine), httpx (LiteLLM transport)

## Extension Points

- **Add a forensic tool**: create `tools/your_tool.py`, add to `collect_forensic_context()` in `tools/forensics.py`
- **Add a provider**: add config field in `config.py`, create provider client in `providers/`, add fallback entry in `runner.py`
- **Add a guardrail**: add function to `guardrails/validation.py` or `guardrails/injection.py`, call from `api.py`
- **Add a report format**: add service in `services/`, call from `runner.py` output assembly

See [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for detailed flow.
