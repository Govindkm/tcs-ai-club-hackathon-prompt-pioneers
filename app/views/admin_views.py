"""Admin views: review submissions, manage schemes, publish notifications.

Every decision requires an explicit human-entered rationale and is written
via src.db.repository.record_review - no path here can auto-finalize a case.
"""
from __future__ import annotations

import streamlit as st

from src.db import repository as db

_DECISION_OPTIONS = ["needs_more_info", "approved", "rejected"]
_DECISION_LABELS = {
    "needs_more_info": "Request more information",
    "approved": "Approve",
    "rejected": "Reject",
}


def admin_submissions_view(user: dict) -> None:
    st.subheader("Review Submissions")
    status_filter = st.selectbox(
        "Filter by status",
        ["all", "submitted", "under_review", "needs_more_info", "approved", "rejected"],
    )
    submissions = db.list_all_submissions(None if status_filter == "all" else status_filter)
    if not submissions:
        st.info("No submissions match this filter.")
        return

    for sub in submissions:
        label = f"#{sub['id']} · {sub['applicant_name']} · {sub['scheme_name']} · {sub['status']}"
        with st.expander(label):
            st.write(f"Submitted: {sub['created_at']}")
            st.text_area(
                "Document content", sub["document_text"], height=150, disabled=True, key=f"doc_{sub['id']}"
            )
            if sub["extracted_fields"]:
                st.json(sub["extracted_fields"])
            if sub["validation_result"]:
                st.json(sub["validation_result"])
            if sub["score"] is not None:
                st.markdown(f"**Advisory score:** {sub['score']}")
                st.json(sub["score_explanation"])

            reviews = db.list_reviews_for_submission(sub["id"])
            if reviews:
                st.markdown("**Review history**")
                for r in reviews:
                    st.caption(f"{r['created_at']} · {r['decision']} · {r['rationale']}")

            if sub["status"] in ("approved", "rejected"):
                st.success("This case has already been finalized.")
                continue

            with st.form(f"review_form_{sub['id']}"):
                decision = st.selectbox(
                    "Decision",
                    _DECISION_OPTIONS,
                    format_func=lambda d: _DECISION_LABELS[d],
                    key=f"decision_{sub['id']}",
                )
                rationale = st.text_area("Rationale", key=f"rationale_{sub['id']}")
                submitted = st.form_submit_button("Record decision")
            if submitted:
                if not rationale.strip():
                    st.error("A rationale is required for auditability.")
                else:
                    db.record_review(sub["id"], user["id"], decision, rationale)
                    st.success("Decision recorded.")
                    st.rerun()


def admin_schemes_view(user: dict) -> None:
    st.subheader("Manage Schemes")
    with st.form("new_scheme_form"):
        name = st.text_input("Scheme name")
        description = st.text_area("Description")
        eligibility = st.text_area("Eligibility criteria")
        required_documents = st.text_area("Required documents")
        submitted = st.form_submit_button("Create scheme")
    if submitted:
        if not name.strip() or not description.strip():
            st.error("Name and description are required.")
        else:
            db.create_scheme(name, description, eligibility, required_documents, user["id"])
            st.success(f"Scheme '{name}' created.")
            st.rerun()

    st.divider()
    st.markdown("### Existing schemes")
    for scheme in db.list_schemes(active_only=False):
        cols = st.columns([4, 1])
        cols[0].write(f"**{scheme['name']}** — {'active' if scheme['is_active'] else 'inactive'}")
        toggle_label = "Deactivate" if scheme["is_active"] else "Activate"
        if cols[1].button(toggle_label, key=f"toggle_scheme_{scheme['id']}"):
            db.set_scheme_active(scheme["id"], not scheme["is_active"])
            st.rerun()


def admin_notifications_view(user: dict) -> None:
    st.subheader("Publish Notifications")
    with st.form("new_notification_form"):
        title = st.text_input("Title")
        message = st.text_area("Message")
        submitted = st.form_submit_button("Publish")
    if submitted:
        if not title.strip() or not message.strip():
            st.error("Title and message are required.")
        else:
            db.create_notification(title, message, user["id"])
            st.success("Notification published.")
            st.rerun()

    st.divider()
    st.markdown("### Active notifications")
    for note in db.list_active_notifications():
        cols = st.columns([4, 1])
        cols[0].write(f"**{note['title']}** — {note['message']}")
        if cols[1].button("Remove", key=f"remove_note_{note['id']}"):
            db.deactivate_notification(note["id"])
            st.rerun()
