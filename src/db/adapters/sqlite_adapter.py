"""SQLite adapter - the default local/POC backend."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, ClassVar

from src.db.adapters.base import DatabaseAdapter
from src.db.config import REPO_ROOT, DatabaseConfig


class SQLiteAdapter(DatabaseAdapter):
    name = "sqlite"
    placeholder = "?"
    ddl_tokens: ClassVar[dict[str, str]] = {
        "pk": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "text": "TEXT",
        "int": "INTEGER",
        "float": "REAL",
        "timestamp": "TEXT",
        "now": "(datetime('now'))",
    }

    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        configured = config.get("path") or "data/app.db"
        path = Path(configured)
        self.path = path if path.is_absolute() else REPO_ROOT / path
        self.timeout = config.get_int("timeout_seconds", 30)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=self.timeout)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def existing_columns(self, connection: Any, table: str) -> set[str]:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}

    def is_duplicate_key(self, exc: BaseException) -> bool:
        return isinstance(exc, sqlite3.IntegrityError) and "unique" in str(exc).lower()
