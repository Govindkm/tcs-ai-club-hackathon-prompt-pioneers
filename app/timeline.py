"""Color-coded submission timeline widget shared by admin and applicant views.

Color coding (per submission.timeline_stage):
    green (done)        - step already completed
    blinking green      - step currently executing
    orange (not started)- step not started yet
    red (failed)        - step failed/stopped, or was in progress when the
                           submission's analysis_status flipped to 'failed'
"""
from __future__ import annotations

import streamlit as st

_STAGE_ORDER = [
    "ingesting",
    "awaiting_admin_review",
    "extraction_running",
    "validation_running",
    "awaiting_admin_validation",
    "scoring_running",
    "awaiting_score_approval",
    "completed",
]

# Each timeline node maps to one or more timeline_stage values that are "in progress" for it.
_STEPS = [
    ("Submitted & Indexed", {"ingesting"}),
    ("Assigned for AI Analysis", {"awaiting_admin_review"}),
    ("Extraction", {"extraction_running"}),
    ("Validation", {"validation_running", "awaiting_admin_validation"}),
    ("Scoring", {"scoring_running"}),
    ("Approval & Completion", {"awaiting_score_approval"}),
]

_COLORS = {
    "done": "#1e8e3e",  # green
    "current": "#1e8e3e",  # green (blinking)
    "pending": "#e8710a",  # orange
    "failed": "#d93025",  # red
}

_CSS = """
<style>
@keyframes blink-green {
  0% { opacity: 1; }
  50% { opacity: 0.35; }
  100% { opacity: 1; }
}
.timeline-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 6px 0 10px 0; }
.timeline-step {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 14px; font-size: 0.8rem; color: white;
}
.timeline-step.current { animation: blink-green 1.2s ease-in-out infinite; }
.timeline-dot { width: 9px; height: 9px; border-radius: 50%; background: white; }
</style>
"""


def _step_status(step_index: int, current_index: int, failed: bool) -> str:
    if step_index < current_index:
        return "done"
    if step_index == current_index:
        return "failed" if failed else "current"
    return "pending"


def render_timeline(submission: dict) -> None:
    """Render the color-coded submission timeline for one submission."""
    timeline_stage = submission.get("timeline_stage", "ingesting")
    failed = submission.get("analysis_status") == "failed"
    # Unrecognized stage should never paint everything green - default to the start.
    current_index = _STAGE_ORDER.index(timeline_stage) if timeline_stage in _STAGE_ORDER else 0

    st.markdown(_CSS, unsafe_allow_html=True)
    html = ['<div class="timeline-row">']
    for step_name, step_stage_set in _STEPS:
        # A step's stage_index is the position of its first matching timeline_stage.
        step_stage_indices = [i for i, s in enumerate(_STAGE_ORDER) if s in step_stage_set]
        step_index = min(step_stage_indices) if step_stage_indices else 0
        status = _step_status(step_index, current_index, failed)
        css_class = "current" if status == "current" else ""
        color = _COLORS[status]
        icon = {"done": "✓", "current": "●", "pending": "○", "failed": "✕"}[status]
        html.append(
            f'<span class="timeline-step {css_class}" style="background:{color}">'
            f'<span class="timeline-dot"></span>{icon} {step_name}</span>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)
