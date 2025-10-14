#!/usr/bin/env python3
"""Export the CSV data with an ``is_mistake`` flag for the frontend."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "Dataset - Progress page test - Sheet1.csv"
OUTPUT_PATHS = (
    ROOT / "frontend" / "data" / "student_attempts.json",
    ROOT / "docs" / "data" / "student_attempts.json",
)

# Keep the same sample of three students that power the GitHub Pages demo.
SELECTED_STUDENTS: tuple[str, ...] = ("192153", "191956", "181246")


def _to_float(value: str | None) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def derive_tags(row: dict[str, str]) -> set[str]:
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


def is_mistake(row: dict[str, str]) -> int:
    tags = derive_tags(row)
    return 1 if any(tag != "mastered" for tag in tags) else 0


def load_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        raise FileNotFoundError(path)

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]

    students_present = []
    for row in rows:
        student_id = (row.get("student_id") or "").strip()
        if student_id and student_id not in students_present:
            students_present.append(student_id)

    return rows, students_present


def add_flags(rows: Iterable[dict[str, str]]) -> list[dict[str, str | int]]:
    enriched: list[dict[str, str | int]] = []
    for row in rows:
        enriched_row = dict(row)
        enriched_row["is_mistake"] = is_mistake(row)
        enriched.append(enriched_row)
    return enriched


def main() -> None:
    rows, students_present = load_rows(DATASET_PATH)
    enriched = add_flags(rows)

    payload = {
        "selected_students": list(SELECTED_STUDENTS),
        "students_present": students_present,
        "attempts": enriched,
    }

    data = json.dumps(payload, indent=2)

    for path in OUTPUT_PATHS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        print(f"Wrote {len(enriched)} attempt rows to {path}")


if __name__ == "__main__":
    main()

