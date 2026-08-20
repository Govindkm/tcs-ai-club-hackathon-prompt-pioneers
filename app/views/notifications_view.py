"""Shared notifications board, visible to every authenticated user."""
from __future__ import annotations

import streamlit as st

from src.db import repository as db


def notifications_banner() -> None:
    notifications = db.list_active_notifications()
    if not notifications:
        return
    with st.expander(f"📢 Notifications ({len(notifications)})"):
        for note in notifications:
            st.markdown(f"**{note['title']}**")
            st.caption(note["created_at"])
            st.write(note["message"])
            st.divider()
