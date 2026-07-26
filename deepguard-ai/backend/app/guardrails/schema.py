"""JSON schema validation for model outputs.

Ensures agents return valid, well-structured JSON that matches expected schemas.
"""

import json
from typing import Any

ROUTER_SCHEMA = {
    "type": "object",
    "required": ["file_type", "is_corrupt", "face_present", "viable_for_analysis"],
    "properties": {
        "file_type": {"type": "string", "enum": ["image", "video", "unsupported"]},
        "is_corrupt": {"type": "boolean"},
        "face_present": {"type": "boolean"},
        "viable_for_analysis": {"type": "boolean"},
        "early_exit_reason": {"type": ["string", "null"]},
        "faces": {"type": "integer"},
        "resolution": {"type": "string"},
        "quality": {"type": "string", "enum": ["good", "medium", "poor"]},
        "needs_preprocessing": {"type": "boolean"},
        "pipeline": {"type": "string"},
    },
}

ANALYSIS_SCHEMA = {
    "type": "object",
    "required": ["verdict", "confidence", "evidence"],
    "properties": {
        "verdict": {"type": "string", "enum": ["real", "fake", "inconclusive"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "evidence": {"type": "string"},
        "key_indicators": {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
        "limitations": {"type": "string"},
    },
}


def validate_schema(parsed: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Validate a parsed JSON object against a schema.

    Args:
        parsed: The parsed JSON dict.
        schema: The schema dict (JSON Schema subset).

    Returns:
        Dict with 'valid' (bool) and 'errors' (list of str).
    """
    errors: list[str] = []
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    for field in required:
        if field not in parsed:
            errors.append(f"Missing required field: {field}")
    for field, value in parsed.items():
        if field not in properties:
            continue
        prop = properties[field]
        if "type" in prop:
            expected = prop["type"]
            if expected == "string" and not isinstance(value, str):
                errors.append(f"Field '{field}' should be string, got {type(value).__name__}")
            elif expected == "boolean" and not isinstance(value, bool):
                errors.append(f"Field '{field}' should be boolean, got {type(value).__name__}")
            elif expected == "integer" and not isinstance(value, int):
                errors.append(f"Field '{field}' should be integer, got {type(value).__name__}")
            elif expected == "number" and not isinstance(value, (int, float)):
                errors.append(f"Field '{field}' should be number, got {type(value).__name__}")
            elif expected in ("array",) and not isinstance(value, list):
                errors.append(f"Field '{field}' should be array, got {type(value).__name__}")
            elif expected == "object" and not isinstance(value, dict):
                errors.append(f"Field '{field}' should be object, got {type(value).__name__}")
        if "enum" in prop and value not in prop["enum"]:
            errors.append(f"Field '{field}' value '{value}' not in allowed: {prop['enum']}")
    if "minimum" in prop and isinstance(value, (int, float)) and value < prop["minimum"]:
        errors.append(f"Field '{field}' value {value} is below minimum {prop['minimum']}")
    if "maximum" in prop and isinstance(value, (int, float)) and value > prop["maximum"]:
        errors.append(f"Field '{field}' value {value} exceeds maximum {prop['maximum']}")

    return {"valid": len(errors) == 0, "errors": errors}


def validate_router_output(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text) if isinstance(text, str) else text
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [f"Invalid JSON: {e}"], "parsed": {}}
    result = validate_schema(parsed, ROUTER_SCHEMA)
    result["parsed"] = parsed
    return result


def validate_analysis_output(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text) if isinstance(text, str) else text
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [f"Invalid JSON: {e}"], "parsed": {}}
    result = validate_schema(parsed, ANALYSIS_SCHEMA)
    result["parsed"] = parsed
    return result
