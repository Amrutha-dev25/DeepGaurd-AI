"""Test: send instruction as system message vs user message, to diagnose ADK gap."""

import base64
import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("PRIMARY_API_KEY", "")
ENDPOINT = os.getenv("PRIMARY_ENDPOINT", "https://integrate.api.nvidia.com/v1")
IMAGE_PATH = "D:/adk-workspace/deepguard-ai/backend/tests/test_diag.png"

with open(IMAGE_PATH, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode("utf-8")

INSTRUCTION = (
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
    "- Output ONLY the JSON object -- no extra text, no markdown."
)

USER_TEXT = (
    "Analyze this image for AI-generated or manipulated content.\n"
    "File type: unknown\n"
    "Face present: False\n"
    "Filename: backend\tests\test_diag.png\n"
)

models_to_test = [
    "meta/llama-3.2-11b-vision-instruct",
    "meta/llama-3.2-90b-vision-instruct",
]

async def run():
    async with httpx.AsyncClient(timeout=60) as client:
        for model in models_to_test:
            print(f"\n{'=' * 70}")
            print(f"MODEL: {model}")
            print(f"{'=' * 70}")

            # ── Variant A: instruction as system message ─────────
            print(f"\n--- A: Instruction as SYSTEM message ---")
            payload_a = {
                "model": model,
                "messages": [
                    {"role": "system", "content": INSTRUCTION},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": USER_TEXT},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        ],
                    },
                ],
                "max_tokens": 512,
            }
            r = await client.post(
                f"{ENDPOINT}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json=payload_a,
            )
            content_a = r.json()["choices"][0]["message"]["content"] if r.status_code == 200 else f"ERROR {r.status_code}: {r.text[:200]}"
            print(f"RAW ({len(str(content_a))} chars): {content_a[:300]}")
            try:
                json.loads(content_a)
                print("-> JSON PARSE: OK")
            except (json.JSONDecodeError, TypeError) as e:
                print(f"-> JSON PARSE: FAILED: {e}")

            # ── Variant B: instruction as USER message (first text part) ──
            print(f"\n--- B: Instruction as USER message (prepended to text) ---")
            payload_b = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": INSTRUCTION + "\n\n" + USER_TEXT},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        ],
                    },
                ],
                "max_tokens": 512,
            }
            r = await client.post(
                f"{ENDPOINT}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json=payload_b,
            )
            content_b = r.json()["choices"][0]["message"]["content"] if r.status_code == 200 else f"ERROR {r.status_code}: {r.text[:200]}"
            print(f"RAW ({len(str(content_b))} chars): {content_b[:300]}")
            try:
                json.loads(content_b)
                print("-> JSON PARSE: OK")
            except (json.JSONDecodeError, TypeError) as e:
                print(f"-> JSON PARSE: FAILED: {e}")

            # ── Variant C: response_format json_object ─────────────────
            print(f"\n--- C: response_format = json_object (user msg) ---")
            payload_c = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": INSTRUCTION + "\n\n" + USER_TEXT},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        ],
                    },
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 512,
            }
            r = await client.post(
                f"{ENDPOINT}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json=payload_c,
            )
            if r.status_code == 200:
                content_c = r.json()["choices"][0]["message"]["content"]
                print(f"RAW ({len(content_c)} chars): {content_c[:300]}")
                try:
                    parsed = json.loads(content_c)
                    print(f"-> JSON PARSE: OK -> {json.dumps(parsed, indent=2)[:200]}")
                except json.JSONDecodeError as e:
                    print(f"-> JSON PARSE: FAILED: {e}")
            else:
                print(f"HTTP {r.status_code}: {r.text[:300]}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
