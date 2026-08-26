"""Backend-neutral database exceptions.

Adapters translate driver-specific errors into these so the repository layer
never imports a driver module.
"""
from __future__ import annotations


class DatabaseError(RuntimeError):
    """Any failure raised by the database layer."""


class DuplicateKeyError(DatabaseError):
    """A unique or primary key constraint was violated."""
