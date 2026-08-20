"""JWT auth: token creation/verification and FastAPI auth dependencies.

Kept deliberately simple for this POC (HS256, claims embedded in the token so
no DB round-trip is needed per request) - swap for OAuth2/OIDC/Azure AD/a
government IdP later without touching any API route or service code below.
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

_bearer_scheme = HTTPBearer(auto_error=False)
_fallback_secret: str | None = None


def _get_secret_key() -> str:
    global _fallback_secret
    secret = os.getenv("JWT_SECRET_KEY")
    if secret:
        return secret
    if _fallback_secret is None:
        _fallback_secret = secrets.token_hex(32)
        logger.warning(
            "JWT_SECRET_KEY not set - using an ephemeral random secret for this process only "
            "(existing tokens won't survive a restart). Set JWT_SECRET_KEY in .env for production."
        )
    return _fallback_secret


def create_access_token(user: dict) -> str:
    claims = {
        "sub": str(user["id"]),
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(claims, _get_secret_key(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc
    return {
        "id": int(payload["sub"]),
        "username": payload["username"],
        "full_name": payload["full_name"],
        "role": payload["role"],
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return decode_access_token(credentials.credentials)


def require_role(role: str):
    """Dependency factory: only allow the given role (e.g. require_role('admin'))."""

    def _dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires '{role}' role")
        return current_user

    return _dependency
