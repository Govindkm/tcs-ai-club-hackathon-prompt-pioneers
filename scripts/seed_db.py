"""Seed the local SQLite DB with a default admin user.

Run once before demoing: python scripts/seed_db.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python scripts/seed_db.py` from any cwd (adds repo root to sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db import repository as db
from src.db.schema import init_db

_DEFAULT_ADMIN_PASSWORD = "ChangeMe123!"

def main() -> None:
    init_db()

    try:
        db.create_user(
            username="admin", password=_DEFAULT_ADMIN_PASSWORD, full_name="Platform Admin", role="admin"
        )
        print(f"Created default admin user (username: admin / password: {_DEFAULT_ADMIN_PASSWORD}).")
        print("Change this password by re-registering an admin account for real use.")
    except ValueError:
        print("Admin user already exists, skipping.")

    print("Seed complete. No schemes were created; add schemes through the system before submitting applications.")


if __name__ == "__main__":
    main()
