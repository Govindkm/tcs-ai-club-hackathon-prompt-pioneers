"""Streamlit session-state helpers for the authenticated user + API client."""
from __future__ import annotations

import streamlit as st

from app.api_client import BackendClient


def get_client() -> BackendClient:
    if "client" not in st.session_state:
        st.session_state["client"] = BackendClient()
    return st.session_state["client"]


def get_current_user() -> dict | None:
    return st.session_state.get("user")


def set_session(user: dict, token: str) -> None:
    st.session_state["user"] = user
    st.session_state["client"] = BackendClient(token=token)


def logout() -> None:
    st.session_state.pop("user", None)
    st.session_state.pop("client", None)
