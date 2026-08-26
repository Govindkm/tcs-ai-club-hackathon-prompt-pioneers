"""Applicant-facing views: browse schemes, submit applications, track status.

Thin wrappers only - all extraction/validation/scoring/persistence logic
lives behind the FastAPI backend (see backend/app/api/applications.py) so
this UI could be swapped for React/mobile/a government portal unchanged.
"""
from __future__ import annotations

import streamlit as st

from app.api_client import BackendError
from app.analysis_view import render_ai_analysis
from app.file_preview import render_submitted_files
from app.forms import clear_fields, render_flash, reset_uploader, set_flash, uploader_key
from app.scoring_pattern import render_scoring_pattern
from app.state import get_client
from app.timeline import render_timeline

_STATUS_LABELS = {
    "submitted": "Submitted",
    "under_review": "Under review",
    "needs_more_info": "Needs more information",
    "approved": "Approved",
    "rejected": "Rejected",
}
_SUBMIT_UPLOADER = "submit_documents"
_SUBMIT_TEXT_FIELDS = ("submit_pasted_text", "submit_notes")


def schemes_view() -> None:
    st.subheader("Available Schemes")
    schemes = get_client().list_schemes()
    if not schemes:
        st.info("No schemes are currently open for applications.")
        return
    for scheme in schemes:
        with st.expander(scheme["name"]):
            st.write(scheme["description"])
            if scheme["eligibility"]:
                st.markdown(f"**Eligibility:** {scheme['eligibility']}")
            if scheme["required_documents"]:
                st.markdown(f"**Required documents:** {scheme['required_documents']}")
            render_scoring_pattern(scheme.get("scoring_pattern"), heading="📊 How applications are scored")


def submit_view(user: dict) -> None:
    st.subheader("Submit an Application")
    client = get_client()
    schemes = client.list_schemes()
    if not schemes:
        st.info("No schemes are currently open for applications.")
        return

    render_flash("submit_application")
    scheme_options = {s["name"]: s["id"] for s in schemes}
    scheme_name = st.selectbox("Scheme", list(scheme_options.keys()))
    uploaded_files = st.file_uploader(
        "Application documents",
        type=["pdf", "docx", "pptx", "xlsx", "txt", "csv", "png", "jpg", "jpeg", "bmp", "tiff", "webp", "zip"],
        accept_multiple_files=True,
        key=uploader_key(_SUBMIT_UPLOADER),
        help=(
            "Upload one or more supporting documents (PDF, Word, PowerPoint, Excel, "
            "images, or plain text), or a single .zip containing a mix of these."
        ),
    )
    pasted_text = st.text_area(
        "Or paste document content directly (optional)",
        height=150,
        key="submit_pasted_text",
        help="Use this if you don't have files to upload, or to add extra context.",
    )
    notes = st.text_area("Additional notes (optional)", key="submit_notes")

    if st.button("Submit application", type="primary"):
        files = [(f.name, f.getvalue()) for f in (uploaded_files or [])]
        if not files and not pasted_text.strip():
            st.error("Please upload at least one document or paste some content.")
            return
        try:
            result = client.submit_application(scheme_options[scheme_name], notes, pasted_text, files)
        except BackendError as exc:
            st.error(str(exc))
            return
        set_flash("submit_application", f"Application submitted (reference #{result['id']}).")
        clear_fields(*_SUBMIT_TEXT_FIELDS)
        reset_uploader(_SUBMIT_UPLOADER)
        st.rerun()


