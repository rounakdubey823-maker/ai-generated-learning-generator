"""
Adaptive learning models: StudentProfile, LearningSession, QuizAttempt.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    current_level: Mapped[str] = mapped_column(
        String(50), default="Beginner", nullable=False
    )
    total_sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quizzes_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", backref="profile")
    sessions = relationship(
        "LearningSession",
        back_populates="student_profile",
        cascade="all, delete-orphan",
        foreign_keys="LearningSession.user_id",
        primaryjoin="StudentProfile.user_id == LearningSession.user_id",
    )
    attempts = relationship(
        "QuizAttempt",
        back_populates="student_profile",
        cascade="all, delete-orphan",
        foreign_keys="QuizAttempt.user_id",
        primaryjoin="StudentProfile.user_id == QuizAttempt.user_id",
    )

    def __repr__(self) -> str:
        return f"<StudentProfile user_id={self.user_id} level={self.current_level}>"


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    topic: Mapped[str] = mapped_column(String(512), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(50), nullable=False)
    lesson_content: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    quiz_data: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )  # Stores questions with answer key securely on backend
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    student_profile = relationship(
        "StudentProfile",
        foreign_keys=[user_id],
        primaryjoin="LearningSession.user_id == StudentProfile.user_id",
        back_populates="sessions",
    )
    quiz_attempts = relationship(
        "QuizAttempt", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<LearningSession id={self.id} topic={self.topic[:30]} diff={self.difficulty}>"


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("learning_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    submitted_answers: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    score_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    previous_level: Mapped[str] = mapped_column(String(50), nullable=False)
    new_level: Mapped[str] = mapped_column(String(50), nullable=False)
    feedback: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session = relationship("LearningSession", back_populates="quiz_attempts")
    student_profile = relationship(
        "StudentProfile",
        foreign_keys=[user_id],
        primaryjoin="QuizAttempt.user_id == StudentProfile.user_id",
        back_populates="attempts",
    )

    def __repr__(self) -> str:
        return (
            f"<QuizAttempt id={self.id} score={self.score_percentage}% "
            f"{self.previous_level}->{self.new_level}>"
        )
