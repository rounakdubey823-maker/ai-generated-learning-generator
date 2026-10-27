"""
Pydantic schemas for POST /api/v1/generate.

These are the API-layer schemas (what the HTTP client sends/receives).
They mirror the ai_module schemas but are kept separate so the HTTP
API can evolve independently of the internal AI layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Union
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_module.schemas import ContentType, LearningLevel


# ── Request ────────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    topic: str = Field(
        ...,
        min_length=2,
        max_length=500,
        examples=["Python decorators"],
        description="The subject or concept to generate content about.",
    )
    learning_level: LearningLevel = Field(
        LearningLevel.BEGINNER,
        description="Target audience level: beginner, intermediate, or advanced.",
    )
    language: str = Field(
        "English",
        min_length=2,
        max_length=50,
        examples=["English", "Spanish", "French"],
        description="Language for the generated content.",
    )
    content_type: ContentType = Field(
        ContentType.NOTES,
        description="Format of the content: notes, summary, or quiz.",
    )


# ── Response ───────────────────────────────────────────────────────────────────

class GenerateResponse(BaseModel):
    id:             str                = Field(default_factory=lambda: str(uuid4()))
    topic:          str
    learning_level: LearningLevel
    language:       str
    content_type:   ContentType
    content:        Dict[str, Any]     = Field(
        description="Structured content — shape depends on content_type."
    )
    provider:       str                = Field(
        description="AI provider that generated this response (openai/google/mock)."
    )
    model:          str
    is_mock:        bool               = Field(
        description="True when this is an explicitly labelled development mock — not real AI output."
    )
    generated_at:   datetime           = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    model_config = {"from_attributes": True}
