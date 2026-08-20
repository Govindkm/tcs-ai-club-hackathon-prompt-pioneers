# Weighting notes

Default weights are `completeness: 0.6, risk: 0.4`. Consider non-default
weights only when explicitly configured for a scheme, for example:

- High-value grants: increase `risk` weight to prioritize authenticity checks.
- Fast-track / low-value schemes: increase `completeness` weight since risk
  exposure per case is lower.

Never silently change weights without stating the values used in your
explanation output — reviewers must be able to audit why a score changed.
