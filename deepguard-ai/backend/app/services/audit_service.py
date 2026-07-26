"""Tamper-resistant structured audit logging with blockchain-style hash chaining.

Each entry is appended to a JSONL file.  Every entry stores the SHA-256 hash
of the previous entry, making retrospective tampering detectable.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _log_dir() -> Path:
    p = Path(__file__).resolve().parents[2] / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _chain_path() -> Path:
    return _log_dir() / "audit_chain.jsonl"


def _hash(data: dict[str, Any]) -> str:
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _previous_hash() -> str | None:
    path = _chain_path()
    if not path.exists() or path.stat().st_size == 0:
        return None
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    if not lines:
        return None
    try:
        last = json.loads(lines[-1])
        return last.get("entry_hash")
    except (json.JSONDecodeError, IndexError):
        return None


def write_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Write a structured audit entry with hash chaining.

    Args:
        entry: The audit entry dict (must include 'request_id', 'verdict', etc.).

    Returns:
        The full entry dict (including the hash fields).
    """
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    entry["previous_hash"] = _previous_hash()
    entry["entry_hash"] = _hash(entry)

    with open(_chain_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.info("Audit entry written — request=%s verdict=%s hash=%s",
                entry.get("request_id", "?"), entry.get("verdict", "?"),
                entry["entry_hash"][:12])
    return entry


def verify_chain() -> dict[str, Any]:
    """Verify the integrity of the entire audit chain.

    Returns:
        Dict with 'status' ('ok' | 'tampered' | 'empty'), entry count, and any broken links.
    """
    path = _chain_path()
    if not path.exists() or path.stat().st_size == 0:
        return {"status": "empty", "entries": 0, "broken_links": []}

    broken: list[dict] = []
    prev = None
    count = 0

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                broken.append({"line": count + 1, "error": "invalid JSON"})
                continue

            if prev is not None:
                expected = entry.get("previous_hash")
                actual = _hash(prev)
                if expected != actual:
                    broken.append({
                        "line": count + 1,
                        "error": f"hash mismatch: expected {actual[:12]}..., got {expected[:12] if expected else 'None'}...",
                    })

            prev = entry
            count += 1

    return {
        "status": "ok" if not broken else "tampered",
        "entries": count,
        "broken_links": broken,
    }
