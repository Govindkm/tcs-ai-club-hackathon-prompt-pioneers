---
name: scheme-scoring-design
description: Design a transparent, weighted scoring pattern (criteria + weights + rationale) for a government scheme, to be applied identically to every application submitted to it. Use when a scheme is created or edited.
---

# Scheme scoring pattern design

You turn a scheme's description, eligibility criteria, and required documents
into a transparent scoring pattern that validation/scoring agents will apply
identically to every submission against this scheme, and that admins and
applicants will see.

1. Read the scheme's name, description, eligibility criteria, and required
   documents carefully.
2. Produce 4-8 scoring criteria that cover:
   - Eligibility fit (does the applicant/project match what the scheme asks for)
   - Completeness (are the required documents/fields present)
   - Scheme-specific priorities implied by the description (e.g. environmental
     impact, financial viability, risk controls, authenticity indicators)
3. Every criterion needs:
   - A short, specific `name` (not generic labels like "Criterion 1")
   - A `weight` out of 100 - all criteria weights must sum to exactly 100
   - A `rationale`: 1-2 sentences explaining why it matters for THIS scheme and
     how an applicant earns points on it (what "full marks" vs "zero" looks like)
   - Evidence anchors: the document or extracted-field evidence that supports
     low, partial, and full credit, including how uncertainty is handled
4. Write a short `summary` of the overall scoring approach in plain language,
   suitable for showing to an applicant.

5. Define `decision_guidance` separately from the score: shortlist and review
   thresholds, required human checks, and hard-stop conditions. Thresholds may
   route work but must never produce an automatic approval or rejection.

6. Keep completeness, contradiction, authenticity, and eligibility safeguards
   visible as validation gates or review flags. Do not hide a hard stop inside
   a numeric criterion or use a risk flag as proof of fraud.

Never produce vague or interchangeable criteria - each one must be
justifiable by something specific in the scheme's own description/eligibility/
required documents text.
