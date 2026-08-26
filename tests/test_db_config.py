"""Tests for the configurable, adapter-based database layer."""
from __future__ import annotations

import pytest

from src.db.adapters import (
    PostgresAdapter,
    SQLiteAdapter,
    available_adapters,
    create_adapter,
)
from src.db.adapters.base import DatabaseAdapter
from src.db.config import load_config
from src.db.connection import get_adapter, reset_adapter_cache
from src.db.schema import _SCHEMA_TEMPLATE


@pytest.fixture(autouse=True)
def clear_adapter_cache():
    reset_adapter_cache()
    yield
    reset_adapter_cache()


def test_default_backend_is_sqlite_and_path_is_env_overridable(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_DB_BACKEND", raising=False)
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "custom.db"))
    adapter = get_adapter()
    assert isinstance(adapter, SQLiteAdapter)
    assert adapter.path == tmp_path / "custom.db"


def test_backend_selection_comes_from_config(monkeypatch):
    monkeypatch.setenv("APP_DB_BACKEND", "postgres")
    monkeypatch.setenv("POSTGRES_DB", "some_db")
    config = load_config()
    assert config.backend == "postgres"
    assert config.get("database") == "some_db"
    assert isinstance(create_adapter(config), PostgresAdapter)


def test_unknown_backend_is_rejected():
    with pytest.raises(KeyError):
        load_config(backend="does-not-exist")


def test_every_registered_adapter_can_render_the_schema():
    assert {"sqlite", "postgres"} <= set(available_adapters())
    for name in available_adapters():
        adapter = create_adapter(load_config(backend=name))
        ddl = adapter.render_ddl(_SCHEMA_TEMPLATE)
        assert "{" not in ddl
        assert len(adapter.split_statements(ddl)) == 8


def test_adapters_translate_dialect_specifics():
    sqlite = create_adapter(load_config(backend="sqlite"))
    postgres = create_adapter(load_config(backend="postgres"))

    assert sqlite.prepare("SELECT 1 WHERE id = ?") == "SELECT 1 WHERE id = ?"
    assert postgres.prepare("SELECT 1 WHERE id = ?") == "SELECT 1 WHERE id = %s"
    assert sqlite.insert_ignore_sql("t", ["a"]).startswith("INSERT OR IGNORE")
    assert postgres.insert_ignore_sql("t", ["a"]).endswith("ON CONFLICT DO NOTHING")


def test_custom_adapter_only_needs_the_base_contract(tmp_path, monkeypatch):
    class MemoryAdapter(SQLiteAdapter):
        name = "memory"

    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "memory.db"))
    adapter = MemoryAdapter(load_config(backend="sqlite"))
    assert isinstance(adapter, DatabaseAdapter)
    with adapter.connect() as connection:
        connection.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        assert adapter.existing_columns(connection, "t") == {"id"}
