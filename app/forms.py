"""Helpers for clearing Streamlit form state only after a successful submit.

`st.form(clear_on_submit=True)` wipes input on every submit, including failed
ones. These helpers instead clear widget state explicitly on success and carry
the confirmation message across the rerun that re-renders the empty form.
"""
from __future__ import annotations

import streamlit as st

_FLASH_PREFIX = "_flash__"
_NONCE_PREFIX = "_nonce__"


def clear_fields(*keys: str) -> None:
    """Drop each widget's stored value so it renders empty after the next rerun."""
    for key in keys:
        st.session_state.pop(key, None)


def uploader_key(name: str) -> str:
    """Key for a file_uploader; changing it is the only way to drop already-selected files."""
    return f"{name}__{st.session_state.get(_NONCE_PREFIX + name, 0)}"


def reset_uploader(name: str) -> None:
    st.session_state.pop(uploader_key(name), None)
    st.session_state[_NONCE_PREFIX + name] = st.session_state.get(_NONCE_PREFIX + name, 0) + 1


def set_flash(scope: str, message: str) -> None:
    """Queue a success message for the rerun that clears the form."""
    st.session_state[_FLASH_PREFIX + scope] = message


def render_flash(scope: str) -> None:
    message = st.session_state.pop(_FLASH_PREFIX + scope, None)
    if message:
        st.success(message)
