"""Database configuration loading for config/database.yaml.

Resolves the active backend and its options, expanding ${VAR} / ${VAR:-default}
placeholders from the environment so deployments differ by configuration only.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "database.yaml"

_ENV_PATTERN = re.compile(r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::-(?P<default>[^}]*))?\}")


@dataclass(frozen=True)
class DatabaseConfig:
    """Immutable (and hashable, so it can key an adapter cache) backend configuration."""

    backend: str
    adapter: str
    options: tuple[tuple[str, str], ...]

    def get(self, key: str, default: str | None = None) -> str | None:
        for option_key, value in self.options:
            if option_key == key:
                return value or default
        return default

    def get_int(self, key: str, default: int) -> int:
        value = self.get(key)
        try:
            return int(value) if value else default
        except ValueError:
            return default


def _expand(value):
    if isinstance(value, str):
        return _ENV_PATTERN.sub(
            lambda match: os.getenv(match.group("name")) or (match.group("default") or ""), value
        )
    if isinstance(value, dict):
        return {key: _expand(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand(item) for item in value]
    return value


@lru_cache(maxsize=8)
def _load_file(path: Path, _mtime: float) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_config(backend: str | None = None, path: Path | None = None) -> DatabaseConfig:
    """Resolve the active backend's configuration; env vars are re-read on every call."""
    config_path = path or CONFIG_PATH
    raw = _expand(_load_file(config_path, config_path.stat().st_mtime))
    backends = raw.get("backends") or {}
    name = backend or raw.get("default_backend") or "sqlite"

    if name not in backends:
        raise KeyError(f"Backend '{name}' is not defined in {config_path}. Known: {sorted(backends)}")

    options = {key: str(value) for key, value in (backends[name] or {}).items() if key != "adapter"}
    return DatabaseConfig(
        backend=name,
        adapter=str(backends[name].get("adapter", name)),
        options=tuple(sorted(options.items())),
    )
