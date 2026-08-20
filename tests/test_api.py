"""Integration tests for the FastAPI backend, using an isolated temp DB per test.

Covers auth/roles, scheme management, the submit -> agentic analysis -> review
lifecycle, submission ownership isolation, and notifications - i.e. the same
guarantees previously tested at the repository layer, now exercised through
the actual HTTP API that the Streamlit client (and any future client) calls.

The real agentic pipeline (src/agents/orchestrator.py) calls an LLM, so it's
stubbed here to keep these tests fast/deterministic/offline; the orchestrator
itself is exercised for real in scripts/run_pipeline_demo.py against a live
model.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
import backend.app.api.applications as applications_module
from src.agents.results import ExtractionResult, ScoringResult, ValidationResult
from src.db import repository as db
from src.tools.document_tools import extract_fields, summarize_document
from src.tools.scoring_tools import apply_rule_score
from src.tools.validation_tools import check_completeness, flag_authenticity_risks


class _FakePipeline:
    """Deterministic stand-in for ApplicationPipeline, no LLM calls."""

    def __init__(self, event_sink=None) -> None:
        self._event_sink = event_sink or (lambda stage, event_type, content: None)

    def process(self, document_text: str, required_fields: list[str], admin_feedback: str = "") -> dict:
        self._event_sink("extraction", "stage_start", "Extracting fields.")
        extracted = extract_fields(document_text)
        summary = summarize_document(document_text)
        self._event_sink("extraction", "stage_complete", summary)

        self._event_sink("validation", "stage_start", "Validating completeness.")
        completeness = check_completeness(extracted, required_fields)
        risks = flag_authenticity_risks(extracted)
        validation = ValidationResult(
            is_complete=completeness["is_complete"],
            missing_fields=completeness["missing_fields"],
            risk_flags=risks["risk_flags"],
            requires_human_review=risks["requires_human_review"],
        )
        self._event_sink("validation", "stage_complete", validation.model_dump_json())

        self._event_sink("scoring", "stage_start", "Computing score.")
        scoring = apply_rule_score(validation.model_dump())
        self._event_sink("scoring", "stage_complete", json.dumps(scoring))

        return {
            "extraction": ExtractionResult(extracted_fields=extracted, summary=summary),
            "validation": validation,
            "scoring": ScoringResult(score=scoring["score"], explanation=scoring["explanation"]),
        }


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only-0123456789")
    monkeypatch.setenv("STRANDS_TRACE_CONSOLE", "false")
    monkeypatch.setattr(applications_module, "create_orchestrator", lambda event_sink=None: _FakePipeline(event_sink))
    # Run the analysis job synchronously instead of on a detached thread, so
    # assertions right after client.post()/GET reflect the completed job.
    monkeypatch.setattr(
        applications_module,
        "_start_analysis_job",
        lambda submission_id, files, pasted_text, admin_feedback="": applications_module.run_agentic_analysis_job(
            submission_id, files, pasted_text, admin_feedback
        ),
    )
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _register_and_login(client: TestClient, username: str = "alice", password: str = "Sup3rSecret!") -> dict:
    client.post(
        "/api/v1/auth/register", json={"username": username, "password": password, "full_name": "Alice A"}
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


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_register_then_login(client):
    token_info = _register_and_login(client)
    assert token_info["user"]["role"] == "applicant"
    assert "access_token" in token_info


def test_duplicate_registration_rejected(client):
    client.post("/api/v1/auth/register", json={"username": "bob", "password": "Sup3rSecret!", "full_name": "Bob"})
    resp = client.post("/api/v1/auth/register", json={"username": "bob", "password": "Sup3rSecret!", "full_name": "Bob"})
    assert resp.status_code == 409


def test_login_rejects_wrong_password(client):
    client.post("/api/v1/auth/register", json={"username": "carl", "password": "Sup3rSecret!", "full_name": "Carl"})
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


def test_submit_application_runs_agentic_analysis_and_is_owner_isolated(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)

    dave = _register_and_login(client, "dave", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    resp = client.post(
        "/api/v1/applications",
        data={"scheme_id": scheme_id, "notes": "n", "pasted_text": "Rs. 1,000 on 01/01/2025"},
        headers=dave_headers,
    )
    assert resp.status_code == 201
    submission = resp.json()
    # In production the job runs on a detached thread and returns before it
    # completes; in tests _start_analysis_job is monkeypatched to run inline,
    # so the response already reflects the finished analysis.
    assert submission["analysis_status"] == "completed"
    assert submission["status"] == "under_review"
    assert submission["score"] is not None

    erin = _register_and_login(client, "erin", "Sup3rSecret!")
    erin_headers = {"Authorization": f"Bearer {erin['access_token']}"}
    forbidden = client.get(f"/api/v1/applications/{submission['id']}", headers=erin_headers)
    assert forbidden.status_code == 403
    forbidden_status = client.get(f"/api/v1/applications/{submission['id']}/status", headers=erin_headers)
    assert forbidden_status.status_code == 403


def test_submit_application_requires_content(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave3", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}

    resp = client.post(
        "/api/v1/applications", data={"scheme_id": scheme_id, "notes": "", "pasted_text": ""}, headers=dave_headers
    )
    assert resp.status_code == 400


def test_review_flow_records_decision_and_finalizes(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)

    dave = _register_and_login(client, "dave2", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    submission = client.post(
        "/api/v1/applications",
        data={"scheme_id": scheme_id, "notes": "", "pasted_text": "Rs. 500 on 02/02/2025"},
        headers=dave_headers,
    ).json()

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
    dave = _register_and_login(client, "dave4", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    submission = client.post(
        "/api/v1/applications",
        data={"scheme_id": scheme_id, "notes": "", "pasted_text": "text"},
        headers=dave_headers,
    ).json()

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


def test_unauthenticated_request_rejected(client):
    resp = client.get("/api/v1/applications")
    assert resp.status_code == 401


def test_submission_survives_agentic_analysis_failure(client, monkeypatch):
    """A model/network failure during analysis must not lose the submission."""

    class _BrokenPipeline:
        def process(self, document_text: str, required_fields: list[str], admin_feedback: str = "") -> dict:
            raise RuntimeError("model unreachable")

    monkeypatch.setattr("backend.app.api.applications.create_orchestrator", lambda event_sink=None: _BrokenPipeline())

    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave5", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}

    resp = client.post(
        "/api/v1/applications",
        data={"scheme_id": scheme_id, "notes": "", "pasted_text": "some text"},
        headers=dave_headers,
    )
    assert resp.status_code == 201
    submission = resp.json()
    assert submission["status"] == "submitted"  # unanalyzed, but not lost
    assert submission["score"] is None

    failed = client.get(f"/api/v1/applications/{submission['id']}/status", headers=dave_headers).json()
    assert failed["analysis_status"] == "failed"
    assert "model unreachable" in failed["analysis_error"]

    events = client.get(f"/api/v1/applications/{submission['id']}/events", headers=admin_headers).json()
    assert any(e["event_type"] == "error" for e in events)


def test_analyze_endpoint_retries_a_previously_unanalyzed_submission(client, monkeypatch):
    class _BrokenPipeline:
        def process(self, document_text: str, required_fields: list[str], admin_feedback: str = "") -> dict:
            raise RuntimeError("model unreachable")

    monkeypatch.setattr("backend.app.api.applications.create_orchestrator", lambda event_sink=None: _BrokenPipeline())

    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave6", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    submission = client.post(
        "/api/v1/applications",
        data={"scheme_id": scheme_id, "notes": "", "pasted_text": "some text"},
        headers=dave_headers,
    ).json()
    failed = client.get(f"/api/v1/applications/{submission['id']}/status", headers=dave_headers).json()
    assert failed["analysis_status"] == "failed"

    # model comes back online (autouse fixture's _FakePipeline stub)
    monkeypatch.setattr("backend.app.api.applications.create_orchestrator", lambda event_sink=None: _FakePipeline())
    resp = client.post(
        f"/api/v1/applications/{submission['id']}/analyze",
        json={"feedback": "please re-check the amount field"},
        headers=dave_headers,
    )
    assert resp.status_code == 200
    # (In tests the job runs inline; in production this would read "queued" here.)
    assert resp.json()["analysis_status"] == "completed"

    completed = client.get(f"/api/v1/applications/{submission['id']}", headers=dave_headers).json()
    assert completed["analysis_status"] == "completed"
    assert completed["score"] is not None

    events = client.get(f"/api/v1/applications/{submission['id']}/events", headers=admin_headers).json()
    assert any("please re-check the amount field" in e["content"] for e in events)


def test_finalized_submission_cannot_be_reanalyzed(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave7", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    submission = client.post(
        "/api/v1/applications",
        data={"scheme_id": scheme_id, "notes": "", "pasted_text": "some text"},
        headers=dave_headers,
    ).json()
    client.post(
        f"/api/v1/applications/{submission['id']}/review",
        json={"decision": "approved", "rationale": "ok"},
        headers=admin_headers,
    )

    resp = client.post(
        f"/api/v1/applications/{submission['id']}/analyze", json={"feedback": ""}, headers=dave_headers
    )
    assert resp.status_code == 409


def test_only_admin_can_view_analysis_events(client):
    admin_headers = _admin_headers(client)
    scheme_id = _create_scheme(client, admin_headers)
    dave = _register_and_login(client, "dave8", "Sup3rSecret!")
    dave_headers = {"Authorization": f"Bearer {dave['access_token']}"}
    submission = client.post(
        "/api/v1/applications",
        data={"scheme_id": scheme_id, "notes": "", "pasted_text": "some text"},
        headers=dave_headers,
    ).json()

    admin_events = client.get(f"/api/v1/applications/{submission['id']}/events", headers=admin_headers)
    assert admin_events.status_code == 200
    assert len(admin_events.json()) > 0  # stage_start/stage_complete events from the fake pipeline

    applicant_events = client.get(f"/api/v1/applications/{submission['id']}/events", headers=dave_headers)
    assert applicant_events.status_code == 403
