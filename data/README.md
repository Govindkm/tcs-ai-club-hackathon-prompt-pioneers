# Synthetic Evaluation Dataset

`synthetic_dataset.json` is a restricted, local-only benchmark for the Directorate of Environment and Climate Change POC. It contains three scheme definitions and twelve synthetic applications. No record represents a real person, organisation, government department, address, account, certificate, or project.

## Important Runtime Boundary

This file is a benchmark fixture, not a database seed. Do not load its `schemes` or `benchmark_labels` into the application database automatically. In a demo, an administrator creates a scheme through the system, an applicant submits an application, and the normal pipeline performs extraction, validation, duplicate/authenticity checks, and scoring. The final decision remains human-owned.

The `benchmark_labels` object is expected ground truth for evaluation only. It is not an AI analysis result, recommendation, score, approval, or rejection. The runtime should produce its own analysis from the submitted documents.

## Materialized Documents

The per-application submission files under `data/applications/` are generated
from the JSON source. Regenerate them after changing the source with:

```powershell
python scripts/generate_application_files.py
```

Each application directory contains one file per source document, a generated
schematic diagram (`D0_site_diagram.*`), and `BENCHMARK_LABELS.txt`. The label
file is evaluation metadata and must not be uploaded as an application document
or used as runtime analysis input.

Carrier formats vary per document type so a submission bundle exercises the
whole ingestion path:

| Evidence | Typical carrier |
|---|---|
| Application forms, budgets, audited financials, permissions | PDF |
| Proposals, restoration plans, baselines | DOCX (text, tables) |
| Concept notes, monitoring and safeguard plans | PPTX |
| Registration certificates, consent letters | Scanned images (PNG, JPG, WEBP, TIFF, BMP) |
| Match funding proof | Portal screenshot image |
| Site/system schematic | Diagram image (PNG, JPG, WEBP) |

Document `quality` in the JSON drives rendering. `good` and `fair` documents
keep a machine-readable text layer; `poor` and `low` documents are rendered as
degraded scans (downsampled, blurred, noisy, skewed) and are embedded as
image-only PDFs or pictures inside DOCX/PPTX, so OCR and authenticity-risk
handling are exercised rather than assumed.

## Coverage Matrix

| Application | Scheme | Benchmark cases | Expected first human action |
|---|---|---|---|
| APP-SOLAR-001 | Rural Solar Microgrid Grant | complete | Proceed to scoring |
| APP-SOLAR-002 | Rural Solar Microgrid Grant | incomplete | Request more information |
| APP-SOLAR-003 | Rural Solar Microgrid Grant | contradictory, borderline | Clarify before scoring |
| APP-SOLAR-004 | Rural Solar Microgrid Grant | low-quality, suspicious | Manual verification |
| APP-FOREST-001 | Community Forest Restoration Fund | complete | Proceed to scoring |
| APP-FOREST-002 | Community Forest Restoration Fund | incomplete, borderline | Request more information |
| APP-FOREST-003 | Community Forest Restoration Fund | duplicate, suspicious | Duplicate review |
| APP-FOREST-004 | Community Forest Restoration Fund | borderline | Conditional human review |
| APP-WATER-001 | Climate Resilient Watershed Innovation Scheme | complete | Proceed to scoring |
| APP-WATER-002 | Climate Resilient Watershed Innovation Scheme | incomplete, low-quality | Request more information |
| APP-WATER-003 | Climate Resilient Watershed Innovation Scheme | contradictory, borderline | Clarify before scoring |
| APP-WATER-004 | Climate Resilient Watershed Innovation Scheme | suspicious, borderline | Manual verification |

## Evaluation Rubric

### 1. Document and field extraction

Compare system-extracted fields with the evidence text. Use exact or normalized matching for IDs, amounts, dates, areas, capacities, and counts. A field is correct only when its value and unit are correct. Mark a field as uncertain rather than guessing when the source is illegible or conflicting.

- **Pass:** at least 95% of required fields correct, with no material value error.
- **Partial:** 80-94% correct, or a material conflict is surfaced as uncertain.
- **Fail:** below 80%, or a material conflict is silently resolved as fact.

### 2. Completeness

For each scheme, check every item in `required_documents` and whether the document is usable, not merely present.

- **Complete:** all required documents are present and usable.
- **Incomplete:** one or more required documents are absent.
- **Present but unusable:** a required document exists but is illegible, untraceable, unsigned where signature matters, or lacks the evidence needed for the requirement.
- **Complete with condition:** the evidence is sufficient only if a clearly stated condition is confirmed by a human.

### 3. Contradiction handling

Compare claims across documents and against scheme limits. Material conflicts include amount totals, dates, site area, capacity, beneficiary count, permissions, and match funding.

- **Pass:** every material contradiction is listed with source document IDs and no score is finalized until clarified.
- **Partial:** contradiction is detected but source or impact is incomplete.
- **Fail:** contradictory values are merged, silently selected, or passed into scoring as settled facts.

### 4. Quality and authenticity risk

Flag low resolution, missing pages, unreadable text, altered-looking layouts, untraceable issuers, unsigned consents, unsupported screenshots, and documents whose identifiers do not reconcile. These are indicators for human verification, not proof of fraud.

- **Low risk:** evidence is traceable, coherent, and readable.
- **Medium risk:** fixable gaps or unresolved inconsistencies exist.
- **High risk:** material authenticity, identity, land-rights, permission, or duplicate-content concern exists.

### 5. Duplicate detection

Compare normalized text, document hashes where available, identifiers, names, staff names, coordinates, and repeated measurements across applications.

- **Pass:** APP-FOREST-003 is linked to APP-FOREST-001 and the copied sections are identified.
- **Partial:** similarity is flagged without useful evidence.
- **Fail:** duplicate evidence is missed or treated as independent corroboration.

### 6. Scheme scoring

Only score an application after completeness and material contradiction checks. For each scheme, award each rubric criterion from 0 to 100 using the anchors in the JSON. Calculate:

`weighted score = sum(criterion weight * awarded value / 100)`

The result is a transparent analytical aid, not an approval decision. Apply scheme hard stops and uncertainty flags separately; never hide them inside an unexplained score.

- **Pass:** correct criterion, weight, awarded value, contribution, total, and explanation are shown.
- **Partial:** arithmetic is correct but evidence links or uncertainty are missing.
- **Fail:** weights are changed, unsupported criteria are invented, or a score becomes an automatic final decision.

### 7. Human-in-the-loop controls

Every application must retain the analysis events, evidence references, flags, reviewer rationale, and final human decision. AI may recommend a route such as `request_more_information`, `manual_verification`, or `proceed_to_scoring`, but only an authorized human can approve or reject.

## Suggested Acceptance Targets

- Required-document classification: 100% on the twelve labelled cases.
- Material contradiction recall: 100% on APP-SOLAR-003 and APP-WATER-003.
- Duplicate recall: 100% on APP-FOREST-003.
- High-risk flag recall: 100% on APP-SOLAR-004, APP-FOREST-003, and APP-WATER-004.
- Score arithmetic: 100% against the weighted formula for any runtime-generated criterion awards.
- Final-decision control: 0 cases where AI analysis changes `approved` or `rejected` without a human review record.
