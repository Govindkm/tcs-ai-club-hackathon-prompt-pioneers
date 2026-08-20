"""Login and self-registration views.

Self-registration always creates an 'applicant' account - admin accounts are
provisioned separately (see scripts/seed_db.py) to avoid privilege escalation.
"""
from __future__ import annotations

import streamlit as st

from app.state import set_current_user
from src.db import repository as db


def login_view() -> None:
    st.subheader("Log in")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")
    if submitted:
        user = db.authenticate(username, password)
        if user:
            set_current_user(user)
            st.rerun()
        else:
            st.error("Invalid username or password.")


def register_view() -> None:
    st.subheader("Create an account")
    with st.form("register_form"):
        full_name = st.text_input("Full name")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Register")
    if submitted:
        if not username or not password or not full_name:
            st.error("All fields are required.")
        elif password != confirm:
            st.error("Passwords do not match.")
        elif len(password) < 8:
            st.error("Password must be at least 8 characters.")
        else:
            try:
                db.create_user(username=username, password=password, full_name=full_name, role="applicant")
                st.success("Account created. You can now log in from the Log in tab.")
            except ValueError as exc:
                st.error(str(exc))
