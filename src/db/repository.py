"""Repository layer: all database access lives here (parameterized queries only).

Encapsulates auth (bcrypt password hashing) and CRUD for users, schemes,
submissions, reviews, and notifications so views never touch SQL directly.
SQL is written once in a dialect-neutral form and executed through the
configured adapter (see src/db/connection.py and src/db/adapters/).
"""
from __future__ import annotations

import json

import bcrypt

from src.db.connection import get_database
from src.db.errors import DuplicateKeyError

_VALID_ROLES = {"admin", "applicant"}


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _parse_scheme_json(scheme: dict) -> dict:
    for field in ("pending_update", "scoring_pattern"):
        if isinstance(scheme.get(field), str):
            scheme[field] = json.loads(scheme[field])
    return scheme


# ---------------------------------------------------------------------------
# Users / auth
# ---------------------------------------------------------------------------

def create_user(
    username: str,
    password: str,
    full_name: str,
    role: str = "applicant",
    email: str | None = None,
    organisation_name: str | None = None,
) -> int:
    if role not in _VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")
    try:
        return get_database().insert(
            "INSERT INTO users (username, password_hash, full_name, role, email, organisation_name) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (username, _hash_password(password), full_name, role, email, organisation_name),
        )
    except DuplicateKeyError as exc:
        raise ValueError(f"Username '{username}' is already taken.") from exc


def authenticate(username: str, password: str) -> dict | None:
    user = get_database().query_one(
        "SELECT id, username, password_hash, full_name, role, is_active, email, organisation_name "
        "FROM users WHERE username = ?",
        (username,),
    )
    if user is None or not user["is_active"] or not _verify_password(password, user["password_hash"]):
        return None
    user.pop("password_hash")
    return user


def list_users(role: str | None = None) -> list[dict]:
    query = "SELECT id, username, full_name, role, is_active, email, organisation_name, created_at FROM users"
    params: tuple = ()
    if role:
        query += " WHERE role = ?"
        params = (role,)
    return get_database().query_all(f"{query} ORDER BY created_at DESC", params)


def get_user(user_id: int) -> dict | None:
    return get_database().query_one(
        "SELECT id, username, full_name, role, is_active, email, organisation_name, created_at "
        "FROM users WHERE id = ?",
        (user_id,),
    )


def count_active_admins(exclude_user_id: int | None = None) -> int:
    return get_database().query_value(
        "SELECT COUNT(*) AS c FROM users WHERE role = 'admin' AND is_active = 1 AND id != ?",
        (exclude_user_id or -1,),
    )


def set_user_active(user_id: int, is_active: bool) -> None:
    get_database().execute("UPDATE users SET is_active = ? WHERE id = ?", (int(is_active), user_id))


def reset_password(user_id: int, new_password: str) -> None:
    get_database().execute(
        "UPDATE users SET password_hash = ? WHERE id = ?", (_hash_password(new_password), user_id)
    )


# ---------------------------------------------------------------------------
# Schemes
# ---------------------------------------------------------------------------

def create_scheme(
    name: str, description: str, eligibility: str, required_documents: str, created_by: int | None
) -> int:
    return get_database().insert(
        "INSERT INTO schemes (name, description, eligibility, required_documents, created_by) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, description, eligibility, required_documents, created_by),
    )


def list_schemes(active_only: bool = True) -> list[dict]:
    query = "SELECT * FROM schemes"
    if active_only:
        query += " WHERE is_active = 1"
    rows = get_database().query_all(f"{query} ORDER BY created_at DESC")
    return [_parse_scheme_json(row) for row in rows]


def get_scheme(scheme_id: int) -> dict | None:
    row = get_database().query_one("SELECT * FROM schemes WHERE id = ?", (scheme_id,))
    return _parse_scheme_json(row) if row else None


def set_scheme_active(scheme_id: int, is_active: bool) -> None:
    get_database().execute(
        "UPDATE schemes SET is_active = ? WHERE id = ?", (int(is_active), scheme_id)
    )


