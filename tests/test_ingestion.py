from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.ingest import TAG_DEFINITIONS, derive_tags, ingest_csv
from backend.app.models import Attempt, MistakeTag, Subtopic

DATASET_PATH = Path(__file__).resolve().parents[1] / "Dataset - Progress page test - Sheet1.csv"


def test_ingest_populates_expected_counts(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"

    ingest_csv(DATASET_PATH, database_url=db_url)

    engine = create_engine(db_url, future=True)
    df = pd.read_csv(DATASET_PATH)

    with Session(engine) as session:
        attempt_total = session.scalar(select(func.count(Attempt.id)))
        assert attempt_total == len(df.index)

        tag_names = set(session.scalars(select(MistakeTag.name)))
        assert tag_names == set(TAG_DEFINITIONS.keys())

        expected_counts: dict[tuple[str, str], int] = {}
        for record in df.to_dict("records"):
            subtopic_name = str(record["description"])
            for tag in derive_tags(record):
                expected_counts[(subtopic_name, tag)] = expected_counts.get((subtopic_name, tag), 0) + 1

        rows = list(
            session.execute(
            select(Subtopic.name, MistakeTag.name, func.count(Attempt.id))
            .join(Attempt, Attempt.subtopic_id == Subtopic.id)
            .join(Attempt.tags)
            .group_by(Subtopic.name, MistakeTag.name)
        )
        )

        for subtopic_name, tag_name, count in rows:
            assert expected_counts[(subtopic_name, tag_name)] == count

        # Ensure every expected combination exists in the database
        db_pairs = {(row[0], row[1]) for row in rows}
        assert db_pairs == set(expected_counts.keys())


def test_student_subtopic_tags_match_expected(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"

    ingest_csv(DATASET_PATH, database_url=db_url)

    engine = create_engine(db_url, future=True)
    df = pd.read_csv(DATASET_PATH)

    with Session(engine) as session:
        expected: dict[tuple[int, str], set[str]] = {}
        for record in df.to_dict("records"):
            student_id = int(record["student_id"])
            subtopic_name = str(record["description"])
            key = (student_id, subtopic_name)
            expected.setdefault(key, set()).update(derive_tags(record))

        rows = list(
            session.execute(
                select(Attempt.student_id, Subtopic.name, MistakeTag.name)
                .join(Subtopic, Attempt.subtopic_id == Subtopic.id)
                .join(Attempt.tags)
            )
        )

        actual: dict[tuple[int, str], set[str]] = {}
        for student_id, subtopic_name, tag_name in rows:
            actual.setdefault((student_id, subtopic_name), set()).add(tag_name)

        assert actual == expected
