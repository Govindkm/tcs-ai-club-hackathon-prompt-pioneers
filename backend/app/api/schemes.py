"""Scheme catalog endpoints - browse (any authenticated user) and manage (admin only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.schemas import SchemeIn, SchemeOut
from backend.app.security import get_current_user, require_role
from src.db import repository as db

router = APIRouter(prefix="/api/v1/schemes", tags=["schemes"])


def _to_out(scheme: dict) -> SchemeOut:
    return SchemeOut(**{**scheme, "is_active": bool(scheme["is_active"])})


@router.get("", response_model=list[SchemeOut])
def list_schemes(active_only: bool = True, current_user: dict = Depends(get_current_user)) -> list[SchemeOut]:
    return [_to_out(s) for s in db.list_schemes(active_only=active_only)]


@router.post("", response_model=SchemeOut, status_code=201)
def create_scheme(payload: SchemeIn, current_user: dict = Depends(require_role("admin"))) -> SchemeOut:
    scheme_id = db.create_scheme(
        payload.name, payload.description, payload.eligibility, payload.required_documents, current_user["id"]
    )
    scheme = next(s for s in db.list_schemes(active_only=False) if s["id"] == scheme_id)
    return _to_out(scheme)


@router.patch("/{scheme_id}/active", response_model=SchemeOut)
def set_scheme_active(
    scheme_id: int, is_active: bool, current_user: dict = Depends(require_role("admin"))
) -> SchemeOut:
    db.set_scheme_active(scheme_id, is_active)
    scheme = next(s for s in db.list_schemes(active_only=False) if s["id"] == scheme_id)
    return _to_out(scheme)
