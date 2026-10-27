"""
AI Service — wraps OpenAI and Google Generative AI SDKs.

Raises ServiceUnavailableError when no provider is configured so the
API returns a clean 503 instead of silently returning fake content.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.core.config import settings
from app.core.errors import ServiceUnavailableError

logger = logging.getLogger(__name__)

# ── Prompt builder ─────────────────────────────────────────────────────────────

_PROMPT_TEMPLATE = """
You are an expert educator. Generate a {content_type} for the following topic.

Topic: {topic}
Difficulty: {difficulty}
Content type: {content_type}

Guidelines:
- For a *lesson*: explain the concept clearly with examples.
- For a *quiz*: provide 5 multiple-choice questions with answers.
- For a *summary*: write a concise 3-5 sentence overview.

Respond with only the educational content — no preambles.
""".strip()


def _build_prompt(topic: str, difficulty: str, content_type: str) -> str:
    return _PROMPT_TEMPLATE.format(
        topic=topic, difficulty=difficulty, content_type=content_type
    )


# ── Provider implementations ───────────────────────────────────────────────────

async def _call_openai(prompt: str) -> Dict[str, Any]:
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        content = response.choices[0].message.content or ""
        return {"content": content, "provider": "openai", "model": settings.OPENAI_MODEL}
    except Exception as exc:
        logger.error("OpenAI call failed: %s", exc)
        raise


async def _call_google(prompt: str) -> Dict[str, Any]:
    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel(settings.GOOGLE_MODEL)
        response = await model.generate_content_async(prompt)
        return {
            "content": response.text,
            "provider": "google",
            "model": settings.GOOGLE_MODEL,
        }
    except Exception as exc:
        logger.error("Google GenAI call failed: %s", exc)
        raise


# ── Public API ─────────────────────────────────────────────────────────────────

async def generate_learning_content(
    topic: str, difficulty: str = "beginner", content_type: str = "lesson"
) -> Dict[str, Any]:
    """
    Generate learning content using the configured AI provider.

    Raises:
        ServiceUnavailableError: if no AI provider API key is configured.
    """
    prompt = _build_prompt(topic, difficulty, content_type)
    provider = settings.AI_PROVIDER.lower()

    if provider == "openai" and settings.OPENAI_API_KEY:
        return await _call_openai(prompt)

    if provider == "google" and settings.GOOGLE_API_KEY:
        return await _call_google(prompt)

    raise ServiceUnavailableError(
        message="No AI provider is configured. Set OPENAI_API_KEY or GOOGLE_API_KEY in .env.",
        detail={"configured_provider": settings.AI_PROVIDER, "hint": "See .env.example"},
    )
