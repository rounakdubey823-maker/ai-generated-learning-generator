"""Pydantic schemas for Learning Content endpoints."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500, examples=["Python decorators"])
    difficulty: str = Field("beginner", pattern="^(beginner|intermediate|advanced)$")
    content_type: str = Field("lesson", pattern="^(lesson|quiz|summary)$")


class LearningContentOut(BaseModel):
    id: str
    topic: str
    difficulty: str
    content_type: str
    content: str
    ai_provider: Optional[str]
    ai_model: Optional[str]

    model_config = {"from_attributes": True}
