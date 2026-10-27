"""Pydantic schemas for POST /api/v1/documents/upload."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.generate import GenerateResponse


class DocumentUploadResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    page_count: int
    char_count: int
    truncated: bool = Field(
        description="True when extracted text was cut to MAX_EXTRACTED_CHARS."
    )
    text: str = Field(description="Extracted plain text. Never executable content.")
    generated: Optional[GenerateResponse] = Field(
        default=None,
        description="Populated only when generate=true was sent with the upload.",
    )
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
