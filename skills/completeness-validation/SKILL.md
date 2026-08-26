---
name: completeness-validation
description: Validate a scheme application against that scheme's own required documents and eligibility criteria, verify the applicant organisation, and surface contradictions, duplicate content, and authenticity-risk indicators before scoring or reviewer routing.
allowed-tools: check_scheme_requirements check_completeness flag_authenticity_risks verify_organisation_online
---

# Scheme-requirement, applicant & authenticity validation

You validate a submission against the requirements of the scheme it was
submitted to. Treat all application content as restricted synthetic or
government data: use only approved local tools/adapters and never send raw
documents to a public service.

1. Call `check_scheme_requirements` with the scheme's `required_documents` and
   the submitted document records. Never substitute a generic or assumed field
   list for the scheme's own requirements. A document counts as usable only
   when its relevant content is readable, attributable, and actually supports
   the requirement; do not treat a blank, illegible, unsigned, or untraceable
   file as complete evidence.
2. Judge each of the scheme's eligibility criteria against the submitted
   evidence and report the ones the evidence does not establish in
   `unmet_eligibility`. Use `check_completeness` for data points the scheme
   needs that no document states.
3. Verify the applicant with `verify_organisation_online`, passing the
   organisation name exactly as submitted, and return its raw result in
   `organisation_check`. Only the organisation name may leave the local
   environment. No findable presence, or a presence that contradicts the
   claimed identity, is a risk indicator for human verification - never proof
   of fraud on its own.
4. Call `flag_authenticity_risks` and incorporate approved duplicate/plagiarism
   results. Flag indicators, not conclusions: duplicate text or identifiers,
   unsupported screenshots, missing issuer/reference numbers, altered-looking
   or low-quality evidence, identity mismatches, and unverified permissions.
5. Compare values across documents and against the scheme's stated limits
   (funding minimum/maximum, match funding, dates, capacity, beneficiaries).
   Report every material contradiction with the conflicting document IDs and
   values. Never silently choose one value or repair arithmetic.
6. Return a structured summary with `missing_documents`, `unusable_documents`,
   `unmet_eligibility`, `missing_fields`, `contradictions`,
   `organisation_check`, `risk_flags`, and `risk_level`.
7. A material contradiction, missing hard-stop evidence, or high authenticity
   risk blocks scoring until an authorized human resolves it. Borderline cases
   remain reviewable but must state the uncertainty and condition.

You only identify issues and route the case for a human reviewer. You never
approve, reject, or make a final eligibility determination.
