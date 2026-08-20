"""Human review decision endpoints - the only path that can finalize a case."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.schemas import ReviewIn, ReviewOut
from backend.app.security import get_current_user, require_role
from src.db import repository as db

router = APIRouter(prefix="/api/v1/applications", tags=["reviews"])


@router.post("/{application_id}/review", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def submit_review(
    application_id: int, payload: ReviewIn, current_user: dict = Depends(require_role("admin"))
) -> ReviewOut:
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if submission["status"] in ("approved", "rejected"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This case has already been finalized.")

    db.record_review(application_id, current_user["id"], payload.decision, payload.rationale)
    reviews = db.list_reviews_for_submission(application_id)
    return ReviewOut(**reviews[-1])


@router.get("/{application_id}/reviews", response_model=list[ReviewOut])
def list_reviews(application_id: int, current_user: dict = Depends(get_current_user)) -> list[ReviewOut]:
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if current_user["role"] != "admin" and submission["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your application")
    return [ReviewOut(**r) for r in db.list_reviews_for_submission(application_id)]
