"""Seed script to ingest the demo dataset into the local SQLite database."""

from pathlib import Path

from backend.app.ingest import ingest_csv

DATASET_PATH = Path(__file__).resolve().parents[2] / "Dataset - Progress page test - Sheet1.csv"


def main() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATASET_PATH}")
    ingest_csv(DATASET_PATH)
    print("Seed data ingested successfully")


if __name__ == "__main__":
    main()
