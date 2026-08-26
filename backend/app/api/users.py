"""Admin-only user management: list users, create additional admins, and
activate/deactivate or reset passwords for any account. Self-registration
(backend/app/api/auth.py) can only ever create applicants - this is the only
way to provision additional admins.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.schemas import CreateAdminRequest, ResetPasswordRequest, UserOut
from backend.app.security import require_role
from src.db import repository as db

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(current_user: dict = Depends(require_role("admin"))) -> list[UserOut]:
    return [UserOut(**u) for u in db.list_users()]


@router.post("/admins", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_admin(payload: CreateAdminRequest, current_user: dict = Depends(require_role("admin"))) -> UserOut:
    try:
        user_id = db.create_user(
            username=payload.username,
            password=payload.password,
            full_name=payload.full_name,
            role="admin",
            email=payload.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserOut(**db.get_user(user_id))


@router.patch("/{user_id}/active", response_model=UserOut)
def set_user_active(
    user_id: int, is_active: bool, current_user: dict = Depends(require_role("admin"))
) -> UserOut:
    target = db.get_user(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_id == current_user["id"] and not is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot deactivate your own account.")
    if target["role"] == "admin" and not is_active and db.count_active_admins(exclude_user_id=user_id) == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cannot deactivate the last active admin account."
        )
    db.set_user_active(user_id, is_active)
    return UserOut(**db.get_user(user_id))


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int, payload: ResetPasswordRequest, current_user: dict = Depends(require_role("admin"))
) -> None:
    if db.get_user(user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    db.reset_password(user_id, payload.new_password)
