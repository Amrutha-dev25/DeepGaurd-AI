"""Report formatting service — transforms verdict + forensic context into structured reports."""

import json
from datetime import datetime, timezone
from typing import Any


def build_report_json(
    request_id: str,
    verdict: dict[str, Any],
    routing: dict[str, Any],
    forensic_context: dict[str, Any],
    pipeline_latency: float,
    model_used: str,
    fallback_used: bool,
    investigation_trace: dict | None = None,
) -> dict[str, Any]:
    """Build the structured JSON report returned to the frontend."""
    v = verdict.get("verdict", "inconclusive")
    confidence = verdict.get("confidence", 0.5)

    recommendations: list[str] = verdict.get("recommendation", "").split("\n") if verdict.get("recommendation") else []
    recommendations = [r.strip() for r in recommendations if r.strip()]
    if not recommendations:
        if v == "fake":
            recommendations.append("Classified as AI-generated or manipulated. Treat with high suspicion.")
            recommendations.append("Cross-reference with original source if available.")
        elif v == "real":
            recommendations.append("No significant manipulation indicators detected.")
        else:
            recommendations.append("Insufficient data for a definitive classification. Manual review recommended.")

    result = {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "file_type": routing.get("file_type", "unknown"),
        "face_present": routing.get("face_present", False),
        "verdict": v,
        "confidence": round(confidence, 4),
        "confidence_percent": round(confidence * 100, 1),
        "model_used": model_used,
        "fallback_triggered": fallback_used,
        "pipeline_time_seconds": round(pipeline_latency, 3),
        "recommendations": recommendations,
    }

    # Forward new forensic fields from the Analysis Agent verdict
    if verdict.get("analysis_summary"):
        result["analysis_summary"] = verdict["analysis_summary"]
    if verdict.get("visual_observations"):
        result["visual_observations"] = verdict["visual_observations"]
    if verdict.get("forensic_observations"):
        result["forensic_observations"] = verdict["forensic_observations"]
    if verdict.get("supporting_evidence"):
        result["supporting_evidence"] = verdict["supporting_evidence"]
    if verdict.get("conflicting_evidence"):
        result["conflicting_evidence"] = verdict["conflicting_evidence"]
    if verdict.get("limitations"):
        result["limitations"] = verdict["limitations"]
    if verdict.get("recommendation"):
        result["recommendation"] = verdict["recommendation"]
    if verdict.get("frame_analysis"):
        result["frame_analysis"] = verdict["frame_analysis"]
    if verdict.get("raw_prob") is not None:
        result["raw_prob"] = verdict["raw_prob"]

    # Legacy field support
    if not result.get("analysis_summary"):
        result["analysis_summary"] = verdict.get("evidence", "")
    result["evidence"] = verdict.get("evidence", verdict.get("analysis_summary", ""))
    result["key_indicators"] = verdict.get("key_indicators", verdict.get("supporting_evidence", []))

    # Investigation trace (supervisor decision loop)
    if investigation_trace:
        result["investigation_trace"] = investigation_trace

    return result


def format_report_markdown(report_json: dict[str, Any], report_text: str) -> str:
    """Format the report as a clean markdown document."""
    lines = [
        "# DeepGuard AI — Forensic Report",
        "",
        f"**Request ID:** {report_json.get('request_id', 'N/A')}",
        f"**Timestamp:** {report_json.get('timestamp', 'N/A')}",
        "",
        "---",
        "",
        report_text,
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Field | Value |",
        "|-------|-------|",
        f"| Verdict | **{report_json.get('verdict', 'inconclusive').upper()}** |",
        f"| Confidence | {report_json.get('confidence_percent', 0)}% |",
        f"| Model Used | {report_json.get('model_used', 'N/A')} |",
        f"| Fallback Triggered | {'Yes' if report_json.get('fallback_triggered') else 'No'} |",
        f"| Pipeline Time | {report_json.get('pipeline_time_seconds', 0)}s |",
        "",
    ]
    if report_json.get("conflicting_evidence"):
        lines.append("## Conflicting Evidence")
        lines.append("")
        for ce in report_json["conflicting_evidence"]:
            lines.append(f"- ⚠ {ce}")
        lines.append("")
    if report_json.get("analysis_summary"):
        lines.append("## Analysis Summary")
        lines.append("")
        lines.append(report_json["analysis_summary"])
        lines.append("")
    if report_json.get("frame_analysis"):
        lines.append("## Per-Frame Analysis")
        lines.append("")
        lines.append("| Frame | Verdict | Confidence |")
        lines.append("|-------|---------|------------|")
        for fa in report_json["frame_analysis"]:
            lines.append(
                f"| {fa.get('frame_index', '?')} "
                f"| {fa.get('verdict', '?').upper()} "
                f"| {fa.get('confidence', 0):.0%} |"
            )
        lines.append("")
    lines.append("## Recommendations")
    for rec in report_json.get("recommendations", []):
        lines.append(f"- {rec}")
    lines.append("")
    return "\n".join(lines)
