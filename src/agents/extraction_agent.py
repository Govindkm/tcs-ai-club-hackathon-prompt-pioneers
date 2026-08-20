"""Agent that extracts structured fields and summaries from submitted documents."""
from __future__ import annotations

from src.agents.base import build_agent


def create_extraction_agent():
    return build_agent(
        "extraction_agent",
        system_prompt=(
            "You extract structured fields and concise summaries from government "
            "scheme/project application documents. Use your tools; never invent "
            "field values that aren't supported by the document text."
        ),
    )
