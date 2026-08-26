"""Login and self-registration views - thin wrappers around the backend API.

Self-registration always creates an 'applicant' account (enforced server-side
in backend/app/api/auth.py) - admin accounts are provisioned separately (see
scripts/seed_db.py) to avoid privilege escalation.
"""
from __future__ import annotations

import streamlit as st

from app.api_client import BackendError
from app.state import get_client, set_session


def login_view() -> None:
    st.subheader("Log in")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")
    if submitted:
        try:
            result = get_client().login(username, password)
        except BackendError as exc:
            st.error(str(exc))
            return
        set_session(result["user"], result["access_token"])
        st.rerun()


def register_view() -> None:
    st.subheader("Create an account")
    with st.form("register_form"):
        full_name = st.text_input("Full name")
        email = st.text_input("Email")
        organisation_name = st.text_input("Organisation name")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Register")
    if submitted:
        if not username or not password or not full_name or not email or not organisation_name:
            st.error("All fields are required.")
        elif "@" not in email or "." not in email.split("@")[-1]:
            st.error("Please enter a valid email address.")
        elif password != confirm:
            st.error("Passwords do not match.")
        elif len(password) < 8:
            st.error("Password must be at least 8 characters.")
        else:
            try:
                get_client().register(username, password, full_name, email, organisation_name)
                st.success("Account created. You can now log in from the Log in tab.")
            except BackendError as exc:
                st.error(str(exc))
