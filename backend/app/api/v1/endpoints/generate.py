"""
POST /api/v1/generate — core AI content generation endpoint.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, status

from ai_module.generator import generate as ai_generate
from ai_module.providers.base import ProviderError
from ai_module.schemas import AIRequest
from app.core.config import settings
from app.core.errors import ServiceUnavailableError
from app.schemas.generate import GenerateRequest, GenerateResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=GenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI learning content",
    response_description=(
        "Structured educational content. Check `is_mock` to know whether "
        "this came from a real AI provider or a development placeholder."
    ),
)
async def generate_content(payload: GenerateRequest) -> GenerateResponse:
    """
    Generate educational content for the given topic.

    - **topic**: Subject to learn about (2–500 chars)
    - **learning_level**: `beginner` | `intermediate` | `advanced`
    - **language**: Response language (default: English)
    - **content_type**: `notes` | `summary` | `quiz`

    Returns structured JSON content validated against the content_type schema.
    `is_mock: true` indicates a development placeholder — not real AI output.
    """
    ai_request = AIRequest(
        topic          = payload.topic,
        learning_level = payload.learning_level,
        language       = payload.language,
        content_type   = payload.content_type,
    )

    try:
        ai_response = await ai_generate(ai_request, config=settings)

    except ServiceUnavailableError:
        raise  # re-raise; the registered handler returns 503 with error envelope

    except ProviderError as exc:
        logger.error(
            "Provider error during generation [provider=%s]: %s",
            exc.provider, exc, exc_info=True,
        )
        raise ServiceUnavailableError(
            message=f"The AI provider encountered an error: {exc}",
            detail={"provider": exc.provider},
        ) from exc

    except Exception as exc:
        logger.exception("Unexpected error during content generation: %s", exc)
        raise ServiceUnavailableError(
            message="An unexpected error occurred while generating content.",
        ) from exc

    return GenerateResponse(
        topic          = payload.topic,
        learning_level = payload.learning_level,
        language       = payload.language,
        content_type   = payload.content_type,
        content        = ai_response.content,
        provider       = ai_response.provider,
        model          = ai_response.model,
        is_mock        = ai_response.is_mock,
    )
