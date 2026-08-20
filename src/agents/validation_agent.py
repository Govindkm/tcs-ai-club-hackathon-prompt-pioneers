"""Agent that checks completeness and authenticity indicators on extracted data."""
from __future__ import annotations

from src.agents.base import build_agent


def create_validation_agent():
    return build_agent(
        "validation_agent",
        system_prompt=(
            "You validate extracted application data for completeness and "
            "authenticity risk indicators. Always explain which fields are "
            "missing or which risks were flagged; you do not approve or reject."
        ),
    )
