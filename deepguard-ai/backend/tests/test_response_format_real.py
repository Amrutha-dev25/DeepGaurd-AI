"""Test response_format with system message + real image."""
import base64, json, os
import httpx
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("PRIMARY_API_KEY", "")
ENDPOINT = os.getenv("PRIMARY_ENDPOINT", "https://integrate.api.nvidia.com/v1")
IMAGE_PATH = "D:/adk-workspace/deepguard-ai/.venv/images/imagehash.png"

with open(IMAGE_PATH, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode("utf-8")

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
            
            # Test A: system msg + response_format
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
                "response_format": {"type": "json_object"},
                "max_tokens": 1024,
            }
            try:
                r = await client.post(
                    f"{ENDPOINT}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json=payload,
                )
                print(f"--- response_format + system msg ---")
                print(f"HTTP {r.status_code}")
                if r.status_code == 200:
                    data = r.json()
                    content = data["choices"][0]["message"]["content"]
                    finish = data["choices"][0].get("finish_reason", "")
                    print(f"finish: {finish}")
                    print(f"RAW ({len(content)} chars): {content[:400]}")
                    try:
                        parsed = json.loads(content)
                        print(f"-> JSON OK: {json.dumps(parsed, indent=2)[:600]}")
                    except json.JSONDecodeError:
                        print("-> NOT JSON")
                else:
                    print(f"Body: {r.text[:300]}")
            except Exception as e:
                print(f"ERROR: {e}")

            # Test B: NO system msg, instruction in user msg
            COMBINED = SYSTEM + "\n\n" + USER
            payload2 = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": COMBINED},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        ],
                    },
                ],
                "max_tokens": 1024,
            }
            try:
                r2 = await client.post(
                    f"{ENDPOINT}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json=payload2,
                )
                print(f"\n--- instruction in user msg, no response_format ---")
                print(f"HTTP {r2.status_code}")
                if r2.status_code == 200:
                    data2 = r2.json()
                    content2 = data2["choices"][0]["message"]["content"]
                    finish2 = data2["choices"][0].get("finish_reason", "")
                    print(f"finish: {finish2}")
                    print(f"RAW ({len(content2)} chars): {content2[:400]}")
                    try:
                        parsed2 = json.loads(content2)
                        print(f"-> JSON OK: {json.dumps(parsed2, indent=2)[:600]}")
                    except json.JSONDecodeError:
                        print("-> NOT JSON")
                else:
                    print(f"Body: {r2.text[:300]}")
            except Exception as e:
                print(f"ERROR: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
