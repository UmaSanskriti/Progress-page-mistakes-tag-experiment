from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    database_url: str = f"sqlite:///{Path(__file__).resolve().parents[1] / 'data' / 'app.db'}"


def get_settings() -> Settings:
    database_url = os.getenv("APP_DATABASE_URL")
    if database_url:
        return Settings(database_url=database_url)
    return Settings()
