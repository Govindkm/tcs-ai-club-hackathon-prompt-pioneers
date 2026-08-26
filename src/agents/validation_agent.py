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
            "authenticity risk indicators. If a plagiarism/duplicate-content check "
            "result is provided, factor any flagged matches into your risk assessment. "
            "If an applicant organisation name is provided, use verify_organisation_online "
            "to check it has a genuine, findable public presence, and factor a missing/weak "
            "online presence into your risk flags (e.g. 'no_online_presence_found') - this is "
            "one signal among several, not proof of fraud on its own. "
            "Always explain which fields are missing or which risks were flagged; "
            "you do not approve or reject."
        ),
    )
