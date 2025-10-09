#!/usr/bin/env python3
"""Generate aggregated mistake tag data for three students."""
from __future__ import annotations

import csv
import json
import pathlib
from collections import Counter, defaultdict, OrderedDict

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "Dataset - Progress page test - Sheet1.csv"
# Locations that should receive the generated dataset. We keep a copy under
# `frontend/` for local development and another under `docs/` so that GitHub
# Pages can serve the JSON alongside the static site.
OUTPUT_PATHS = (
    ROOT / "frontend" / "data" / "three_student_mistake_summary.json",
    ROOT / "docs" / "data" / "three_student_mistake_summary.json",
)

# Select the first three students that appear in the dataset.
SELECTED_STUDENTS: tuple[str, ...] = ("192153", "191956", "181246")


def _to_float(value: str | None) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def derive_tags(row: dict[str, str]) -> set[str]:
    """Replicate the tagging heuristics defined in backend.app.ingest."""

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


def main() -> None:
    if not DATASET_PATH.exists():
        raise SystemExit(f"Dataset not found: {DATASET_PATH}")

    subtopic_meta: dict[str, dict[str, str]] = {}
    overall_counts: dict[str, Counter] = defaultdict(Counter)
    per_student_counts: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    attempt_counts: dict[str, int] = defaultdict(int)
    students_seen: "OrderedDict[str, None]" = OrderedDict()

    with DATASET_PATH.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            student_id = row["student_id"].strip()
            students_seen.setdefault(student_id, None)
            if student_id not in SELECTED_STUDENTS:
                continue

            mark = _to_float(row.get("mark"))
            mark_awarded = _to_float(row.get("mark_awarded"))

            # Only consider incorrect attempts where the student did not receive full marks.
            if mark_awarded >= mark and mark > 0:
                continue

            subtopic_id = row["id"].strip()
            subtopic_meta.setdefault(
                subtopic_id,
                {
                    "subject": row.get("subject_name", "").strip(),
                    "topic": row.get("name", "").strip(),
                    "subtopic": row.get("description", "").strip(),
                },
            )

            tags = {
                tag
                for tag in derive_tags(row)
                if tag != "mastered"  # Guard against edge cases when mark is zero.
            }

            if not tags:
                continue

            overall_counts[subtopic_id].update(tags)
            per_student_counts[subtopic_id][student_id].update(tags)
            attempt_counts[subtopic_id] += 1

    sorted_subtopics = sorted(
        overall_counts.keys(),
        key=lambda sid: (subtopic_meta[sid]["subject"], subtopic_meta[sid]["topic"], subtopic_meta[sid]["subtopic"].lower()),
    )

    output = {
        "selected_students": list(SELECTED_STUDENTS),
        "students_present": list(students_seen.keys()),
        "subtopics": [],
    }

    for subtopic_id in sorted_subtopics:
        meta = subtopic_meta[subtopic_id]
        tag_counts = overall_counts[subtopic_id]
        student_counts = per_student_counts[subtopic_id]

        output["subtopics"].append(
            {
                "subtopic_id": int(subtopic_id),
                "subject": meta["subject"],
                "topic": meta["topic"],
                "subtopic": meta["subtopic"],
                "attempts_considered": attempt_counts[subtopic_id],
                "tag_counts": [
                    {"tag": tag, "count": tag_counts[tag]}
                    for tag in sorted(tag_counts.keys())
                ],
                "students": [
                    {
                        "student_id": int(student_id),
                        "tag_counts": [
                            {"tag": tag, "count": counts[tag]}
                            for tag in sorted(counts.keys())
                        ],
                    }
                    for student_id, counts in sorted(student_counts.items())
                ],
            }
        )

    payload = json.dumps(output, indent=2)

    for output_path in OUTPUT_PATHS:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
        print(
            f"Wrote aggregated data for {len(output['subtopics'])} subtopics to {output_path}"
        )


if __name__ == "__main__":
    main()
