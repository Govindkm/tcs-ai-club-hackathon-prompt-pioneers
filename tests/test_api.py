"""Integration tests for the FastAPI backend, using an isolated temp DB per test.

Covers auth/roles, scheme management, the staged submit -> ingest/index ->
assign -> validate -> score -> approve workflow, ownership isolation, and
notifications - exercised through the actual HTTP API that the Streamlit
client (and any future client) calls.

The real agentic pipeline (src/agents/orchestrator.py) calls an LLM, so it's
stubbed here to keep these tests fast/deterministic/offline; the orchestrator
itself is exercised for real in scripts/run_pipeline_demo.py against a live
model.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
import backend.app.api.applications as applications_module
import backend.app.api.schemes as schemes_module
from src.agents.results import (
    EmbeddingIndexResult,
    ExtractionResult,
    ScoringPatternResult,
    ScoringResult,
    ValidationResult,
)
from src.db import repository as db
from src.tools.document_tools import extract_fields, summarize_document
from src.tools.scoring_tools import apply_rule_score
from src.tools.validation_tools import check_completeness, flag_authenticity_risks


class _FakePipeline:
    """Deterministic stand-in for ApplicationPipeline, no LLM/vector-store calls."""

    def __init__(self, event_sink=None) -> None:
        self._event_sink = event_sink or (lambda stage, event_type, content: None)

    def index_and_check(self, document_bundle, scheme_id, scheme_title, submission_id) -> dict:
        self._event_sink("embedding", "stage_start", "Indexing.")
        embedding = EmbeddingIndexResult(
            scheme_id=scheme_id,
            submission_id=submission_id,
            indexed_document_count=len(document_bundle),
            indexed_chunk_count=len(document_bundle),
            collection_name="test_collection",
            embedding_model="test-model",
            record_ids=["r1"],
        )
        self._event_sink("embedding", "stage_complete", embedding.model_dump_json())
        plagiarism = {"checked_document_count": len(document_bundle), "potential_matches": [], "flagged": False}
        self._event_sink("plagiarism_check", "stage_complete", str(plagiarism))
        return {"embedding": embedding, "plagiarism": plagiarism}

    def run_extraction(self, document_text: str, admin_feedback: str = "") -> ExtractionResult:
        self._event_sink("extraction", "stage_start", "Extracting fields.")
        extracted = extract_fields(document_text)
        summary = summarize_document(document_text)
        self._event_sink("extraction", "stage_complete", summary)
        return ExtractionResult(extracted_fields=extracted, summary=summary)

    def run_validation(
        self,
        extracted_fields,
        required_fields,
        admin_feedback="",
        plagiarism_summary=None,
        organisation_name=None,
        scoring_pattern=None,
    ) -> ValidationResult:
        self._event_sink("validation", "stage_start", "Validating completeness.")
        completeness = check_completeness(extracted_fields, required_fields)
        risks = flag_authenticity_risks(extracted_fields)
        validation = ValidationResult(
            is_complete=completeness["is_complete"],
            missing_fields=completeness["missing_fields"],
            risk_flags=risks["risk_flags"],
            requires_human_review=risks["requires_human_review"],
        )
        if admin_feedback:
            self._event_sink("validation", "text", f"Incorporating feedback: {admin_feedback}")
        self._event_sink("validation", "stage_complete", validation.model_dump_json())
        return validation

    def run_scoring(self, validation_result: dict, admin_feedback: str = "", scoring_pattern=None) -> ScoringResult:
        self._event_sink("scoring", "stage_start", "Computing score.")
        scoring = apply_rule_score(validation_result)
        self._event_sink("scoring", "stage_complete", str(scoring))
        return ScoringResult(score=scoring["score"], explanation=scoring["explanation"])


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("UPLOAD_STORAGE_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only-0123456789")
    monkeypatch.setenv("STRANDS_TRACE_CONSOLE", "false")
    monkeypatch.setattr(applications_module, "create_orchestrator", lambda event_sink=None: _FakePipeline(event_sink))
    monkeypatch.setattr(
        schemes_module,
        "generate_scheme_scoring_pattern",
        lambda name, description, eligibility, required_documents: ScoringPatternResult(
            criteria=[
                {"name": "Eligibility fit", "weight": 60.0, "rationale": "Matches scheme eligibility."},
                {"name": "Completeness", "weight": 40.0, "rationale": "All required documents present."},
            ],
            summary="Stub scoring pattern for tests.",
        ),
    )
    # Run every background job synchronously instead of on a detached thread, so
    # assertions right after client.post() reflect the completed job.
    monkeypatch.setattr(
        applications_module,
        "_start_background_job",
        lambda target, *args: target(*args),
    )
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _register_and_login(client: TestClient, username: str = "alice", password: str = "Sup3rSecret!") -> dict:
    client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": password,
            "full_name": "Alice A",
            "email": f"{username}@example.com",
            "organisation_name": "Example Org",
        },
    )
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.json()


def _admin_headers(client: TestClient, username: str = "admin1", password: str = "Sup3rSecret!") -> dict:
    db.create_user(username=username, password=password, full_name="Admin One", role="admin")
    token = client.post("/api/v1/auth/login", json={"username": username, "password": password}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


def _create_scheme(client: TestClient, admin_headers: dict) -> int:
    resp = client.post(
        "/api/v1/schemes",
        json={"name": "Grant", "description": "desc", "eligibility": "elig", "required_documents": "docs"},
        headers=admin_headers,
    )
    return resp.json()["id"]


def _submit(client: TestClient, headers: dict, scheme_id: int, text: str = "Rs. 1,000 on 01/01/2025") -> dict:
    resp = client.post(
        "/api/v1/applications",
        data={"scheme_id": scheme_id, "notes": "n", "pasted_text": text},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_register_then_login(client):
    token_info = _register_and_login(client)
    assert token_info["user"]["role"] == "applicant"
    assert token_info["user"]["email"] == "alice@example.com"
    assert token_info["user"]["organisation_name"] == "Example Org"
    assert "access_token" in token_info


def test_register_requires_email_and_organisation(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": "noemail", "password": "Sup3rSecret!", "full_name": "No Email"},
    )
    assert resp.status_code == 422


def test_register_rejects_invalid_email(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": "bademail",
            "password": "Sup3rSecret!",
            "full_name": "Bad Email",
            "email": "not-an-email",
            "organisation_name": "Example Org",
        },
    )
    assert resp.status_code == 422


def test_duplicate_registration_rejected(client):
    payload = {
        "username": "bob",
        "password": "Sup3rSecret!",
        "full_name": "Bob",
        "email": "bob@example.com",
        "organisation_name": "Example Org",
    }
    client.post("/api/v1/auth/register", json=payload)
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


def test_login_rejects_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "carl",
            "password": "Sup3rSecret!",
            "full_name": "Carl",
            "email": "carl@example.com",
            "organisation_name": "Example Org",
        },
    )
    resp = client.post("/api/v1/auth/login", json={"username": "carl", "password": "wrong"})
    assert resp.status_code == 401


def test_applicant_cannot_create_scheme(client):
    token_info = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token_info['access_token']}"}
    resp = client.post("/api/v1/schemes", json={"name": "X", "description": "Y"}, headers=headers)
    assert resp.status_code == 403


def test_admin_can_create_scheme_and_applicant_can_list_it(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)

    applicant = _register_and_login(client)
    applicant_headers = {"Authorization": f"Bearer {applicant['access_token']}"}
    schemes = client.get("/api/v1/schemes", headers=applicant_headers).json()
    assert any(s["id"] == scheme_id for s in schemes)


def test_scheme_edit_requires_two_distinct_admin_approvals(client):
    admin1 = _admin_headers(client, "sadmin1", "Sup3rSecret!")
    admin2 = _admin_headers(client, "sadmin2", "Sup3rSecret!")
    scheme_id = _create_scheme(client, admin1)

    applicant = _register_and_login(client)
    applicant_headers = {"Authorization": f"Bearer {applicant['access_token']}"}
    forbidden = client.put(
        f"/api/v1/schemes/{scheme_id}",
        json={"name": "New name", "description": "d2", "eligibility": "e2", "required_documents": "doc2"},
        headers=applicant_headers,
    )
    assert forbidden.status_code == 403

    proposed = client.put(
        f"/api/v1/schemes/{scheme_id}",
        json={"name": "New name", "description": "d2", "eligibility": "e2", "required_documents": "doc2"},
        headers=admin1,
    )
    assert proposed.status_code == 200
    scheme = proposed.json()
    assert scheme["name"] == "Grant"  # not applied yet
    assert scheme["pending_update"]["name"] == "New name"

    # Still not applied after a single approval (even the proposer's own).
    first_approval = client.post(f"/api/v1/schemes/{scheme_id}/approve-update", headers=admin1)
    assert first_approval.status_code == 200
    assert first_approval.json()["name"] == "Grant"
    assert first_approval.json()["pending_update"] is not None

    approvals = client.get(f"/api/v1/schemes/{scheme_id}/update-approvals", headers=admin1).json()
    assert len(approvals) == 1

    # A second, distinct admin's approval applies the update.
    second_approval = client.post(f"/api/v1/schemes/{scheme_id}/approve-update", headers=admin2)
    assert second_approval.status_code == 200
    applied = second_approval.json()
    assert applied["name"] == "New name"
    assert applied["pending_update"] is None

    approvals_after = client.get(f"/api/v1/schemes/{scheme_id}/update-approvals", headers=admin1).json()
    assert approvals_after == []


def test_submit_application_runs_ingestion_and_is_owner_isolated(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)

    dave = _register_and_login(client, "dave", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    submission = _submit(client, dave_headers, scheme_id)

    # Ingestion (extract -> index -> plagiarism check) runs inline in tests.
    assert submission["timeline_stage"] == "awaiting_admin_review"
    assert submission["analysis_status"] == "completed"
    assert submission["plagiarism_result"] is not None
    assert submission["score"] is None  # scoring hasn't run yet - requires admin assignment

    erin = _register_and_login(client, "erin", "Sup3rSecret!")
    erin_headers = {"Authorization": f"Bearer {erin['access_token']}"}
    forbidden = client.get(f"/api/v1/applications/{submission['id']}", headers=erin_headers)
    assert forbidden.status_code == 403


def test_submit_application_requires_content(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave3", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}

    resp = client.post(
        "/api/v1/applications", data={"scheme_id": scheme_id, "notes": "", "pasted_text": ""}, headers=dave_headers
    )
    assert resp.status_code == 400


def test_full_workflow_assign_validate_score_and_two_admin_approvals(client):
    admin1 = _admin_headers(client, "admin_a", "Sup3rSecret!")
    admin2 = _admin_headers(client, "admin_b", "Sup3rSecret!")
    scheme_id = _create_scheme(client, admin1)

    dave = _register_and_login(client, "dave2", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    submission = _submit(client, dave_headers, scheme_id)
    sid = submission["id"]
    assert submission["timeline_stage"] == "awaiting_admin_review"

    assigned = client.post(f"/api/v1/applications/{sid}/assign", headers=admin1)
    assert assigned.status_code == 200
    body = assigned.json()
    assert body["assigned_admin_id"] is not None
    assert body["timeline_stage"] == "awaiting_admin_validation"
    assert body["validation_result"] is not None

    # Second admin cannot claim after the first does.
    already = client.post(f"/api/v1/applications/{sid}/assign", headers=admin2)
    assert already.status_code == 409

    # Only the assigned admin can control validation feedback/complete.
    forbidden = client.post(f"/api/v1/applications/{sid}/validation/complete", headers=admin2)
    assert forbidden.status_code == 403

    feedback_resp = client.post(
        f"/api/v1/applications/{sid}/validation/feedback", json={"feedback": "double-check the amount"}, headers=admin1
    )
    assert feedback_resp.status_code == 200
    assert feedback_resp.json()["timeline_stage"] == "awaiting_admin_validation"
    assert feedback_resp.json()["validation_feedback"] == "double-check the amount"

    completed = client.post(f"/api/v1/applications/{sid}/validation/complete", headers=admin1)
    assert completed.status_code == 200
    assert completed.json()["timeline_stage"] == "awaiting_score_approval"
    assert completed.json()["score"] is not None

    # First approval doesn't finalize; second (distinct) admin's approval does.
    first_approval = client.post(f"/api/v1/applications/{sid}/score/approve", headers=admin1)
    assert first_approval.status_code == 200
    assert first_approval.json()["timeline_stage"] == "awaiting_score_approval"

    second_approval = client.post(f"/api/v1/applications/{sid}/score/approve", headers=admin2)
    assert second_approval.status_code == 200
    assert second_approval.json()["timeline_stage"] == "completed"

    approvals = client.get(f"/api/v1/applications/{sid}/score/approvals", headers=admin1).json()
    assert len(approvals) == 2

    # Applicant can see their own submission's progress throughout.
    own = client.get(f"/api/v1/applications/{sid}", headers=dave_headers).json()
    assert own["timeline_stage"] == "completed"


def test_review_flow_records_decision_and_finalizes(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)

    dave = _register_and_login(client, "dave4", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    submission = _submit(client, dave_headers, scheme_id, "Rs. 500 on 02/02/2025")

    review_resp = client.post(
        f"/api/v1/applications/{submission['id']}/review",
        json={"decision": "approved", "rationale": "Meets criteria"},
        headers=admin_headers,
    )
    assert review_resp.status_code == 201

    final = client.get(f"/api/v1/applications/{submission['id']}", headers=dave_headers).json()
    assert final["status"] == "approved"

    # already-finalized cases cannot be reviewed again
    second_review = client.post(
        f"/api/v1/applications/{submission['id']}/review",
        json={"decision": "rejected", "rationale": "changed my mind"},
        headers=admin_headers,
    )
    assert second_review.status_code == 409


def test_applicant_cannot_submit_review(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave5", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    submission = _submit(client, dave_headers, scheme_id, "text")

    resp = client.post(
        f"/api/v1/applications/{submission['id']}/review",
        json={"decision": "approved", "rationale": "self-approve"},
        headers=dave_headers,
    )
    assert resp.status_code == 403


def test_notifications_visible_to_all_authenticated_users(client):
    admin_headers = _admin_headers(client)
    client.post("/api/v1/notifications", json={"title": "T", "message": "M"}, headers=admin_headers)

    applicant = _register_and_login(client)
    applicant_headers = {"Authorization": f"Bearer {applicant['access_token']}"}
    notes = client.get("/api/v1/notifications", headers=applicant_headers).json()
    assert len(notes) == 1


def test_admins_are_notified_when_a_submission_is_ready_for_review(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave6", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    _submit(client, dave_headers, scheme_id, "text")

    notes = client.get("/api/v1/notifications", headers=admin_headers).json()
    assert any("ready for review" in n["title"] for n in notes)


def test_unauthenticated_request_rejected(client):
    resp = client.get("/api/v1/applications")
    assert resp.status_code == 401


def test_submission_survives_ingestion_failure(client, monkeypatch):
    """A model/network failure during ingestion must not lose the submission, and the
    timeline should stay pinned at the stage that failed (so the UI can mark that one
    step red and leave earlier/later steps at their correct done/not-started color)."""

    class _BrokenPipeline:
        def index_and_check(self, *args, **kwargs):
            raise RuntimeError("model unreachable")

    monkeypatch.setattr(applications_module, "create_orchestrator", lambda event_sink=None: _BrokenPipeline())

    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave7", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}

    resp = client.post(
        "/api/v1/applications",
        data={"scheme_id": scheme_id, "notes": "", "pasted_text": "some text"},
        headers=dave_headers,
    )
    assert resp.status_code == 201
    submission = resp.json()
    assert submission["timeline_stage"] == "ingesting"

    failed = client.get(f"/api/v1/applications/{submission['id']}/status", headers=dave_headers).json()
    assert failed["analysis_status"] == "failed"
    assert "model unreachable" in failed["analysis_error"]

    events = client.get(f"/api/v1/applications/{submission['id']}/events", headers=admin_headers).json()
    assert any(e["event_type"] == "error" for e in events)


def test_restart_re_extracts_uploaded_files_from_disk(client, monkeypatch):
    """Restarting a failed ingestion should re-run extraction (incl. OCR) from the
    originally uploaded file bytes persisted on disk, not just reuse stale text."""

    class _BrokenPipeline:
        def index_and_check(self, *args, **kwargs):
            raise RuntimeError("model unreachable")

    monkeypatch.setattr(applications_module, "create_orchestrator", lambda event_sink=None: _BrokenPipeline())
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave12", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}

    resp = client.post(
        "/api/v1/applications",
        data={"scheme_id": scheme_id, "notes": ""},
        files=[("files", ("notes.txt", b"Rs. 2,000 on 03/03/2025", "text/plain"))],
        headers=dave_headers,
    )
    assert resp.status_code == 201
    submission = resp.json()
    assert submission["analysis_status"] == "failed"
    assert submission["timeline_stage"] == "ingesting"

    monkeypatch.setattr(applications_module, "create_orchestrator", lambda event_sink=None: _FakePipeline(event_sink))
    restarted = client.post(f"/api/v1/applications/{submission['id']}/restart", headers=admin_headers).json()
    assert restarted["timeline_stage"] == "awaiting_admin_review"
    assert "notes.txt" in restarted["document_text"]


def test_admin_can_restart_failed_ingestion(client, monkeypatch):
    class _BrokenPipeline:
        def index_and_check(self, *args, **kwargs):
            raise RuntimeError("model unreachable")

    monkeypatch.setattr(applications_module, "create_orchestrator", lambda event_sink=None: _BrokenPipeline())
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave10", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    submission = client.post(
        "/api/v1/applications",
        data={"scheme_id": scheme_id, "notes": "", "pasted_text": "some text"},
        headers=dave_headers,
    ).json()
    assert submission["analysis_status"] == "failed"

    # Applicants cannot restart the pipeline.
    forbidden = client.post(f"/api/v1/applications/{submission['id']}/restart", headers=dave_headers)
    assert forbidden.status_code == 403

    monkeypatch.setattr(applications_module, "create_orchestrator", lambda event_sink=None: _FakePipeline(event_sink))
    restarted = client.post(f"/api/v1/applications/{submission['id']}/restart", headers=admin_headers)
    assert restarted.status_code == 200
    assert restarted.json()["timeline_stage"] == "awaiting_admin_review"
    assert restarted.json()["analysis_status"] == "completed"


def test_applicant_can_request_reevaluation_but_not_others(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave11", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    submission = _submit(client, dave_headers, scheme_id, "some text")

    resp = client.post(
        f"/api/v1/applications/{submission['id']}/request-reevaluation",
        json={"details": "please re-check the budget figure"},
        headers=dave_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["reevaluation_request"] == "please re-check the budget figure"

    notes = client.get("/api/v1/notifications", headers=admin_headers).json()
    assert any("Re-evaluation requested" in n["title"] for n in notes)

    # An admin (not the applicant) cannot request reevaluation on someone else's submission.
    forbidden = client.post(
        f"/api/v1/applications/{submission['id']}/request-reevaluation",
        json={"details": "x"},
        headers=admin_headers,
    )
    assert forbidden.status_code == 403


def test_finalized_submission_cannot_be_reanalyzed(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave8", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    submission = _submit(client, dave_headers, scheme_id, "some text")
    client.post(
        f"/api/v1/applications/{submission['id']}/review",
        json={"decision": "approved", "rationale": "ok"},
        headers=admin_headers,
    )

    resp = client.post(
        f"/api/v1/applications/{submission['id']}/analyze", json={"feedback": ""}, headers=admin_headers
    )
    assert resp.status_code == 409


def test_only_admin_can_view_analysis_events(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave9", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    submission = _submit(client, dave_headers, scheme_id, "some text")

    admin_events = client.get(f"/api/v1/applications/{submission['id']}/events", headers=admin_headers)
    assert admin_events.status_code == 200
    assert len(admin_events.json()) > 0

    applicant_events = client.get(f"/api/v1/applications/{submission['id']}/events", headers=dave_headers)
    assert applicant_events.status_code == 403


def test_admin_can_create_and_manage_other_admins(client):
    admin_headers = _admin_headers(client, "root_admin", "Sup3rSecret!")

    created = client.post(
        "/api/v1/users/admins",
        json={"username": "new_admin", "password": "Sup3rSecret!", "full_name": "New Admin"},
        headers=admin_headers,
    )
    assert created.status_code == 201
    new_admin_id = created.json()["id"]
    assert created.json()["role"] == "admin"

    # New admin can log in and use admin-only endpoints.
    new_admin_login = client.post(
        "/api/v1/auth/login", json={"username": "new_admin", "password": "Sup3rSecret!"}
    ).json()
    new_admin_headers = {"Authorization": f"Bearer {new_admin_login['access_token']}"}
    users = client.get("/api/v1/users", headers=new_admin_headers).json()
    assert any(u["username"] == "new_admin" for u in users)

    # root_admin is still active, so deactivating new_admin (not the last admin) succeeds.
    deactivated = client.patch(
        f"/api/v1/users/{new_admin_id}/active", params={"is_active": False}, headers=admin_headers
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    # Deactivated admin can no longer log in.
    relogin = client.post("/api/v1/auth/login", json={"username": "new_admin", "password": "Sup3rSecret!"})
    assert relogin.status_code == 401

    # An admin cannot deactivate their own account.
    self_ids = client.get("/api/v1/users", headers=admin_headers).json()
    root_id = next(u["id"] for u in self_ids if u["username"] == "root_admin")
    self_deactivate = client.patch(f"/api/v1/users/{root_id}/active", params={"is_active": False}, headers=admin_headers)
    assert self_deactivate.status_code == 409

    # Reset another user's password.
    reset_resp = client.post(
        f"/api/v1/users/{new_admin_id}/reset-password", json={"new_password": "BrandNewPass1!"}, headers=admin_headers
    )
    assert reset_resp.status_code == 204
    reactivated = client.patch(f"/api/v1/users/{new_admin_id}/active", params={"is_active": True}, headers=admin_headers)
    assert reactivated.status_code == 200
    relogin_new_pw = client.post(
        "/api/v1/auth/login", json={"username": "new_admin", "password": "BrandNewPass1!"}
    )
    assert relogin_new_pw.status_code == 200


def test_cannot_deactivate_the_last_active_admin(client):
    admin_a = _admin_headers(client, "admin_only_a", "Sup3rSecret!")
    admin_b = _admin_headers(client, "admin_only_b", "Sup3rSecret!")
    users = client.get("/api/v1/users", headers=admin_a).json()
    admin_b_id = next(u["id"] for u in users if u["username"] == "admin_only_b")
    admin_a_id = next(u["id"] for u in users if u["username"] == "admin_only_a")

    # admin_b deactivates admin_a (allowed - admin_b remains active).
    assert client.patch(f"/api/v1/users/{admin_a_id}/active", params={"is_active": False}, headers=admin_b).status_code == 200

    # Now admin_b is the only active admin - even a different account can't deactivate it.
    blocked = client.patch(f"/api/v1/users/{admin_b_id}/active", params={"is_active": False}, headers=admin_b)
    assert blocked.status_code == 409


def test_non_admin_cannot_manage_users(client):
    applicant = _register_and_login(client, "plain_user", "Sup3rSecret!")
    applicant_headers = {"Authorization": f"Bearer {applicant['access_token']}"}

    assert client.get("/api/v1/users", headers=applicant_headers).status_code == 403
    assert client.post(
        "/api/v1/users/admins",
        json={"username": "hacker_admin", "password": "Sup3rSecret!", "full_name": "Hacker"},
        headers=applicant_headers,
    ).status_code == 403


def test_owner_and_admin_can_preview_submitted_files_but_others_cannot(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave13", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    eve = _register_and_login(client, "eve13", "Sup3rSecret!")
    eve_headers = {"Authorization": f"Bearer {eve['access_token']}"}

    resp = client.post(
        "/api/v1/applications",
        data={"scheme_id": scheme_id, "notes": ""},
        files=[("files", ("notes.txt", b"Rs. 2,000 on 03/03/2025", "text/plain"))],
        headers=dave_headers,
    )
    assert resp.status_code == 201
    submission_id = resp.json()["id"]

    manifest = client.get(f"/api/v1/applications/{submission_id}/files", headers=dave_headers)
    assert manifest.status_code == 200
    files = manifest.json()
    assert len(files) == 1
    assert files[0]["filename"] == "notes.txt"

    file_resp = client.get(f"/api/v1/applications/{submission_id}/files/0", headers=dave_headers)
    assert file_resp.status_code == 200
    assert file_resp.content == b"Rs. 2,000 on 03/03/2025"

    admin_manifest = client.get(f"/api/v1/applications/{submission_id}/files", headers=admin_headers)
    assert admin_manifest.status_code == 200

    forbidden = client.get(f"/api/v1/applications/{submission_id}/files", headers=eve_headers)
    assert forbidden.status_code == 403

    missing = client.get(f"/api/v1/applications/{submission_id}/files/5", headers=dave_headers)
    assert missing.status_code == 404
