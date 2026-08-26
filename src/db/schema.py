"""SQLite schema definition and initialization."""
from __future__ import annotations

from src.db.connection import get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT,
    organisation_name TEXT,
    role TEXT NOT NULL CHECK (role IN ('admin', 'applicant')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS schemes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    eligibility TEXT NOT NULL DEFAULT '',
    required_documents TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    scheme_id INTEGER NOT NULL REFERENCES schemes(id),
    applicant_notes TEXT NOT NULL DEFAULT '',
    document_text TEXT NOT NULL DEFAULT '',
    document_manifest TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'under_review', 'needs_more_info', 'approved', 'rejected')),
    analysis_status TEXT NOT NULL DEFAULT 'queued'
        CHECK (analysis_status IN ('queued', 'running', 'completed', 'failed')),
    analysis_stage TEXT,
    analysis_error TEXT,
    extracted_fields TEXT,
    summary TEXT,
    validation_result TEXT,
    score REAL,
    score_explanation TEXT,
    timeline_stage TEXT NOT NULL DEFAULT 'ingesting',
    assigned_admin_id INTEGER REFERENCES users(id),
    plagiarism_result TEXT,
    validation_feedback TEXT,
    reevaluation_request TEXT,
    reevaluation_requested_at TEXT,
    raw_files TEXT,
    pasted_text TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS score_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    admin_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(submission_id, admin_id)
);

CREATE TABLE IF NOT EXISTS analysis_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    stage TEXT NOT NULL,
    event_type TEXT NOT NULL
        CHECK (event_type IN ('stage_start', 'reasoning', 'text', 'tool_call', 'stage_complete', 'error')),
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    reviewer_id INTEGER NOT NULL REFERENCES users(id),
    decision TEXT NOT NULL,
    rationale TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA)
        user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "is_active" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
        if "email" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        if "organisation_name" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN organisation_name TEXT")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(submissions)").fetchall()}
        if "document_manifest" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN document_manifest TEXT NOT NULL DEFAULT '[]'")
        if "timeline_stage" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN timeline_stage TEXT NOT NULL DEFAULT 'ingesting'")
        if "assigned_admin_id" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN assigned_admin_id INTEGER REFERENCES users(id)")
        if "plagiarism_result" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN plagiarism_result TEXT")
        if "validation_feedback" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN validation_feedback TEXT")
        if "reevaluation_request" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN reevaluation_request TEXT")
        if "reevaluation_requested_at" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN reevaluation_requested_at TEXT")
        if "raw_files" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN raw_files TEXT")
        if "pasted_text" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN pasted_text TEXT")
        conn.commit()
    finally:
        conn.close()
