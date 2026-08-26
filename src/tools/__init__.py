"""Strands @tool registry shared by all agents.

Distinct from Agent Skills (SKILL.md packages under ./skills/): these are
plain Strands tools passed directly via Agent(tools=[...]), and are also
what SKILL.md files reference in their `allowed-tools` frontmatter.
"""
from __future__ import annotations

from src.tools import document_tools, embedding_tools, scoring_tools, validation_tools, verification_tools, workflow_tools

TOOL_MODULES = {
    "document_tools": document_tools.TOOLS,
    "embedding_tools": embedding_tools.TOOLS,
    "validation_tools": validation_tools.TOOLS,
    "verification_tools": verification_tools.TOOLS,
    "scoring_tools": scoring_tools.TOOLS,
    "workflow_tools": workflow_tools.TOOLS,
}


def get_tools(*module_names: str) -> list:
    """Resolve one or more tool module names into a flat list of @tool callables."""
    tools: list = []
    for name in module_names:
        if name not in TOOL_MODULES:
            raise KeyError(f"Unknown tool module: {name}")
        tools.extend(TOOL_MODULES[name])
    return tools
