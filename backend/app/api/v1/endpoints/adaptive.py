"""
Adaptive Learning Endpoints:
- GET  /api/v1/adaptive/profile           — Fetch student profile and current level
- POST /api/v1/adaptive/session           — Start adaptive session (calls generate_adaptive_content)
- GET  /api/v1/adaptive/session/{id}      — Get session details (hides quiz answer key)
- POST /api/v1/adaptive/session/{id}/quiz/submit — Evaluate quiz server-side and calculate next level
- GET  /api/v1/adaptive/progress          — Get student progression history
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_module import calculate_next_level, generate_adaptive_content
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.adaptive import LearningSession, QuizAttempt, StudentProfile
from app.models.user import User
from app.schemas.adaptive import (
    LearningSessionOut,
    ProgressHistoryItem,
    QuestionEvaluationDetail,
    QuizEvaluationResponse,
    QuizOptionOut,
    QuizQuestionClientOut,
    QuizSubmissionRequest,
    StartSessionRequest,
    StudentProfileOut,
)

router = APIRouter()
logger = logging.getLogger(__name__)

DEMO_USER_EMAIL = "student@example.com"


# ── Dependency: Resolve current student or demo student ─────────────────────────

async def get_current_student(
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> Tuple[User, StudentProfile]:
    """
    Resolve the active user from the JWT Bearer token if provided.
    If unauthenticated (guest / demo mode), seamlessly resolve or provision a default demo student.
    Ensures a corresponding StudentProfile exists.
    """
    user: Optional[User] = None

    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        user_id = decode_access_token(token)
        if user_id:
            res = await db.execute(select(User).where(User.id == user_id))
            user = res.scalar_one_or_none()

    if user is None:
        # Resolve or create default demo student
        res = await db.execute(select(User).where(User.email == DEMO_USER_EMAIL))
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                email=DEMO_USER_EMAIL,
                hashed_password="demo-hashed-password",
                full_name="Demo Student",
            )
            db.add(user)
            await db.flush()
            await db.refresh(user)

    # Resolve or create StudentProfile
    profile_res = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == user.id)
    )
    profile = profile_res.scalar_one_or_none()
    if not profile:
        profile = StudentProfile(
            user_id=user.id,
            current_level="Beginner",
            total_sessions=0,
            quizzes_completed=0,
            average_score=0.0,
        )
        db.add(profile)
        await db.flush()
        await db.refresh(profile)

    return user, profile


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/profile", response_model=StudentProfileOut)
async def get_profile(
    student_ctx: Tuple[User, StudentProfile] = Depends(get_current_student),
):
    """Retrieve the current student's profile, difficulty level, and progress statistics."""
    _, profile = student_ctx
    return profile


@router.post(
    "/session",
    response_model=LearningSessionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_learning_session(
    payload: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
    student_ctx: Tuple[User, StudentProfile] = Depends(get_current_student),
):
    """
    Start a new adaptive learning session for a topic.

    1. Determines difficulty (defaults to student's current proficiency level).
    2. Calls ai_module.generate_adaptive_content(topic, difficulty).
    3. Securely stores the lesson and the full quiz (with secret answer key) on the server.
    4. Returns the lesson and quiz to the client with answer keys stripped to prevent cheating.
    """
    user, profile = student_ctx

    # Determine difficulty level (normalized to exact contract TitleCase)
    valid_difficulties = {
        "beginner": "Beginner",
        "intermediate": "Intermediate",
        "advanced": "Advanced",
    }
    if payload.difficulty and payload.difficulty.lower().strip() in valid_difficulties:
        difficulty = valid_difficulties[payload.difficulty.lower().strip()]
    else:
        difficulty = profile.current_level or "Beginner"

    # Call AI module adaptive generator
    try:
        content = await generate_adaptive_content(
            topic=payload.topic,
            difficulty=difficulty,
            language=payload.language,
        )
    except Exception as exc:
        logger.error("generate_adaptive_content failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to generate adaptive content: {exc}",
        ) from exc

    # Persist session with the secret answer key stored in DB
    session = LearningSession(
        user_id=user.id,
        topic=payload.topic,
        difficulty=difficulty,
        lesson_content=content.get("lesson", {}),
        quiz_data=content.get("quiz", {}),  # Contains questions with correct_label
        is_completed=False,
    )
    profile.total_sessions += 1
    db.add(session)
    await db.flush()
    await db.refresh(session)

    # Build client-safe quiz shape (omit correct_label and explanation)
    raw_questions = content.get("quiz", {}).get("questions", [])
    safe_questions: List[QuizQuestionClientOut] = []
    for idx, q in enumerate(raw_questions):
        raw_options = q.get("options", [])
        safe_options = [
            QuizOptionOut(label=opt.get("label", ""), text=opt.get("text", ""))
            for opt in raw_options
        ]
        safe_questions.append(
            QuizQuestionClientOut(
                index=idx,
                question=q.get("question", ""),
                options=safe_options,
            )
        )

    return LearningSessionOut(
        session_id=session.id,
        topic=session.topic,
        difficulty=session.difficulty,
        language=payload.language,
        lesson=session.lesson_content,
        quiz=safe_questions,
        is_completed=session.is_completed,
    )


@router.get("/session/{session_id}", response_model=LearningSessionOut)
async def get_learning_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    student_ctx: Tuple[User, StudentProfile] = Depends(get_current_student),
):
    """Retrieve an existing learning session. Answer keys remain hidden until evaluated."""
    res = await db.execute(
        select(LearningSession).where(LearningSession.id == session_id)
    )
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Learning session not found"
        )

    raw_questions = session.quiz_data.get("questions", [])
    safe_questions: List[QuizQuestionClientOut] = []
    for idx, q in enumerate(raw_questions):
        safe_options = [
            QuizOptionOut(label=opt.get("label", ""), text=opt.get("text", ""))
            for opt in q.get("options", [])
        ]
        safe_questions.append(
            QuizQuestionClientOut(
                index=idx,
                question=q.get("question", ""),
                options=safe_options,
            )
        )

    return LearningSessionOut(
        session_id=session.id,
        topic=session.topic,
        difficulty=session.difficulty,
        language="English",
        lesson=session.lesson_content,
        quiz=safe_questions,
        is_completed=session.is_completed,
    )


