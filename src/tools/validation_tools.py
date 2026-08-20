"""Completeness & authenticity-indicator skills.

Checks are rule-based and explainable by design; they flag issues for a
human reviewer rather than making a final accept/reject determination.
"""
from __future__ import annotations

from strands import tool


@tool
def check_completeness(extracted_fields: dict, required_fields: list[str]) -> dict:
    """Check which required fields are missing from an extracted-fields dict.

    Args:
        extracted_fields: Fields extracted from the submission.
        required_fields: List of field names that must be present.
    """
    missing = [f for f in required_fields if not extracted_fields.get(f)]
    return {
        "is_complete": len(missing) == 0,
        "missing_fields": missing,
    }


@tool
def flag_authenticity_risks(extracted_fields: dict) -> dict:
    """Flag simple authenticity risk indicators (e.g. inconsistent/duplicate amounts).

    Args:
        extracted_fields: Fields extracted from the submission, e.g. amounts/dates lists.
    """
    amounts = extracted_fields.get("amounts_found", [])
    risks = []
    if len(amounts) != len(set(amounts)) and amounts:
        risks.append("duplicate_amount_values")
    if not amounts:
        risks.append("no_financial_data_detected")
    return {"risk_flags": risks, "requires_human_review": bool(risks)}


TOOLS = [check_completeness, flag_authenticity_risks]
