"""Streamlit session-state helpers for the authenticated user."""
from __future__ import annotations

import streamlit as st


def get_current_user() -> dict | None:
    return st.session_state.get("user")


def set_current_user(user: dict) -> None:
    st.session_state["user"] = user


def logout() -> None:
    st.session_state.pop("user", None)
