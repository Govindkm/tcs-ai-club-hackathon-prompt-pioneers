---
name: explainable-scoring
description: Compute an explainable, weight-configurable rule score from validation results for a government scheme application. Use when a validated application needs a transparent score before reviewer routing.
allowed-tools: apply_rule_score
---

# Explainable rule-based scoring

You turn validation results into a transparent score a human reviewer can audit.

1. Call `apply_rule_score` with the validation result (and custom weights only
   if the reviewer/config explicitly asked for different weighting).
2. Always report the returned score **and** its `explanation` breakdown
   (completeness score, risk penalty, weights used) — never report a bare
   number. The score is advisory input for a human reviewer, not a verdict.

See [references/weighting-notes.md](references/weighting-notes.md) for
guidance on when non-default weights are appropriate.
