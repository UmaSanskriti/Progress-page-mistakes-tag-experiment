from pydantic import BaseModel


class SubtopicTagCount(BaseModel):
    subtopic_id: int
    subtopic: str
    topic: str
    subject: str
    tag: str
    count: int
