"""Agent that checks completeness and authenticity indicators on extracted data."""
from __future__ import annotations

from typing import Any, Callable

from src.agents.base import build_agent


def create_validation_agent(callback_handler: Callable[..., Any] | None = None):
    return build_agent(
        "validation_agent",
        callback_handler=callback_handler,
        system_prompt=(
            "You validate extracted application data for completeness and "
            "authenticity risk indicators. Always explain which fields are "
            "missing or which risks were flagged; you do not approve or reject."
        ),
    )
