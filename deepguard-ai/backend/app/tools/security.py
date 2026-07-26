"""Security tools — PII redaction, prompt-injection detection.

Exports `security_checkpoint` as a plain function and `security_tools` as ADK FunctionTool list.
"""

import os
import re
from datetime import datetime, timezone
from typing import Any

from google.adk.tools import FunctionTool

from app.config import settings

_WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\(?:[^\\\s]+\\)*[^\\\s]*")
_UNIX_FS_ROOTS = "|".join(re.escape(r) for r in ("/home/", "/var/", "/tmp/", "/usr/", "/root/", "/mnt/", "/uploads/", "/proc/", "/etc/"))
_UNIX_PATH_RE = re.compile(r"(?:" + _UNIX_FS_ROOTS + r")[^\s]*")
_EMAIL_RE = re.compile(r"[\w.\-]+@[\w.\-]+")
_SUSPICIOUS_PATTERNS = ["drop table", "--exec", "sudo rm", "ignore previous instructions", "system prompt", "__import__", "eval(", "exec(", "os.system"]

try:
    _USERNAME = os.getlogin()
except Exception:
    _USERNAME = os.environ.get("USERNAME") or os.environ.get("USER") or ""


def _redact_value(val: Any) -> Any:
    if isinstance(val, str):
        s = val
        s = _WINDOWS_PATH_RE.sub("[REDACTED_PATH]", s)
        s = _UNIX_PATH_RE.sub("[REDACTED_PATH]", s)
        s = _EMAIL_RE.sub("[REDACTED_EMAIL]", s)
        if _USERNAME:
            s = re.sub(re.escape(_USERNAME), "[REDACTED_USER]", s, flags=re.IGNORECASE)
        return s
    if isinstance(val, dict):
        return {k: _redact_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_redact_value(v) for v in val]
    return val


def _contains_suspicious(val: Any) -> bool:
    if isinstance(val, str):
        low = val.lower()
        return any(p in low for p in _SUSPICIOUS_PATTERNS)
    if isinstance(val, dict):
        return any(_contains_suspicious(v) for v in val.values())
    if isinstance(val, list):
        return any(_contains_suspicious(v) for v in val)
    return False


def security_checkpoint(context: dict[str, Any]) -> dict[str, Any]:
    """Run PII redaction and prompt-injection detection on forensic context data.

    Args:
        context: The aggregated forensic context dict.

    Returns:
        Dict with 'blocked' (bool), 'reason' (str or None), and 'secured_context' (dict).
    """
    if not settings.pii_redaction_enabled and not settings.injection_detection_enabled:
        return {"blocked": False, "reason": None, "secured_context": context}
    secured = _redact_value(context) if settings.pii_redaction_enabled else context
    violation = _contains_suspicious(secured) if settings.injection_detection_enabled else False
    if violation:
        return {"blocked": True, "reason": "Prompt injection or malicious content detected.", "secured_context": {}}
    return {"blocked": False, "reason": None, "secured_context": secured}


security_tools = [
    FunctionTool(func=security_checkpoint),
]
