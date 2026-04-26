from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing in your .env file.")

client = Groq(api_key=GROQ_API_KEY)


def _extract_json(text: str) -> dict:
    text = text.strip()

    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        text = text.replace("json", "", 1).strip()

    start_obj = text.find("{")
    end_obj = text.rfind("}")
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        text = text[start_obj:end_obj + 1]

    return json.loads(text)


def call_llm_text(system_prompt: str, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def call_llm_json(system_prompt: str, user_prompt: str) -> dict:
    text = call_llm_text(system_prompt, user_prompt)
    return _extract_json(text)
