"""Admin views: review submissions, manage schemes, publish notifications.

Thin wrappers only - every decision requires an explicit human-entered
rationale and is recorded via the backend's /applications/{id}/review
endpoint (backend/app/api/reviews.py); no path here can auto-finalize a case.
"""
from __future__ import annotations

import streamlit as st

from app.api_client import BackendError
from app.analysis_view import render_ai_analysis
from app.file_preview import render_submitted_files
from app.scoring_pattern import render_scoring_pattern
from app.state import get_client
from app.timeline import render_timeline

_DECISION_OPTIONS = ["needs_more_info", "approved", "rejected"]
_DECISION_LABELS = {
    "needs_more_info": "Request more information",
    "approved": "Approve",
    "rejected": "Reject",
}
_TIMELINE_STAGE_LABELS = {
    "ingesting": "🟠 Ingesting & indexing",
    "awaiting_admin_review": "🟠 Awaiting admin assignment",
    "extraction_running": "🟢 Extraction running",
    "validation_running": "🟢 Validation running",
    "awaiting_admin_validation": "🟢 Awaiting admin validation review",
    "scoring_running": "🟢 Scoring running",
    "awaiting_score_approval": "🟠 Awaiting score approval",
    "completed": "🟢 Completed",
    "failed": "🔴 Failed",
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
        timeline_label = _TIMELINE_STAGE_LABELS.get(sub["timeline_stage"], sub["timeline_stage"])
        label = f"#{sub['id']} · {applicant_label} · {scheme_label} · {sub['status']} · {timeline_label}"
        with st.expander(label):
            st.write(f"Submitted: {sub['created_at']}")
            render_timeline(sub)
            render_submitted_files(client, sub["id"])

            assigned_label = sub.get("assigned_admin_name") or "Unassigned"
            st.caption(f"Assigned admin: **{assigned_label}**")

            cols = st.columns([1, 4])
            if cols[0].button("🔄 Refresh", key=f"refresh_{sub['id']}"):
                st.rerun()
            if sub["analysis_status"] == "failed" and sub.get("analysis_error"):
                st.error(f"Last analysis error: {sub['analysis_error']}")
                if st.button("♻️ Restart pipeline from failed step", key=f"restart_{sub['id']}"):
                    try:
                        client.restart_pipeline(sub["id"])
                    except BackendError as exc:
                        st.error(str(exc))
                    else:
                        st.success("Pipeline restarted.")
                        st.rerun()

            if sub.get("reevaluation_request"):
                st.info(
                    f"📩 Applicant requested re-evaluation ({sub.get('reevaluation_requested_at', '')}): "
                    f"{sub['reevaluation_request']}"
                )

            if sub.get("plagiarism_result"):
                plag = sub["plagiarism_result"]
                if plag.get("flagged"):
                    st.warning("⚠️ Potential plagiarism/duplicate content detected against other indexed submissions.")
                with st.expander("🔎 Plagiarism / duplicate-content check"):
                    st.json(plag)

            is_assigned_admin = sub.get("assigned_admin_id") == user["id"]

            # --- Stage 1: assignment ---
            if sub["timeline_stage"] == "awaiting_admin_review":
                if st.button("🙋 Assign myself for AI analysis", key=f"assign_{sub['id']}"):
                    try:
                        client.assign_for_analysis(sub["id"])
                    except BackendError as exc:
                        st.error(str(exc))
                    else:
                        st.success("Assigned - extraction & validation started.")
                        st.rerun()

            if any(sub.get(key) for key in ("extracted_fields", "summary", "validation_result", "score")):
                render_ai_analysis(sub, show_raw_details=True)
            if sub.get("validation_feedback"):
                st.caption(f"Last feedback given: {sub['validation_feedback']}")

            # --- Stage 2: validation review (assigned admin only controls; all can view) ---
            if sub["timeline_stage"] == "awaiting_admin_validation":
                if is_assigned_admin:
                    with st.form(f"validation_form_{sub['id']}"):
                        feedback = st.text_area(
                            "Instructions for the validation agent (optional - resumes/re-checks validation)",
                            key=f"val_feedback_{sub['id']}",
                        )
                        resume = st.form_submit_button("🔁 Resume validation with feedback")
                        complete = st.form_submit_button("✅ Mark validation complete → run scoring")
                    if resume:
                        if not feedback.strip():
                            st.error("Provide instructions to resume validation.")
                        else:
                            client.submit_validation_feedback(sub["id"], feedback)
                            st.success("Validation resumed with feedback.")
                            st.rerun()
                    if complete:
                        client.complete_validation(sub["id"])
                        st.success("Validation marked complete - scoring started.")
                        st.rerun()
                else:
                    st.info(f"Awaiting {assigned_label}'s validation review.")

            # --- Stage 3: score approval (any admin) ---
            if sub["timeline_stage"] in ("awaiting_score_approval", "completed"):
                approvals = client.list_score_approvals(sub["id"])
                approver_ids = {a["admin_id"] for a in approvals}
                st.caption(
                    f"Score approvals: {len(approvals)}/2 "
                    + (", ".join(a["admin_name"] for a in approvals) if approvals else "none yet")
                )
                if sub["timeline_stage"] == "awaiting_score_approval" and user["id"] not in approver_ids:
                    if st.button("👍 Approve score", key=f"approve_score_{sub['id']}"):
                        client.approve_score(sub["id"])
                        st.success("Score approval recorded.")
                        st.rerun()
                elif sub["timeline_stage"] == "completed":
                    st.success("This submission's timeline is complete.")

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

            with st.expander("🔧 Legacy: manual re-run (feedback-only retry)"):
                with st.form(f"analyze_form_{sub['id']}"):
                    feedback = st.text_area(
                        "Feedback for the AI (optional - human-in-the-loop guidance incorporated into the next run)",
                        key=f"feedback_{sub['id']}",
                    )
                    run_analysis = st.form_submit_button("Re-run extraction/validation")
                if run_analysis:
                    try:
                        client.analyze_application(sub["id"], feedback=feedback)
                    except BackendError as exc:
                        st.error(str(exc))
                    else:
                        st.success("Analysis restarted - refresh in a few seconds to see progress.")
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
        label = f"{scheme['name']} — {'active' if scheme['is_active'] else 'inactive'}"
        if scheme.get("pending_update"):
            label += " · ⏳ pending edit"
        with st.expander(label):
            st.write(scheme["description"])
            if scheme["eligibility"]:
                st.markdown(f"**Eligibility:** {scheme['eligibility']}")
            if scheme["required_documents"]:
                st.markdown(f"**Required documents:** {scheme['required_documents']}")
            render_scoring_pattern(scheme.get("scoring_pattern"))

            toggle_label = "Deactivate" if scheme["is_active"] else "Activate"
            if st.button(toggle_label, key=f"toggle_scheme_{scheme['id']}"):
                client.set_scheme_active(scheme["id"], not scheme["is_active"])
                st.rerun()

            if scheme.get("pending_update"):
                pending = scheme["pending_update"]
                st.info(
                    f"⏳ Pending edit proposed by {scheme.get('pending_update_by_name') or 'an admin'} "
                    f"({scheme.get('pending_update_at', '')}) - needs 2 distinct admin approvals to apply."
                )
                st.markdown("**Proposed changes:**")
                st.json({k: v for k, v in pending.items() if k != "scoring_pattern"})
                render_scoring_pattern(pending.get("scoring_pattern"), heading="📊 Proposed scoring pattern")
                approvals = client.list_scheme_update_approvals(scheme["id"])
                approver_ids = {a["admin_id"] for a in approvals}
                st.caption(
                    f"Approvals: {len(approvals)}/2 "
                    + (", ".join(a["admin_name"] for a in approvals) if approvals else "none yet")
                )
                if user["id"] not in approver_ids:
                    if st.button("👍 Approve this edit", key=f"approve_scheme_{scheme['id']}"):
                        client.approve_scheme_update(scheme["id"])
                        st.success("Approval recorded.")
                        st.rerun()
                else:
                    st.caption("You already approved this edit.")
            elif st.toggle("✏️ Edit this scheme", key=f"edit_toggle_{scheme['id']}"):
                with st.form(f"edit_scheme_form_{scheme['id']}"):
                    new_name = st.text_input("Scheme name", value=scheme["name"])
                    new_description = st.text_area("Description", value=scheme["description"])
                    new_eligibility = st.text_area("Eligibility criteria", value=scheme["eligibility"])
                    new_required_documents = st.text_area(
                        "Required documents", value=scheme["required_documents"]
                    )
                    propose = st.form_submit_button("Propose update (needs 2 admin approvals)")
                if propose:
                    if not new_name.strip() or not new_description.strip():
                        st.error("Name and description are required.")
                    else:
                        client.propose_scheme_update(
                            scheme["id"], new_name, new_description, new_eligibility, new_required_documents
                        )
                        st.success("Update proposed - awaiting admin approvals.")
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


def admin_users_view(user: dict) -> None:
    st.subheader("Manage Admins & Users")
    client = get_client()

    st.markdown("### Create a new admin")
    with st.form("new_admin_form"):
        full_name = st.text_input("Full name")
        email = st.text_input("Email (optional)")
        username = st.text_input("Username")
        password = st.text_input("Temporary password", type="password")
        submitted = st.form_submit_button("Create admin")
    if submitted:
        if not full_name.strip() or not username.strip() or len(password) < 8:
            st.error("Full name and username are required; password must be at least 8 characters.")
        else:
            try:
                client.create_admin(username.strip(), password, full_name.strip(), email.strip() or None)
            except BackendError as exc:
                st.error(str(exc))
            else:
                st.success(f"Admin '{username}' created.")
                st.rerun()

    st.divider()
    st.markdown("### All users")
    for u in client.list_users():
        cols = st.columns([3, 2, 2, 2, 2])
        status_label = "🟢 Active" if u["is_active"] else "🔴 Deactivated"
        org_suffix = f" · {u['organisation_name']}" if u.get("organisation_name") else ""
        cols[0].write(f"**{u['full_name']}** (@{u['username']}){org_suffix}")
        if u.get("email"):
            cols[0].caption(u["email"])
        cols[1].caption(u["role"])
        cols[2].caption(status_label)

        is_self = u["id"] == user["id"]
        toggle_label = "Deactivate" if u["is_active"] else "Activate"
        if cols[3].button(toggle_label, key=f"toggle_user_{u['id']}", disabled=is_self):
            try:
                client.set_user_active(u["id"], not u["is_active"])
            except BackendError as exc:
                st.error(str(exc))
            else:
                st.rerun()

        with cols[4].popover("Reset password"):
            new_password = st.text_input(
                "New password", type="password", key=f"reset_pw_{u['id']}", help="At least 8 characters."
            )
            if st.button("Confirm reset", key=f"confirm_reset_{u['id']}"):
                if len(new_password) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    try:
                        client.reset_user_password(u["id"], new_password)
                    except BackendError as exc:
                        st.error(str(exc))
                    else:
                        st.success("Password reset.")
