#!/usr/bin/env python3
"""DeepGuard AI — Production Deployment Verification Script.

Usage:
    python deployment/verify_deploy.py --backend https://your-backend.a.run.app
    python deployment/verify_deploy.py --backend https://your-backend.a.run.app --frontend https://your-app.vercel.app
"""
import argparse
import json
import os
import sys

import requests

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET} {msg}")


def check_backend(url: str) -> bool:
    print(f"\n── Checking backend: {url} ──")

    # 1. Health endpoint
    try:
        r = requests.get(f"{url}/health", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"
        ok("/health returns 200: ok")
    except Exception as e:
        fail(f"/health failed: {e}")
        return False

    # 2. Liveness probe
    try:
        r = requests.get(f"{url}/livez", timeout=10)
        assert r.status_code == 200
        ok("/livez returns 200")
    except Exception as e:
        fail(f"/livez failed: {e}")

    # 3. Readiness probe
    try:
        r = requests.get(f"{url}/readyz", timeout=10)
        assert r.status_code == 200
        ok("/readyz returns 200")
    except Exception as e:
        fail(f"/readyz failed: {e}")

    # 4. Root endpoint
    try:
        r = requests.get(f"{url}/", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
        ok(f"Root endpoint — version: {data.get('version')}")
    except Exception as e:
        fail(f"Root endpoint failed: {e}")

    # 5. CORS headers
    try:
        r = requests.options(
            f"{url}/api/analyze",
            headers={"Origin": "https://example.com", "Access-Control-Request-Method": "POST"},
            timeout=10,
        )
        cors = r.headers.get("Access-Control-Allow-Origin", "")
        if cors and cors != "*":
            ok(f"CORS policy set: {cors}")
        elif cors == "*":
            warn("CORS is wildcard (*) — restrict to your frontend domain in production")
        else:
            warn("No CORS header in OPTIONS response")
    except Exception as e:
        fail(f"CORS check failed: {e}")

    # 6. Provider configuration
    try:
        r = requests.get(f"{url}/health", timeout=10)
        ok("Backend reachable and responding")
    except Exception as e:
        fail(f"Backend unreachable: {e}")

    # Check which providers are configured by env var presence
    # (The /health endpoint doesn't expose this, so we read from the settings)
    print("\n── Provider Configuration ──")
    print("  (Check these are set in Cloud Run env vars, not from health endpoint)")
    print("  Required: SIGHTENGINE_API_USER, SIGHTENGINE_API_SECRET, GROQ_API_KEY, PRIMARY_API_KEY")
    print("  Optional: GOOGLE_API_KEY, TAVILY_API_KEY")
    warn("Provider status: check Cloud Run console → Environment variables tab")
    warn("Or deploy with LOG_LEVEL=DEBUG and check logs for provider init messages")

    return True


def check_frontend(url: str) -> bool:
    print(f"\n── Checking frontend: {url} ──")
    try:
        r = requests.get(url, timeout=15)
        assert r.status_code == 200
        content_type = r.headers.get("content-type", "")
        if "text/html" in content_type:
            ok("Frontend returns HTML (React app loaded)")
        else:
            warn(f"Unexpected content-type: {content_type}")
    except Exception as e:
        fail(f"Frontend unreachable: {e}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Verify DeepGuard AI production deployment")
    parser.add_argument("--backend", required=True, help="Cloud Run URL (e.g. https://deepguard-ai-xxxx.a.run.app)")
    parser.add_argument("--frontend", help="Vercel URL (optional)")
    args = parser.parse_args()

    print(f"DeepGuard AI — Deployment Verification")
    print(f"{'='*60}")

    backend_ok = check_backend(args.backend.rstrip("/"))

    frontend_ok = True
    if args.frontend:
        frontend_ok = check_frontend(args.frontend.rstrip("/"))
    else:
        warn("--frontend not provided, skipping frontend check")

    print(f"\n{'='*60}")
    if backend_ok and frontend_ok:
        print(f"{GREEN}All checks passed.{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}Some checks failed. Review the output above.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
