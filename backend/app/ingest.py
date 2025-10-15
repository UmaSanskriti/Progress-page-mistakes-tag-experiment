from __future__ import annotations

from pathlib import Path
import re
from typing import Protocol

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


class MistakeCategoryClient(Protocol):
    def generate_category(
        self,
        *,
        question: str,
        reference_answer: str,
        student_answer: str,
        mark_available: float,
        mark_awarded: float,
    ) -> str:
        """Return a concise category (1-3 words) for the student's mistake."""


_DEFAULT_CATEGORY_CLIENT: MistakeCategoryClient | None = None


def _normalise_category(raw_category: str | None) -> str:
    if not raw_category:
        return "General Error"

    cleaned = re.sub(r"[^\w\s-]", "", raw_category).strip()
    if not cleaned:
        return "General Error"

    words = cleaned.split()
    words = words[:3]
    formatted = [word.capitalize() for word in words]
    return " ".join(formatted) if formatted else "General Error"


def _fallback_category(mark_awarded: float, mark: float) -> str:
    if mark_awarded <= 0:
        return "Concept Error"
    if mark_awarded < mark:
        return "Partial Understanding"
    return "General Error"


def _get_default_category_client() -> MistakeCategoryClient | None:
    global _DEFAULT_CATEGORY_CLIENT
    return _DEFAULT_CATEGORY_CLIENT


def set_default_category_client(client: MistakeCategoryClient | None) -> None:
    global _DEFAULT_CATEGORY_CLIENT
    _DEFAULT_CATEGORY_CLIENT = client


def classify_mistake(
    row: dict[str, str],
    *,
    category_client: MistakeCategoryClient | None = None,
) -> tuple[int, str]:
    """Return `(is_mistake, category)` using an LLM backed classifier when available."""

    raw_student_answer = (
        row.get("student_answer")
        or row.get("student_response")
        or row.get("student_answer_text")
        or row.get("student_answer_clean")
        or row.get("student_answer_raw")
    )
    student_answer = raw_student_answer if raw_student_answer is not None else ""
    if not student_answer:
        student_answer = row.get("answer", "") or ""
    mark = _to_float(row.get("mark"))
    mark_awarded = _to_float(row.get("mark_awarded"))

    if (raw_student_answer is not None and raw_student_answer.strip() == "") or (
        student_answer.strip() == ""
    ):
        return 1, "No Answer"

    if mark_awarded >= mark and mark > 0:
        return 0, "null"

    client = category_client or _get_default_category_client()

    if client is None:
        try:
            from .llm import OpenAIMistakeCategoryClient
        except Exception:  # pragma: no cover - optional dependency
            client = None
        else:
            client = OpenAIMistakeCategoryClient.from_env()
            if client is not None:
                set_default_category_client(client)

    if client is not None:
        try:
            category = client.generate_category(
                question=row.get("q_text", "") or "",
                reference_answer=row.get("answer", "") or "",
                student_answer=student_answer,
                mark_available=mark,
                mark_awarded=mark_awarded,
            )
        except Exception:
            category = None
    else:
        category = None

    if not category:
        category = _fallback_category(mark_awarded, mark)

    return 1, _normalise_category(category)


def get_engine(database_url: str | None = None):
    if database_url:
        return create_engine(database_url, echo=False, future=True)
    return default_engine


def _reset_database(engine) -> None:
    metadata = MetaData()
    metadata.reflect(bind=engine)
    if metadata.tables:
        metadata.drop_all(bind=engine)


def ingest_csv(
    csv_path: str | Path,
    database_url: str | None = None,
    *,
    category_client: MistakeCategoryClient | None = None,
) -> None:
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
            is_mistake, category = classify_mistake(
                record, category_client=category_client
            )
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
