"""Utilities to rebuild the SQLite database from the source CSV."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import AttemptRecord, Base

CSV_HEADERS = [
    "student_id",
    "subject_id",
    "subject_name",
    "name",
    "id",
    "description",
    "kid",
    "answer_id",
    "part_id",
    "q_text",
    "q_image",
    "q_text1",
    "answer",
    "mark",
    "mark_awarded",
    "student_score",
]


def _to_float(value: str | None) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def derive_tags(row: dict[str, str]) -> set[str]:
    """Replicate the tagging heuristics used across the project."""

    mark = _to_float(row.get("mark"))
    mark_awarded = _to_float(row.get("mark_awarded"))
    student_score = _to_float(row.get("student_score"))
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


def is_mistake_attempt(tags: Iterable[str]) -> bool:
    return any(tag != "mastered" for tag in tags)


def _resolve_database_path(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///"):
        return None
    db_path = Path(database_url.replace("sqlite:///", "", 1))
    return db_path


def ingest_csv(csv_path: str | Path, database_url: str | None = None) -> None:
    """Rebuild the database so it mirrors the CSV plus an ``is_mistake`` flag."""

    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    settings = get_settings()
    url = database_url or settings.database_url

    db_path = _resolve_database_path(url)
    if db_path:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.exists():
            db_path.unlink()

    engine = create_engine(url, echo=False, future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CSV_HEADERS:
            raise ValueError(
                "CSV headers do not match expected schema."
            )

        with SessionLocal() as session:
            _ingest_rows(session, reader)
            session.commit()


def _ingest_rows(session: Session, rows: Iterable[dict[str, str]]) -> None:
    for row in rows:
        # Preserve the original values exactly as they appear in the CSV.
        data = {header: row.get(header, "") for header in CSV_HEADERS}
        tags = derive_tags(data)
        record = AttemptRecord(
            answer_id=data["answer_id"],
            student_id=data["student_id"],
            subject_id=data["subject_id"],
            subject_name=data["subject_name"],
            name=data["name"],
            subtopic_id=data["id"],
            description=data["description"],
            kid=data["kid"],
            part_id=data["part_id"],
            q_text=data["q_text"],
            q_image=data["q_image"],
            q_text1=data["q_text1"],
            answer=data["answer"],
            mark=data["mark"],
            mark_awarded=data["mark_awarded"],
            student_score=data["student_score"],
            is_mistake=1 if is_mistake_attempt(tags) else 0,
        )
        session.add(record)

