from pathlib import Path
from pydantic import BaseSettings


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{Path(__file__).resolve().parents[1] / 'data' / 'app.db'}"

    class Config:
        env_prefix = "APP_"
        env_file = ".env"


def get_settings() -> Settings:
    return Settings()
