from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from .database import engine as default_engine
from .models import Attempt, Base, MistakeTag, Question, Student, Subtopic

TAG_DEFINITIONS = {
    "blank_response": "The learner did not submit an answer for the question.",
    "conceptual_gap": "The learner received zero marks, signalling a core misunderstanding.",
    "partial_understanding": "The learner earned partial credit, indicating emerging understanding.",
    "mastered": "The learner achieved full marks for the attempt.",
    "needs_revision": "The learner scored below the available mark and may need targeted revision.",
    "review_with_teacher": "An incorrect non-blank response that can anchor teacher feedback.",
}


def _normalise_value(value):
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value


def derive_tags(row: dict) -> Iterable[str]:
    mark = float(row.get("mark") or 0)
    mark_awarded = float(row.get("mark_awarded") or 0)
    student_score = float(row.get("student_score") or 0)
    answer_text = (row.get("answer") or "").strip()

    tags: set[str] = set()

    if not answer_text:
        tags.add("blank_response")

    if mark > 0 and mark_awarded == mark:
        tags.add("mastered")
    elif mark_awarded == 0:
        tags.add("conceptual_gap")
    elif mark_awarded < mark:
        tags.add("partial_understanding")

    if mark_awarded < mark:
        tags.add("review_with_teacher")

    if student_score < mark:
        tags.add("needs_revision")

    if not tags:
        tags.add("needs_revision")

    return tags


def get_engine(database_url: str | None = None):
    if database_url:
        return create_engine(database_url, echo=False, future=True)
    return default_engine


def ingest_csv(csv_path: str | Path, database_url: str | None = None) -> None:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    df = pd.read_csv(csv_path)
    df = df.where(pd.notnull(df), None)

    with SessionLocal() as session:
        _ensure_tags(session)
        tag_entities = {
            tag.name: tag for tag in session.query(MistakeTag).filter(MistakeTag.name.in_(TAG_DEFINITIONS.keys()))
        }
        for record in df.to_dict("records"):
            _process_row(session, record, tag_entities)
        session.commit()


def _ensure_tags(session: Session) -> None:
    existing = {tag.name for tag in session.query(MistakeTag).all()}
    for name, description in TAG_DEFINITIONS.items():
        if name not in existing:
            session.add(MistakeTag(name=name, description=description))
    session.flush()


def _process_row(session: Session, row: dict, tag_entities: dict[str, MistakeTag]) -> None:
    student_id = int(row["student_id"])
    subtopic_id = int(row["id"])
    question_id = int(row["kid"])
    attempt_id = int(row["answer_id"])

    student = session.get(Student, student_id)
    if student is None:
        student = Student(id=student_id)
        session.add(student)

    subtopic = session.get(Subtopic, subtopic_id)
    if subtopic is None:
        subtopic = Subtopic(
            id=subtopic_id,
            subject_id=int(row["subject_id"]),
            subject_name=str(row["subject_name"]),
            topic_name=str(row["name"]),
            name=str(row["description"]),
        )
        session.add(subtopic)

    question = session.get(Question, question_id)
    if question is None:
        question = Question(
            id=question_id,
            subtopic=subtopic,
            text=_normalise_value(row.get("q_text1")) or _normalise_value(row.get("q_text")),
            image_url=_normalise_value(row.get("q_image")),
        )
        session.add(question)

    attempt = session.get(Attempt, attempt_id)
    if attempt is None:
        attempt = Attempt(
            id=attempt_id,
            student=student,
            question=question,
            subtopic=subtopic,
            answer_text=_normalise_value(row.get("answer")),
            mark=float(row.get("mark") or 0),
            mark_awarded=float(row.get("mark_awarded") or 0),
            student_score=float(row.get("student_score") or 0),
        )
        session.add(attempt)
    else:
        attempt.answer_text = _normalise_value(row.get("answer"))
        attempt.mark = float(row.get("mark") or 0)
        attempt.mark_awarded = float(row.get("mark_awarded") or 0)
        attempt.student_score = float(row.get("student_score") or 0)

    attempt.tags.clear()
    for tag_name in derive_tags(row):
        attempt.tags.append(tag_entities[tag_name])

    session.flush()
