"""Pydantic request/response models for the FastAPI backend."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)
    email: str = Field(min_length=3, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    organisation_name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    email: str | None = None
    organisation_name: str | None = None
    is_active: bool = True
    created_at: str | None = None


class CreateAdminRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)
    email: str | None = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SchemeIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    eligibility: str = ""
    required_documents: str = ""


class SchemeOut(BaseModel):
    id: int
    name: str
    description: str
    eligibility: str
    required_documents: str
    is_active: bool
    created_at: str
    pending_update: dict | None = None
    pending_update_by_name: str | None = None
    pending_update_at: str | None = None
    scoring_pattern: dict | None = None


class SchemeUpdateApprovalOut(BaseModel):
    id: int
    scheme_id: int
    admin_id: int
    admin_name: str
    created_at: str


class SubmissionOut(BaseModel):
    id: int
    user_id: int
    scheme_id: int
    scheme_name: str | None = None
    applicant_name: str | None = None
    applicant_organisation: str | None = None
    applicant_notes: str
    document_text: str
    document_manifest: list[dict] = Field(default_factory=list)
    status: str
    analysis_status: str
    analysis_stage: str | None = None
    analysis_error: str | None = None
    timeline_stage: str = "ingesting"
    assigned_admin_id: int | None = None
    assigned_admin_name: str | None = None
    plagiarism_result: dict | None = None
    validation_feedback: str | None = None
    reevaluation_request: str | None = None
    reevaluation_requested_at: str | None = None
    extracted_fields: dict | None = None
    summary: str | None = None
    validation_result: dict | None = None
    score: float | None = None
    score_explanation: dict | None = None
    created_at: str
    updated_at: str


class ValidationFeedbackRequest(BaseModel):
    feedback: str = Field(min_length=1, description="Instructions for the validation agent to re-check.")


class ReevaluationRequestIn(BaseModel):
    details: str = Field(min_length=1, description="What the applicant wants re-checked/changed.")


class ScoreApprovalOut(BaseModel):
    id: int
    submission_id: int
    admin_id: int
    admin_name: str
    created_at: str


class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(approved|rejected|needs_more_info)$")
    rationale: str = Field(min_length=1)


class ReviewOut(BaseModel):
    id: int
    submission_id: int
    reviewer_id: int
    decision: str
    rationale: str
    created_at: str


class AnalyzeRequest(BaseModel):
    feedback: str = Field(default="", description="Optional human-in-the-loop guidance for the agents to incorporate.")


class AnalysisStatusOut(BaseModel):
    id: int
    status: str
    analysis_status: str
    analysis_stage: str | None = None
    analysis_error: str | None = None


class AnalysisEventOut(BaseModel):
    id: int
    submission_id: int
    stage: str
    event_type: str
    content: str
    created_at: str


class NotificationIn(BaseModel):
    title: str = Field(min_length=1)
    message: str = Field(min_length=1)


class NotificationOut(BaseModel):
    id: int
    title: str
    message: str
    created_at: str
