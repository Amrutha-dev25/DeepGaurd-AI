# DeepGuard AI

Multi-agent deepfake video forensics system.

- **3 ADK agents** — Router, Analysis, Report
- **Sightengine REST API** for primary analysis
- **NVIDIA NIM fallback** (Nemotron Omni → Nemotron Nano)
- **Groq LLM** for routing and report generation
- **FastAPI** backend with async upload pipeline
- **React** frontend with real-time results

## Quick start

```bash
# Create/activate venv
cd deepguard-ai
uv venv .venv
.venv\Scripts\activate
uv sync

# Copy env and fill in API keys
copy ..\.env.example ..\.env

# Run backend
cd backend
uv run uvicorn app.api:app --reload --port 8000

# Run frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Docker

```bash
docker compose up --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173

## Docs

See [deepguard-ai/docs/](deepguard-ai/docs/) for architecture and detailed documentation.

## Structure

```
D:\adk-workspace/
├── .env                     # API keys (gitignored)
├── .env.example             # Template with all variable names
├── docker-compose.yml
└── deepguard-ai/
    ├── .venv/               # Python virtual environment
    ├── backend/             # FastAPI + ADK agents
    │   ├── app/             # Router, Analysis, Report agents + API
    │   └── tests/           # E2E and unit tests
    ├── frontend/            # React + Vite + TypeScript
    ├── docs/                # Architecture and setup docs
    ├── deployment/          # Cloud Run / CI/CD configs
    ├── Dockerfile
    └── pyproject.toml       # Single dependency source (uv)
```
