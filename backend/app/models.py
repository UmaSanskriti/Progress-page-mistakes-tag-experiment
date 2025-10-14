from __future__ import annotations

from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AttemptRecord(Base):
    """Single row mirroring the source CSV with additional mistake metadata."""

    __tablename__ = "attempt_records"

    answer_id = Column(String, primary_key=True)
    student_id = Column(String, nullable=False)
    subject_id = Column(String, nullable=True)
    subject_name = Column(Text, nullable=True)
    name = Column(Text, nullable=True)
    id = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    kid = Column(String, nullable=False, primary_key=True)
    part_id = Column(String, nullable=False, primary_key=True)
    q_text = Column(Text, nullable=True)
    q_image = Column(Text, nullable=True)
    q_text1 = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    mark = Column(String, nullable=True)
    mark_awarded = Column(String, nullable=True)
    student_score = Column(String, nullable=True)
    is_mistake = Column(Integer, nullable=False, default=0)
    mistake_category = Column(String, nullable=False, default="null")
