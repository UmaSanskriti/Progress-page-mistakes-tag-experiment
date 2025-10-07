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
from .schemas import SubtopicTagCount

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


@app.post("/ingest")
def ingest_dataset(csv_path: str):
    ingest_csv(csv_path)
    return {"status": "ingested"}
