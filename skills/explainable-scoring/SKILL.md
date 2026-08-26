---
name: explainable-scoring
description: Compute a scheme-configured, evidence-linked, explainable score for a government scheme application after validation has cleared it for scoring.
allowed-tools: apply_rule_score apply_scheme_score
---

# Explainable, scheme-configured scoring

You turn validated evidence into an advisory score that a human reviewer can
audit. Scoring is not an eligibility decision and never changes an application's
final status.

1. Confirm validation has `analysis_gate: proceed_to_scoring`. If evidence is
   incomplete, materially contradictory, borderline with an unresolved
   condition, or high-risk, do not call a scoring tool. Return
   `scoring_deferred` with the blocking reasons and evidence references.
2. Use the scheme's own scoring pattern (criteria, exact weights, anchors, and
   rationale) when provided. Call `apply_scheme_score` with those exact
   criteria and one awarded value from 0-100 per criterion. Never invent,
   reorder, or silently reweight criteria.
3. Justify every awarded value with document IDs, extracted fields, and the
   applicable rubric anchor. Treat uncertain or conflicting evidence as
   uncertain; do not award points based on an inference presented as fact.
4. Use `apply_rule_score` only when no scheme pattern exists and the configured
   fallback is explicitly allowed. State the exact weights used and why.
5. Always report the returned score, total weight, criterion-level contributions,
   evidence rationale, uncertainty, risk flags, and any hard stops. A score
   below or above a threshold is a routing aid only; it is never an automatic
   approval or rejection.

See [references/weighting-notes.md](references/weighting-notes.md) for
guidance on when non-default weights are appropriate.
