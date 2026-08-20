"""SQLite connection helper.

DB path is overridable via APP_DB_PATH so tests can point at an isolated
temp file instead of the real local database.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "app.db"


def get_db_path() -> Path:
    override = os.getenv("APP_DB_PATH")
    return Path(override) if override else _DEFAULT_DB_PATH


def get_connection() -> sqlite3.Connection:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
