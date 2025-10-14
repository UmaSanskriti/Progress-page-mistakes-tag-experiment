"""Lightweight configuration helpers."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    database_url: str = f"sqlite:///{Path(__file__).resolve().parents[1] / 'data' / 'app.db'}"

    def __post_init__(self) -> None:
        override = os.getenv("APP_DATABASE_URL")
        if override:
            self.database_url = override


def get_settings() -> Settings:
    return Settings()