def set_scheme_scoring_pattern(scheme_id: int, scoring_pattern: dict) -> None:
    get_database().execute(
        "UPDATE schemes SET scoring_pattern = ? WHERE id = ?", (json.dumps(scoring_pattern), scheme_id)
    )


def propose_scheme_update(scheme_id: int, updates: dict, admin_id: int) -> None:
    """Stage a scheme edit as a pending update (not applied yet) and reset any prior
    approvals - it needs fresh approvals from >= 2 distinct admins to take effect."""
    with get_database().transaction() as tx:
        tx.execute(
            "UPDATE schemes SET pending_update = ?, pending_update_by = ?, "
            "pending_update_at = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(updates), admin_id, scheme_id),
        )
        tx.execute("DELETE FROM scheme_update_approvals WHERE scheme_id = ?", (scheme_id,))


def add_scheme_update_approval(scheme_id: int, admin_id: int) -> int:
    """Record a distinct admin's approval of the pending scheme update; returns the
    total distinct-approval count."""
    with get_database().transaction() as tx:
        tx.insert_ignore("scheme_update_approvals", {"scheme_id": scheme_id, "admin_id": admin_id})
        return tx.query_value(
            "SELECT COUNT(*) AS c FROM scheme_update_approvals WHERE scheme_id = ?", (scheme_id,)
        )


def list_scheme_update_approvals(scheme_id: int) -> list[dict]:
    return get_database().query_all(
        "SELECT sa.*, u.full_name AS admin_name FROM scheme_update_approvals sa "
        "JOIN users u ON sa.admin_id = u.id WHERE sa.scheme_id = ? ORDER BY sa.created_at ASC",
        (scheme_id,),
    )


def apply_pending_scheme_update(scheme_id: int, updates: dict) -> None:
    """Apply an approved pending update (incl. its freshly-designed scoring pattern) to
    the live scheme fields and clear the pending-update/approval state."""
    with get_database().transaction() as tx:
        tx.execute(
            "UPDATE schemes SET name = ?, description = ?, eligibility = ?, required_documents = ?, "
            "scoring_pattern = ?, pending_update = NULL, pending_update_by = NULL, pending_update_at = NULL "
            "WHERE id = ?",
            (
                updates["name"],
                updates["description"],
                updates["eligibility"],
                updates["required_documents"],
                json.dumps(updates["scoring_pattern"]) if updates.get("scoring_pattern") else None,
                scheme_id,
            ),
        )
        tx.execute("DELETE FROM scheme_update_approvals WHERE scheme_id = ?", (scheme_id,))


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------

def _parse_submission_json(sub: dict) -> dict:
    for field in (
        "extracted_fields",
        "validation_result",
        "score_explanation",
        "document_manifest",
        "plagiarism_result",
        "raw_files",
    ):
        if isinstance(sub.get(field), str):
            sub[field] = json.loads(sub[field])
    return sub


def create_submission(user_id: int, scheme_id: int, applicant_notes: str, document_text: str) -> int:
    return get_database().insert(
        "INSERT INTO submissions (user_id, scheme_id, applicant_notes, document_text) VALUES (?, ?, ?, ?)",
        (user_id, scheme_id, applicant_notes, document_text),
    )


def update_submission_documents(submission_id: int, document_text: str, document_manifest: list[dict]) -> None:
    """Persist both legacy combined text and the structured extracted-document manifest."""
    get_database().execute(
        "UPDATE submissions SET document_text = ?, document_manifest = ?, "
        "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (document_text, json.dumps(document_manifest), submission_id),
    )


def update_submission_document_text(submission_id: int, document_text: str) -> None:
    """Backward-compatible helper for callers that only have combined text."""
    get_database().execute(
        "UPDATE submissions SET document_text = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (document_text, submission_id),
    )


def save_analysis_result(
    submission_id: int,
    extracted_fields: dict,
    summary: str,
    validation_result: dict,
    score: float,
    score_explanation: dict,
) -> None:
    """Persist the completed agentic analysis result and mark it as such."""
    get_database().execute(
        "UPDATE submissions SET extracted_fields = ?, summary = ?, validation_result = ?, "
        "score = ?, score_explanation = ?, status = 'under_review', "
        "analysis_status = 'completed', analysis_stage = 'done', analysis_error = NULL, "
        "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (
            json.dumps(extracted_fields),
            summary,
            json.dumps(validation_result),
            score,
            json.dumps(score_explanation),
            submission_id,
        ),
    )


