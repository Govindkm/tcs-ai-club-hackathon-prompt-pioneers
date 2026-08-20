---
name: completeness-validation
description: Check completeness of extracted application fields and flag authenticity-risk indicators (duplicates, missing financial data). Use when deciding whether a submission has enough information and whether it looks suspicious before scoring or routing.
allowed-tools: check_completeness flag_authenticity_risks
---

# Completeness & authenticity validation

You are validating already-extracted application fields, not raw documents.

1. Call `check_completeness` with the extracted fields and the list of fields
   required for this scheme to see what is missing.
2. Call `flag_authenticity_risks` on the same extracted fields to surface
   simple risk indicators (e.g. duplicate amounts, no financial data).
3. Summarize both results clearly, including which fields are missing and
   which risk flags were raised. You only flag issues for a human reviewer —
   you never approve or reject an application yourself.
