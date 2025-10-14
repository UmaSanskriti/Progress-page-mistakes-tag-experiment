from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class AttemptRecordSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    answer_id: str
    student_id: str
    subject_id: Optional[str]
    subject_name: Optional[str]
    name: Optional[str]
    id: str
    description: Optional[str]
    kid: str
    part_id: Optional[str]
    q_text: Optional[str]
    q_image: Optional[str]
    q_text1: Optional[str]
    answer: Optional[str]
    mark: Optional[str]
    mark_awarded: Optional[str]
    student_score: Optional[str]
    is_mistake: int
    mistake_category: str


class SubtopicMistakeCount(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subtopic_id: str
    subtopic: Optional[str]
    topic: Optional[str]
    subject: Optional[str]
    mistake_category: str
    count: int


class StudentSubtopicSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: str
    subtopic_id: str
    subtopic: Optional[str]
    topic: Optional[str]
    subject: Optional[str]
    mistake_categories: List[str]
    attempt_count: int
