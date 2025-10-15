from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.ingest import classify_mistake, ingest_csv
from backend.app.models import AttemptRecord

DATASET_PATH = Path(__file__).resolve().parents[1] / "Dataset - Progress page test - Sheet1.csv"


def test_ingest_preserves_csv_and_mistake_flags(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"

    ingest_csv(DATASET_PATH, database_url=db_url)

    engine = create_engine(db_url, future=True)
    df = pd.read_csv(DATASET_PATH, dtype=str, keep_default_na=False)

    with Session(engine) as session:
        stored_count = session.scalar(select(func.count()).select_from(AttemptRecord))
        assert stored_count == len(df.index)

        records = session.query(AttemptRecord).all()
        record_map = {(record.answer_id, record.kid, record.part_id): record for record in records}

        csv_columns = [
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

        for _, csv_row in df.iterrows():
            csv_data = csv_row.to_dict()
            key = (csv_data["answer_id"], csv_data["kid"], csv_data["part_id"])
            record = record_map[key]
            for column in csv_columns:
                assert getattr(record, column) == csv_data[column]

            expected_flag, expected_category = classify_mistake(csv_data)
            assert record.is_mistake == expected_flag
            assert record.mistake_category == expected_category
            if record.is_mistake == 0:
                assert record.mistake_category == "null"


def test_attempt_lookup_filters(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"

    ingest_csv(DATASET_PATH, database_url=db_url)

    engine = create_engine(db_url, future=True)

    with Session(engine) as session:
        any_record = session.query(AttemptRecord).first()
        assert any_record is not None

        student_records = (
            session.query(AttemptRecord)
            .filter(AttemptRecord.student_id == any_record.student_id)
            .all()
        )
        assert all(record.student_id == any_record.student_id for record in student_records)

        mistake_records = (
            session.query(AttemptRecord)
            .filter(AttemptRecord.is_mistake == 1)
            .all()
        )
        assert all(record.is_mistake == 1 for record in mistake_records)