def my_submissions_view(user: dict) -> None:
    st.subheader("My Submissions")
    client = get_client()
    submissions = client.list_my_applications()
    if not submissions:
        st.info("You haven't submitted any applications yet.")
        return

    for sub in submissions:
        scheme_label = sub.get("scheme_name") or f"scheme #{sub['scheme_id']}"
        label = f"#{sub['id']} · {scheme_label} · {_STATUS_LABELS.get(sub['status'], sub['status'])}"
        with st.expander(label):
            st.write(f"Submitted: {sub['created_at']}")
            render_timeline(sub)
            render_submitted_files(client, sub["id"])
            if sub.get("assigned_admin_name"):
                st.caption(f"Being handled by: {sub['assigned_admin_name']}")
            if sub["analysis_status"] in ("queued", "running"):
                st.info("Your application is being analyzed by our AI review pipeline...")
            elif sub["analysis_status"] == "failed":
                st.warning("Analysis hit a temporary issue; a reviewer will follow up shortly.")
            if any(sub.get(key) for key in ("extracted_fields", "summary", "validation_result", "score")):
                render_ai_analysis(sub)
            if sub["timeline_stage"] == "completed":
                st.success("Score approved by admins - your submission's review timeline is complete.")

            reviews = client.list_reviews(sub["id"])
            if sub["status"] in ("approved", "rejected"):
                st.markdown(f"### Final decision: {_STATUS_LABELS[sub['status']]}")
                if reviews:
                    st.write(f"Reviewer note: {reviews[-1]['rationale']}")
            elif sub["status"] == "needs_more_info" and reviews:
                st.warning(f"Reviewer requested more information: {reviews[-1]['rationale']}")
            else:
                st.info("Your application is being processed.")

            if sub.get("reevaluation_request"):
                st.caption(
                    f"📩 Re-evaluation requested ({sub.get('reevaluation_requested_at', '')}): "
                    f"{sub['reevaluation_request']}"
                )
            _render_edit_controls(client, sub)
            with st.form(f"reevaluate_form_{sub['id']}"):
                details = st.text_area(
                    "Request a re-evaluation with changes (describe what to re-check or update)",
                    key=f"reevaluate_details_{sub['id']}",
                )
                requested = st.form_submit_button("Request re-evaluation")
            if requested:
                if not details.strip():
                    st.error("Please describe the change/clarification you want re-checked.")
                else:
                    try:
                        client.request_reevaluation(sub["id"], details)
                    except BackendError as exc:
                        st.error(str(exc))
                    else:
                        st.success("Re-evaluation request sent to the admins.")
                        st.rerun()


def _render_edit_controls(client, sub: dict) -> None:
    """Let the applicant re-point the submission at another scheme and replace its documents."""
    submission_id = sub["id"]
    render_flash(f"edit_submission_{submission_id}")
    if sub.get("scheme_closing_date"):
        st.caption(f"🗓️ Editing closes on {sub['scheme_closing_date']}.")
    if not sub.get("is_editable"):
        st.caption(f"🔒 Editing is closed. {sub.get('lock_reason') or ''}".strip())
        return

    if not st.toggle("✏️ Edit this submission", key=f"edit_toggle_{submission_id}"):
        return

    st.caption("Submitting an edit replaces the documents on file and restarts the review from the start.")
    schemes = client.list_schemes()
    scheme_names = [s["name"] for s in schemes]
    current_index = next((i for i, s in enumerate(schemes) if s["id"] == sub["scheme_id"]), 0)
    scheme_name = st.selectbox(
        "Scheme", scheme_names, index=current_index if scheme_names else 0, key=f"edit_scheme_{submission_id}"
    )
    uploaded_files = st.file_uploader(
        "Replacement documents",
        type=["pdf", "docx", "pptx", "xlsx", "txt", "csv", "png", "jpg", "jpeg", "bmp", "tiff", "webp", "zip"],
        accept_multiple_files=True,
        key=uploader_key(f"edit_documents_{submission_id}"),
    )
    pasted_text = st.text_area(
        "Or paste document content directly",
        height=120,
        key=f"edit_pasted_text_{submission_id}",
    )
    notes = st.text_area(
        "Additional notes (optional)",
        key=f"edit_notes_{submission_id}",
        value=sub.get("applicant_notes") or "",
    )

    if st.button("Save changes", type="primary", key=f"edit_save_{submission_id}"):
        files = [(f.name, f.getvalue()) for f in (uploaded_files or [])]
        if not files and not pasted_text.strip():
            st.error("Please upload at least one document or paste some content.")
            return
        scheme_id = next(s["id"] for s in schemes if s["name"] == scheme_name)
        try:
            client.update_application(submission_id, scheme_id, notes, pasted_text, files)
        except BackendError as exc:
            st.error(str(exc))
            return
        set_flash(f"edit_submission_{submission_id}", "Submission updated - it is being re-analyzed.")
        clear_fields(f"edit_pasted_text_{submission_id}", f"edit_toggle_{submission_id}")
        reset_uploader(f"edit_documents_{submission_id}")
        st.rerun()
