---
description: "Use when creating, updating, or reviewing flowcharts, architecture diagrams, data-flow diagrams, sequence diagrams, state diagrams, ER diagrams, or threat-boundary diagrams for the Application Intelligence Platform. Covers Mermaid conventions, the authoritative source files for each diagram, the required diagram catalog, and the accuracy checklist."
applyTo: "docs/**/*.md,README.md"
---

# Diagram Design Instructions

Rules for designing flowcharts and architectural diagrams for this platform. A diagram here is a technical claim about the system, so it must be derived from code, not from assumption.

## Non-Negotiable Rules

1. **Ground every element in code.** Before drawing, read the source files listed in the "Source of Truth" map below. Never draw a component, stage, table, or route that does not exist in the repository.
2. **Use Mermaid in fenced ```mermaid blocks.** Diagrams must live in version control as text so they diff in review. Do not commit binary images or link to external diagram services.
3. **Never imply AI autonomy over final decisions.** Every diagram that reaches an outcome must show the human review gate. AI output is advisory.
4. **Label the async boundary.** Ingestion and analysis run on background threads. A diagram that shows analysis completing inside the HTTP request is wrong.
5. **Do not invent aspirational architecture.** If you show a planned component (job queue, IdP, portal integration), place it in a clearly marked "planned" subgraph and state that it is not implemented.
6. **Keep one diagram to one question.** If a diagram needs more than roughly 20 nodes, split it by concern instead of adding detail.
7. **Update diagrams with the code.** When a workflow stage, trust boundary, storage location, route, or provider contract changes, update the affected diagram in the same change.

## Source of Truth

Read the owning file before drawing the corresponding concept.

| Concept | Authoritative source |
| --- | --- |
| UI entry, navigation, role routing | `streamlit_app.py` |
| The only UI-to-backend boundary | `app/api_client.py` |
| Session and token handling | `app/state.py` |
| Timeline stage order and colors | `app/timeline.py` |
| Routes, jobs, stage transitions | `backend/app/api/applications.py` |
| Final decision gate | `backend/app/api/reviews.py` |
| Scheme lifecycle and two-admin approval | `backend/app/api/schemes.py` |
| App wiring and middleware | `backend/app/main.py` |
| Auth, roles, claims | `backend/app/security.py` |
| Pipeline stage orchestration | `src/agents/orchestrator.py` |
| Agent construction, tools, skills | `src/agents/base.py` |
| Agent capability registry | `config/agents.yaml` |
| Structured stage outputs | `src/agents/results.py` |
| Model provider abstraction | `src/agents/model_provider.py` |
| Tables, columns, migrations | `src/db/schema.py` |
| DB facade and adapters | `src/db/connection.py`, `src/db/adapters/` |
| File extraction and OCR | `src/ingestion/` |
| Vector store and similarity | `src/vectorstore/chroma_store.py` |
| External web verification | `src/tools/verification_tools.py` |

## Style Conventions

- Node labels use the real artifact name plus its path, for example `FastAPI API<br/>backend/app/`.
- Direction: `flowchart LR` for layered architecture, `flowchart TD` for process flows.
- Use `subgraph` for deployment or trust zones, not for decoration.
- Solid arrows are synchronous calls; dotted arrows (`-.->`) are asynchronous or polled paths. State this in a legend when both appear.
- Cylinders (`[(...)]`) are persistent stores only.
- Mark human actions explicitly, for example `Admin decision (human)`.
- Avoid characters that break Mermaid parsing inside labels: prefer `<br/>` over newlines, and avoid unescaped parentheses and quotes.
- Use sentence case in labels. Keep labels under about six words.

## Required Diagram Catalog

Each entry states the question the diagram answers and the elements it must contain.

### 1. System context

Type: `flowchart LR`. Question: what is inside the system and what is external?
Must show: browser actor, Streamlit client, FastAPI API, `src/` domain layer, relational database, raw upload storage, ChromaDB, the configured model provider, and the optional Exa lookup. Mark which of these leave the local machine.

### 2. Component and layer architecture

Type: `flowchart TD`. Question: which layers exist and which imports are legal?
Must show the four layers (`app/`, `backend/app/`, `src/`, `config/` plus `skills/`) and the rule that `app/` never imports `src.db`, `src.tools`, or `src.ingestion`. Show `BackendClient` as the single crossing point.

### 3. Submission-to-decision flowchart

Type: `flowchart TD`. Question: what is the end-to-end path of one application?
Must show submission intake, background ingestion, admin assignment, extraction, validation with its feedback loop, scoring with its re-score loop, two-admin score approval, and the human review decision. Include failure branches.

### 4. Staged workflow state machine

Type: `stateDiagram-v2`. Question: how does `timeline_stage` advance?
Use exactly the stages defined in `app/timeline.py`: `ingesting`, `awaiting_admin_review`, `extraction_running`, `validation_running`, `awaiting_admin_validation`, `scoring_running`, `awaiting_score_approval`, `completed`. Show which transitions are human-triggered. Do not merge `timeline_stage` with `analysis_status`, which is separately `queued`, `running`, `completed`, or `failed`.

### 5. Asynchronous job and event sequence

Type: `sequenceDiagram`. Question: how does work happen off the request path and how does the UI learn about it?
Must show the immediate response on submit, the background job thread, the `event_sink` writing to `analysis_events`, and the client reading progress via the status, events, or event-stream routes.

### 6. Agent, tool, and skill map

Type: `flowchart TD`. Question: what capability does each agent hold?
Derive strictly from `config/agents.yaml`. Show all six agents and their granted tool modules and skills. Show that `src/agents/base.py` composes model, tools, and skills, and that each stage returns a validated model from `src/agents/results.py`.

### 7. Document ingestion flowchart

Type: `flowchart TD`. Question: how does a heterogeneous upload become indexed text?
Must show extension dispatch, the scanned-page OCR fallback, recursive archive handling with its limits, manifest construction, raw-file persistence for retry, chunking, embedding, and the duplicate or plagiarism check.

### 8. Data model

Type: `erDiagram`. Question: what is persisted and how is it related?
Derive tables and keys from `src/db/schema.py`. Include the uniqueness constraints that enforce distinct-admin approval on `score_approvals` and `scheme_update_approvals`.

### 9. Data-flow and classification

Type: `flowchart LR`. Question: where does submission data travel and what is allowed to leave?
Must distinguish document content, derived analysis, and identifiers. Show that document content stays local and that only an organisation name is sent to the external verification service when it is enabled.

### 10. Trust and threat boundaries

Type: `flowchart TD` with `subgraph` zones. Question: where are the enforcement points?
Must show the browser zone, the API enforcement zone, the local processing zone, and the external zone. Mark authentication, role checks, ownership checks, assigned-admin checks, and the human decision gate. Note the permissive CORS setting and the development JWT fallback as risks rather than hiding them.

### 11. Scheme lifecycle

Type: `stateDiagram-v2` or `sequenceDiagram`. Question: how is a scheme created and changed?
Must show rubric generation on create, staged edits that are not applied immediately, and the requirement for two distinct admin approvals before a pending update is written.

### 12. Deployment and configuration

Type: `flowchart LR`. Question: what runs where and what is swappable?
Must show the two local processes, the selectable database backend, the selectable model provider, and the local storage directories. Do not imply a managed cloud deployment.

## Accuracy Checklist

Verify before committing a diagram.

- [ ] Every node maps to a real file, route, table, stage, or configured service.
- [ ] Stage names match `app/timeline.py` exactly.
- [ ] Agent, tool, and skill names match `config/agents.yaml` exactly.
- [ ] Table and column names match `src/db/schema.py` exactly.
- [ ] The human decision gate is present in any diagram that shows an outcome.
- [ ] Background execution is visually distinct from the request path.
- [ ] External calls are marked, and no diagram implies document content leaving the machine.
- [ ] Both approval gates show the two-distinct-admin requirement.
- [ ] The Mermaid block renders without syntax errors.
- [ ] A legend exists when arrow styles or colors carry meaning.

## Anti-Patterns

- Copying a generic three-tier template instead of modeling this system.
- Showing extraction, validation, and scoring as one automatic step; they are separately gated.
- Drawing Streamlit talking to the database or the agents directly.
- Presenting the score as a decision.
- Adding a message broker, cache, or load balancer that the repository does not contain.
- Letting a diagram and `docs/architecture.md` disagree; reconcile them in the same change.
