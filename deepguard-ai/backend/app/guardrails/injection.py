"""Prompt injection detection and PII redaction guardrails."""

import os
import re
from typing import Any

from app.config import settings

_WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\(?:[^\\\s]+\\)*[^\\\s]*")
_UNIX_FS_ROOTS = "|".join(re.escape(r) for r in ("/home/", "/var/", "/tmp/", "/usr/", "/root/", "/mnt/", "/uploads/", "/proc/", "/etc/"))
_UNIX_PATH_RE = re.compile(r"(?:" + _UNIX_FS_ROOTS + r")[^\s]*")
_EMAIL_RE = re.compile(r"[\w.\-]+@[\w.\-]+")

_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "ignore above",
    "system prompt",
    "you are now",
    "pretend you are",
    "new instructions",
    "override",
    "forget your",
    "you are not",
    "your new prompt",
    "tell me your",
    "show your prompt",
    "output your instructions",
    "reveal your",
    "expose your",
    "what is your api key",
    "what is your api",
    "api key",
    "secret key",
    "password",
    "administrator",
    "drop table",
    "--exec",
    "sudo rm",
    "sudo",
    "__import__",
    "eval(",
    "exec(",
    "os.system",
    "subprocess",
    "open(",
    "shell_exec",
    "base64_decode",
    "curl ",
    "wget ",
    "powershell",
    "Invoke-Expression",
    "cmd.exe",
    "/etc/passwd",
    "/etc/shadow",
    "C:\\Windows",
    "System32",
]

try:
    _USERNAME = os.getlogin()
except Exception:
    _USERNAME = os.environ.get("USERNAME") or os.environ.get("USER") or ""


def redact_pii(val: Any) -> Any:
    if isinstance(val, str):
        s = val
        s = _WINDOWS_PATH_RE.sub("[REDACTED_PATH]", s)
        s = _UNIX_PATH_RE.sub("[REDACTED_PATH]", s)
        s = _EMAIL_RE.sub("[REDACTED_EMAIL]", s)
        if _USERNAME:
            s = re.sub(re.escape(_USERNAME), "[REDACTED_USER]", s, flags=re.IGNORECASE)
        return s
    if isinstance(val, dict):
        return {k: redact_pii(v) for k, v in val.items()}
    if isinstance(val, list):
        return [redact_pii(v) for v in val]
    return val


def detect_injection(val: Any) -> bool:
    if isinstance(val, str):
        low = val.lower()
        return any(p in low for p in _INJECTION_PATTERNS)
    if isinstance(val, dict):
        return any(detect_injection(v) for v in val.values())
    if isinstance(val, list):
        return any(detect_injection(v) for v in val)
    return False


def security_checkpoint(context: dict[str, Any]) -> dict[str, Any]:
    """Run PII redaction and prompt-injection detection on data.

    Args:
        context: The data dict to check.

    Returns:
        Dict with 'blocked' (bool), 'reason' (str or None), and 'secured_context' (dict).
    """
    if not settings.pii_redaction_enabled and not settings.injection_detection_enabled:
        return {"blocked": False, "reason": None, "secured_context": context}
    secured = redact_pii(context) if settings.pii_redaction_enabled else context
    violation = detect_injection(secured) if settings.injection_detection_enabled else False
    if violation:
        return {"blocked": True, "reason": "Prompt injection or malicious content detected.", "secured_context": {}}
    return {"blocked": False, "reason": None, "secured_context": secured}


def check_user_input(user_text: str) -> dict[str, Any]:
    """Check user-supplied text for prompt injection."""
    if not user_text:
        return {"blocked": False, "reason": None}
    if detect_injection(user_text):
        return {"blocked": True, "reason": "Prompt injection detected in user input."}
    return {"blocked": False, "reason": None}
