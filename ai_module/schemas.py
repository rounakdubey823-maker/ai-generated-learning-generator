"""
Shared Pydantic schemas for the AI module layer.

These are internal schemas (AI ↔ generator ↔ endpoint).
They are intentionally separate from the FastAPI API schemas
so the ai_module stays framework-agnostic.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────

class LearningLevel(str, Enum):
    BEGINNER     = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED     = "advanced"


class ContentType(str, Enum):
    NOTES   = "notes"
    SUMMARY = "summary"
    QUIZ    = "quiz"


# ── AI request ─────────────────────────────────────────────────────────────────

class AIRequest(BaseModel):
    topic:          str          = Field(..., min_length=2, max_length=500)
    learning_level: LearningLevel = LearningLevel.BEGINNER
    language:       str          = Field("English", min_length=2, max_length=50)
    content_type:   ContentType  = ContentType.NOTES
    source_text:    Optional[str] = Field(
        None,
        description="Optional extracted document text to ground generation.",
    )


# ── Structured content shapes (what the AI must return) ────────────────────────

class NotesSection(BaseModel):
    heading: str
    body:    str


class NotesContent(BaseModel):
    title:    str
    sections: List[NotesSection] = Field(..., min_length=1)


class SummaryContent(BaseModel):
    title:      str
    summary:    str
    key_points: List[str] = Field(..., min_length=1)


class QuizOption(BaseModel):
    label: str   # "A", "B", "C", "D"
    text:  str


class QuizQuestion(BaseModel):
    question:       str
    options:        List[QuizOption] = Field(..., min_length=2)
    correct_label:  str
    explanation:    str


class QuizContent(BaseModel):
    title:     str
    questions: List[QuizQuestion] = Field(..., min_length=1)


# ── AI response ────────────────────────────────────────────────────────────────

class AIResponse(BaseModel):
    """What every provider must return after a successful call."""
    content:    Dict[str, Any]   # validated separately per content_type
    provider:   str
    model:      str
    is_mock:    bool = False
    raw_tokens: Optional[int] = None
