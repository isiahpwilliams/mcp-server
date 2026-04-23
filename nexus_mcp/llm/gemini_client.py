from __future__ import annotations

import os

from google import genai


def generate_replacement_symbol_code(prompt: str) -> str:
    """
    Generate replacement symbol code using Gemini.

    Requires `GEMINI_API_KEY` in the environment.
    Uses `GEMINI_MODEL` for model selection.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable.")

    model = os.getenv("GEMINI_MODEL")
    if not model:
        raise RuntimeError("Missing GEMINI_MODEL environment variable.")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents=prompt)
    text = getattr(response, "text", None)
    if not text or not str(text).strip():
        raise RuntimeError("Gemini returned an empty response.")
    return str(text).strip()

