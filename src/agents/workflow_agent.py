"""Agent that routes cases to reviewers and records human decisions/audit trail."""
from __future__ import annotations

from src.agents.base import build_agent


def create_workflow_agent():
    return build_agent(
        "workflow_agent",
        system_prompt=(
            "You route cases to reviewers and record the audit trail. You "
            "must never finalize an approval/rejection yourself - only a "
            "human reviewer's decision is recorded as final via your tools."
        ),
    )
