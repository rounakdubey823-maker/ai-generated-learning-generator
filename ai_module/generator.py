"""
AI Generator — main orchestrator.

Responsibilities:
  1. Select the correct provider based on config.
  2. Build prompts.
  3. Call the provider with timeout + retry.
  4. Parse and validate the raw JSON response.
  5. Return a typed AIResponse.

This module is the only public API of ai_module that the backend imports.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Type

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ai_module.prompts import get_prompts
from ai_module.providers.base import BaseProvider, ProviderError
from ai_module.schemas import (
    AIRequest,
    AIResponse,
    ContentType,
    LearningLevel,
    NotesContent,
    QuizContent,
    SummaryContent,
)
from ai_module.utils import extract_json_text

logger = logging.getLogger(__name__)

# ── Per content-type validators ────────────────────────────────────────────────

_CONTENT_VALIDATORS: Dict[ContentType, Type[Any]] = {
    ContentType.NOTES:   NotesContent,
    ContentType.SUMMARY: SummaryContent,
    ContentType.QUIZ:    QuizContent,
}


def _validate_content(raw_json: str, content_type: ContentType) -> Dict[str, Any]:
    """
    Parse the raw JSON string and validate it against the expected schema.

    Raises:
        ProviderError: If the JSON is invalid or doesn't match the schema.
    """
    try:
        data = json.loads(extract_json_text(raw_json))
    except json.JSONDecodeError as exc:
        raise ProviderError(
            f"Provider returned invalid JSON: {exc}",
            provider="unknown",
            cause=exc,
        ) from exc

    validator = _CONTENT_VALIDATORS[content_type]
    try:
        validated = validator.model_validate(data)
        return validated.model_dump()
    except Exception as exc:
        raise ProviderError(
            f"Provider response did not match the expected {content_type.value!r} schema: {exc}",
            provider="unknown",
            cause=exc,
        ) from exc


# ── Provider factory ───────────────────────────────────────────────────────────

def _build_provider(
    ai_provider: str,
    openai_key: str,
    openai_model: str,
    google_key: str,
    google_model: str,
    environment: str,
    mock_in_dev: bool,
) -> Optional[BaseProvider]:
    """
    Instantiate and return the appropriate provider.

    Priority:
      1. Use the named provider if its key is set.
      2. Fall back to the other provider if its key is set.
      3. Use MockProvider in development (explicit label) if mock_in_dev=True.
      4. Raise ServiceUnavailableError in production or when mock disabled.
    """
    from ai_module.providers.openai_provider import OpenAIProvider
    from ai_module.providers.google_provider import GoogleProvider
    from ai_module.providers.mock_provider   import MockProvider

    named = ai_provider.lower()

    if named == "openai" and openai_key:
        return OpenAIProvider(api_key=openai_key, model=openai_model)
    if named == "google" and google_key:
        return GoogleProvider(api_key=google_key, model=google_model)

    # Fallback to whichever key is available
    if openai_key:
        return OpenAIProvider(api_key=openai_key, model=openai_model)
    if google_key:
        return GoogleProvider(api_key=google_key, model=google_model)

    # No real key available
    if mock_in_dev and environment.lower() in ("development", "dev", "test"):
        logger.warning(
            "No AI provider API key configured — using MockProvider (development mode only)."
        )
        return MockProvider()

    # Production with no key → hard error (handled by caller)
    return None


# ── Public API ─────────────────────────────────────────────────────────────────

async def generate(request: AIRequest, *, config: Any) -> AIResponse:
    """
    Generate learning content for the given request.

    Args:
        request: Validated AIRequest.
        config:  Settings object (app.core.config.Settings or compatible).

    Returns:
        AIResponse with structured, validated content.

    Raises:
        ServiceUnavailableError: No provider configured and mock disabled/prod.
        ProviderError:           Provider call or response-parsing failure.
    """
    # Lazy import to avoid circular deps when used standalone
    from app.core.errors import ServiceUnavailableError

    provider = _build_provider(
        ai_provider  = config.AI_PROVIDER,
        openai_key   = config.OPENAI_API_KEY,
        openai_model = config.OPENAI_MODEL,
        google_key   = config.GOOGLE_API_KEY,
        google_model = config.GOOGLE_MODEL,
        environment  = config.ENVIRONMENT,
        mock_in_dev  = config.MOCK_AI_IN_DEV,
    )

    if provider is None:
        raise ServiceUnavailableError(
            message=(
                "No AI provider is configured. "
                "Set OPENAI_API_KEY or GOOGLE_API_KEY in your .env file."
            ),
            detail={
                "configured_provider": config.AI_PROVIDER,
                "hint": "Copy .env.example to .env and add your API key.",
            },
        )

    system_prompt, user_prompt = get_prompts(
        topic          = request.topic,
        learning_level = request.learning_level.value,
        language       = request.language,
        content_type   = request.content_type.value,
        source_text    = request.source_text,
    )

    timeout_s   = config.AI_TIMEOUT_SECONDS
    max_retries = config.AI_MAX_RETRIES

    # ── Call with timeout + exponential-backoff retry ──────────────────────────
    try:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(ProviderError),
            stop=stop_after_attempt(max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        ):
            with attempt:
                raw = await asyncio.wait_for(
                    provider.generate(system_prompt, user_prompt),
                    timeout=timeout_s,
                )

    except asyncio.TimeoutError as exc:
        raise ProviderError(
            f"Provider {provider.name!r} timed out after {timeout_s}s.",
            provider=provider.name,
            cause=exc,
        ) from exc

    # ── Validate the structured response ──────────────────────────────────────
    content_dict = _validate_content(raw, request.content_type)

    return AIResponse(
        content    = content_dict,
        provider   = provider.name,
        model      = provider.model,
        is_mock    = provider.is_mock,
    )


# ── Adaptive learning helpers ──────────────────────────────────────────────────

def calculate_next_level(current_level: str, score_percentage: float) -> str:
    """
    Determine the next learning level based on the quiz score percentage.

    Progression rules:
      - score >= 80.0%: promote (Beginner -> Intermediate -> Advanced)
      - score < 50.0%: demote/reinforce (Advanced -> Intermediate -> Beginner)
      - 50.0% <= score < 80.0%: retain current level
      - Beginner cannot go below Beginner
      - Advanced cannot go above Advanced
      - The returned level values match the exact capitalization required by the contract:
        "Beginner", "Intermediate", "Advanced"

    Validation:
      - Raises ValueError if current_level is not a recognized level
      - Raises ValueError if score_percentage is not a valid number between 0.0 and 100.0
    """
    if not isinstance(current_level, str):
        raise ValueError(
            f"Invalid level type: {type(current_level).__name__}. Must be a string."
        )

    lvl = current_level.strip().lower()
    valid_levels = {
        "beginner": "Beginner",
        "intermediate": "Intermediate",
        "advanced": "Advanced",
    }
    if lvl not in valid_levels:
        raise ValueError(
            f"Invalid level: '{current_level}'. Must be one of 'Beginner', 'Intermediate', 'Advanced'."
        )

    # Boolean is a subclass of int in Python; reject explicit booleans
    if isinstance(score_percentage, bool):
        raise ValueError(f"Invalid score percentage: {score_percentage}. Must be a numeric value.")

    try:
        score = float(score_percentage)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid score percentage: {score_percentage}. Must be a numeric value."
        ) from exc

    if score < 0.0 or score > 100.0:
        raise ValueError(
            f"Invalid score percentage: {score_percentage}. Must be between 0.0 and 100.0."
        )

    if lvl == "beginner":
        if score >= 80.0:
            return "Intermediate"
        return "Beginner"
    elif lvl == "intermediate":
        if score >= 80.0:
            return "Advanced"
        elif score < 50.0:
            return "Beginner"
        else:
            return "Intermediate"
    else:  # advanced
        if score < 50.0:
            return "Intermediate"
        return "Advanced"


async def generate_adaptive_content(
    topic: str,
    difficulty: str = "beginner",
    *,
    language: str = "English",
    config: Any = None,
) -> Dict[str, Any]:
    """
    Generate integrated adaptive learning content containing:
      1. Lesson notes adapted to the current difficulty level
      2. 5-question multiple choice quiz with answer key and explanations
    """
    if config is None:
        try:
            from app.core.config import settings
            config = settings
        except ImportError:
            class _DefaultConfig:
                AI_PROVIDER = "openai"
                OPENAI_API_KEY = ""
                OPENAI_MODEL = "gpt-4o-mini"
                GOOGLE_API_KEY = ""
                GOOGLE_MODEL = "gemini-1.5-flash"
                ENVIRONMENT = "development"
                AI_TIMEOUT_SECONDS = 30
                AI_MAX_RETRIES = 2
                MOCK_AI_IN_DEV = True

            config = _DefaultConfig()

    try:
        level_enum = LearningLevel(difficulty.lower().strip())
    except ValueError:
        level_enum = LearningLevel.BEGINNER

    # Generate lesson notes
    notes_request = AIRequest(
        topic=topic,
        learning_level=level_enum,
        language=language,
        content_type=ContentType.NOTES,
    )
    notes_response = await generate(notes_request, config=config)

    # Generate quiz with answer key
    quiz_request = AIRequest(
        topic=topic,
        learning_level=level_enum,
        language=language,
        content_type=ContentType.QUIZ,
    )
    quiz_response = await generate(quiz_request, config=config)

    return {
        "topic": topic,
        "difficulty": level_enum.value,
        "language": language,
        "lesson": notes_response.content,
        "quiz": quiz_response.content,
        "provider": notes_response.provider,
        "model": notes_response.model,
        "is_mock": notes_response.is_mock or quiz_response.is_mock,
    }

