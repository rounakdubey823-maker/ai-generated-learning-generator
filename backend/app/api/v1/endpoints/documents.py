"""
POST /api/v1/documents/upload — PDF upload, safe text extraction, optional AI generation.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile, status

from ai_module.generator import generate as ai_generate
from ai_module.providers.base import ProviderError
from ai_module.schemas import AIRequest, ContentType, LearningLevel
from ai_module.utils import sanitise_topic
from app.core.config import settings
from app.core.errors import PayloadTooLargeError, ServiceUnavailableError
from app.schemas.document import DocumentUploadResponse
from app.schemas.generate import GenerateResponse
from app.services.pdf_extractor import extract_from_upload

logger = logging.getLogger(__name__)

router = APIRouter()

# Multipart wrapping adds a small amount of overhead on top of the file bytes.
_MULTIPART_OVERHEAD = 64 * 1024


def enforce_upload_size(request: Request) -> None:
    raw = request.headers.get("content-length")
    if not raw:
        return
    try:
        length = int(raw)
    except ValueError:
        return
    limit = settings.MAX_UPLOAD_BYTES + _MULTIPART_OVERHEAD
    if length > limit:
        raise PayloadTooLargeError(
            message=f"Upload exceeds the maximum size of {settings.MAX_UPLOAD_BYTES} bytes.",
            detail={"content_length": length, "max_upload_bytes": settings.MAX_UPLOAD_BYTES},
        )


def _topic_from_upload(topic: str | None, filename: str, extracted_text: str) -> str:
    if topic:
        cleaned = sanitise_topic(topic)
        if len(cleaned) >= 2:
            return cleaned[:500]
    stem = sanitise_topic(Path(filename).stem.replace("_", " ").replace("-", " "))
    if len(stem) >= 2:
        return stem[:500]
    preview = sanitise_topic(extracted_text[:80])
    if len(preview) >= 2:
        return preview[:500]
    return "Uploaded document"


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload a PDF and extract text",
)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="A PDF file (.pdf) whose signature is %PDF-."),
    generate: bool = Form(
        False,
        description="If true, send extracted text to the existing AI generation service.",
    ),
    topic: str | None = Form(None),
    learning_level: LearningLevel = Form(LearningLevel.BEGINNER),
    language: str = Form("English"),
    content_type: ContentType = Form(ContentType.NOTES),
) -> DocumentUploadResponse:
    """
    Accept a PDF, validate type + signature, extract text, then delete the temp copy.

    Uploaded bytes are parsed only — they are never executed.
    """
    enforce_upload_size(request)

    extracted = extract_from_upload(
        file.file,
        filename=file.filename,
        content_type=file.content_type,
        max_bytes=settings.MAX_UPLOAD_BYTES,
        max_pages=settings.MAX_PDF_PAGES,
        max_chars=settings.MAX_EXTRACTED_CHARS,
    )

    generated: GenerateResponse | None = None
    if generate:
        ai_request = AIRequest(
            topic=_topic_from_upload(topic, extracted.filename, extracted.text),
            learning_level=learning_level,
            language=language,
            content_type=content_type,
            source_text=extracted.text,
        )
        try:
            ai_response = await ai_generate(ai_request, config=settings)
        except ServiceUnavailableError:
            raise
        except ProviderError as exc:
            logger.error(
                "Provider error after PDF extract [provider=%s]: %s",
                exc.provider, exc, exc_info=True,
            )
            raise ServiceUnavailableError(
                message=f"The AI provider encountered an error: {exc}",
                detail={"provider": exc.provider},
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error generating from uploaded PDF: %s", exc)
            raise ServiceUnavailableError(
                message="An unexpected error occurred while generating content.",
            ) from exc

        generated = GenerateResponse(
            topic=ai_request.topic,
            learning_level=ai_request.learning_level,
            language=ai_request.language,
            content_type=ai_request.content_type,
            content=ai_response.content,
            provider=ai_response.provider,
            model=ai_response.model,
            is_mock=ai_response.is_mock,
        )

    return DocumentUploadResponse(
        filename=extracted.filename,
        page_count=extracted.page_count,
        char_count=len(extracted.text),
        truncated=extracted.truncated,
        text=extracted.text,
        generated=generated,
    )
