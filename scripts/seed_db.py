"""Seed the local SQLite DB with a default admin user and sample schemes.

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

_SAMPLE_SCHEMES = [
    (
        "Green Energy Grant",
        "Funding for renewable micro-grid projects in rural communities.",
        "Registered cooperatives or NGOs operating in eligible districts.",
        "Project proposal, budget breakdown, registration certificate",
    ),
    (
        "Reforestation Support Scheme",
        "Grants for community-led reforestation and afforestation drives.",
        "Community groups with at least 2 years of prior environmental activity.",
        "Land use certificate, project plan, prior activity report",
    ),
]


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

    existing_names = {s["name"] for s in db.list_schemes(active_only=False)}
    for name, description, eligibility, docs in _SAMPLE_SCHEMES:
        if name not in existing_names:
            db.create_scheme(name, description, eligibility, docs, created_by=None)
    print("Seed complete.")


if __name__ == "__main__":
    main()
