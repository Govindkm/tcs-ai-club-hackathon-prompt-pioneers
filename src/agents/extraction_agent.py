"""Agent that extracts structured fields and summaries from submitted documents."""
from __future__ import annotations

from typing import Any, Callable

from src.agents.base import build_agent


def create_extraction_agent(callback_handler: Callable[..., Any] | None = None):
    return build_agent(
        "extraction_agent",
        callback_handler=callback_handler,
        system_prompt=(
            "You extract structured fields and concise summaries from government "
            "scheme/project application documents. Use your tools; never invent "
            "field values that aren't supported by the document text."
        ),
    )