def set_analysis_status(
    submission_id: int, analysis_status: str, stage: str | None = None, error: str | None = None
) -> None:
    """Update the in-progress analysis job's status/stage (queued/running/completed/failed)."""
    get_database().execute(
        "UPDATE submissions SET analysis_status = ?, analysis_stage = COALESCE(?, analysis_stage), "
        "analysis_error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (analysis_status, stage, error, submission_id),
    )


def append_analysis_event(submission_id: int, stage: str, event_type: str, content: str) -> None:
    """Record one step of an agent's reasoning/tool-use/output for later (or live) review."""
    get_database().execute(
        "INSERT INTO analysis_events (submission_id, stage, event_type, content) VALUES (?, ?, ?, ?)",
        (submission_id, stage, event_type, content),
    )


def list_analysis_events(submission_id: int, after_id: int = 0) -> list[dict]:
    return get_database().query_all(
        "SELECT * FROM analysis_events WHERE submission_id = ? AND id > ? ORDER BY id ASC",
        (submission_id, after_id),
    )


def get_submission(submission_id: int) -> dict | None:
    row = get_database().query_one(
        "SELECT sub.*, sc.name AS scheme_name, u.full_name AS applicant_name, "
        "u.organisation_name AS applicant_organisation, "
        "admin.full_name AS assigned_admin_name FROM submissions sub "
        "JOIN schemes sc ON sub.scheme_id = sc.id "
        "JOIN users u ON sub.user_id = u.id "
        "LEFT JOIN users admin ON sub.assigned_admin_id = admin.id "
        "WHERE sub.id = ?",
        (submission_id,),
    )
    return _parse_submission_json(row) if row else None


def list_submissions_for_user(user_id: int) -> list[dict]:
    rows = get_database().query_all(
        "SELECT sub.*, sc.name AS scheme_name, admin.full_name AS assigned_admin_name FROM submissions sub "
        "JOIN schemes sc ON sub.scheme_id = sc.id "
        "LEFT JOIN users admin ON sub.assigned_admin_id = admin.id "
        "WHERE sub.user_id = ? ORDER BY sub.created_at DESC",
        (user_id,),
    )
    return [_parse_submission_json(row) for row in rows]


def list_all_submissions(status: str | None = None) -> list[dict]:
    query = (
        "SELECT sub.*, sc.name AS scheme_name, u.full_name AS applicant_name, "
        "u.organisation_name AS applicant_organisation, "
        "admin.full_name AS assigned_admin_name FROM submissions sub "
        "JOIN schemes sc ON sub.scheme_id = sc.id "
        "JOIN users u ON sub.user_id = u.id "
        "LEFT JOIN users admin ON sub.assigned_admin_id = admin.id"
    )
    params: tuple = ()
    if status:
        query += " WHERE sub.status = ?"
        params = (status,)
    rows = get_database().query_all(f"{query} ORDER BY sub.created_at DESC", params)
    return [_parse_submission_json(row) for row in rows]


def set_timeline_stage(submission_id: int, timeline_stage: str) -> None:
    get_database().execute(
        "UPDATE submissions SET timeline_stage = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (timeline_stage, submission_id),
    )


def assign_admin(submission_id: int, admin_id: int) -> bool:
    """Claim a submission for AI-analysis oversight. Returns False if already assigned to someone else."""
    with get_database().transaction() as tx:
        row = tx.query_one("SELECT assigned_admin_id FROM submissions WHERE id = ?", (submission_id,))
        if row is None:
            return False
        if row["assigned_admin_id"] is not None and row["assigned_admin_id"] != admin_id:
            return False
        tx.execute(
            "UPDATE submissions SET assigned_admin_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (admin_id, submission_id),
        )
        return True


