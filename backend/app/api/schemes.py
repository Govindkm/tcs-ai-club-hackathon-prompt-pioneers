"""Scheme catalog endpoints - browse (any authenticated user) and manage (admin only).

Editing an existing scheme never applies immediately: it's staged as a
pending_update and only takes effect once >= 2 distinct admins approve it
(see approve_scheme_update below) - mirrors the score-approval pattern used
for submissions (backend/app/api/applications.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.schemas import SchemeIn, SchemeOut, SchemeUpdateApprovalOut
from backend.app.security import get_current_user, require_role
from src.agents.orchestrator import generate_scheme_scoring_pattern
from src.db import repository as db

router = APIRouter(prefix="/api/v1/schemes", tags=["schemes"])

_UPDATE_APPROVALS_REQUIRED = 2


def _to_out(scheme: dict) -> SchemeOut:
    pending_update_by_name = None
    if scheme.get("pending_update_by"):
        admin = db.get_user(scheme["pending_update_by"])
        pending_update_by_name = admin["full_name"] if admin else None
    return SchemeOut(**{**scheme, "is_active": bool(scheme["is_active"]), "pending_update_by_name": pending_update_by_name})


def _get_or_404(scheme_id: int) -> dict:
    scheme = db.get_scheme(scheme_id)
    if scheme is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheme not found")
    return scheme


@router.get("", response_model=list[SchemeOut])
def list_schemes(active_only: bool = True, current_user: dict = Depends(get_current_user)) -> list[SchemeOut]:
    return [_to_out(s) for s in db.list_schemes(active_only=active_only)]


@router.post("", response_model=SchemeOut, status_code=201)
def create_scheme(payload: SchemeIn, current_user: dict = Depends(require_role("admin"))) -> SchemeOut:
    scheme_id = db.create_scheme(
        payload.name, payload.description, payload.eligibility, payload.required_documents, current_user["id"]
    )
    pattern = generate_scheme_scoring_pattern(
        payload.name, payload.description, payload.eligibility, payload.required_documents
    )
    db.set_scheme_scoring_pattern(scheme_id, pattern.model_dump())
    return _to_out(_get_or_404(scheme_id))


@router.patch("/{scheme_id}/active", response_model=SchemeOut)
def set_scheme_active(
    scheme_id: int, is_active: bool, current_user: dict = Depends(require_role("admin"))
) -> SchemeOut:
    db.set_scheme_active(scheme_id, is_active)
    return _to_out(_get_or_404(scheme_id))


@router.put("/{scheme_id}", response_model=SchemeOut)
def propose_scheme_update(
    scheme_id: int, payload: SchemeIn, current_user: dict = Depends(require_role("admin"))
) -> SchemeOut:
    """Stage an edit to an existing scheme (incl. a freshly-designed scoring pattern for
    the proposed fields); it only takes effect once >= 2 distinct admins approve it via
    POST /{scheme_id}/approve-update."""
    _get_or_404(scheme_id)
    pattern = generate_scheme_scoring_pattern(
        payload.name, payload.description, payload.eligibility, payload.required_documents
    )
    updates = {**payload.model_dump(), "scoring_pattern": pattern.model_dump()}
    db.propose_scheme_update(scheme_id, updates, current_user["id"])
    return _to_out(_get_or_404(scheme_id))


@router.post("/{scheme_id}/approve-update", response_model=SchemeOut)
def approve_scheme_update(scheme_id: int, current_user: dict = Depends(require_role("admin"))) -> SchemeOut:
    scheme = _get_or_404(scheme_id)
    if not scheme.get("pending_update"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This scheme has no pending update.")
    approval_count = db.add_scheme_update_approval(scheme_id, current_user["id"])
    if approval_count >= _UPDATE_APPROVALS_REQUIRED:
        db.apply_pending_scheme_update(scheme_id, scheme["pending_update"])
    return _to_out(_get_or_404(scheme_id))


@router.get("/{scheme_id}/update-approvals", response_model=list[SchemeUpdateApprovalOut])
def list_scheme_update_approvals(
    scheme_id: int, current_user: dict = Depends(require_role("admin"))
) -> list[SchemeUpdateApprovalOut]:
    _get_or_404(scheme_id)
    return [SchemeUpdateApprovalOut(**a) for a in db.list_scheme_update_approvals(scheme_id)]
