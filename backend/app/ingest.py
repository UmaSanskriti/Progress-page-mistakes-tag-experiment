from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker

from .database import engine as default_engine
from .models import AttemptRecord, Base


def _to_float(value: str | None) -> float:
    try:
        return float(value) if value not in {None, ""} else 0.0
    except (TypeError, ValueError):
        return 0.0


def classify_mistake(row: dict[str, str]) -> tuple[int, str]:
    """Return `(is_mistake, category)` using lightweight heuristics."""

    answer_text = row.get("answer", "") or ""
    mark = _to_float(row.get("mark"))
    mark_awarded = _to_float(row.get("mark_awarded"))

    if answer_text.strip() == "":
        return 1, "No Answer"

    if mark_awarded >= mark and mark > 0:
        return 0, "null"

    if mark_awarded == 0:
        return 1, "Concept Error"

    if mark_awarded < mark:
        return 1, "Partial Understanding"

    return 0, "null"


def get_engine(database_url: str | None = None):
    if database_url:
        return create_engine(database_url, echo=False, future=True)
    return default_engine


def _reset_database(engine) -> None:
    metadata = MetaData()
    metadata.reflect(bind=engine)
    if metadata.tables:
        metadata.drop_all(bind=engine)


def ingest_csv(csv_path: str | Path, database_url: str | None = None) -> None:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    engine = get_engine(database_url)
    _reset_database(engine)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)

    with SessionLocal() as session:
        for record in df.to_dict("records"):
            is_mistake, category = classify_mistake(record)
            session.add(
                AttemptRecord(
                    answer_id=record.get("answer_id", ""),
                    student_id=record.get("student_id", ""),
                    subject_id=record.get("subject_id"),
                    subject_name=record.get("subject_name"),
                    name=record.get("name"),
                    id=record.get("id", ""),
                    description=record.get("description"),
                    kid=record.get("kid", ""),
                    part_id=record.get("part_id"),
                    q_text=record.get("q_text"),
                    q_image=record.get("q_image"),
                    q_text1=record.get("q_text1"),
                    answer=record.get("answer"),
                    mark=record.get("mark"),
                    mark_awarded=record.get("mark_awarded"),
                    student_score=record.get("student_score"),
                    is_mistake=is_mistake,
                    mistake_category=category,
                )
            )
        session.commit()
