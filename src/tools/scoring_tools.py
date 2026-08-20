"""Configurable rules + explainable scoring skills.

Scoring is transparent: every score returns the contributing factors so a
reviewer can see why a number was produced (no black-box final decisions).
"""
from __future__ import annotations

from strands import tool


@tool
def apply_rule_score(validation_result: dict, weights: dict | None = None) -> dict:
    """Compute an explainable rule-based score from validation results.

    Args:
        validation_result: Output of check_completeness/flag_authenticity_risks.
        weights: Optional override of scoring weights, e.g. {"completeness": 0.6, "risk": 0.4}.
    """
    weights = weights or {"completeness": 0.6, "risk": 0.4}
    completeness_score = 1.0 if validation_result.get("is_complete") else 0.0
    risk_penalty = 1.0 if validation_result.get("requires_human_review") else 0.0

    score = (
        weights["completeness"] * completeness_score
        - weights["risk"] * risk_penalty
    )
    return {
        "score": round(max(score, 0.0), 3),
        "explanation": {
            "completeness_score": completeness_score,
            "risk_penalty": risk_penalty,
            "weights": weights,
        },
    }


TOOLS = [apply_rule_score]
