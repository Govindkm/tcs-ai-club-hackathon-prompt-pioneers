"""Agent that applies configurable rules and explainable scoring to applications."""
from __future__ import annotations

from typing import Any, Callable

from src.agents.base import build_agent


def create_scoring_agent(callback_handler: Callable[..., Any] | None = None):
    return build_agent(
        "scoring_agent",
        callback_handler=callback_handler,
        system_prompt=(
            "Compute a scheme-configured advisory score only when validation has "
            "analysis_gate proceed_to_scoring. If required evidence is missing or unusable, "
            "a material contradiction is unresolved, or authenticity risk is high, defer "
            "scoring and return the blocking reasons. When a scheme scoring pattern is "
            "provided, call apply_scheme_score with its exact criteria and weights; do not "
            "invent or reweight criteria. Justify every awarded value from document IDs, "
            "extracted fields, and rubric anchors, and surface uncertainty, flags, hard stops, "
            "and the complete breakdown. Use apply_rule_score only for an explicitly allowed "
            "fallback. The score is never an approval or rejection and cannot finalize status."
        ),
    )
