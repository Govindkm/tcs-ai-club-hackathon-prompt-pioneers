"""Structured presentation of the AI analysis attached to a submission."""
from __future__ import annotations

import streamlit as st


def _format_value(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "None"
    if isinstance(value, dict):
        return "; ".join(f"{key}: {item}" for key, item in value.items())
    return str(value) if value not in (None, "") else "Not provided"


def _render_validation(validation: dict) -> None:
    st.markdown("#### Validation findings")
    complete = validation.get("is_complete")
    review_required = validation.get("requires_human_review")
    status_col, review_col = st.columns(2)
    with status_col:
        if complete is True:
            st.success("Complete", icon=":material/check_circle:")
        elif complete is False:
            st.warning("Incomplete", icon=":material/warning:")
        else:
            st.info("Not reported", icon=":material/help:")
    with review_col:
        if review_required:
            st.warning("Human review required", icon=":material/visibility:")
        else:
            st.success("No review flag", icon=":material/check:")

    missing_fields = validation.get("missing_fields") or []
    risk_flags = validation.get("risk_flags") or []
    if missing_fields:
        st.markdown("**Missing fields**")
        st.write(", ".join(str(field) for field in missing_fields))
    if risk_flags:
        st.markdown("**Risk flags**")
        for flag in risk_flags:
            st.warning(str(flag), icon=":material/flag:")


def _render_score(score: float, explanation: dict | None) -> None:
    st.markdown("#### Advisory score")
    score_col, note_col = st.columns([1, 3])
    with score_col:
        st.metric("Score", f"{score:g}")
    with note_col:
        st.caption("AI-generated guidance for human review, not a final decision.")

    explanation = explanation or {}
    criteria = explanation.get("criteria") or []
    if criteria:
        rows = [
            {
                "Criterion": item.get("criterion", "Unnamed criterion"),
                "Weight": f"{item.get('weight', 0):g}%",
                "Awarded": f"{item.get('awarded', 0):g}%",
                "Contribution": f"{item.get('weighted_contribution', 0):g}",
            }
            for item in criteria
        ]
        st.dataframe(rows, hide_index=True, width="stretch")
        for item in criteria:
            rationale = item.get("rationale")
            if rationale:
                with st.expander(f"Why {item.get('criterion', 'this criterion')} scored {item.get('awarded', 0):g}%"):
                    st.write(rationale)
    elif {"completeness_score", "risk_penalty"}.intersection(explanation):
        rule_cols = st.columns(3)
        rule_cols[0].metric("Completeness", f"{explanation.get('completeness_score', 0):g}")
        rule_cols[1].metric("Risk penalty", f"{explanation.get('risk_penalty', 0):g}")
        rule_cols[2].metric("Weights", _format_value(explanation.get("weights")))
    elif explanation:
        with st.expander("View score details"):
            st.json(explanation)


def render_ai_analysis(submission: dict, *, show_raw_details: bool = False) -> None:
    """Render the model output as a reviewer-friendly analysis summary."""
    extracted_fields = submission.get("extracted_fields") or {}
    validation = submission.get("validation_result") or {}
    score = submission.get("score")

    st.markdown("### AI analysis")
    if submission.get("summary"):
        st.info(submission["summary"], icon=":material/summarize:")

    if extracted_fields:
        st.markdown("#### Extracted evidence")
        rows = [{"Field": key, "Value": _format_value(value)} for key, value in extracted_fields.items()]
        st.dataframe(rows, hide_index=True, width="stretch")
    if validation:
        _render_validation(validation)
    if score is not None:
        _render_score(score, submission.get("score_explanation"))

    if show_raw_details:
        with st.expander("View raw analysis payload"):
            st.json(
                {
                    "extracted_fields": extracted_fields,
                    "validation_result": validation,
                    "score_explanation": submission.get("score_explanation"),
                }
            )