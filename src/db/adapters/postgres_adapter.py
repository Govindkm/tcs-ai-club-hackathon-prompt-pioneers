"""PostgreSQL adapter (psycopg 3).

Registered but optional: `pip install "psycopg[binary]"` and set
APP_DB_BACKEND=postgres to use it. Serves as the reference implementation for
adding further backends - only this file plus a config/database.yaml entry are
needed, no repository or schema changes.
"""
from __future__ import annotations

from typing import Any, ClassVar

from src.db.adapters.base import DatabaseAdapter
from src.db.config import DatabaseConfig
from src.db.errors import DatabaseError


class PostgresAdapter(DatabaseAdapter):
    name = "postgres"
    placeholder = "%s"
    ddl_tokens: ClassVar[dict[str, str]] = {
        "pk": "SERIAL PRIMARY KEY",
        "text": "TEXT",
        "int": "INTEGER",
        "float": "DOUBLE PRECISION",
        "timestamp": "TIMESTAMP",
        "now": "CURRENT_TIMESTAMP",
    }

    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.dsn = config.get("dsn") or None
        self.connection_kwargs = {
            "host": config.get("host", "localhost"),
            "port": config.get_int("port", 5432),
            "dbname": config.get("database", "prompt_pioneers"),
            "user": config.get("user", "postgres"),
            "password": config.get("password", ""),
            "sslmode": config.get("sslmode", "prefer"),
        }

    def _driver(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise DatabaseError(
                "The postgres backend requires psycopg: pip install \"psycopg[binary]\""
            ) from exc
        return psycopg, dict_row

    def connect(self) -> Any:
        psycopg, dict_row = self._driver()
        if self.dsn:
            return psycopg.connect(self.dsn, row_factory=dict_row)
        return psycopg.connect(row_factory=dict_row, **self.connection_kwargs)

    def existing_columns(self, connection: Any, table: str) -> set[str]:
        rows = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = %s",
            (table,),
        ).fetchall()
        return {row["column_name"] for row in rows}

    def insert_ignore_sql(self, table: str, columns: list[str]) -> str:
        values = ", ".join(self.placeholder for _ in columns)
        return (
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({values}) ON CONFLICT DO NOTHING"
        )

    def insert(self, cursor: Any, sql: str, params: tuple) -> int:
        cursor.execute(f"{self.prepare(sql)} RETURNING id", params)
        return cursor.fetchone()["id"]

    def is_duplicate_key(self, exc: BaseException) -> bool:
        psycopg, _ = self._driver()
        return isinstance(exc, psycopg.errors.UniqueViolation)
