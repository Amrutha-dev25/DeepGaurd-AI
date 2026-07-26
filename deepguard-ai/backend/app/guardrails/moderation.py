"""Output guardrails — hallucination detection, confidence validation, fabricated value detection."""

import json
import re
from typing import Any

_MIN_CONFIDENCE = 0.0
_MAX_CONFIDENCE = 1.0
_MIN_EVIDENCE_LENGTH = 10


def validate_confidence(confidence: float) -> dict[str, Any]:
    if not isinstance(confidence, (int, float)):
        return {"valid": False, "error": f"Confidence must be numeric, got {type(confidence).__name__}"}
    if confidence < _MIN_CONFIDENCE or confidence > _MAX_CONFIDENCE:
        return {"valid": False, "error": f"Confidence {confidence} out of range [{_MIN_CONFIDENCE}, {_MAX_CONFIDENCE}]"}
    return {"valid": True, "error": None}


def validate_evidence(evidence: str) -> dict[str, Any]:
    if not isinstance(evidence, str):
        return {"valid": False, "error": f"Evidence must be a string, got {type(evidence).__name__}"}
    if len(evidence.strip()) < _MIN_EVIDENCE_LENGTH:
        return {"valid": False, "error": f"Evidence too short ({len(evidence.strip())} chars, min {_MIN_EVIDENCE_LENGTH})"}
    return {"valid": True, "error": None}


_FABRICATED_PATTERNS = [
    r"confidence\s*[=:]\s*\d+\.?\d*\s*%",
    r"\d+\.\d{5,}",  # overly precise numbers
]


def detect_fabricated_values(text: str) -> list[str]:
    flags: list[str] = []
    for pat in _FABRICATED_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            flags.append(f"Suspicious pattern: {pat}")
    return flags


def check_analysis_output(parsed: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []

    conf_result = validate_confidence(parsed.get("confidence", -1))
    if not conf_result["valid"]:
        issues.append(conf_result["error"])

    ev_result = validate_evidence(parsed.get("evidence", ""))
    if not ev_result["valid"]:
        issues.append(ev_result["error"])

    fabricated = detect_fabricated_values(json.dumps(parsed))
    issues.extend(fabricated)

    return {"valid": len(issues) == 0, "issues": issues}


def check_router_output(parsed: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    if not isinstance(parsed.get("viable_for_analysis"), bool):
        issues.append("viable_for_analysis must be boolean")
    if parsed.get("file_type") not in ("image", "video", "unsupported"):
        issues.append(f"Invalid file_type: {parsed.get('file_type')}")
    return {"valid": len(issues) == 0, "issues": issues}
