"""Small PostgreSQL connection and schema helpers."""

from dataclasses import asdict
from pathlib import Path

import psycopg

from demandpilot.config import DatabaseConfig


def connect() -> psycopg.Connection:
    return psycopg.connect(**asdict(DatabaseConfig.from_env()), connect_timeout=10)


def initialize_schema(path: str | Path = "sql/schema.sql") -> None:
    with connect() as connection:
        connection.execute(Path(path).read_text(encoding="utf-8"))


def check_database() -> str:
    with connect() as connection:
        return connection.execute("SELECT version()").fetchone()[0]
