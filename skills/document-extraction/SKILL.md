---
name: document-extraction
description: Extract structured fields and produce summaries from government scheme/project application documents (forms, proposals, budgets, reports). Use when a submission needs fields pulled out or condensed before validation or scoring.
allowed-tools: extract_fields summarize_document
---

# Document extraction

You are extracting structured data from a citizen/organization application document.

1. Call `extract_fields` on the raw document text to pull out amounts, dates, and basic stats.
2. Call `summarize_document` to produce a short (2-3 sentence) summary of the submission.
3. Report the extracted fields and summary together. Do not invent values that
   aren't supported by the document text — if a field can't be found, say so
   explicitly instead of guessing.
