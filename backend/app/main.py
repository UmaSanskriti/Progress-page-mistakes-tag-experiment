from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import SessionLocal, engine
from .ingest import ingest_csv
from .models import AttemptRecord, Base
from .schemas import AttemptRecordSchema, StudentSubtopicSummary, SubtopicMistakeCount

app = FastAPI(title="Progress Mistake Tag Experiment")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if not FRONTEND_DIR.exists():
    # Support running the app from within the backend package as well.
    fallback_dir = Path(__file__).resolve().parent / "frontend"
    if fallback_dir.exists():
        FRONTEND_DIR = fallback_dir

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", include_in_schema=False)
def read_root():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        return {"message": "Frontend not built yet"}
    return FileResponse(index_path)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/attempts", response_model=List[AttemptRecordSchema])
def read_attempts(
    student_id: str | None = Query(default=None, description="Filter by exact student ID"),
    subtopic_id: str | None = Query(default=None, description="Filter by subtopic/learning objective ID"),
    is_mistake: int | None = Query(default=None, ge=0, le=1, description="Filter by mistake flag"),
    db: Session = Depends(get_db),
):
    query = db.query(AttemptRecord)

    if student_id is not None:
        query = query.filter(AttemptRecord.student_id == str(student_id))
    if subtopic_id is not None:
        query = query.filter(AttemptRecord.id == str(subtopic_id))
    if is_mistake is not None:
        query = query.filter(AttemptRecord.is_mistake == is_mistake)

    query = query.order_by(AttemptRecord.answer_id)
    return [AttemptRecordSchema.model_validate(row) for row in query.all()]


@app.get("/subtopics", response_model=List[SubtopicMistakeCount])
def read_subtopic_tag_counts(
    tag: str | None = Query(default=None, description="Filter by mistake category"),
    subtopic: str | None = Query(default=None, description="Case-insensitive contains filter by subtopic name"),
    sort_by: str = Query(default="subtopic", description="Sort by subtopic, mistake_category, or count"),
    sort_dir: str = Query(default="asc", description="Sort direction asc or desc"),
    db: Session = Depends(get_db),
):
    count_expr = func.count(AttemptRecord.answer_id)

    query = (
        db.query(
            AttemptRecord.id.label("subtopic_id"),
            AttemptRecord.description.label("subtopic"),
            AttemptRecord.name.label("topic"),
            AttemptRecord.subject_name.label("subject"),
            AttemptRecord.mistake_category.label("mistake_category"),
            count_expr.label("count"),
        )
        .filter(AttemptRecord.is_mistake == 1)
    )

    if tag:
        query = query.filter(AttemptRecord.mistake_category == tag)
    if subtopic:
        query = query.filter(AttemptRecord.description.ilike(f"%{subtopic}%"))

    query = query.group_by(
        AttemptRecord.id,
        AttemptRecord.description,
        AttemptRecord.name,
        AttemptRecord.subject_name,
        AttemptRecord.mistake_category,
    )

    sort_by = sort_by.lower()
    sort_dir = sort_dir.lower()

    if sort_by not in {"subtopic", "mistake_category", "tag", "count"}:
        sort_by = "subtopic"
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "asc"

    order_column = {
        "subtopic": AttemptRecord.description,
        "mistake_category": AttemptRecord.mistake_category,
        "tag": AttemptRecord.mistake_category,
        "count": count_expr,
    }[sort_by]

    if sort_dir == "desc":
        order_column = order_column.desc()

    query = query.order_by(order_column)

    results = query.all()
    return [
        SubtopicMistakeCount(
            subtopic_id=row.subtopic_id,
            subtopic=row.subtopic,
            topic=row.topic,
            subject=row.subject,
            mistake_category=row.mistake_category,
            count=row.count,
        )
        for row in results
    ]


@app.get("/student_subtopics", response_model=List[StudentSubtopicSummary])
def read_student_subtopic_tags(
    tag: str | None = Query(default=None, description="Filter to rows that contain this mistake category"),
    subtopic: str | None = Query(default=None, description="Case-insensitive contains filter by subtopic name"),
    student_id: str | None = Query(default=None, description="Filter by exact student ID"),
    sort_by: str = Query(
        default="student",
        description="Sort by student, subtopic, category_count, tag_count, or attempts",
    ),
    sort_dir: str = Query(default="asc", description="Sort direction asc or desc"),
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            AttemptRecord.student_id,
            AttemptRecord.id.label("subtopic_id"),
            AttemptRecord.description.label("subtopic"),
            AttemptRecord.name.label("topic"),
            AttemptRecord.subject_name.label("subject"),
            AttemptRecord.answer_id.label("attempt_id"),
            AttemptRecord.mistake_category,
            AttemptRecord.is_mistake,
        )
    )

    if subtopic:
        query = query.filter(AttemptRecord.description.ilike(f"%{subtopic}%"))
    if student_id is not None:
        query = query.filter(AttemptRecord.student_id == str(student_id))

    rows = query.all()

    summaries: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (row.student_id, row.subtopic_id)
        if key not in summaries:
            summaries[key] = {
                "student_id": row.student_id,
                "subtopic_id": row.subtopic_id,
                "subtopic": row.subtopic,
                "topic": row.topic,
                "subject": row.subject,
                "mistake_categories": set(),
                "attempt_ids": set(),
            }
        entry = summaries[key]
        if row.is_mistake and row.mistake_category and row.mistake_category != "null":
            entry["mistake_categories"].add(row.mistake_category)
        entry["attempt_ids"].add(row.attempt_id)

    result_dicts = [
        {
            "student_id": entry["student_id"],
            "subtopic_id": entry["subtopic_id"],
            "subtopic": entry["subtopic"],
            "topic": entry["topic"],
            "subject": entry["subject"],
            "mistake_categories": sorted(entry["mistake_categories"]),
            "attempt_count": len(entry["attempt_ids"]),
        }
        for entry in summaries.values()
    ]

    if tag:
        result_dicts = [summary for summary in result_dicts if tag in summary["mistake_categories"]]

    sort_by = sort_by.lower()
    if sort_by not in {"student", "subtopic", "category_count", "tag_count", "attempts"}:
        sort_by = "student"

    sort_dir = sort_dir.lower()
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "asc"

    def _student_sort_value(value: str) -> tuple[int, str]:
        return (int(value), value) if value.isdigit() else (0, value)

    def sort_key(summary: dict[str, object]):
        student_value = summary.get("student_id", "")
        student_tuple = _student_sort_value(str(student_value))
        subtopic_value = (summary.get("subtopic") or "").lower()
        category_count = len(summary.get("mistake_categories", []))
        attempts = summary.get("attempt_count", 0)

        if sort_by == "student":
            return (*student_tuple, subtopic_value)
        if sort_by == "subtopic":
            return (subtopic_value, student_tuple[0], student_tuple[1])
        if sort_by in {"tag_count", "category_count"}:
            return (category_count, student_tuple[0], subtopic_value)
        if sort_by == "attempts":
            return (attempts, student_tuple[0], subtopic_value)
        return (*student_tuple, subtopic_value)

    result_dicts.sort(key=sort_key, reverse=sort_dir == "desc")

    return [StudentSubtopicSummary.model_validate(summary) for summary in result_dicts]


@app.post("/ingest")
def ingest_dataset(csv_path: str):
    ingest_csv(csv_path)
    return {"status": "ingested"}
