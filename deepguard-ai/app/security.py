"""Security checkpoint module for DeepGuard AI.
Provides a thin wrapper around the forensic security function to match the API expectations.
"""

from . import forensics


def security_checkpoint(aggregated: dict) -> dict:
    """Process aggregated forensic results through the security checkpoint.

    The underlying ``forensics.security_checkpoint`` returns a tuple ``(secured, audit)``.
    This wrapper extracts a simple verdict and formats the output structure expected
    by the FastAPI endpoint.
    """
    secured, audit = forensics.security_checkpoint(aggregated)
    verdict = "blocked" if audit.get("blocked") else "ok"
    # Placeholder for recommendations and agent logs - can be extended later.
    recommendations: list[str] = []
    agent_logs: list[dict] = []
    return {
        "verdict": verdict,
        "recommendations": recommendations,
        "agent_logs": agent_logs,
        # Include the secured data for potential downstream usage (optional).
        "secured": secured,
    }
