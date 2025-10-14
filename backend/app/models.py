"""Database models for the progress page experiment."""
from __future__ import annotations

from typing import Dict, List

from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AttemptRecord(Base):
    """Represents a single row from the source CSV file.

    The column names mirror the CSV headers exactly so that the resulting
    database can be compared field-for-field with the original dataset.  The
    only additional field is ``is_mistake`` which stores a binary flag derived
    from the grading information that indicates whether the attempt should be
    treated as a mistake.
    """

    __tablename__ = "attempt_records"

    answer_id = Column(String, primary_key=True)
    student_id = Column(String, nullable=False)
    subject_id = Column(String, nullable=True)
    subject_name = Column(String, nullable=True)
    name = Column(String, nullable=True)
    subtopic_id = Column("id", String, nullable=True)
    description = Column(String, nullable=True)
    kid = Column(String, primary_key=True, nullable=True)
    part_id = Column(String, primary_key=True, nullable=True)
    q_text = Column(Text, nullable=True)
    q_image = Column(String, nullable=True)
    q_text1 = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    mark = Column(String, nullable=True)
    mark_awarded = Column(String, nullable=True)
    student_score = Column(String, nullable=True)
    is_mistake = Column(Integer, nullable=False, default=0)

    def as_dict(self) -> Dict[str, str | int | None]:
        """Return a serialisable representation using the CSV headers."""

        return {
            "student_id": self.student_id,
            "subject_id": self.subject_id,
            "subject_name": self.subject_name,
            "name": self.name,
            "id": self.subtopic_id,
            "description": self.description,
            "kid": self.kid,
            "answer_id": self.answer_id,
            "part_id": self.part_id,
            "q_text": self.q_text,
            "q_image": self.q_image,
            "q_text1": self.q_text1,
            "answer": self.answer,
            "mark": self.mark,
            "mark_awarded": self.mark_awarded,
            "student_score": self.student_score,
            "is_mistake": self.is_mistake,
        }


def to_serialisable(records: List[AttemptRecord]) -> List[Dict[str, str | int | None]]:
    """Convert attempt rows into dictionaries for JSON responses."""

    return [record.as_dict() for record in records]

