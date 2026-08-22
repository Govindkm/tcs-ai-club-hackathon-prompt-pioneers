"""Strands agent that delegates document indexing to deterministic tools."""
from __future__ import annotations

from typing import Any, Callable

from src.agents.base import build_agent


def create_embedding_agent(callback_handler: Callable[..., Any] | None = None):
    return build_agent(
        "embedding_agent",
        callback_handler=callback_handler,
        system_prompt=(
            "Index the complete structured document bundle in the local vector database. "
            "The orchestrator invokes the indexing tool exactly once. Pass every document "
            "unchanged; never summarize, rewrite, filter, or omit content."
        ),
    )