import os
import httpx
import time
import json
from typing import Optional

OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://172.18.192.1:11434")
FAST_MODEL  = "phi3"
DEEP_MODEL  = "deepseek-r1:7b"
MAX_RETRIES = 2
RETRY_DELAY = 3


def ask_fast(prompt: str) -> str:
    """Phi3 — fast, free-text response"""
    return _ask_ollama(prompt, FAST_MODEL, json_mode=False)


def ask_deep(prompt: str) -> str:
    """DeepSeek-R1 — deep reasoning, free-text"""
    return _ask_ollama(prompt, DEEP_MODEL, json_mode=False)


def ask_structured(prompt: str, schema_example: dict, model: str = FAST_MODEL) -> dict:
    """
    Force JSON output from LLM.
    schema_example shows the LLM exactly what fields to return.
    Falls back to safe defaults if parsing fails — never crashes.
    """
    json_prompt = f"""{prompt}

You MUST respond with valid JSON only. No explanation, no markdown, no code blocks.
Return exactly this structure:
{json.dumps(schema_example, indent=2)}"""

    raw = _ask_ollama(json_prompt, model, json_mode=True)

    # attempt 1 — direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # attempt 2 — extract JSON from text (LLM sometimes adds preamble)
    try:
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(raw[start:end])
    except json.JSONDecodeError:
        pass

    # attempt 3 — fallback to safe defaults from schema_example
    print(f"[LLM] JSON parse failed — using safe defaults. Raw: {raw[:100]}")
    return schema_example.copy()


def _ask_ollama(prompt: str, model: str, json_mode: bool = False) -> str:
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            payload = {
                "model":  model,
                "prompt": prompt,
                "stream": False,
            }
            if json_mode:
                payload["format"] = "json"  # Ollama native JSON mode

            response = httpx.post(
                f"{OLLAMA_URL}/api/generate",
                json=payload,
                timeout=180,
            )

            if response.status_code != 200:
                raise ValueError(f"HTTP {response.status_code}: {response.text[:100]}")

            ct = response.headers.get("content-type", "")
            if "application/json" not in ct:
                raise ValueError(f"Unexpected content-type: {ct}")

            raw = response.json().get("response", "").strip()

            if not raw:
                raise ValueError("Empty response from LLM")

            # strip DeepSeek <think> blocks
            if "<think>" in raw and "</think>" in raw:
                think_start = raw.find("<think>")
                think_end   = raw.find("</think>") + len("</think>")
                thinking    = raw[think_start + 7: think_end - 8].strip()
                answer      = raw[think_end:].strip()
                if thinking:
                    print(f"\n[LLM] {model} thinking:\n{thinking[:400]}...")
                return answer if answer else raw

            return raw

        except Exception as e:
            last_error = str(e)
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY * (attempt + 1)
                print(f"[LLM] Attempt {attempt+1} failed ({last_error}) — retrying in {wait}s")
                time.sleep(wait)

    raise RuntimeError(
        f"LLM {model} unavailable after {MAX_RETRIES+1} attempts: {last_error}"
    )
