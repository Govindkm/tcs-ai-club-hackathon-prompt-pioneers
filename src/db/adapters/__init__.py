"""Adapter registry.

Adding a backend: drop a DatabaseAdapter subclass in this package, register it
below (or call register_adapter at import time), and add a matching entry to
config/database.yaml.
"""
from __future__ import annotations

from collections.abc import Callable

from src.db.adapters.base import DatabaseAdapter
from src.db.adapters.postgres_adapter import PostgresAdapter
from src.db.adapters.sqlite_adapter import SQLiteAdapter
from src.db.config import DatabaseConfig

_REGISTRY: dict[str, Callable[[DatabaseConfig], DatabaseAdapter]] = {
    SQLiteAdapter.name: SQLiteAdapter,
    PostgresAdapter.name: PostgresAdapter,
}


def register_adapter(name: str, factory: Callable[[DatabaseConfig], DatabaseAdapter]) -> None:
    _REGISTRY[name] = factory


def available_adapters() -> list[str]:
    return sorted(_REGISTRY)


def create_adapter(config: DatabaseConfig) -> DatabaseAdapter:
    if config.adapter not in _REGISTRY:
        raise KeyError(
            f"Unknown database adapter '{config.adapter}'. Registered: {available_adapters()}"
        )
    return _REGISTRY[config.adapter](config)


__all__ = [
    "DatabaseAdapter",
    "PostgresAdapter",
    "SQLiteAdapter",
    "available_adapters",
    "create_adapter",
    "register_adapter",
]
