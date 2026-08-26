"""Adapter contract every database backend implements.

The repository writes one dialect-neutral SQL string; the adapter owns the
per-database differences: connection handling, parameter style, DDL types,
auto-increment ids, upserts, column introspection, and error translation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from src.db.config import DatabaseConfig
from src.db.errors import DuplicateKeyError

# Tokens used by the schema template in src/db/schema.py. Every adapter supplies a
# concrete SQL fragment for each one.
DDL_TOKENS = ("pk", "text", "int", "float", "timestamp", "now")


class DatabaseAdapter(ABC):
    """Base class for database backends."""

    name: ClassVar[str]
    placeholder: ClassVar[str] = "?"
    ddl_tokens: ClassVar[dict[str, str]] = {}

    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config

    # -- connection ---------------------------------------------------------

    @abstractmethod
    def connect(self) -> Any:
        """Open a new DB-API connection with dict-like row access enabled."""

    # -- schema -------------------------------------------------------------

    @abstractmethod
    def existing_columns(self, connection: Any, table: str) -> set[str]:
        """Return the column names currently defined for `table` (empty if absent)."""

    def render_ddl(self, ddl: str) -> str:
        missing = [token for token in DDL_TOKENS if token not in self.ddl_tokens]
        if missing:
            raise NotImplementedError(f"{type(self).__name__} is missing DDL tokens: {missing}")
        return ddl.format(**self.ddl_tokens)

    def split_statements(self, script: str) -> list[str]:
        return [statement.strip() for statement in script.split(";") if statement.strip()]

    # -- statements ---------------------------------------------------------

    def prepare(self, sql: str) -> str:
        """Translate neutral SQL (which uses `?` placeholders) into this dialect."""
        if self.placeholder == "?":
            return sql
        return sql.replace("?", self.placeholder)

    def insert_ignore_sql(self, table: str, columns: list[str]) -> str:
        """Insert that silently skips rows violating a unique constraint."""
        values = ", ".join(self.placeholder for _ in columns)
        return f"INSERT OR IGNORE INTO {table} ({', '.join(columns)}) VALUES ({values})"

    def insert(self, cursor: Any, sql: str, params: tuple) -> int:
        """Execute an INSERT and return the generated primary key."""
        cursor.execute(self.prepare(sql), params)
        return cursor.lastrowid

    def row_to_dict(self, row: Any) -> dict:
        return dict(row)

    # -- errors -------------------------------------------------------------

    @abstractmethod
    def is_duplicate_key(self, exc: BaseException) -> bool:
        """True when `exc` is this driver's unique-constraint violation."""

    def translate_error(self, exc: BaseException) -> BaseException:
        if self.is_duplicate_key(exc):
            return DuplicateKeyError(str(exc))
        return exc
