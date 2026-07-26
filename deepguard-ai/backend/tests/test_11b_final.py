"""Test 11B with response_format + instruction in user msg + real image."""
import base64, json, os
import httpx
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("PRIMARY_API_KEY", "")
ENDPOINT = os.getenv("PRIMARY_ENDPOINT", "https://integrate.api.nvidia.com/v1")
IMAGE_PATH = "D:/adk-workspace/deepguard-ai/.venv/images/imagehash.png"

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
    "Output ONLY the JSON object -- no extra text, no markdown.\n\n"
    "Analyze this image for AI-generated or manipulated content."
)
USER = "Analyze this image for AI-generated or manipulated content."

async def run():
    async with httpx.AsyncClient(timeout=120) as client:
        model = "meta/llama-3.2-11b-vision-instruct"
        
        # Test: response_format + instruction in user msg
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": INSTRUCTION},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    ],
                },
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 1024,
        }
        try:
            r = await client.post(
                f"{ENDPOINT}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json=payload,
            )
            print(f"--- response_format + instruction in user msg ---")
            print(f"HTTP {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                finish = data["choices"][0].get("finish_reason", "")
                print(f"finish: {finish}")
                print(f"RAW ({len(content)} chars):")
                print(content)
                try:
                    parsed = json.loads(content)
                    print(f"\n-> JSON OK: {json.dumps(parsed, indent=2)[:600]}")
                except json.JSONDecodeError as e:
                    print(f"\n-> NOT JSON: {e}")
                    # Try regex
                    import re
                    m = re.search(r"\{[\s\S]*\}", content)
                    if m:
                        try:
                            parsed = json.loads(m.group())
                            print(f"Regex extraction: {json.dumps(parsed, indent=2)[:600]}")
                        except:
                            pass
            else:
                print(f"Body: {r.text[:300]}")
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
