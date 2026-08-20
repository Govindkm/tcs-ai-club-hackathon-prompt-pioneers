"""Admin views: review submissions, manage schemes, publish notifications.

Thin wrappers only - every decision requires an explicit human-entered
rationale and is recorded via the backend's /applications/{id}/review
endpoint (backend/app/api/reviews.py); no path here can auto-finalize a case.
"""
from __future__ import annotations

import streamlit as st

from app.api_client import BackendError
from app.state import get_client

_DECISION_OPTIONS = ["needs_more_info", "approved", "rejected"]
_DECISION_LABELS = {
    "needs_more_info": "Request more information",
    "approved": "Approve",
    "rejected": "Reject",
}
_ANALYSIS_STATUS_LABELS = {
    "queued": "⏳ Queued",
    "running": "⚙️ Running",
    "completed": "✅ Completed",
    "failed": "❌ Failed",
}
_EVENT_ICONS = {
    "stage_start": "▶️",
    "reasoning": "🧠",
    "text": "💬",
    "tool_call": "🔧",
    "stage_complete": "✅",
    "error": "❌",
}


def admin_submissions_view(user: dict) -> None:
    st.subheader("Review Submissions")
    client = get_client()
    status_filter = st.selectbox(
        "Filter by status",
        ["all", "submitted", "under_review", "needs_more_info", "approved", "rejected"],
    )
    submissions = client.list_all_applications(None if status_filter == "all" else status_filter)
    if not submissions:
        st.info("No submissions match this filter.")
        return

    for sub in submissions:
        applicant_label = sub.get("applicant_name") or f"user #{sub['user_id']}"
        scheme_label = sub.get("scheme_name") or f"scheme #{sub['scheme_id']}"
        analysis_badge = _ANALYSIS_STATUS_LABELS.get(sub["analysis_status"], sub["analysis_status"])
        label = f"#{sub['id']} · {applicant_label} · {scheme_label} · {sub['status']} · {analysis_badge}"
        with st.expander(label):
            st.write(f"Submitted: {sub['created_at']}")
            st.text_area(
                "Document content", sub["document_text"], height=150, disabled=True, key=f"doc_{sub['id']}"
            )

            cols = st.columns([1, 4])
            if cols[0].button("🔄 Refresh", key=f"refresh_{sub['id']}"):
                st.rerun()
            cols[1].caption(
                f"Analysis: {analysis_badge}"
                + (f" ({sub['analysis_stage']})" if sub.get("analysis_stage") else "")
            )
            if sub["analysis_status"] == "failed" and sub.get("analysis_error"):
                st.error(f"Last analysis error: {sub['analysis_error']}")

            if sub.get("extracted_fields"):
                st.json(sub["extracted_fields"])
            if sub.get("validation_result"):
                st.json(sub["validation_result"])
            if sub.get("score") is not None:
                st.markdown(f"**Advisory score:** {sub['score']}")
                st.json(sub["score_explanation"])

            with st.expander("🧠 AI reasoning & thinking (live log)"):
                events = client.list_analysis_events(sub["id"])
                if not events:
                    st.caption("No reasoning captured yet.")
                for event in events:
                    icon = _EVENT_ICONS.get(event["event_type"], "•")
                    st.caption(f"{icon} [{event['stage']}] {event['created_at']}")
                    if event["content"]:
                        st.code(event["content"], language=None)
                if st.button("🔄 Refresh log", key=f"refresh_events_{sub['id']}"):
                    st.rerun()

            with st.form(f"analyze_form_{sub['id']}"):
                feedback = st.text_area(
                    "Feedback for the AI (optional - human-in-the-loop guidance incorporated into the next run)",
                    key=f"feedback_{sub['id']}",
                )
                run_analysis = st.form_submit_button("Run/re-run AI analysis")
            if run_analysis:
                try:
                    client.analyze_application(sub["id"], feedback=feedback)
                except BackendError as exc:
                    st.error(str(exc))
                else:
                    st.success("Analysis queued - refresh in a few seconds to see progress.")
                    st.rerun()

            reviews = client.list_reviews(sub["id"])
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
                    try:
                        client.submit_review(sub["id"], decision, rationale)
                    except BackendError as exc:
                        st.error(str(exc))
                    else:
                        st.success("Decision recorded.")
                        st.rerun()


def admin_schemes_view(user: dict) -> None:
    st.subheader("Manage Schemes")
    client = get_client()
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
            client.create_scheme(name, description, eligibility, required_documents)
            st.success(f"Scheme '{name}' created.")
            st.rerun()

    st.divider()
    st.markdown("### Existing schemes")
    for scheme in client.list_schemes(active_only=False):
        cols = st.columns([4, 1])
        cols[0].write(f"**{scheme['name']}** — {'active' if scheme['is_active'] else 'inactive'}")
        toggle_label = "Deactivate" if scheme["is_active"] else "Activate"
        if cols[1].button(toggle_label, key=f"toggle_scheme_{scheme['id']}"):
            client.set_scheme_active(scheme["id"], not scheme["is_active"])
            st.rerun()


def admin_notifications_view(user: dict) -> None:
    st.subheader("Publish Notifications")
    client = get_client()
    with st.form("new_notification_form"):
        title = st.text_input("Title")
        message = st.text_area("Message")
        submitted = st.form_submit_button("Publish")
    if submitted:
        if not title.strip() or not message.strip():
            st.error("Title and message are required.")
        else:
            client.create_notification(title, message)
            st.success("Notification published.")
            st.rerun()

    st.divider()
    st.markdown("### Active notifications")
    for note in client.list_notifications():
        cols = st.columns([4, 1])
        cols[0].write(f"**{note['title']}** — {note['message']}")
        if cols[1].button("Remove", key=f"remove_note_{note['id']}"):
            client.deactivate_notification(note["id"])
            st.rerun()
