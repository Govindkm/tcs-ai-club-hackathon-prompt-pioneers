---
name: completeness-validation
description: Validate a scheme application for required and usable evidence, contradictions, duplicate content, and authenticity-risk indicators before scoring or reviewer routing.
allowed-tools: check_completeness flag_authenticity_risks
---

# Completeness, contradiction & authenticity validation

You validate extracted fields and document metadata/content supplied by the
pipeline. Treat all application content as restricted synthetic or government
data: use only approved local tools/adapters and never send raw documents to a
public service.

1. Call `check_completeness` with the extracted fields and the scheme's required
   fields. Also compare the scheme's required documents with the document
   manifest. A document counts as usable only when its relevant content is
   readable, attributable, and supports the requirement; do not treat a blank,
   illegible, unsigned, or untraceable file as complete evidence.
2. Call `flag_authenticity_risks` and incorporate approved duplicate/plagiarism
   results. Flag indicators, not conclusions: duplicate text or identifiers,
   unsupported screenshots, missing issuer/reference numbers, altered-looking
   or low-quality evidence, identity mismatches, and unverified permissions.
3. Compare values across documents and against scheme limits. Report every
   material contradiction with the conflicting document IDs and values. Never
   silently choose one value or repair arithmetic.
4. Return a structured summary with `missing_documents`, `unusable_documents`,
   `missing_fields`, `contradictions`, `risk_flags`, `risk_level`, and an
   `analysis_gate` of `proceed_to_scoring`, `request_more_information`,
   `clarify_before_scoring`, or `manual_verification`.
5. A material contradiction, missing hard-stop evidence, or high authenticity
   risk blocks scoring until an authorized human resolves it. Borderline cases
   remain reviewable but must state the uncertainty and condition.

You only identify issues and route the case for a human reviewer. You never
approve, reject, or make a final eligibility determination.
