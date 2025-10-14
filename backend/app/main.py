from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .database import SessionLocal, engine
from .ingest import ingest_csv
from .models import AttemptRecord, Base, to_serialisable
from .schemas import AttemptRecordSchema

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


def _apply_filters(
    query: Iterable[AttemptRecord],
    student_id: str | None,
    only_mistakes: bool,
) -> List[AttemptRecord]:
    results: List[AttemptRecord] = []
    for record in query:
        if student_id and record.student_id != student_id:
            continue
        if only_mistakes and record.is_mistake != 1:
            continue
        results.append(record)
    return results


@app.get("/attempts", response_model=List[AttemptRecordSchema])
def read_attempts(
    student_id: str | None = Query(default=None, description="Filter by student ID"),
    mistakes_only: bool = Query(default=True, description="Return only mistake attempts"),
    db: Session = Depends(get_db),
):
    records = db.query(AttemptRecord).order_by(AttemptRecord.student_id, AttemptRecord.answer_id).all()
    filtered = _apply_filters(records, student_id=student_id, only_mistakes=mistakes_only)
    return to_serialisable(filtered)


@app.post("/ingest")
def ingest_dataset(csv_path: str):
    ingest_csv(csv_path)
    return {"status": "ingested"}

