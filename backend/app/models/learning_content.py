"""
LearningContent ORM model.
"""

import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class LearningContent(Base):
    __tablename__ = "learning_content"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic: Mapped[str] = mapped_column(String(512), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(50), default="beginner")  # beginner|intermediate|advanced
    content_type: Mapped[str] = mapped_column(String(50), default="lesson")  # lesson|quiz|summary
    content: Mapped[str] = mapped_column(Text, nullable=False)
    ai_provider: Mapped[str] = mapped_column(String(50), nullable=True)
    ai_model: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship (lazy by default; enable selectin as needed)
    user = relationship("User", backref="learning_content")

    def __repr__(self) -> str:
        return f"<LearningContent id={self.id} topic={self.topic[:30]}>"
