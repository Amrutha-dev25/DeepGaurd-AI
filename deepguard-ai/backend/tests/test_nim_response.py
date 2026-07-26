"""Test script: send the real image to NVIDIA NIM, capture RAW response."""

import base64
import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("PRIMARY_MODEL", "meta/llama-3.2-11b-vision-instruct")
API_KEY = os.getenv("PRIMARY_API_KEY", "")
ENDPOINT = os.getenv("PRIMARY_ENDPOINT", "https://integrate.api.nvidia.com/v1")
IMAGE_PATH = "D:/adk-workspace/deepguard-ai/backend/tests/test_diag.png"

# Read & encode the test image
with open(IMAGE_PATH, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode("utf-8")
mime = "image/png"

# ── Test 1: Standard request, no structured output ─────────────────
print("=" * 70)
print("TEST 1: Standard request (no response_format)")
print("=" * 70)

payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "You are the Analysis Agent for a deepfake forensic system.\n\n"
                        "Your sole job is to examine the provided media and determine whether it is "
                        "REAL (authentic), FAKE (AI-generated or manipulated), or INCONCLUSIVE.\n\n"
                        "Output a valid JSON object with these keys:\n"
                        "{\n"
                        '  "verdict": "real" | "fake" | "inconclusive",\n'
                        '  "confidence": 0.0-1.0,\n'
                        '  "evidence": "Brief explanation of what led to this verdict",\n'
                        '  "key_indicators": ["list", "of", "specific", "indicators"]\n'
                        "}\n\n"
                        "Rules:\n"
                        "- Your verdict MUST be based on your own analysis of the visual content you receive.\n"
                        '- "fake" means the media appears AI-generated or manipulated.\n'
                        '- "real" means the media appears authentic.\n'
                        '- "inconclusive" only if you truly cannot determine.\n'
                        "- Confidence reflects your certainty (0.0 = none, 1.0 = certain).\n"
                        "- Output ONLY the JSON object -- no extra text, no markdown.\n"
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{img_b64}"},
                },
            ],
        }
    ],
    "max_tokens": 512,
}

async def run():
    async with httpx.AsyncClient(timeout=60) as client:
        # Test 1
        r1 = await client.post(
            f"{ENDPOINT}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json=payload,
        )
        print(f"HTTP status: {r1.status_code}")
        if r1.status_code == 200:
            data = r1.json()
            content = data["choices"][0]["message"]["content"]
            print(f"\nRAW RESPONSE ({len(content)} chars):")
            print("---BEGIN RAW---")
            print(content)
            print("---END RAW---")
            # Try parsing
            try:
                parsed = json.loads(content)
                print(f"\nJSON PARSED OK: {json.dumps(parsed, indent=2)}")
            except json.JSONDecodeError as e:
                print(f"\nJSON PARSE FAILED: {e}")
                # Try regex
                import re
                m = re.search(r"\{[\s\S]*\}", content)
                if m:
                    try:
                        parsed = json.loads(m.group())
                        print(f"Regex extraction + parse: OK -> {json.dumps(parsed, indent=2)}")
                    except json.JSONDecodeError as e2:
                        print(f"Regex extraction + parse FAILED: {e2}")
                else:
                    print("No JSON object found via regex.")
        else:
            print(f"Error body: {r1.text[:500]}")

        # ── Test 2: With response_format json_object ─────────────────
        print("\n" + "=" * 70)
        print("TEST 2: With response_format = json_object")
        print("=" * 70)

        payload2 = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyze this image for AI-generated or manipulated content. "
                                "Return ONLY a JSON object."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{img_b64}"},
                        },
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 512,
        }

        r2 = await client.post(
            f"{ENDPOINT}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json=payload2,
        )
        print(f"HTTP status: {r2.status_code}")
        if r2.status_code == 200:
            data2 = r2.json()
            content2 = data2["choices"][0]["message"]["content"]
            print(f"\nRAW RESPONSE ({len(content2)} chars):")
            print("---BEGIN RAW---")
            print(content2)
            print("---END RAW---")
            try:
                parsed2 = json.loads(content2)
                print(f"\nJSON PARSED OK: {json.dumps(parsed2, indent=2)}")
            except json.JSONDecodeError as e:
                print(f"\nJSON PARSE FAILED: {e}")
        else:
            print(f"Response body: {r2.text[:500]}")

        # ── Test 3: Check model metadata for capabilities ────────────
        print("\n" + "=" * 70)
        print("TEST 3: Model list check")
        print("=" * 70)
        r3 = await client.get(
            f"{ENDPOINT}/models",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        if r3.status_code == 200:
            models = r3.json()
            for m in models.get("data", []):
                mid = m.get("id", "")
                if "llama-3.2-11b" in mid or "llama-3.2-90b" in mid or "cosmos" in mid or "nemotron" in mid or "phi-3" in mid:
                    owned = m.get("owned_by", "")
                    print(f"  {mid}  (owned_by: {owned})")
        else:
            print(f"Error: {r3.status_code} {r3.text[:300]}")

        # ── Test 4: Text-only model (meta/llama-3.1-8b-instruct) with response_format
        print("\n" + "=" * 70)
        print("TEST 4: Text model (llama-3.1-8b) with response_format = json_object")
        print("=" * 70)
        payload4 = {
            "model": "meta/llama-3.1-8b-instruct",
            "messages": [
                {
                    "role": "user",
                    "content": "Return a JSON object with keys: name, version, status. Use example values."
                }
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 128,
        }
        r4 = await client.post(
            f"{ENDPOINT}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json=payload4,
        )
        print(f"HTTP status: {r4.status_code}")
        if r4.status_code == 200:
            data4 = r4.json()
            content4 = data4["choices"][0]["message"]["content"]
            print(f"RAW: {content4}")
            try:
                parsed4 = json.loads(content4)
                print(f"JSON OK: {json.dumps(parsed4)}")
            except json.JSONDecodeError as e:
                print(f"PARSE FAILED: {e}")
        else:
            print(f"Error: {r4.text[:500]}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
