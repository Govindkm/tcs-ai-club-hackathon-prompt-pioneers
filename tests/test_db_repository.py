"""Tests for the SQLite repository layer, using an isolated temp DB per test."""
from __future__ import annotations

import pytest

from src.db import repository as db
from src.db.schema import init_db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    yield


def test_create_user_and_authenticate():
    db.create_user(username="alice", password="Sup3rSecret!", full_name="Alice A", role="applicant")
    user = db.authenticate("alice", "Sup3rSecret!")
    assert user is not None
    assert user["role"] == "applicant"
    assert "password_hash" not in user


def test_authenticate_rejects_wrong_password():
    db.create_user(username="bob", password="Sup3rSecret!", full_name="Bob B", role="applicant")
    assert db.authenticate("bob", "wrong-password") is None


def test_duplicate_username_rejected():
    db.create_user(username="carol", password="Sup3rSecret!", full_name="Carol C", role="applicant")
    with pytest.raises(ValueError):
        db.create_user(username="carol", password="OtherPass1!", full_name="Carol Dup", role="applicant")


def test_submission_lifecycle_and_user_isolation():
    applicant_id = db.create_user(username="dave", password="Sup3rSecret!", full_name="Dave D", role="applicant")
    other_id = db.create_user(username="erin", password="Sup3rSecret!", full_name="Erin E", role="applicant")
    admin_id = db.create_user(username="admin1", password="Sup3rSecret!", full_name="Admin One", role="admin")
    scheme_id = db.create_scheme("Test Scheme", "desc", "elig", "docs", created_by=admin_id)

    submission_id = db.create_submission(applicant_id, scheme_id, "notes", "Rs. 1,000 on 01/01/2025")

    assert len(db.list_submissions_for_user(applicant_id)) == 1
    assert len(db.list_submissions_for_user(other_id)) == 0  # cannot see others' submissions

    db.save_auto_analysis(
        submission_id,
        extracted_fields={"amounts_found": ["1,000"]},
        summary="Test summary.",
        validation_result={"is_complete": True, "requires_human_review": False},
        score=0.6,
        score_explanation={"weights": {"completeness": 0.6, "risk": 0.4}},
    )
    updated = db.get_submission(submission_id)
    assert updated["status"] == "under_review"
    assert updated["score"] == 0.6
    assert updated["extracted_fields"] == {"amounts_found": ["1,000"]}

    db.record_review(submission_id, admin_id, "approved", "Meets all criteria")
    final = db.get_submission(submission_id)
    assert final["status"] == "approved"
    reviews = db.list_reviews_for_submission(submission_id)
    assert len(reviews) == 1
    assert reviews[0]["decision"] == "approved"


def test_notifications_created_and_listed():
    admin_id = db.create_user(username="admin2", password="Sup3rSecret!", full_name="Admin Two", role="admin")
    db.create_notification("Deadline extended", "Applications now close Dec 31.", admin_id)
    notes = db.list_active_notifications()
    assert len(notes) == 1
    assert notes[0]["title"] == "Deadline extended"

    db.deactivate_notification(notes[0]["id"])
    assert db.list_active_notifications() == []
