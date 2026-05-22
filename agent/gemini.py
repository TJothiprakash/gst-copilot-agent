import httpx
import json
import base64
import os
from typing import Optional
from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
BASE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# ── Langfuse client ───────────────────────────────────────────────────────────
langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)


# ── Send text prompt to Gemini ────────────────────────────────────────────────
async def call_gemini(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.0,
    trace_name: str = "gemini-call",
) -> str:
    contents = []
    if system_prompt:
        contents.append({
            "role": "user",
            "parts": [{"text": f"[SYSTEM]\n{system_prompt}\n[/SYSTEM]\n\n{prompt}"}]
        })
    else:
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 8192,
        }
    }

    # ── Langfuse trace ────────────────────────────────────────────────────────
    trace = langfuse.trace(name=trace_name)
    generation = trace.generation(
        name=trace_name,
        model=GEMINI_MODEL,
        input=prompt,
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}?key={GEMINI_API_KEY}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()

        result = data["candidates"][0]["content"]["parts"][0]["text"]

        # ── Log success to Langfuse ───────────────────────────────────────────
        generation.end(output=result)
        return result

    except Exception as e:
        generation.end(output=str(e), level="ERROR")
        raise


# ── Send image/PDF to Gemini (multimodal) ─────────────────────────────────────
async def call_gemini_with_file(
    prompt: str,
    file_bytes: bytes,
    mime_type: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.0,
    trace_name: str = "gemini-file-call",
) -> str:
    encoded = base64.b64encode(file_bytes).decode("utf-8")

    parts = []
    if system_prompt:
        parts.append({"text": f"[SYSTEM]\n{system_prompt}\n[/SYSTEM]\n\n{prompt}"})
    else:
        parts.append({"text": prompt})

    parts.append({
        "inline_data": {
            "mime_type": mime_type,
            "data": encoded
        }
    })

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 8192,
        }
    }

    # ── Langfuse trace ────────────────────────────────────────────────────────
    trace = langfuse.trace(name=trace_name)
    generation = trace.generation(
        name=trace_name,
        model=GEMINI_MODEL,
        input=f"[FILE: {mime_type}] {prompt[:200]}",
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}?key={GEMINI_API_KEY}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()

        result = data["candidates"][0]["content"]["parts"][0]["text"]

        # ── Log success to Langfuse ───────────────────────────────────────────
        generation.end(output=result)
        return result

    except Exception as e:
        generation.end(output=str(e), level="ERROR")
        raise


# ── Parse JSON from Gemini response ───────────────────────────────────────────
def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw: {text}")