@router.post(
    "/session/{session_id}/quiz/submit",
    response_model=QuizEvaluationResponse,
)
async def submit_quiz(
    session_id: str,
    payload: QuizSubmissionRequest,
    db: AsyncSession = Depends(get_db),
    student_ctx: Tuple[User, StudentProfile] = Depends(get_current_student),
):
    """
    Evaluate a quiz submission on the backend against the stored answer key.

    1. Retrieves the session and its server-stored answer key (never trusts frontend scores).
    2. Calculates correct_count and score_percentage = (correct_count / total_questions) * 100.
    3. Calls calculate_next_level(current_level, score_percentage).
    4. Updates student profile proficiency and enables the next personalized lesson.
    5. Returns detailed question feedback and recommendations.
    """
    user, profile = student_ctx

    res = await db.execute(
        select(LearningSession).where(LearningSession.id == session_id)
    )
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Learning session not found"
        )

    if session.is_completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This quiz has already been evaluated.",
        )

    stored_questions = session.quiz_data.get("questions", [])
    if not stored_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No quiz questions found for this session.",
        )

    total_questions = len(stored_questions)
    correct_count = 0
    feedback_list: List[QuestionEvaluationDetail] = []

    # Map student answers by question index
    submitted_map = {
        ans.question_index: ans.selected_label.strip().upper()
        for ans in payload.answers
    }

    # Server-side evaluation against stored answer key
    for idx, q in enumerate(stored_questions):
        selected = submitted_map.get(idx, "")
        correct = q.get("correct_label", "").strip().upper()
        is_correct = bool(selected and selected == correct)
        if is_correct:
            correct_count += 1

        feedback_list.append(
            QuestionEvaluationDetail(
                question_index=idx,
                question=q.get("question", ""),
                selected_label=selected,
                correct_label=correct,
                is_correct=is_correct,
                explanation=q.get("explanation", ""),
            )
        )

    # Precise score calculation: (correct_count / total_questions) * 100
    score_percentage = round((correct_count / total_questions) * 100.0, 2)

    # Adaptive progression calculation
    previous_level = profile.current_level
    new_level = calculate_next_level(previous_level, score_percentage)
    level_changed = new_level != previous_level

    # Update profile statistics and adaptive level
    new_completed = profile.quizzes_completed + 1
    new_avg = round(
        ((profile.average_score * profile.quizzes_completed) + score_percentage)
        / new_completed,
        2,
    )
    profile.quizzes_completed = new_completed
    profile.average_score = new_avg
    profile.current_level = new_level

    # Mark session as completed
    session.is_completed = True

    # Persist the attempt in DB
    attempt = QuizAttempt(
        session_id=session.id,
        user_id=user.id,
        submitted_answers=[ans.model_dump() for ans in payload.answers],
        total_questions=total_questions,
        correct_count=correct_count,
        score_percentage=score_percentage,
        previous_level=previous_level,
        new_level=new_level,
        feedback=[f.model_dump() for f in feedback_list],
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    await db.refresh(profile)

    # Build student recommendation for the next lesson
    if new_level.lower() == "advanced" and previous_level.lower() != "advanced":
        recommendation = (
            f"Mastery demonstrated ({score_percentage}%)! Promoted to ADVANCED level. "
            "Next personalized lesson will feature in-depth, advanced scenarios."
        )
    elif level_changed and previous_level.lower() == "beginner":
        recommendation = (
            f"Great job ({score_percentage}%)! Promoted to INTERMEDIATE level. "
            "Next personalized lesson unlocked with intermediate depth."
        )
    elif level_changed and score_percentage < 50.0:
        recommendation = (
            f"Score: {score_percentage}%. Level adjusted to {new_level.upper()} "
            "to reinforce foundation before advancing."
        )
    else:
        recommendation = (
            f"Score: {score_percentage}%. Solid effort! Continuing at {new_level.upper()} level "
            "for the next lesson."
        )

    return QuizEvaluationResponse(
        session_id=session.id,
        total_questions=total_questions,
        correct_count=correct_count,
        score_percentage=score_percentage,
        previous_level=previous_level,
        new_level=new_level,
        level_changed=level_changed,
        details=feedback_list,
        next_lesson_recommendation=recommendation,
    )


@router.get("/progress", response_model=List[ProgressHistoryItem])
async def get_progress_history(
    db: AsyncSession = Depends(get_db),
    student_ctx: Tuple[User, StudentProfile] = Depends(get_current_student),
):
    """Retrieve full history of quiz attempts and difficulty progression for the student."""
    user, _ = student_ctx

    stmt = (
        select(QuizAttempt, LearningSession.topic)
        .join(LearningSession, QuizAttempt.session_id == LearningSession.id)
        .where(QuizAttempt.user_id == user.id)
        .order_by(desc(QuizAttempt.created_at))
    )
    result = await db.execute(stmt)
    rows = result.all()

    history: List[ProgressHistoryItem] = []
    for attempt, topic in rows:
        history.append(
            ProgressHistoryItem(
                attempt_id=attempt.id,
                session_id=attempt.session_id,
                topic=topic,
                score_percentage=attempt.score_percentage,
                previous_level=attempt.previous_level,
                new_level=attempt.new_level,
                created_at=attempt.created_at,
            )
        )

    return history
