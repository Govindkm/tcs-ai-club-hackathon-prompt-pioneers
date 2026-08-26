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


def test_deactivated_user_cannot_authenticate():
    user_id = db.create_user(username="frank", password="Sup3rSecret!", full_name="Frank F", role="applicant")
    db.set_user_active(user_id, False)
    assert db.authenticate("frank", "Sup3rSecret!") is None
    db.set_user_active(user_id, True)
    assert db.authenticate("frank", "Sup3rSecret!") is not None


def test_list_and_get_users_exclude_password_hash():
    db.create_user(username="gina", password="Sup3rSecret!", full_name="Gina G", role="applicant")
    users = db.list_users()
    assert len(users) == 1
    assert "password_hash" not in users[0]
    fetched = db.get_user(users[0]["id"])
    assert fetched["username"] == "gina"


def test_count_active_admins_excludes_given_user_and_inactive():
    admin1 = db.create_user(username="admin_a", password="Sup3rSecret!", full_name="Admin A", role="admin")
    admin2 = db.create_user(username="admin_b", password="Sup3rSecret!", full_name="Admin B", role="admin")
    assert db.count_active_admins(exclude_user_id=admin1) == 1
    db.set_user_active(admin2, False)
    assert db.count_active_admins(exclude_user_id=admin1) == 0


def test_reset_password_changes_credentials():
    user_id = db.create_user(username="hank", password="OldPass123!", full_name="Hank H", role="applicant")
    db.reset_password(user_id, "NewPass456!")
    assert db.authenticate("hank", "OldPass123!") is None
    assert db.authenticate("hank", "NewPass456!") is not None


def test_submission_lifecycle_and_user_isolation():
    applicant_id = db.create_user(username="dave", password="Sup3rSecret!", full_name="Dave D", role="applicant")
    other_id = db.create_user(username="erin", password="Sup3rSecret!", full_name="Erin E", role="applicant")
    admin_id = db.create_user(username="admin1", password="Sup3rSecret!", full_name="Admin One", role="admin")
    scheme_id = db.create_scheme("Test Scheme", "desc", "elig", "docs", created_by=admin_id)

    submission_id = db.create_submission(applicant_id, scheme_id, "notes", "Rs. 1,000 on 01/01/2025")

    assert len(db.list_submissions_for_user(applicant_id)) == 1
    assert len(db.list_submissions_for_user(other_id)) == 0  # cannot see others' submissions

    db.set_analysis_status(submission_id, "running", stage="extraction")
    assert db.get_submission(submission_id)["analysis_status"] == "running"

    db.save_analysis_result(
        submission_id,
        extracted_fields={"amounts_found": ["1,000"]},
        summary="Test summary.",
        validation_result={"is_complete": True, "requires_human_review": False},
        score=0.6,
        score_explanation={"weights": {"completeness": 0.6, "risk": 0.4}},
    )
    updated = db.get_submission(submission_id)
    assert updated["status"] == "under_review"
    assert updated["analysis_status"] == "completed"
    assert updated["score"] == 0.6
    assert updated["extracted_fields"] == {"amounts_found": ["1,000"]}

    db.append_analysis_event(submission_id, "extraction", "reasoning", "Looking for monetary amounts...")
    events = db.list_analysis_events(submission_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "reasoning"

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
