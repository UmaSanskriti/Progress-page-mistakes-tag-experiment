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
from .models import Attempt, MistakeTag, Subtopic, attempt_mistake_tags, Base
from .schemas import StudentSubtopicSummary, SubtopicTagCount

app = FastAPI(title="Progress Mistake Tag Experiment")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"

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


@app.get("/subtopics", response_model=List[SubtopicTagCount])
def read_subtopic_tag_counts(
    tag: str | None = Query(default=None, description="Filter by tag name"),
    subtopic: str | None = Query(default=None, description="Case-insensitive contains filter by subtopic name"),
    sort_by: str = Query(default="subtopic", description="Sort by subtopic, tag, or count"),
    sort_dir: str = Query(default="asc", description="Sort direction asc or desc"),
    db: Session = Depends(get_db),
):
    count_expr = func.count(Attempt.id)

    query = (
        db.query(
            Subtopic.id.label("subtopic_id"),
            Subtopic.name.label("subtopic"),
            Subtopic.topic_name.label("topic"),
            Subtopic.subject_name.label("subject"),
            MistakeTag.name.label("tag"),
            count_expr.label("count"),
        )
        .join(Attempt, Attempt.subtopic_id == Subtopic.id)
        .join(attempt_mistake_tags, attempt_mistake_tags.c.attempt_id == Attempt.id)
        .join(MistakeTag, MistakeTag.id == attempt_mistake_tags.c.mistake_tag_id)
    )

    if tag:
        query = query.filter(MistakeTag.name == tag)
    if subtopic:
        query = query.filter(Subtopic.name.ilike(f"%{subtopic}%"))

    query = query.group_by(Subtopic.id, Subtopic.name, Subtopic.topic_name, Subtopic.subject_name, MistakeTag.name)

    sort_by = sort_by.lower()
    sort_dir = sort_dir.lower()

    if sort_by not in {"subtopic", "tag", "count"}:
        sort_by = "subtopic"
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "asc"

    order_column = {
        "subtopic": Subtopic.name,
        "tag": MistakeTag.name,
        "count": count_expr,
    }[sort_by]

    if sort_dir == "desc":
        order_column = order_column.desc()

    query = query.order_by(order_column)

    results = query.all()
    return [
        SubtopicTagCount(
            subtopic_id=row.subtopic_id,
            subtopic=row.subtopic,
            topic=row.topic,
            subject=row.subject,
            tag=row.tag,
            count=row.count,
        )
        for row in results
    ]


@app.get("/student_subtopics", response_model=List[StudentSubtopicSummary])
def read_student_subtopic_tags(
    tag: str | None = Query(default=None, description="Filter to rows that contain this tag"),
    subtopic: str | None = Query(default=None, description="Case-insensitive contains filter by subtopic name"),
    student_id: int | None = Query(default=None, description="Filter by exact student ID"),
    sort_by: str = Query(
        default="student",
        description="Sort by student, subtopic, tag_count, or attempts",
    ),
    sort_dir: str = Query(default="asc", description="Sort direction asc or desc"),
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            Attempt.student_id,
            Subtopic.id.label("subtopic_id"),
            Subtopic.name.label("subtopic"),
            Subtopic.topic_name.label("topic"),
            Subtopic.subject_name.label("subject"),
            MistakeTag.name.label("tag"),
            Attempt.id.label("attempt_id"),
        )
        .join(Subtopic, Attempt.subtopic_id == Subtopic.id)
        .join(attempt_mistake_tags, attempt_mistake_tags.c.attempt_id == Attempt.id)
        .join(MistakeTag, MistakeTag.id == attempt_mistake_tags.c.mistake_tag_id)
    )

    if subtopic:
        query = query.filter(Subtopic.name.ilike(f"%{subtopic}%"))
    if student_id is not None:
        query = query.filter(Attempt.student_id == student_id)

    rows = query.all()

    summaries: dict[tuple[int, int], dict[str, object]] = {}
    for row in rows:
        key = (row.student_id, row.subtopic_id)
        if key not in summaries:
            summaries[key] = {
                "student_id": row.student_id,
                "subtopic_id": row.subtopic_id,
                "subtopic": row.subtopic,
                "topic": row.topic,
                "subject": row.subject,
                "tags": set(),
                "attempt_ids": set(),
            }
        entry = summaries[key]
        if row.tag:
            entry["tags"].add(row.tag)
        entry["attempt_ids"].add(row.attempt_id)

    results = [
        StudentSubtopicSummary(
            student_id=entry["student_id"],
            subtopic_id=entry["subtopic_id"],
            subtopic=entry["subtopic"],
            topic=entry["topic"],
            subject=entry["subject"],
            tags=sorted(entry["tags"]),
            attempt_count=len(entry["attempt_ids"]),
        )
        for entry in summaries.values()
    ]

    if tag:
        results = [summary for summary in results if tag in summary.tags]

    sort_by = sort_by.lower()
    if sort_by not in {"student", "subtopic", "tag_count", "attempts"}:
        sort_by = "student"

    sort_dir = sort_dir.lower()
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "asc"

    def sort_key(summary: StudentSubtopicSummary):
        if sort_by == "student":
            return (summary.student_id, summary.subtopic.lower())
        if sort_by == "subtopic":
            return (summary.subtopic.lower(), summary.student_id)
        if sort_by == "tag_count":
            return (len(summary.tags), summary.student_id, summary.subtopic.lower())
        if sort_by == "attempts":
            return (summary.attempt_count, summary.student_id, summary.subtopic.lower())
        return (summary.student_id, summary.subtopic.lower())

    results.sort(key=sort_key, reverse=sort_dir == "desc")

    return results


@app.post("/ingest")
def ingest_dataset(csv_path: str):
    ingest_csv(csv_path)
    return {"status": "ingested"}
