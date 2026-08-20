"""Agent that applies configurable rules and explainable scoring to applications."""
from __future__ import annotations

from typing import Any, Callable

from src.agents.base import build_agent


def create_scoring_agent(callback_handler: Callable[..., Any] | None = None):
    return build_agent(
        "scoring_agent",
        callback_handler=callback_handler,
        system_prompt=(
            "You compute explainable scores for applications using the "
            "configured rule weights. Always surface the score breakdown; "
            "the score is advisory input for a human reviewer, not a verdict."
        ),
    )
