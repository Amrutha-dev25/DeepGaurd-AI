"""Centralized provider factory — single source of truth for model creation.

Each agent requests a provider by name from this factory.
No agent constructs LiteLlm or Gemini clients directly.

Model strings MUST use the correct LiteLLM provider prefix:
  - NVIDIA NIM:  nvidia_nim/nvidia/...  or  nvidia_nim/meta/...
  - Groq:        groq/...
  - Gemini:      gemini-... (native ADK string, not via LiteLlm)
"""

import logging
import os

from google.adk.models.lite_llm import LiteLlm

from app.config import settings

logger = logging.getLogger(__name__)

# ── NVIDIA NIM API key bootstrap ─────────────────────────────────────
# LiteLLM's nvidia_nim provider validates against the NVIDIA_NIM_API_KEY
# environment variable.  Even when api_key= is passed programmatically,
# the provider checks this specific env var.  We set it here from whichever
# config field has a value, so all NVIDIA NIM agents (Router, Analysis,
# Report) authenticate through a single source regardless of which config
# key was populated.
_NVIDIA_KEY_SOURCES = [
    settings.router_fallback2_api_key,
    settings.router_fallback3_api_key,
    settings.primary_api_key,
    settings.fallback1_api_key,
    settings.report_fallback2_api_key,
    settings.report_fallback3_api_key,
]
_nvidia_key = next((k for k in _NVIDIA_KEY_SOURCES if k), "")
if _nvidia_key:
    os.environ.setdefault("NVIDIA_NIM_API_KEY", _nvidia_key)


# ── Router Agent ──────────────────────────────────────────────────────


def get_router_model() -> LiteLlm:
    """Router Primary: Groq via LiteLlm."""
    logger.info("Router Primary: Groq (%s)", settings.router_model)
    kwargs = dict(
        model=settings.router_model,
        api_key=settings.groq_api_key,
        temperature=0.1,
        max_tokens=1024,
    )
    if settings.router_endpoint:
        kwargs["base_url"] = settings.router_endpoint
    return LiteLlm(**kwargs)


def _nvidia_key_or_fallback(specific_key: str) -> str:
    """Return specific_key if non-empty, otherwise fall back to bootstrapped env var."""
    if specific_key:
        return specific_key
    return os.environ.get("NVIDIA_NIM_API_KEY", "")


def get_router_fallback1_model() -> LiteLlm:
    """Router NVIDIA Omni (Fallback 1 in execution order) via LiteLlm."""
    logger.info("Router NVIDIA Omni (Fallback 2): %s", settings.router_fallback2_model)
    return LiteLlm(
        model=settings.router_fallback2_model,
        api_key=_nvidia_key_or_fallback(settings.router_fallback2_api_key),
        base_url=settings.router_fallback2_endpoint,
        temperature=0.1,
        max_tokens=1024,
    )


def get_router_fallback2_model() -> LiteLlm:
    """Unused NVIDIA Nano — retained for interface compatibility."""
    logger.info("Router NVIDIA Nano (unused in Router chain)")
    return LiteLlm(
        model=settings.router_fallback3_model,
        api_key=_nvidia_key_or_fallback(settings.router_fallback3_api_key),
        base_url=settings.router_fallback3_endpoint,
        temperature=0.1,
        max_tokens=1024,
    )


def get_router_fallback3_model() -> str:
    """Router Gemini (Fallback 2 in execution order) — native ADK string."""
    logger.info("Router Gemini (Fallback 1): %s", settings.router_fallback1_model)
    return settings.router_fallback1_model


# ── Analysis Agent ───────────────────────────────────────────────────


def get_analysis_primary_model() -> LiteLlm:
    """Analysis NVIDIA Omni (Fallback 1 in execution order) via LiteLlm with json_object."""
    logger.info("Analysis NVIDIA Omni (Fallback 2): %s", settings.primary_model)
    return LiteLlm(
        model=settings.primary_model,
        api_key=_nvidia_key_or_fallback(settings.primary_api_key),
        base_url=settings.primary_endpoint,
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=1024,
    )


def get_analysis_fallback1_model() -> LiteLlm:
    """Analysis NVIDIA Nano (Fallback 2 in execution order) via LiteLlm with json_object."""
    logger.info("Analysis NVIDIA Nano (Fallback 3): %s", settings.fallback1_model)
    return LiteLlm(
        model=settings.fallback1_model,
        api_key=_nvidia_key_or_fallback(settings.fallback1_api_key),
        base_url=settings.fallback1_endpoint,
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=1024,
    )


def get_analysis_fallback2_model() -> str:
    """Analysis Gemini (Fallback 3 in execution order) — native ADK string."""
    logger.info("Analysis Gemini (Fallback 1): %s", settings.fallback2_model)
    return settings.fallback2_model


# ── Report Agent ─────────────────────────────────────────────────────


def get_report_model() -> LiteLlm:
    """Report Primary: Groq via LiteLlm."""
    logger.info("Report Primary: Groq (%s)", settings.report_model)
    return LiteLlm(
        model=settings.report_model,
        api_key=settings.groq_api_key,
        temperature=0.2,
        max_tokens=2048,
    )


def get_report_fallback1_model() -> LiteLlm:
    """Report NVIDIA Omni (Fallback 1 in execution order) via LiteLlm."""
    logger.info("Report NVIDIA Omni (Fallback 2): %s", settings.report_fallback2_model)
    return LiteLlm(
        model=settings.report_fallback2_model,
        api_key=_nvidia_key_or_fallback(settings.report_fallback2_api_key),
        base_url=settings.report_fallback2_endpoint,
        temperature=0.2,
        max_tokens=2048,
    )


def get_report_fallback2_model() -> LiteLlm:
    """Unused NVIDIA Nano — retained for interface compatibility."""
    logger.info("Report NVIDIA Nano (unused in Report chain)")
    return LiteLlm(
        model=settings.report_fallback3_model,
        api_key=_nvidia_key_or_fallback(settings.report_fallback3_api_key),
        base_url=settings.report_fallback3_endpoint,
        temperature=0.2,
        max_tokens=2048,
    )


def get_report_fallback3_model() -> str:
    """Report Gemini (Fallback 2 in execution order) — native ADK string."""
    logger.info("Report Gemini (Fallback 1): %s", settings.report_fallback1_model)
    return settings.report_fallback1_model
