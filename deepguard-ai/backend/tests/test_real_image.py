"""Test with the REAL imagehash.png — system msg only (ADK default)."""
import base64, json, os
import httpx
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("PRIMARY_API_KEY", "")
ENDPOINT = os.getenv("PRIMARY_ENDPOINT", "https://integrate.api.nvidia.com/v1")
IMAGE_PATH = "D:/adk-workspace/deepguard-ai/.venv/images/imagehash.png"

with open(IMAGE_PATH, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode("utf-8")
print(f"Image: {os.path.getsize(IMAGE_PATH)} bytes")

SYSTEM = (
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
    "Output ONLY the JSON object -- no extra text, no markdown."
)
USER = "Analyze this image for AI-generated or manipulated content."

async def run():
    async with httpx.AsyncClient(timeout=120) as client:
        for model in ["meta/llama-3.2-11b-vision-instruct", "meta/llama-3.2-90b-vision-instruct"]:
            print(f"\n{'='*60}")
            print(f"MODEL: {model}")
            
            # ADK default: system msg + user msg (no response_format)
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": USER},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        ],
                    },
                ],
                "max_tokens": 1024,
            }
            try:
                r = await client.post(
                    f"{ENDPOINT}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json=payload,
                )
                print(f"HTTP {r.status_code}")
                if r.status_code == 200:
                    data = r.json()
                    content = data["choices"][0]["message"]["content"]
                    finish = data["choices"][0].get("finish_reason", "")
                    usage = data.get("usage", {})
                    print(f"finish: {finish}, tokens: {usage}")
                    print(f"RAW ({len(content)} chars):")
                    print(repr(content[:500]))
                    try:
                        parsed = json.loads(content)
                        print(f"\n-> JSON OK: {json.dumps(parsed, indent=2)[:600]}")
                    except json.JSONDecodeError:
                        print("\n-> NOT JSON")
                else:
                    print(f"Body: {r.text[:300]}")
            except Exception as e:
                print(f"ERROR: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
