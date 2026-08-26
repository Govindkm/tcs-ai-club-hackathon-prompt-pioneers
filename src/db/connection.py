"""Backend-neutral database access used by the repository layer.

`get_database()` resolves the backend from config/database.yaml (env-overridable
via APP_DB_BACKEND) and returns a facade whose `query_*`/`execute`/`insert`
helpers hide connection handling and dialect differences behind the adapter.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.db.adapters import DatabaseAdapter, create_adapter
from src.db.config import DatabaseConfig, load_config

_ADAPTERS: dict[DatabaseConfig, DatabaseAdapter] = {}


def get_adapter(backend: str | None = None) -> DatabaseAdapter:
    """Return the adapter for the configured backend (cached per resolved config)."""
    config = load_config(backend)
    if config not in _ADAPTERS:
        _ADAPTERS[config] = create_adapter(config)
    return _ADAPTERS[config]


def reset_adapter_cache() -> None:
    _ADAPTERS.clear()


class Transaction:
    """Statement helpers bound to one open connection, committed by `Database.transaction`."""

    def __init__(self, adapter: DatabaseAdapter, connection: Any) -> None:
        self._adapter = adapter
        self._connection = connection

    @property
    def connection(self) -> Any:
        return self._connection

    def _cursor(self, sql: str, params: tuple):
        cursor = self._connection.cursor()
        cursor.execute(self._adapter.prepare(sql), params)
        return cursor

    def execute(self, sql: str, params: tuple = ()) -> None:
        self._cursor(sql, params).close()

    def insert(self, sql: str, params: tuple = ()) -> int:
        cursor = self._connection.cursor()
        try:
            return self._adapter.insert(cursor, sql, params)
        finally:
            cursor.close()

    def insert_ignore(self, table: str, values: dict) -> None:
        columns = list(values)
        self.execute(
            self._adapter.insert_ignore_sql(table, columns), tuple(values[column] for column in columns)
        )

    def query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        cursor = self._cursor(sql, params)
        try:
            return [self._adapter.row_to_dict(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def query_one(self, sql: str, params: tuple = ()) -> dict | None:
        cursor = self._cursor(sql, params)
        try:
            row = cursor.fetchone()
        finally:
            cursor.close()
        return self._adapter.row_to_dict(row) if row is not None else None

    def query_value(self, sql: str, params: tuple = (), column: str = "c", default: Any = None) -> Any:
        row = self.query_one(sql, params)
        return default if row is None else row[column]


class Database:
    """Connection-per-operation facade over a `DatabaseAdapter`."""

    def __init__(self, adapter: DatabaseAdapter) -> None:
        self.adapter = adapter

    @contextmanager
    def transaction(self) -> Iterator[Transaction]:
        connection = self.adapter.connect()
        try:
            yield Transaction(self.adapter, connection)
            connection.commit()
        except BaseException as exc:
            connection.rollback()
            translated = self.adapter.translate_error(exc)
            if translated is not exc:
                raise translated from exc
            raise
        finally:
            connection.close()

    def execute(self, sql: str, params: tuple = ()) -> None:
        with self.transaction() as tx:
            tx.execute(sql, params)

    def insert(self, sql: str, params: tuple = ()) -> int:
        with self.transaction() as tx:
            return tx.insert(sql, params)

    def insert_ignore(self, table: str, values: dict) -> None:
        with self.transaction() as tx:
            tx.insert_ignore(table, values)

    def query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.transaction() as tx:
            return tx.query_all(sql, params)

    def query_one(self, sql: str, params: tuple = ()) -> dict | None:
        with self.transaction() as tx:
            return tx.query_one(sql, params)

    def query_value(self, sql: str, params: tuple = (), column: str = "c", default: Any = None) -> Any:
        with self.transaction() as tx:
            return tx.query_value(sql, params, column=column, default=default)

    def execute_script(self, script: str) -> None:
        with self.transaction() as tx:
            for statement in self.adapter.split_statements(script):
                tx.execute(statement)


def get_database(backend: str | None = None) -> Database:
    return Database(get_adapter(backend))


def get_connection() -> Any:
    """Raw DB-API connection for the configured backend (prefer `get_database()`)."""
    return get_adapter().connect()


def get_db_path() -> Path | None:
    """Filesystem path of a file-backed backend, or None for server-backed ones."""
    return getattr(get_adapter(), "path", None)
