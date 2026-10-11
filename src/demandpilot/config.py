"""Configuration independent of the UI and database implementation."""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        return cls(
            host=os.getenv("POSTGRES_HOST", "db"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "demandpilot"),
            user=os.getenv("POSTGRES_USER", "demandpilot"),
            password=os.environ["POSTGRES_PASSWORD"],
        )


def load_settings(path: str | Path = "config/settings.yaml") -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)
