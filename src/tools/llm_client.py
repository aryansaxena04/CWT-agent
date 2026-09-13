"""OpenRouter chat client with a JSON-schema-constrained generation helper.

OpenRouter exposes an OpenAI-compatible API, so we reuse the `openai` SDK
pointed at OpenRouter's base URL rather than pulling in a separate client.
"""

from __future__ import annotations

import json
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from src.config import settings

T = TypeVar("T", bound=BaseModel)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        settings.require("OPENROUTER_API_KEY")
        _client = OpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=settings.OPENROUTER_API_KEY,
            default_headers={
                "HTTP-Referer": "https://github.com/crowdwisdomtrading/video-ads-agent",
                "X-Title": "CrowdWisdomTrading Video Ads Agent",
            },
        )
    return _client


def chat(system: str, user: str, model: str | None = None, temperature: float = 0.7, max_tokens: int = 3000) -> str:
    client = _get_client()
    completion = client.chat.completions.create(
        model=model or settings.OPENROUTER_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return completion.choices[0].message.content or ""


def generate_structured(
    system: str,
    user: str,
    schema: type[T],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 3000,
) -> T:
    """Ask the model for JSON matching `schema` and parse+validate the result.

    Retries once with the validation error fed back to the model if the first
    response doesn't parse, since even instructed models occasionally wrap
    JSON in prose or emit a schema-invalid field.
    """
    schema_hint = json.dumps(schema.model_json_schema(), indent=2)
    full_system = (
        f"{system}\n\n"
        "Respond with ONLY a single JSON object matching this JSON Schema. "
        "No markdown fences, no commentary.\n\n"
        f"{schema_hint}"
    )

    raw = chat(full_system, user, model=model, temperature=temperature, max_tokens=max_tokens)
    try:
        return schema.model_validate_json(_strip_fences(raw))
    except Exception as first_error:
        retry_user = (
            f"{user}\n\n"
            f"Your previous response failed validation with error:\n{first_error}\n\n"
            f"Previous response was:\n{raw}\n\n"
            "Return corrected JSON only."
        )
        raw_retry = chat(full_system, retry_user, model=model, temperature=temperature, max_tokens=max_tokens)
        return schema.model_validate_json(_strip_fences(raw_retry))


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()
