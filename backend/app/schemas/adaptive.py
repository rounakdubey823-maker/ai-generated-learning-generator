"""
Pydantic schemas for adaptive learning endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Student Profile Schemas ───────────────────────────────────────────────────

class StudentProfileOut(BaseModel):
    id: str
    user_id: str
    current_level: str
    total_sessions: int
    quizzes_completed: int
    average_score: float

    model_config = {"from_attributes": True}


# ── Learning Session Schemas ──────────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    topic: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="The topic to generate adaptive learning content for.",
        examples=["Python Generators and Iterators"],
    )
    difficulty: Optional[str] = Field(
        None,
        description="Optional difficulty level ('beginner', 'intermediate', 'advanced'). If omitted, defaults to student's current_level.",
        examples=["intermediate"],
    )
    language: str = Field(
        "English",
        min_length=2,
        max_length=50,
        description="Target language for lesson notes and quiz.",
        examples=["English"],
    )


class QuizOptionOut(BaseModel):
    label: str
    text: str


class QuizQuestionClientOut(BaseModel):
    """Client-facing question shape — hides correct answer and explanation to prevent cheating."""
    index: int
    question: str
    options: List[QuizOptionOut]


class LearningSessionOut(BaseModel):
    session_id: str
    topic: str
    difficulty: str
    language: str
    lesson: Dict[str, Any]
    quiz: List[QuizQuestionClientOut]
    is_completed: bool


# ── Quiz Submission & Evaluation Schemas ──────────────────────────────────────

class QuizSubmissionAnswer(BaseModel):
    question_index: int = Field(..., ge=0, description="0-based index of the question.")
    selected_label: str = Field(..., min_length=1, max_length=10, description="Selected option label (e.g. 'A', 'B', 'C', 'D').")


class QuizSubmissionRequest(BaseModel):
    answers: List[QuizSubmissionAnswer] = Field(
        ..., min_length=1, description="List of submitted answers for the session's quiz."
    )


class QuestionEvaluationDetail(BaseModel):
    question_index: int
    question: str
    selected_label: str
    correct_label: str
    is_correct: bool
    explanation: str


class QuizEvaluationResponse(BaseModel):
    session_id: str
    total_questions: int
    correct_count: int
    score_percentage: float
    previous_level: str
    new_level: str
    level_changed: bool
    details: List[QuestionEvaluationDetail]
    next_lesson_recommendation: str


class ProgressHistoryItem(BaseModel):
    attempt_id: str
    session_id: str
    topic: str
    score_percentage: float
    previous_level: str
    new_level: str
    created_at: datetime
