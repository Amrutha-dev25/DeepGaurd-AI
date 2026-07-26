FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000

# ── System deps (OpenCV, MIME, health) ─────────────────────────────
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Install uv (fast Python package installer) ─────────────────────
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# ── Copy dependency manifests (cache layer) ───────────────────────
COPY pyproject.toml uv.lock* ./

# ── Install production dependencies ───────────────────────────────
RUN uv pip install --system \
    fastapi uvicorn[standard] python-multipart slowapi \
    pydantic-settings \
    aiohttp httpx \
    opencv-python-headless pillow numpy \
    exifread imagehash python-magic fpdf2 \
    "google-adk[gcp]>=2.0.0,<3.0.0" \
    opentelemetry-instrumentation-google-genai \
    python-dotenv

# ── Copy application code ─────────────────────────────────────────
COPY backend/ /app/backend/

# ── Working directory ─────────────────────────────────────────────
WORKDIR /app/backend

EXPOSE 8000

# ── Health check (Cloud Run uses /health) ─────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -sf http://localhost:${PORT}/health || exit 1

# ── Start FastAPI (reads $PORT from env, Cloud Run injects it) ────
CMD uvicorn app.api:app --host 0.0.0.0 --port ${PORT}
