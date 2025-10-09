from typing import List

from pydantic import BaseModel


class SubtopicTagCount(BaseModel):
    subtopic_id: int
    subtopic: str
    topic: str
    subject: str
    tag: str
    count: int


class StudentSubtopicSummary(BaseModel):
    student_id: int
    subtopic_id: int
    subtopic: str
    topic: str
    subject: str
    tags: List[str]
    attempt_count: int
