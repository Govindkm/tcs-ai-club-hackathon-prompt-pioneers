"""Reviewer routing, decision recording, and audit-trail skills.

No tool here can finalize a decision on its own; `record_review_decision`
only persists a human-supplied decision and always keeps an audit entry.
"""
from __future__ import annotations

import datetime

from strands import tool

_AUDIT_LOG: list[dict] = []


@tool
def route_to_reviewer(score: float, reviewer_pool: list[str]) -> dict:
    """Pick a reviewer for a case based on its score band (does not decide the outcome).

    Args:
        score: Explainable score produced by the scoring skill.
        reviewer_pool: Available reviewer identifiers to route to.
    """
    if not reviewer_pool:
        raise ValueError("reviewer_pool must not be empty")
    band = "priority" if score < 0.4 else "standard"
    reviewer = reviewer_pool[hash(band) % len(reviewer_pool)]
    return {"assigned_reviewer": reviewer, "priority_band": band}


@tool
def record_review_decision(case_id: str, reviewer: str, decision: str, rationale: str) -> dict:
    """Persist a human reviewer's final decision and append an audit-trail entry.

    Args:
        case_id: Identifier of the application/case being decided.
        reviewer: Identifier of the human reviewer making the decision.
        decision: The human-made decision (e.g. "approved", "rejected", "needs_more_info").
        rationale: Reviewer's stated reasoning, stored for auditability.
    """
    entry = {
        "case_id": case_id,
        "reviewer": reviewer,
        "decision": decision,
        "rationale": rationale,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    _AUDIT_LOG.append(entry)
    return entry


@tool
def get_audit_trail(case_id: str) -> list[dict]:
    """Retrieve all recorded audit entries for a given case.

    Args:
        case_id: Identifier of the application/case to look up.
    """
    return [e for e in _AUDIT_LOG if e["case_id"] == case_id]


TOOLS = [route_to_reviewer, record_review_decision, get_audit_trail]
