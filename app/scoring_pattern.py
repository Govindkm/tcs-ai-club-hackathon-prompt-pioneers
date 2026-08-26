"""Shared "scoring pattern" transparency widget for admin and applicant views.

Renders the weighted, rationale-backed criteria an AI agent designed for a
scheme (src/agents/orchestrator.py: generate_scheme_scoring_pattern) - the same
pattern validation/scoring agents apply to every submission against it.
"""
from __future__ import annotations

import streamlit as st


def render_scoring_pattern(pattern: dict | None, heading: str = "📊 Scoring pattern") -> None:
    if not pattern or not pattern.get("criteria"):
        return
    st.markdown(f"**{heading}**")
    if pattern.get("summary"):
        st.caption(pattern["summary"])
    for criterion in pattern["criteria"]:
        st.markdown(
            f"- **{criterion.get('name', '')}** — {criterion.get('weight', 0)}% : "
            f"{criterion.get('rationale', '')}"
        )
