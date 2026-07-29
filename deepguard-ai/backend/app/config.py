"""Pydantic Settings for DeepGuard AI — all runtime config driven by environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at workspace root (docker-compose auto-loads it).
# Path from this file: backend/app/config.py -> ../../../.env
_env_file = str(Path(__file__).resolve().parents[3] / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_file, env_file_encoding="utf-8")

    # ── Sightengine (Analysis Primary — REST API) ─────────────────────────
    sightengine_api_user: str = ""
    sightengine_api_secret: str = ""
    sightengine_api_url: str = "https://api.sightengine.com/1.0/check.json"

    # ── Google / Gemini (Fallback for Router, Analysis, Report) ──────────
    google_api_key: str = ""

    # ── Router Agent — Primary (Groq) ──────────────────────────────────
    router_model: str = "groq/llama-3.3-70b-versatile"
    router_api_key: str = ""
    router_endpoint: str = "https://api.groq.com/openai/v1"

    # ── Router Agent — Fallback 1 (Gemini) ─────────────────────────────
    router_fallback1_model: str = "gemini-2.5-flash"

    # ── Router Agent — Fallback 2 (NVIDIA Omni) ────────────────────────
    router_fallback2_model: str = "nvidia_nim/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    router_fallback2_api_key: str = ""
    router_fallback2_endpoint: str = "https://integrate.api.nvidia.com/v1"

    # ── Router Agent — Fallback 3 (NVIDIA Nano) ────────────────────────
    router_fallback3_model: str = "nvidia_nim/nvidia/nemotron-nano-12b-v2-vl"
    router_fallback3_api_key: str = ""
    router_fallback3_endpoint: str = "https://integrate.api.nvidia.com/v1"

    # ── Analysis Agent — Fallback 1 (NVIDIA Nemotron Omni via LiteLlm) ──
    # Previously was Primary before Sightengine integration.
    primary_model: str = "nvidia_nim/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    primary_api_key: str = ""
    primary_endpoint: str = "https://integrate.api.nvidia.com/v1"

    # ── Analysis Agent — Fallback 2 (NVIDIA Nemotron Nano 12B VL via LiteLlm) ─
    fallback1_model: str = "nvidia_nim/nvidia/nemotron-nano-12b-v2-vl"
    fallback1_api_key: str = ""
    fallback1_endpoint: str = "https://integrate.api.nvidia.com/v1"

    # ── Analysis Agent — Fallback 3 (Gemini — only if ENABLE_GEMINI_FALLBACK) ─
    fallback2_model: str = "gemini-2.5-flash"

    # ── Report Agent — Primary (Groq) ─────────────────────────────────────
    report_model: str = "groq/llama-3.3-70b-versatile"

    # ── Report Agent — Fallback 1 (Gemini) ────────────────────────────────
    report_fallback1_model: str = "gemini-2.5-flash"

    # ── Report Agent — Fallback 2 (NVIDIA Omni) ───────────────────────────
    report_fallback2_model: str = "nvidia_nim/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    report_fallback2_api_key: str = ""
    report_fallback2_endpoint: str = "https://integrate.api.nvidia.com/v1"

    # ── Report Agent — Fallback 3 (NVIDIA Nano) ───────────────────────────
    report_fallback3_model: str = "nvidia_nim/nvidia/nemotron-nano-12b-v2-vl"
    report_fallback3_api_key: str = ""
    report_fallback3_endpoint: str = "https://integrate.api.nvidia.com/v1"

    # ── Groq (required for Router & Report Agent) ────────────────────────
    groq_api_key: str = ""

    # ── Tavily (replaces Google Custom Search) ─────────────────────────────
    tavily_api_key: str = ""

    # ── Gemini Fallback toggle (default OFF — applies to Router, Analysis, Report) ──
    enable_gemini_fallback: bool = False

    # ── Retry & Timeout ──────────────────────────────────────────────────
    max_retries_primary: int = 2
    request_timeout_seconds: int = 240

    # ── Upload Limits ────────────────────────────────────────────────────
    max_file_size_mb: int = 100
    allowed_mime_types: list[str] = [
        "image/jpeg", "image/png", "image/webp", "video/mp4",
    ]

    # ── Preprocessing ────────────────────────────────────────────────────
    image_target_size: int = 384
    clahe_clip_limit: float = 2.0
    denoise_strength: int = 10
    ela_quality: int = 95
    video_max_frames: int = 30
    video_informative_frames: int = 10

    # ── CORS (production frontend domain, no wildcard) ───────────────────
    frontend_url: str = ""
    cors_origins: str = ""

    # ── Rate Limiting ────────────────────────────────────────────────────
    rate_limit_per_minute: int = 20

    # ── Security ─────────────────────────────────────────────────────────
    pii_redaction_enabled: bool = True
    injection_detection_enabled: bool = True

    # ── Supervisor Agent — Cerebras (primary, separate from NVIDIA/Groq) ───
    # Sign up at cloud.cerebras.ai, no credit card required.
    cerebras_api_key: str = ""
    supervisor_primary_model: str = "cerebras/gemma-4-31b"

    # ── Supervisor Agent — Gemini (fallback, reuse existing Google key) ──
    supervisor_fallback_model: str = "gemini-2.5-flash"

    # ── Supervisor Agent — legacy model override (deprecated, replaced by
    # supervisor_primary_model / supervisor_fallback_model) ────────────────
    supervisor_model: str = ""

    # ── Logging ──────────────────────────────────────────────────────────
    log_level: str = "INFO"


settings = Settings()

# ── Startup credential audit ──────────────────────────────────────────
import logging as _logging
_logging.getLogger(__name__).info(
    "Sightengine credentials: %s (user_len=%d secret_len=%d)",
    "PRESENT" if settings.sightengine_api_user and settings.sightengine_api_secret else "MISSING",
    len(settings.sightengine_api_user) if settings.sightengine_api_user else 0,
    len(settings.sightengine_api_secret) if settings.sightengine_api_secret else 0,
)
