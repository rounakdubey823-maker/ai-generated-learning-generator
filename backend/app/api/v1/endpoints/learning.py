"""
Learning content endpoints — generate and retrieve AI-produced lessons.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.learning_content import LearningContent
from app.schemas.learning_content import GenerateRequest, LearningContentOut
from app.services.ai_service import generate_learning_content

router = APIRouter()

# NOTE: Auth dependency will be added once the auth flow is wired up.
#       For now the endpoint is open so you can test without a token.


@router.post("/generate", response_model=LearningContentOut, status_code=status.HTTP_201_CREATED)
async def generate(payload: GenerateRequest, db: AsyncSession = Depends(get_db)):
    """Call the AI service and persist the generated content."""
    result = await generate_learning_content(
        topic=payload.topic,
        difficulty=payload.difficulty,
        content_type=payload.content_type,
    )
    content_obj = LearningContent(
        user_id="anonymous",  # replace with real user_id after auth wiring
        topic=payload.topic,
        difficulty=payload.difficulty,
        content_type=payload.content_type,
        content=result["content"],
        ai_provider=result.get("provider"),
        ai_model=result.get("model"),
    )
    db.add(content_obj)
    await db.flush()
    await db.refresh(content_obj)
    return content_obj


@router.get("/{content_id}", response_model=LearningContentOut)
async def get_content(content_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(LearningContent).where(LearningContent.id == content_id)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    return obj