def save_plagiarism_result(submission_id: int, plagiarism_result: dict) -> None:
    get_database().execute(
        "UPDATE submissions SET plagiarism_result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (json.dumps(plagiarism_result), submission_id),
    )


def save_extraction_and_validation(
    submission_id: int, extracted_fields: dict, summary: str, validation_result: dict
) -> None:
    get_database().execute(
        "UPDATE submissions SET extracted_fields = ?, summary = ?, validation_result = ?, "
        "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (json.dumps(extracted_fields), summary, json.dumps(validation_result), submission_id),
    )


def save_validation_result(submission_id: int, validation_result: dict, feedback: str | None = None) -> None:
    get_database().execute(
        "UPDATE submissions SET validation_result = ?, validation_feedback = COALESCE(?, validation_feedback), "
        "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (json.dumps(validation_result), feedback, submission_id),
    )


def save_scoring_result(submission_id: int, score: float, score_explanation: dict) -> None:
    get_database().execute(
        "UPDATE submissions SET score = ?, score_explanation = ?, status = 'under_review', "
        "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (score, json.dumps(score_explanation), submission_id),
    )


def request_reevaluation(submission_id: int, details: str) -> None:
    """Record the submitting applicant's request for admins to reevaluate with changes."""
    get_database().execute(
        "UPDATE submissions SET reevaluation_request = ?, reevaluation_requested_at = CURRENT_TIMESTAMP, "
        "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (details, submission_id),
    )


def save_raw_files(submission_id: int, raw_files: list[dict], pasted_text: str) -> None:
    """Persist the manifest of originally-uploaded files (+ pasted text) so ingestion
    (including OCR) can be retried later without requiring the applicant to re-upload."""
    get_database().execute(
        "UPDATE submissions SET raw_files = ?, pasted_text = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (json.dumps(raw_files), pasted_text, submission_id),
    )


def add_score_approval(submission_id: int, admin_id: int) -> int:
    """Record a distinct admin's approval of the score; returns the total distinct-approval count."""
    with get_database().transaction() as tx:
        tx.insert_ignore("score_approvals", {"submission_id": submission_id, "admin_id": admin_id})
        return tx.query_value(
            "SELECT COUNT(*) AS c FROM score_approvals WHERE submission_id = ?", (submission_id,)
        )


def list_score_approvals(submission_id: int) -> list[dict]:
    return get_database().query_all(
        "SELECT sa.*, u.full_name AS admin_name FROM score_approvals sa "
        "JOIN users u ON sa.admin_id = u.id WHERE sa.submission_id = ? ORDER BY sa.created_at ASC",
        (submission_id,),
    )


# ---------------------------------------------------------------------------
# Reviews (audit trail) - human decisions only, never auto-finalized
# ---------------------------------------------------------------------------

def record_review(submission_id: int, reviewer_id: int, decision: str, rationale: str) -> None:
    if decision not in ("approved", "rejected", "needs_more_info"):
        raise ValueError(f"Invalid decision: {decision}")
    with get_database().transaction() as tx:
        tx.execute(
            "INSERT INTO reviews (submission_id, reviewer_id, decision, rationale) VALUES (?, ?, ?, ?)",
            (submission_id, reviewer_id, decision, rationale),
        )
        tx.execute(
            "UPDATE submissions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (decision, submission_id),
        )


def list_reviews_for_submission(submission_id: int) -> list[dict]:
    return get_database().query_all(
        "SELECT * FROM reviews WHERE submission_id = ? ORDER BY created_at ASC", (submission_id,)
    )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def create_notification(title: str, message: str, created_by: int | None) -> int:
    return get_database().insert(
        "INSERT INTO notifications (title, message, created_by) VALUES (?, ?, ?)",
        (title, message, created_by),
    )


def list_active_notifications() -> list[dict]:
    return get_database().query_all(
        "SELECT * FROM notifications WHERE is_active = 1 ORDER BY created_at DESC"
    )


def deactivate_notification(notification_id: int) -> None:
    get_database().execute(
        "UPDATE notifications SET is_active = 0 WHERE id = ?", (notification_id,)
    )
