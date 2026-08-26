"""Authentication endpoints: register (applicant-only) and login."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from backend.app.security import create_access_token
from src.db import repository as db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> UserOut:
    # Self-registration always creates an applicant - admins are provisioned via scripts/seed_db.py.
    try:
        user_id = db.create_user(
            username=payload.username,
            password=payload.password,
            full_name=payload.full_name,
            role="applicant",
            email=payload.email,
            organisation_name=payload.organisation_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserOut(
        id=user_id,
        username=payload.username,
        full_name=payload.full_name,
        role="applicant",
        email=payload.email,
        organisation_name=payload.organisation_name,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    user = db.authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token = create_access_token(user)
    return TokenResponse(access_token=token, user=UserOut(**user))
