"""Dialect-neutral schema definition and initialization.

Column types and defaults are written as tokens ({pk}, {text}, {now}, ...) that the
active adapter renders for its dialect, so a new backend needs no schema changes.
"""
from __future__ import annotations

from src.db.connection import get_adapter, get_database

_SCHEMA_TEMPLATE = """
CREATE TABLE IF NOT EXISTS users (
    id {pk},
    username {text} UNIQUE NOT NULL,
    password_hash {text} NOT NULL,
    full_name {text} NOT NULL,
    email {text},
    organisation_name {text},
    role {text} NOT NULL CHECK (role IN ('admin', 'applicant')),
    is_active {int} NOT NULL DEFAULT 1,
    created_at {timestamp} NOT NULL DEFAULT {now}
);

CREATE TABLE IF NOT EXISTS schemes (
    id {pk},
    name {text} NOT NULL,
    description {text} NOT NULL,
    eligibility {text} NOT NULL DEFAULT '',
    required_documents {text} NOT NULL DEFAULT '',
    is_active {int} NOT NULL DEFAULT 1,
    created_by {int} REFERENCES users(id),
    created_at {timestamp} NOT NULL DEFAULT {now},
    closing_date {text},
    pending_update {text},
    pending_update_by {int} REFERENCES users(id),
    pending_update_at {timestamp},
    scoring_pattern {text}
);

CREATE TABLE IF NOT EXISTS scheme_update_approvals (
    id {pk},
    scheme_id {int} NOT NULL REFERENCES schemes(id),
    admin_id {int} NOT NULL REFERENCES users(id),
    created_at {timestamp} NOT NULL DEFAULT {now},
    UNIQUE(scheme_id, admin_id)
);

CREATE TABLE IF NOT EXISTS submissions (
    id {pk},
    user_id {int} NOT NULL REFERENCES users(id),
    scheme_id {int} NOT NULL REFERENCES schemes(id),
    applicant_notes {text} NOT NULL DEFAULT '',
    document_text {text} NOT NULL DEFAULT '',
    document_manifest {text} NOT NULL DEFAULT '[]',
    status {text} NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'under_review', 'needs_more_info', 'approved', 'rejected')),
    analysis_status {text} NOT NULL DEFAULT 'queued'
        CHECK (analysis_status IN ('queued', 'running', 'completed', 'failed')),
    analysis_stage {text},
    analysis_error {text},
    extracted_fields {text},
    summary {text},
    validation_result {text},
    score {float},
    score_explanation {text},
    timeline_stage {text} NOT NULL DEFAULT 'ingesting',
    assigned_admin_id {int} REFERENCES users(id),
    plagiarism_result {text},
    validation_feedback {text},
    score_feedback {text},
    reevaluation_request {text},
    reevaluation_requested_at {timestamp},
    raw_files {text},
    pasted_text {text},
    locked_at {timestamp},
    locked_by {int} REFERENCES users(id),
    created_at {timestamp} NOT NULL DEFAULT {now},
    updated_at {timestamp} NOT NULL DEFAULT {now}
);

CREATE TABLE IF NOT EXISTS score_approvals (
    id {pk},
    submission_id {int} NOT NULL REFERENCES submissions(id),
    admin_id {int} NOT NULL REFERENCES users(id),
    created_at {timestamp} NOT NULL DEFAULT {now},
    UNIQUE(submission_id, admin_id)
);

CREATE TABLE IF NOT EXISTS analysis_events (
    id {pk},
    submission_id {int} NOT NULL REFERENCES submissions(id),
    stage {text} NOT NULL,
    event_type {text} NOT NULL
        CHECK (event_type IN ('stage_start', 'reasoning', 'text', 'tool_call', 'stage_complete', 'error')),
    content {text} NOT NULL DEFAULT '',
    created_at {timestamp} NOT NULL DEFAULT {now}
);

CREATE TABLE IF NOT EXISTS reviews (
    id {pk},
    submission_id {int} NOT NULL REFERENCES submissions(id),
    reviewer_id {int} NOT NULL REFERENCES users(id),
    decision {text} NOT NULL,
    rationale {text} NOT NULL,
    created_at {timestamp} NOT NULL DEFAULT {now}
);

CREATE TABLE IF NOT EXISTS notifications (
    id {pk},
    title {text} NOT NULL,
    message {text} NOT NULL,
    created_by {int} REFERENCES users(id),
    is_active {int} NOT NULL DEFAULT 1,
    created_at {timestamp} NOT NULL DEFAULT {now}
);
"""

# Columns added after the initial release, applied to databases created earlier.
_MIGRATIONS: dict[str, dict[str, str]] = {
    "users": {
        "is_active": "{int} NOT NULL DEFAULT 1",
        "email": "{text}",
        "organisation_name": "{text}",
    },
    "schemes": {
        "pending_update": "{text}",
        "pending_update_by": "{int} REFERENCES users(id)",
        "pending_update_at": "{timestamp}",
        "scoring_pattern": "{text}",
        "closing_date": "{text}",
    },
    "submissions": {
        "document_manifest": "{text} NOT NULL DEFAULT '[]'",
        "timeline_stage": "{text} NOT NULL DEFAULT 'ingesting'",
        "assigned_admin_id": "{int} REFERENCES users(id)",
        "plagiarism_result": "{text}",
        "validation_feedback": "{text}",
        "score_feedback": "{text}",
        "reevaluation_request": "{text}",
        "reevaluation_requested_at": "{timestamp}",
        "raw_files": "{text}",
        "pasted_text": "{text}",
        "locked_at": "{timestamp}",
        "locked_by": "{int} REFERENCES users(id)",
    },
}


def init_db() -> None:
    adapter = get_adapter()
    database = get_database()
    database.execute_script(adapter.render_ddl(_SCHEMA_TEMPLATE))

    with database.transaction() as tx:
        for table, columns in _MIGRATIONS.items():
            existing = adapter.existing_columns(tx.connection, table)
            for column, definition in columns.items():
                if column not in existing:
                    tx.execute(f"ALTER TABLE {table} ADD COLUMN {column} {adapter.render_ddl(definition)}")
