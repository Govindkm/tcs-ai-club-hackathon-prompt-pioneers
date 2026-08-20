# TCS AI Club Hackathon – Team Prompt Pioneers

## Enterprise AI Application Processing and Evaluation Platform
### Directorate of Environment and Climate Change

An end-to-end application intelligence platform for scheme and project evaluation.

---

## Problem Statement

**Government Department Context:** Directorate of Environment and Climate Change.

The department receives scheme and project applications containing forms, proposals, certificates, budgets, reports, images, and supporting records. Review quality depends on consistent eligibility checks, reliable extraction, transparent scoring, document verification, workflow traceability, fair review practices, and integration with an existing schemes portal.

### The Core Challenge

Create an end-to-end application intelligence platform that:
- Ingests heterogeneous submissions
- Extracts and summarizes content
- Validates completeness and authenticity indicators
- Applies configurable rules and explainable ML scoring
- Routes cases to reviewers
- Records human decisions
- Produces operational analytics

**Note:** The platform must **not** allow AI to make an irreversible final determination — humans remain in the loop for final decisions.

---

## Expected Outcome

The POC must demonstrate every normalized capability from the eight relevant proposals. Core application-processing features and advanced workflow, transparency, fraud, multilingual, reporting, feedback, and conversational features are all in scope. Live scheme portals, messaging platforms, and identity services may be represented by mock adapters.

---

## Solution Guidelines

### Data Sovereignty & Infrastructure Constraints
- Teams may choose their own tools and development environments, including personal machines.
- Cloud AI/API services may be used only for approved **non-sensitive synthetic data**.
- Any mock data representing government or citizen information must be classified as **restricted**, processed **locally**, and must **never** be transmitted to public cloud infrastructure.
- Target architecture must remain **isolated and on-premise-ready**.
- External data may be ingested; unavailable integrations may be represented via secure mock adapters.

### Architecture & Engineering Standards
- Scalable, modular architecture with explicit trust boundaries
- API-first contracts
- Model/provider abstraction
- Configuration separation
- Structured logging, observability, and audit trails
- Robust error handling and testable components
- Standard POC repository practices: meaningful branching/commits, code review where practical, README + Architecture Decision Records (ADRs), dependency management, automated testing for critical paths, static analysis/linting, secrets exclusion, and reproducible setup
- Avoid both throwaway code and unnecessary platform engineering

---

## Mandatory Deliverables

1. **Functional application-processing POC** covering submission, extraction, summarization, validation, scoring, review, override, audit, workflow, and all labeled advanced capabilities.
2. **Synthetic dataset** with complete, incomplete, contradictory, low-quality, duplicate, suspicious, and borderline applications, plus a transparent evaluation rubric.
3. **Modular repository** with documented API contracts, configurable rules, automated tests, model/evaluation notebooks or scripts, and reproducible local deployment.
4. **Architecture, data-flow, and threat-boundary diagrams** addressing document storage, local processing, cloud-safe data, model adapters, auditability, fairness, and portal integration.
5. **Evidence of extraction and scoring evaluation**, negative tests, bias/uncertainty handling, deployment scripts, operational logs, and an end-to-end reviewer demo.

---

## Team

**Team Name:** Prompt Pioneers

---

## Repository Structure (planned)

```
.
├── docs/                  # Architecture, ADRs, data-flow & threat-boundary diagrams
├── data/                  # Synthetic dataset generation & samples (non-sensitive only)
├── src/
│   ├── ingestion/         # Submission intake & heterogeneous document handling
│   ├── extraction/        # Content extraction & summarization
│   ├── validation/        # Completeness & authenticity checks
│   ├── scoring/           # Configurable rules + explainable ML scoring
│   ├── workflow/          # Reviewer routing, decisions, overrides, audit trail
│   ├── analytics/         # Operational analytics & reporting
│   └── adapters/          # Mock adapters (schemes portal, messaging, identity)
├── notebooks/             # Model/evaluation notebooks
├── tests/                 # Automated tests for critical paths
└── README.md
```

## Getting Started

_Setup instructions will be added as the project is scaffolded._

## Status

🚧 Work in progress — POC under active development for the TCS AI Club Hackathon.
