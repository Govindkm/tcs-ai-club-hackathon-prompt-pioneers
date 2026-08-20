"""Notification board endpoints - visible to all users, managed by admins."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from backend.app.schemas import NotificationIn, NotificationOut
from backend.app.security import get_current_user, require_role
from src.db import repository as db

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(current_user: dict = Depends(get_current_user)) -> list[NotificationOut]:
    return [NotificationOut(**n) for n in db.list_active_notifications()]


@router.post("", response_model=NotificationOut, status_code=status.HTTP_201_CREATED)
def create_notification(
    payload: NotificationIn, current_user: dict = Depends(require_role("admin"))
) -> NotificationOut:
    notification_id = db.create_notification(payload.title, payload.message, current_user["id"])
    return NotificationOut(**next(n for n in db.list_active_notifications() if n["id"] == notification_id))


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_notification(notification_id: int, current_user: dict = Depends(require_role("admin"))) -> None:
    db.deactivate_notification(notification_id)
