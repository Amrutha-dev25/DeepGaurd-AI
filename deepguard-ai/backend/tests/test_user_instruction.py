"""Test: full instruction in user message, no system message, no response_format.

This replicates the approach of putting instruction in user text.
"""

import base64, json, os
import httpx
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("PRIMARY_API_KEY", "")
ENDPOINT = os.getenv("PRIMARY_ENDPOINT", "https://integrate.api.nvidia.com/v1")
IMAGE_PATH = "D:/adk-workspace/deepguard-ai/backend/tests/test_diag.png"

with open(IMAGE_PATH, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode("utf-8")

FULL_INSTRUCTION = (
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

combined_prompt = FULL_INSTRUCTION + "\n\n" + USER_TEXT

async def run():
    async with httpx.AsyncClient(timeout=120) as client:
        for model in [
            "meta/llama-3.2-11b-vision-instruct",
            "meta/llama-3.2-90b-vision-instruct",
        ]:
            print(f"\n{'='*60}")
            print(f"MODEL: {model}")
            print(f"{'='*60}")

            for rf in [None, {"type": "json_object"}]:
                label = f"response_format={rf}"
                payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": combined_prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                            ],
                        },
                    ],
                    "max_tokens": 1024,
                }
                if rf:
                    payload["response_format"] = rf

                try:
                    r = await client.post(
                        f"{ENDPOINT}/chat/completions",
                        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                        json=payload,
                    )
                    if r.status_code == 200:
                        data = r.json()
                        content = data["choices"][0]["message"]["content"]
                        finish = data["choices"][0].get("finish_reason", "unknown")
                        print(f"\n--- {label} (finish={finish}) ---")
                        print(f"content ({len(content)} chars): {content[:400]}")
                        try:
                            parsed = json.loads(content)
                            print(f"-> JSON OK: {json.dumps(parsed)[:200]}")
                        except json.JSONDecodeError as e:
                            print(f"-> JSON FAILED: {e}")
                    else:
                        print(f"\n--- {label} ---")
                        print(f"HTTP {r.status_code}: {r.text[:300]}")
                except Exception as e:
                    print(f"\n--- {label} ---")
                    print(f"ERROR: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
