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


@tool
def apply_scheme_score(criteria: list[dict], awarded: dict) -> dict:
    """Compute an explainable weighted score from a scheme's own scoring pattern.

    Args:
        criteria: The scheme's scoring pattern criteria, each a dict with
            "name", "weight" (0-100), and "rationale". All weights sum to ~100.
        awarded: Map of criterion name -> awarded value (0-100), the percentage
            of that criterion's weight the submission earned based on your review.
    """
    breakdown = []
    total_score = 0.0
    for criterion in criteria:
        name = criterion.get("name", "")
        weight = float(criterion.get("weight", 0))
        awarded_value = max(0.0, min(100.0, float(awarded.get(name, 0.0))))
        contribution = round(weight * awarded_value / 100.0, 3)
        total_score += contribution
        breakdown.append(
            {
                "criterion": name,
                "weight": weight,
                "awarded": awarded_value,
                "weighted_contribution": contribution,
                "rationale": criterion.get("rationale", ""),
            }
        )
    return {
        "score": round(total_score, 3),
        "explanation": {
            "criteria": breakdown,
            "total_weight": round(sum(float(c.get("weight", 0)) for c in criteria), 3),
        },
    }


TOOLS = [apply_rule_score, apply_scheme_score]
