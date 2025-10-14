"""API response models."""
from __future__ import annotations

from pydantic import BaseModel


class AttemptRecordSchema(BaseModel):
    student_id: str | None
    subject_id: str | None
    subject_name: str | None
    name: str | None
    id: str | None
    description: str | None
    kid: str | None
    answer_id: str
    part_id: str | None
    q_text: str | None
    q_image: str | None
    q_text1: str | None
    answer: str | None
    mark: str | None
    mark_awarded: str | None
    student_score: str | None
    is_mistake: int

    class Config:
        orm_mode = True

