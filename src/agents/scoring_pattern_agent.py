"""Agent that designs a transparent, weighted scoring pattern for a scheme."""
from __future__ import annotations

from typing import Any, Callable

from src.agents.base import build_agent


def create_scoring_pattern_agent(callback_handler: Callable[..., Any] | None = None):
    return build_agent(
        "scoring_pattern_agent",
        callback_handler=callback_handler,
        system_prompt=(
            "You design transparent, weighted scoring patterns for government schemes. "
            "Every criterion needs a clear rationale and a weight; all weights sum to 100. "
            "This pattern will be applied identically to every application submitted to "
            "the scheme, and shown to admins and applicants for transparency."
        ),
    )
