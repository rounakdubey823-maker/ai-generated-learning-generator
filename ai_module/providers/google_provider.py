"""
Google Gemini provider implementation.

Uses google-generativeai SDK with generation_config for JSON output.
"""

from __future__ import annotations

import logging

from ai_module.providers.base import BaseProvider, ProviderError
from ai_module.utils import redact_secrets

logger = logging.getLogger(__name__)


class GoogleProvider(BaseProvider):
    name    = "google"
    is_mock = False

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("Google API key must not be empty.")
        self.api_key = api_key
        self.model   = model

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            import google.generativeai as genai
            from google.generativeai.types import GenerationConfig

            genai.configure(api_key=self.api_key)

            model_instance = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_prompt,
                generation_config=GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.4,
                    max_output_tokens=2048,
                ),
            )

            response = await model_instance.generate_content_async(user_prompt)
            raw = response.text
            if not raw:
                raise ProviderError(
                    "Google Gemini returned an empty response.", provider=self.name
                )
            return raw.strip()

        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                redact_secrets(f"Google Gemini API call failed: {exc}", self.api_key),
                provider=self.name,
                cause=exc,
            ) from exc
