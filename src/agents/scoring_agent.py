"""Agent that applies configurable rules and explainable scoring to applications."""
from __future__ import annotations

from src.agents.base import build_agent


def create_scoring_agent():
    return build_agent(
        "scoring_agent",
        system_prompt=(
            "You compute explainable scores for applications using the "
            "configured rule weights. Always surface the score breakdown; "
            "the score is advisory input for a human reviewer, not a verdict."
        ),
    )
