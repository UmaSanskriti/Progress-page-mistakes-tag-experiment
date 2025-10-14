#!/usr/bin/env python3
"""Generate aggregated mistake tag data for three students."""
from __future__ import annotations

import csv
import html
import json
import pathlib
import re
from collections import OrderedDict, defaultdict

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

TAG_CLEANER = re.compile(r"<[^>]+>")


def _to_float(value: str | None) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def clean_html(value: str | None) -> str:
    """Convert the HTML snippets in the CSV into legible plain text."""

    if not value:
        return ""
    stripped = TAG_CLEANER.sub(" ", value)
    stripped = html.unescape(stripped)
    return re.sub(r"\s+", " ", stripped).strip()


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


def is_mistake_attempt(tags: set[str]) -> bool:
    return any(tag != "mastered" for tag in tags)


def determine_skill_label(total_awarded: float, total_available: float) -> dict[str, object]:
    """Turn marks into a coarse skill descriptor."""

    if total_available <= 0:
        return {"label": "No data", "accuracy": None}

    ratio = 0.0 if total_available == 0 else max(0.0, min(1.0, total_awarded / total_available))

    if ratio >= 0.8:
        label = "Advanced"
    elif ratio >= 0.5:
        label = "Proficient"
    else:
        label = "Developing"

    return {"label": label, "accuracy": round(ratio * 100, 1)}


def main() -> None:
    if not DATASET_PATH.exists():
        raise SystemExit(f"Dataset not found: {DATASET_PATH}")

    students_seen: "OrderedDict[str, None]" = OrderedDict()
    student_topics: dict[str, dict[tuple[str, str], dict[str, object]]] = defaultdict(
        lambda: defaultdict(
            lambda: {
                "subject": "",
                "topic": "",
                "questions_attempted": 0,
                "mistake_attempts": 0,
                "marks_available": 0.0,
                "marks_awarded": 0.0,
                "subtopics": defaultdict(
                    lambda: {
                        "subtopic_id": 0,
                        "subtopic": "",
                        "attempt_count": 0,
                        "tags": defaultdict(
                            lambda: {"tag": "", "count": 0, "questions": []}
                        ),
                    }
                ),
            }
        )
    )

    with DATASET_PATH.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            student_id = (row.get("student_id") or "").strip()
            if not student_id:
                continue

            students_seen.setdefault(student_id, None)
            if student_id not in SELECTED_STUDENTS:
                continue

            subject = (row.get("subject_name") or "").strip()
            topic_name = (row.get("name") or "").strip()
            subtopic_id_raw = (row.get("id") or "0").strip()
            subtopic_name = (row.get("description") or "").strip()

            topic_entry = student_topics[student_id][(subject, topic_name)]
            topic_entry["subject"] = subject
            topic_entry["topic"] = topic_name
            topic_entry["questions_attempted"] += 1

            mark = _to_float(row.get("mark"))
            mark_awarded = _to_float(row.get("mark_awarded"))
            if mark > 0:
                topic_entry["marks_available"] += mark
                topic_entry["marks_awarded"] += min(mark_awarded, mark)

            tags_all = derive_tags(row)
            mistake_tags = {tag for tag in tags_all if tag != "mastered"}
            if is_mistake_attempt(tags_all):
                topic_entry["mistake_attempts"] += 1

            subtopic_entry = topic_entry["subtopics"][subtopic_id_raw]
            subtopic_entry["subtopic_id"] = int(subtopic_id_raw or 0)
            subtopic_entry["subtopic"] = subtopic_name
            subtopic_entry["attempt_count"] += 1

            if not mistake_tags:
                continue

            prompt_primary = clean_html(row.get("q_text"))
            prompt_secondary = clean_html(row.get("q_text1"))
            if prompt_primary and prompt_secondary and prompt_secondary != prompt_primary:
                prompt = f"{prompt_primary} {prompt_secondary}".strip()
            else:
                prompt = prompt_primary or prompt_secondary

            question_data = {
                "answer_id": (row.get("answer_id") or "").strip(),
                "part_id": (row.get("part_id") or "").strip(),
                "prompt": prompt,
                "student_answer": clean_html(row.get("answer")),
                "mark": mark,
                "mark_awarded": mark_awarded,
                "student_score": _to_float(row.get("student_score")),
                "is_mistake": True,
            }

            for tag in mistake_tags:
                tag_entry = subtopic_entry["tags"][tag]
                tag_entry["tag"] = tag
                tag_entry["count"] += 1
                tag_entry["questions"].append(question_data)

    output = {
        "selected_students": list(SELECTED_STUDENTS),
        "students_present": list(students_seen.keys()),
        "students": [],
    }

    for student_id in SELECTED_STUDENTS:
        topics = student_topics.get(student_id)
        if not topics:
            continue

        topic_payload = []
        for (subject, topic_name), topic_entry in sorted(
            topics.items(), key=lambda item: (item[0][0], item[0][1].lower())
        ):
            subtopics_payload = []
            for subtopic_id, subtopic_entry in sorted(
                topic_entry["subtopics"].items(),
                key=lambda item: item[1]["subtopic"].lower(),
            ):
                tags_payload = [
                    {
                        "tag": tag_entry["tag"],
                        "count": tag_entry["count"],
                        "questions": tag_entry["questions"],
                    }
                    for tag_entry in sorted(
                        subtopic_entry["tags"].values(),
                        key=lambda info: (-info["count"], info["tag"]),
                    )
                ]

                subtopics_payload.append(
                    {
                        "subtopic_id": subtopic_entry["subtopic_id"],
                        "subtopic": subtopic_entry["subtopic"],
                        "attempt_count": subtopic_entry["attempt_count"],
                        "tags": tags_payload,
                    }
                )

            skill = determine_skill_label(
                topic_entry["marks_awarded"], topic_entry["marks_available"]
            )

            topic_payload.append(
                {
                    "subject": subject,
                    "topic": topic_name,
                    "skill": skill,
                    "questions_attempted": topic_entry["questions_attempted"],
                    "mistake_attempts": topic_entry["mistake_attempts"],
                    "subtopics": subtopics_payload,
                }
            )

        output["students"].append(
            {
                "student_id": int(student_id),
                "topics": topic_payload,
            }
        )

    payload = json.dumps(output, indent=2)

    for output_path in OUTPUT_PATHS:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
        print(
            f"Wrote topic profiles for {len(output['students'])} students to {output_path}"
        )


if __name__ == "__main__":
    main()
