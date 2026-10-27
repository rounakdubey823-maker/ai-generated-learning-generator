"""
OpenAI provider implementation.

Uses the official openai Python SDK with JSON-mode enabled where available.
"""

from __future__ import annotations

import logging

from ai_module.providers.base import BaseProvider, ProviderError
from ai_module.utils import redact_secrets

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    name    = "openai"
    is_mock = False

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("OpenAI API key must not be empty.")
        self.api_key = api_key
        self.model   = model

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.api_key)

            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system",  "content": system_prompt},
                    {"role": "user",    "content": user_prompt},
                ],
                # Request JSON output — supported on gpt-4o / gpt-4o-mini / gpt-3.5-turbo-1106+
                response_format={"type": "json_object"},
                temperature=0.4,   # lower = more deterministic JSON structure
                max_tokens=2048,
            )

            raw = response.choices[0].message.content
            if not raw:
                raise ProviderError(
                    "OpenAI returned an empty response.", provider=self.name
                )
            return raw.strip()

        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                redact_secrets(f"OpenAI API call failed: {exc}", self.api_key),
                provider=self.name,
                cause=exc,
            ) from exc
