"""Repository layer: all SQLite access lives here (parameterized queries only).

Encapsulates auth (bcrypt password hashing) and CRUD for users, schemes,
submissions, reviews, and notifications so views never touch SQL directly.
"""
from __future__ import annotations

import json
import sqlite3

import bcrypt

from src.db.connection import get_connection

_VALID_ROLES = {"admin", "applicant"}


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


# ---------------------------------------------------------------------------
# Users / auth
# ---------------------------------------------------------------------------

def create_user(username: str, password: str, full_name: str, role: str = "applicant") -> int:
    if role not in _VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            (username, _hash_password(password), full_name, role),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Username '{username}' is already taken.") from exc
    finally:
        conn.close()


def authenticate(username: str, password: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash, full_name, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()
    if row is None or not _verify_password(password, row["password_hash"]):
        return None
    user = _row_to_dict(row)
    user.pop("password_hash")
    return user


# ---------------------------------------------------------------------------
# Schemes
# ---------------------------------------------------------------------------

def create_scheme(
    name: str, description: str, eligibility: str, required_documents: str, created_by: int | None
) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO schemes (name, description, eligibility, required_documents, created_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, description, eligibility, required_documents, created_by),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_schemes(active_only: bool = True) -> list[dict]:
    query = "SELECT * FROM schemes"
    params: tuple = ()
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY created_at DESC"
    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return [_row_to_dict(r) for r in rows]


def set_scheme_active(scheme_id: int, is_active: bool) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE schemes SET is_active = ? WHERE id = ?", (int(is_active), scheme_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------

def _parse_submission_json(sub: dict) -> dict:
    for field in ("extracted_fields", "validation_result", "score_explanation"):
        if sub.get(field):
            sub[field] = json.loads(sub[field])
    return sub


def create_submission(user_id: int, scheme_id: int, applicant_notes: str, document_text: str) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO submissions (user_id, scheme_id, applicant_notes, document_text) "
            "VALUES (?, ?, ?, ?)",
            (user_id, scheme_id, applicant_notes, document_text),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_submission_document_text(submission_id: int, document_text: str) -> None:
    """Fill in the fully-extracted document text once the (potentially slow) ingestion stage completes."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE submissions SET document_text = ?, updated_at = datetime('now') WHERE id = ?",
            (document_text, submission_id),
        )
        conn.commit()
    finally:
        conn.close()


def save_analysis_result(
    submission_id: int,
    extracted_fields: dict,
    summary: str,
    validation_result: dict,
    score: float,
    score_explanation: dict,
) -> None:
    """Persist the completed agentic analysis result and mark it as such."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE submissions SET extracted_fields = ?, summary = ?, validation_result = ?, "
            "score = ?, score_explanation = ?, status = 'under_review', "
            "analysis_status = 'completed', analysis_stage = 'done', analysis_error = NULL, "
            "updated_at = datetime('now') WHERE id = ?",
            (
                json.dumps(extracted_fields),
                summary,
                json.dumps(validation_result),
                score,
                json.dumps(score_explanation),
                submission_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def set_analysis_status(
    submission_id: int, analysis_status: str, stage: str | None = None, error: str | None = None
) -> None:
    """Update the in-progress analysis job's status/stage (queued/running/completed/failed)."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE submissions SET analysis_status = ?, analysis_stage = COALESCE(?, analysis_stage), "
            "analysis_error = ?, updated_at = datetime('now') WHERE id = ?",
            (analysis_status, stage, error, submission_id),
        )
        conn.commit()
    finally:
        conn.close()


def append_analysis_event(submission_id: int, stage: str, event_type: str, content: str) -> None:
    """Record one step of an agent's reasoning/tool-use/output for later (or live) review."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO analysis_events (submission_id, stage, event_type, content) VALUES (?, ?, ?, ?)",
            (submission_id, stage, event_type, content),
        )
        conn.commit()
    finally:
        conn.close()


def list_analysis_events(submission_id: int, after_id: int = 0) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM analysis_events WHERE submission_id = ? AND id > ? ORDER BY id ASC",
            (submission_id, after_id),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_dict(r) for r in rows]


def get_submission(submission_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
    finally:
        conn.close()
    return _parse_submission_json(_row_to_dict(row)) if row else None


def list_submissions_for_user(user_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT sub.*, sc.name AS scheme_name FROM submissions sub "
            "JOIN schemes sc ON sub.scheme_id = sc.id "
            "WHERE sub.user_id = ? ORDER BY sub.created_at DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_parse_submission_json(_row_to_dict(r)) for r in rows]


def list_all_submissions(status: str | None = None) -> list[dict]:
    query = (
        "SELECT sub.*, sc.name AS scheme_name, u.full_name AS applicant_name FROM submissions sub "
        "JOIN schemes sc ON sub.scheme_id = sc.id "
        "JOIN users u ON sub.user_id = u.id"
    )
    params: tuple = ()
    if status:
        query += " WHERE sub.status = ?"
        params = (status,)
    query += " ORDER BY sub.created_at DESC"
    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return [_parse_submission_json(_row_to_dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# Reviews (audit trail) - human decisions only, never auto-finalized
# ---------------------------------------------------------------------------

def record_review(submission_id: int, reviewer_id: int, decision: str, rationale: str) -> None:
    if decision not in ("approved", "rejected", "needs_more_info"):
        raise ValueError(f"Invalid decision: {decision}")
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO reviews (submission_id, reviewer_id, decision, rationale) VALUES (?, ?, ?, ?)",
            (submission_id, reviewer_id, decision, rationale),
        )
        conn.execute(
            "UPDATE submissions SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (decision, submission_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_reviews_for_submission(submission_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM reviews WHERE submission_id = ? ORDER BY created_at ASC",
            (submission_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def create_notification(title: str, message: str, created_by: int) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO notifications (title, message, created_by) VALUES (?, ?, ?)",
            (title, message, created_by),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_active_notifications() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE is_active = 1 ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_dict(r) for r in rows]


def deactivate_notification(notification_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE notifications SET is_active = 0 WHERE id = ?", (notification_id,))
        conn.commit()
    finally:
        conn.close()
