"""Streamlit entrypoint - a thin client for the FastAPI backend.

Start the backend first (uvicorn backend.app.main:app --reload), then run
this with `streamlit run streamlit_app.py`. This file (and everything under
app/) must never import src.db/src.tools/src.ingestion directly - see
app/api_client.py and backend/app/main.py.
"""
from __future__ import annotations

import streamlit as st

from app.state import get_current_user, logout
from app.views.admin_views import admin_notifications_view, admin_schemes_view, admin_submissions_view
from app.views.applicant_views import my_submissions_view, schemes_view, submit_view
from app.views.auth_views import login_view, register_view
from app.views.notifications_view import notifications_banner

st.set_page_config(page_title="Application Intelligence Platform", layout="wide")

user = get_current_user()

if not user:
    st.title("Application Intelligence Platform")
    tab_login, tab_register = st.tabs(["Log in", "Register"])
    with tab_login:
        login_view()
    with tab_register:
        register_view()
    st.stop()

st.sidebar.write(f"Signed in as **{user['full_name']}** ({user['role']})")
if st.sidebar.button("Log out"):
    logout()
    st.rerun()

if user["role"] == "admin":
    page = st.sidebar.radio("Navigate", ["Review Submissions", "Manage Schemes", "Notifications"])
else:
    page = st.sidebar.radio("Navigate", ["Schemes", "Submit Application", "My Submissions"])

st.title("Application Intelligence Platform")
notifications_banner()

if user["role"] == "admin":
    if page == "Review Submissions":
        admin_submissions_view(user)
    elif page == "Manage Schemes":
        admin_schemes_view(user)
    elif page == "Notifications":
        admin_notifications_view(user)
else:
    if page == "Schemes":
        schemes_view()
    elif page == "Submit Application":
        submit_view(user)
    elif page == "My Submissions":
        my_submissions_view(user)
