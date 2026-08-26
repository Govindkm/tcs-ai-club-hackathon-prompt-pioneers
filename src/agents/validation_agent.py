"""Agent that checks completeness and authenticity indicators on extracted data."""
from __future__ import annotations

from typing import Any, Callable

from src.agents.base import build_agent


def create_validation_agent(callback_handler: Callable[..., Any] | None = None):
    return build_agent(
        "validation_agent",
        callback_handler=callback_handler,
        system_prompt=(
            "Validate required and usable fields/documents for the scheme, then "
            "check contradictions across document values and scheme limits. If a "
            "plagiarism/duplicate-content result is provided, identify the matched "
            "documents and factor it into risk without calling it proof of fraud. "
            "Flag low-quality, untraceable, unsigned, unsupported, or identity-mismatched "
            "evidence as indicators for human verification. Return missing_documents, "
            "unusable_documents, missing_fields, contradictions, risk_flags, risk_level, "
            "and an analysis_gate. Material contradictions, missing hard-stop evidence, "
            "or high risk block scoring. Keep restricted data local and never send raw "
            "application content to a public service. You do not approve or reject."
        ),
    )
