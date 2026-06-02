from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class NewsroomTrainingExample(Base, TimestampMixin):
    """Human-approved examples for future LoRA/QLoRA fine-tuning."""

    __tablename__ = "newsroom_training_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    final_output: Mapped[str] = mapped_column(Text, nullable=False)
    source_grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    editor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_human: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
