"""Applicant-facing views: browse schemes, submit applications, track status.

Auto-analysis runs the deterministic extraction/validation/scoring tools
directly (no LLM credentials required) so the demo works fully offline;
final approve/reject/needs-more-info decisions always come from a human
reviewer via src.db.repository.record_review.
"""
from __future__ import annotations

import streamlit as st

from src.db import repository as db
from src.ingestion.document_reader import extract_text
from src.tools.document_tools import extract_fields, summarize_document
from src.tools.scoring_tools import apply_rule_score
from src.tools.validation_tools import check_completeness, flag_authenticity_risks

_STATUS_LABELS = {
    "submitted": "Submitted",
    "under_review": "Under review",
    "needs_more_info": "Needs more information",
    "approved": "Approved",
    "rejected": "Rejected",
}


def schemes_view() -> None:
    st.subheader("Available Schemes")
    schemes = db.list_schemes(active_only=True)
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


def submit_view(user: dict) -> None:
    st.subheader("Submit an Application")
    schemes = db.list_schemes(active_only=True)
    if not schemes:
        st.info("No schemes are currently open for applications.")
        return

    scheme_options = {s["name"]: s["id"] for s in schemes}
    scheme_name = st.selectbox("Scheme", list(scheme_options.keys()))
    uploaded_files = st.file_uploader(
        "Application documents",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="Upload one or more supporting documents (PDF, Word, or plain text).",
    )
    pasted_text = st.text_area(
        "Or paste document content directly (optional)",
        height=150,
        help="Use this if you don't have files to upload, or to add extra context.",
    )
    notes = st.text_area("Additional notes (optional)")

    if st.button("Submit application", type="primary"):
        try:
            document_text = _collect_document_text(uploaded_files, pasted_text)
        except ValueError as exc:
            st.error(str(exc))
            return
        if not document_text.strip():
            st.error("Please upload at least one document or paste some content.")
            return
        submission_id = db.create_submission(
            user_id=user["id"],
            scheme_id=scheme_options[scheme_name],
            applicant_notes=notes,
            document_text=document_text,
        )
        _run_auto_analysis(submission_id, document_text)
        st.success(f"Application submitted (reference #{submission_id}).")


def _collect_document_text(uploaded_files, pasted_text: str) -> str:
    """Extract text from uploaded PDF/DOCX/TXT files and merge it with any pasted text."""
    sections = []
    for uploaded_file in uploaded_files or []:
        text = extract_text(uploaded_file.name, uploaded_file.getvalue())
        sections.append(f"--- {uploaded_file.name} ---\n{text}")
    if pasted_text.strip():
        sections.append(pasted_text.strip())
    return "\n\n".join(sections)


def _run_auto_analysis(submission_id: int, document_text: str) -> None:
    extracted = extract_fields(document_text)
    summary = summarize_document(document_text)
    validation = check_completeness(extracted, ["amounts_found", "dates_found"])
    risks = flag_authenticity_risks(extracted)
    validation["risk_flags"] = risks["risk_flags"]
    validation["requires_human_review"] = risks["requires_human_review"]
    scoring = apply_rule_score(validation)
    db.save_auto_analysis(
        submission_id,
        extracted_fields=extracted,
        summary=summary,
        validation_result=validation,
        score=scoring["score"],
        score_explanation=scoring["explanation"],
    )


def my_submissions_view(user: dict) -> None:
    st.subheader("My Submissions")
    submissions = db.list_submissions_for_user(user["id"])
    if not submissions:
        st.info("You haven't submitted any applications yet.")
        return

    for sub in submissions:
        label = f"#{sub['id']} · {sub['scheme_name']} · {_STATUS_LABELS.get(sub['status'], sub['status'])}"
        with st.expander(label):
            st.write(f"Submitted: {sub['created_at']}")
            if sub["summary"]:
                st.markdown(f"**Summary:** {sub['summary']}")
            if sub["score"] is not None:
                st.markdown(f"**Advisory score:** {sub['score']}")

            reviews = db.list_reviews_for_submission(sub["id"])
            if sub["status"] in ("approved", "rejected"):
                st.markdown(f"### Final decision: {_STATUS_LABELS[sub['status']]}")
                if reviews:
                    st.write(f"Reviewer note: {reviews[-1]['rationale']}")
            elif sub["status"] == "needs_more_info" and reviews:
                st.warning(f"Reviewer requested more information: {reviews[-1]['rationale']}")
            else:
                st.info("Your application is being processed.")
