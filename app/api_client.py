"""Thin HTTP client the Streamlit UI uses to talk to the FastAPI backend.

Streamlit must never import src.db/src.tools/src.ingestion directly - all
business logic lives behind the API so future clients (React, a government
portal, etc.) can reuse it unchanged. See backend/app/main.py.
"""
from __future__ import annotations

import os

import requests

_DEFAULT_TIMEOUT = 30


class BackendError(Exception):
    """Raised when the backend API returns a non-2xx response."""


class BackendClient:
    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("API_BASE_URL", "http://localhost:8000")).rstrip("/")
        self.token = token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _request(self, method: str, path: str, timeout: int = _DEFAULT_TIMEOUT, **kwargs):
        response = requests.request(
            method, f"{self.base_url}{path}", headers=self._headers(), timeout=timeout, **kwargs
        )
        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise BackendError(detail)
        return response.json() if response.content else None

    # --- auth ---
    def register(self, username: str, password: str, full_name: str, email: str, organisation_name: str) -> dict:
        return self._request(
            "POST",
            "/api/v1/auth/register",
            json={
                "username": username,
                "password": password,
                "full_name": full_name,
                "email": email,
                "organisation_name": organisation_name,
            },
        )

    def login(self, username: str, password: str) -> dict:
        return self._request("POST", "/api/v1/auth/login", json={"username": username, "password": password})

    # --- users (admin management) ---
    def list_users(self) -> list[dict]:
        return self._request("GET", "/api/v1/users")

    def create_admin(self, username: str, password: str, full_name: str, email: str | None = None) -> dict:
        return self._request(
            "POST",
            "/api/v1/users/admins",
            json={"username": username, "password": password, "full_name": full_name, "email": email},
        )

    def set_user_active(self, user_id: int, is_active: bool) -> dict:
        return self._request("PATCH", f"/api/v1/users/{user_id}/active", params={"is_active": is_active})

    def reset_user_password(self, user_id: int, new_password: str) -> None:
        self._request("POST", f"/api/v1/users/{user_id}/reset-password", json={"new_password": new_password})

    # --- schemes ---
    def list_schemes(self, active_only: bool = True) -> list[dict]:
        return self._request("GET", "/api/v1/schemes", params={"active_only": active_only})

    def create_scheme(self, name: str, description: str, eligibility: str, required_documents: str) -> dict:
        return self._request(
            "POST",
            "/api/v1/schemes",
            json={
                "name": name,
                "description": description,
                "eligibility": eligibility,
                "required_documents": required_documents,
            },
        )

    def set_scheme_active(self, scheme_id: int, is_active: bool) -> dict:
        return self._request("PATCH", f"/api/v1/schemes/{scheme_id}/active", params={"is_active": is_active})

    # --- applications ---
    def submit_application(
        self, scheme_id: int, notes: str, pasted_text: str, files: list[tuple[str, bytes]]
    ) -> dict:
        # Analysis runs as a background job on the backend, so this returns immediately
        # with analysis_status='queued' - poll get_application/get_analysis_status for progress.
        multipart_files = [("files", (name, content)) for name, content in files] or None
        return self._request(
            "POST",
            "/api/v1/applications",
            data={"scheme_id": scheme_id, "notes": notes, "pasted_text": pasted_text},
            files=multipart_files,
        )

    def list_my_applications(self) -> list[dict]:
        return self._request("GET", "/api/v1/applications")

    def list_all_applications(self, status_filter: str | None = None) -> list[dict]:
        params = {"status_filter": status_filter} if status_filter else {}
        return self._request("GET", "/api/v1/applications", params=params)

    def get_application(self, application_id: int) -> dict:
        return self._request("GET", f"/api/v1/applications/{application_id}")

    def get_analysis_status(self, application_id: int) -> dict:
        return self._request("GET", f"/api/v1/applications/{application_id}/status")

    def list_analysis_events(self, application_id: int) -> list[dict]:
        return self._request("GET", f"/api/v1/applications/{application_id}/events")

    def analyze_application(self, application_id: int, feedback: str = "") -> dict:
        """(Re)run analysis in the background; feedback is human-in-the-loop guidance for the agents."""
        return self._request(
            "POST", f"/api/v1/applications/{application_id}/analyze", json={"feedback": feedback}
        )

    def assign_for_analysis(self, application_id: int) -> dict:
        """Claim a submission to run/oversee its AI analysis (extraction + validation)."""
        return self._request("POST", f"/api/v1/applications/{application_id}/assign")

    def submit_validation_feedback(self, application_id: int, feedback: str) -> dict:
        """Assigned admin gives text instructions; loops the validation stage again."""
        return self._request(
            "POST", f"/api/v1/applications/{application_id}/validation/feedback", json={"feedback": feedback}
        )

    def complete_validation(self, application_id: int) -> dict:
        """Assigned admin marks validation complete, advancing the case to scoring."""
        return self._request("POST", f"/api/v1/applications/{application_id}/validation/complete")

    def approve_score(self, application_id: int) -> dict:
        """Any admin approves the computed score; >=2 distinct approvals completes the timeline."""
        return self._request("POST", f"/api/v1/applications/{application_id}/score/approve")

    def restart_pipeline(self, application_id: int) -> dict:
        """Admin-only: restart the pipeline from whichever stage failed."""
        return self._request("POST", f"/api/v1/applications/{application_id}/restart")

    def request_reevaluation(self, application_id: int, details: str) -> dict:
        """Applicant-only: flag the submission for admins to reevaluate with changes."""
        return self._request(
            "POST", f"/api/v1/applications/{application_id}/request-reevaluation", json={"details": details}
        )

    def list_score_approvals(self, application_id: int) -> list[dict]:
        return self._request("GET", f"/api/v1/applications/{application_id}/score/approvals")

    def list_reviews(self, application_id: int) -> list[dict]:
        return self._request("GET", f"/api/v1/applications/{application_id}/reviews")

    def submit_review(self, application_id: int, decision: str, rationale: str) -> dict:
        return self._request(
            "POST",
            f"/api/v1/applications/{application_id}/review",
            json={"decision": decision, "rationale": rationale},
        )

    # --- notifications ---
    def list_notifications(self) -> list[dict]:
        return self._request("GET", "/api/v1/notifications")

    def create_notification(self, title: str, message: str) -> dict:
        return self._request("POST", "/api/v1/notifications", json={"title": title, "message": message})

    def deactivate_notification(self, notification_id: int) -> None:
        self._request("DELETE", f"/api/v1/notifications/{notification_id}")
