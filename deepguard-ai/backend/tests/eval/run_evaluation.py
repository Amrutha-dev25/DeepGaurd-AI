"""
run_evaluation.py — Walk eval_dataset, POST each file to /api/analyze,
compare verdict against ground-truth folder, produce results table +
confusion matrix + per-type breakdown + degraded-mode accuracy.

No automatic retries — each file is attempted exactly once.
On HTTP errors the response body is logged and the script moves on.

Usage:
    python backend/tests/eval/run_evaluation.py [--url URL] [--output FILE] [--dry-run]

Defaults:
    --url       http://localhost:8000
    --output    eval_dataset/results.md

Example:
    python backend/tests/eval/run_evaluation.py --dry-run
    python backend/tests/eval/run_evaluation.py --url http://localhost:8000
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_VIDEOS = {".mp4", ".webm", ".mov", ".avi"}

EVAL_ROOT = Path(__file__).resolve().parents[3] / "eval_dataset"
assert EVAL_ROOT.is_dir(), f"eval_dataset not found at {EVAL_ROOT}"
DEFAULT_OUTPUT = str(Path(__file__).resolve().parents[3] / "eval_dataset" / "results.md")


# ── helpers ──────────────────────────────────────────────────────────────

def _classify(file: Path) -> str:
    """Return the ground-truth label based on parent folder name."""
    return file.parent.name  # "real" or "fake"


def _media_type(file: Path) -> str:
    return "video" if file.suffix.lower() in SUPPORTED_VIDEOS else "image"


def _format_result(r: dict) -> str:
    """Normalise verdict to lower‑case real/fake/inconclusive."""
    v = (r.get("verdict") or "").strip().lower()
    if v in ("real", "authentic", "authentic image"):
        return "real"
    if v in ("fake", "manipulated", "ai-generated", "ai_generated"):
        return "fake"
    return v or "unknown"


def _call_api(url: str, file_path: Path) -> dict:
    """POST file to /api/analyze.  Exactly one attempt — never retry."""
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f)}
        resp = requests.post(f"{url}/api/analyze", files=files, timeout=300)
    # On HTTP error, include the response body in the exception
    if not resp.ok:
        body_preview = resp.text[:500]
        raise RuntimeError(
            f"HTTP {resp.status_code} {resp.reason}: {body_preview}"
        )
    body = resp.json()
    return body


# ── scoring ──────────────────────────────────────────────────────────────

def compute_confusion_matrix(results: list[dict]) -> dict:
    labels = ["real", "fake"]
    matrix = {t: {p: 0 for p in labels} for t in labels}
    for r in results:
        gt = r["ground_truth"]
        pred = r["verdict"]
        if gt in labels and pred in labels:
            matrix[gt][pred] += 1
    return matrix


def accuracy(results: list[dict]) -> float:
    total = len(results) or 1
    correct = sum(1 for r in results if r["passed"])
    return correct / total


# ── main ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="DeepGuard AI evaluation runner")
    parser.add_argument("--url", default="http://localhost:8000", help="Backend API base URL (default: http://localhost:8000)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output markdown file path")
    parser.add_argument("--dry-run", action="store_true", help="List files and API endpoint without making requests")
    args = parser.parse_args()

    url = args.url.rstrip("/")
    output_path = Path(args.output)

    # ── collect files ──
    candidates = []
    for subdir in ("images", "videos"):
        for gt_dir in ("real", "fake"):
            folder = EVAL_ROOT / subdir / gt_dir
            if not folder.is_dir():
                continue
            for f in sorted(folder.iterdir()):
                if f.name.startswith(".") or not f.is_file():
                    continue
                ext = f.suffix.lower()
                if ext in SUPPORTED_IMAGES | SUPPORTED_VIDEOS:
                    candidates.append(f)

    if not candidates:
        print("No eval files found. Add samples to eval_dataset/.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(candidates)} file(s) to evaluate against {url}/api/analyze\n")

    # ── dry-run: list files and stop ──
    if args.dry_run:
        print("DRY RUN — no requests will be made.\n")
        print(f"  Backend URL: {url}/api/analyze")
        print(f"  Dataset root: {EVAL_ROOT}")
        print(f"  Output file: {output_path}\n")
        for subdir in ("images", "videos"):
            for gt_dir in ("real", "fake"):
                folder = EVAL_ROOT / subdir / gt_dir
                files_in_folder = [f for f in candidates if f.parent == folder]
                if files_in_folder:
                    print(f"  {subdir}/{gt_dir}/ ({len(files_in_folder)} files):")
                    for f in files_in_folder:
                        print(f"    {f.name}")
        print(f"\n  Total: {len(candidates)} file(s)")
        print(f"  POST endpoint: {url}/api/analyze")
        print(f"  Timeout per request: 300s")
        print(f"  Retries: NONE — each file attempted exactly once")
        return

    # ── run ──
    results: list[dict] = []
    for i, fp in enumerate(candidates, 1):
        gt = _classify(fp)
        mtype = _media_type(fp)
        print(f"  [{i}/{len(candidates)}] {mtype}/{gt}: {fp.name} ... ", end="", flush=True)
        try:
            t0 = time.perf_counter()
            api_resp = _call_api(url, fp)
            elapsed = time.perf_counter() - t0

            # API response has top-level verdict/confidence,
            # pipeline.model_used, pipeline.degraded, investigation_trace
            verdict = _format_result(api_resp)
            confidence = api_resp.get("confidence")
            pipeline_info = api_resp.get("pipeline", {})
            model = pipeline_info.get("model_used") or api_resp.get("model_used", "?")
            degraded = pipeline_info.get("degraded", False) or api_resp.get("degraded", False)

            # Investigation trace — supervisor loop details
            trace = api_resp.get("investigation_trace", {}) or {}
            rounds_completed = trace.get("rounds_completed", 0)
            converged = trace.get("converged", False)
            # Determine final trusted capability/provider
            evidence_table = trace.get("evidence_table", [])
            if rounds_completed == 0 or not evidence_table:
                final_trusted = "sightengine-direct"
            else:
                last_entry = evidence_table[-1]
                final_trusted = last_entry.get("capability", "unknown")

            passed = verdict == gt
            results.append(
                dict(
                    filename=fp.name,
                    media_type=mtype,
                    ground_truth=gt,
                    verdict=verdict,
                    confidence=round(confidence, 4) if confidence is not None else None,
                    model_used=model,
                    degraded=bool(degraded),
                    rounds=rounds_completed,
                    final_trusted=final_trusted,
                    converged=converged,
                    passed=passed,
                    latency_seconds=round(elapsed, 2),
                )
            )
            status = "PASS" if passed else "FAIL"
            trace_info = f"rounds={rounds_completed} trusted={final_trusted}"
            print(f"{verdict} ({confidence}) [{model}] {elapsed:.1f}s {status} ({trace_info})")

        except requests.exceptions.Timeout:
            results.append(
                dict(
                    filename=fp.name,
                    media_type=mtype,
                    ground_truth=gt,
                    verdict="timeout",
                    confidence=None,
                    model_used=None,
                    degraded=None,
                    rounds=0,
                    final_trusted="error",
                    converged=False,
                    passed=False,
                    latency_seconds=None,
                )
            )
            print("TIMEOUT")
        except Exception as exc:
            results.append(
                dict(
                    filename=fp.name,
                    media_type=mtype,
                    ground_truth=gt,
                    verdict="error",
                    confidence=None,
                    model_used=str(exc),
                    degraded=None,
                    rounds=0,
                    final_trusted="error",
                    converged=False,
                    passed=False,
                    latency_seconds=None,
                )
            )
            print(f"ERROR: {exc}")

    # ── write report ──
    report = _build_report(results, url)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to {output_path}")

    # ── console summary ──
    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    pct = (passed / total * 100) if total else 0
    print(f"  TOTAL: {total}  PASS: {passed}/{total} ({pct:.1f}%)")

    matrix = compute_confusion_matrix(results)
    print("\n  Confusion Matrix:")
    print(f"              Pred real    Pred fake")
    for gt in ("real", "fake"):
        row = matrix.get(gt, {})
        print(f"  GT {gt:>5s}    {row.get('real', 0):>5d}      {row.get('fake', 0):>5d}")

    # per-type
    for mtype in ("image", "video"):
        subset = [r for r in results if r["media_type"] == mtype]
        if subset:
            sp = sum(1 for r in subset if r["passed"])
            print(f"\n  {mtype.title()}s: {sp}/{len(subset)} ({sp/len(subset)*100:.1f}%)")

    # degraded vs full
    degraded_set = [r for r in results if r.get("degraded")]
    full_set = [r for r in results if not r.get("degraded")]
    if degraded_set:
        dp = sum(1 for r in degraded_set if r["passed"])
        print(f"  Degraded mode: {dp}/{len(degraded_set)} ({dp/len(degraded_set)*100:.1f}%)")
    if full_set:
        fp_full = sum(1 for r in full_set if r["passed"])
        print(f"  Full pipeline:  {fp_full}/{len(full_set)} ({fp_full/len(full_set)*100:.1f}%)")

    print("=" * 60)


def _build_report(results: list[dict], url: str) -> str:
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    pct = (passed / total * 100) if total else 0

    lines = ["# Evaluation Results\n"]
    lines.append(f"- **Backend URL**: `{url}`")
    lines.append(f"- **Date**: `{time.strftime('%Y-%m-%d %H:%M:%S')}`")
    lines.append(f"- **Total samples**: {total}")
    lines.append(f"- **Passed**: {passed}/{total} ({pct:.1f}%)")
    lines.append("")

    # confusion matrix
    matrix = compute_confusion_matrix(results)
    lines.append("## Confusion Matrix\n")
    lines.append(f"| GT ↓ / Pred → | real | fake |")
    lines.append(f"|---------------|------|------|")
    for gt in ("real", "fake"):
        row = matrix.get(gt, {})
        lines.append(f"| {gt:>13s} | {row.get('real', 0):>4d} | {row.get('fake', 0):>4d} |")
    lines.append("")

    # per-type breakdown
    for mtype in ("image", "video"):
        subset = [r for r in results if r["media_type"] == mtype]
        if not subset:
            continue
        sp = sum(1 for r in subset if r["passed"])
        lines.append(f"### {mtype.title()} Performance\n")
        lines.append(f"- **Samples**: {len(subset)}")
        lines.append(f"- **Passed**: {sp}/{len(subset)} ({sp/len(subset)*100:.1f}%)")
        lines.append("")

    # degraded vs full
    degraded_set = [r for r in results if r.get("degraded")]
    full_set = [r for r in results if not r.get("degraded")]
    if degraded_set:
        dp = sum(1 for r in degraded_set if r["passed"])
        lines.append("### Degraded vs Full Pipeline\n")
        lines.append(f"- **Degraded**: {dp}/{len(degraded_set)} ({dp/len(degraded_set)*100:.1f}%)")
        if full_set:
            fp_full = sum(1 for r in full_set if r["passed"])
            lines.append(f"- **Full**: {fp_full}/{len(full_set)} ({fp_full/len(full_set)*100:.1f}%)")
        lines.append("")

    # per-file table
    lines.append("## Per-File Results\n")
    lines.append(
        "| # | File | Type | GT | Verdict | Confidence | Model | Rounds | Trusted | Converged | Pass | Latency |"
    )
    lines.append(
        "|---|------|------|----|---------|------------|-------|--------|---------|-----------|------|---------|"
    )
    for idx, r in enumerate(results, 1):
        conf_str = f"{r['confidence']:.1%}" if r["confidence"] is not None else "—"
        model_str = r["model_used"] or "—"
        lat_str = f"{r['latency_seconds']}s" if r["latency_seconds"] is not None else "—"
        deg_str = "✓" if r.get("degraded") else ""
        pass_str = "✓" if r["passed"] else "✗"
        rnd_str = str(r.get("rounds", "?"))
        tr_str = r.get("final_trusted", "?")
        cv_str = "✓" if r.get("converged") else "✗"
        lines.append(
            f"| {idx} | {r['filename']} | {r['media_type']} | {r['ground_truth']} "
            f"| {r['verdict']} | {conf_str} | {model_str} | {rnd_str} | {tr_str} | {cv_str} | {pass_str} | {lat_str} |"
        )

    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
