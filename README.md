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

## Repository Structure

```
.
├── docs/                  # Architecture, ADRs, data-flow & threat-boundary diagrams
├── data/                  # Synthetic dataset generation & samples (non-sensitive only); app.db (gitignored)
├── config/
│   ├── models.yaml        # Model provider config (Bedrock/Anthropic/OpenAI/Ollama)
│   └── agents.yaml        # Declarative agent -> tools/skills mapping
├── skills/                # Agent Skills (SKILL.md packages, per agentskills.io spec)
│   ├── document-extraction/        # Extraction & summarization instructions
│   ├── completeness-validation/    # Completeness & authenticity-risk instructions
│   ├── explainable-scoring/        # Rule scoring instructions + references/
│   └── reviewer-workflow/          # Reviewer routing & audit-trail instructions
├── app/                    # Streamlit portal (views + session-state helpers)
│   ├── state.py                    # Current-user session-state helpers
│   └── views/                      # auth, applicant, admin, notifications views
├── streamlit_app.py        # Streamlit entrypoint (streamlit run streamlit_app.py)
├── src/
│   ├── agents/            # Strands Agent definitions (one per pipeline stage) + orchestrator
│   │   └── base.py                # Wires each agent's tools + AgentSkills plugin from config
│   ├── tools/              # Strands @tool callables granted to agents, grouped by domain
│   │   ├── document_tools.py      # Extraction & summarization tools
│   │   ├── validation_tools.py    # Completeness & authenticity-risk tools
│   │   ├── scoring_tools.py       # Configurable rules + explainable scoring tools
│   │   └── workflow_tools.py      # Reviewer routing, decision recording, audit trail
│   ├── db/                 # SQLite schema + repository (users, schemes, submissions, reviews, notifications)
│   ├── ingestion/         # Heterogeneous file/zip extraction (document_reader.py) + vision OCR (vision.py)
│   ├── analytics/         # Operational analytics & reporting
│   ├── adapters/          # Mock adapters (schemes portal, messaging, identity)
│   └── telemetry.py        # OpenTelemetry tracing setup (console/OTLP exporters)
├── scripts/
│   ├── seed_db.py             # Creates a default admin user + sample schemes
│   └── run_pipeline_demo.py  # End-to-end demo of the agent pipeline
├── backend/
│   └── app/
│       ├── main.py                # FastAPI entrypoint (uvicorn backend.app.main:app)
│       ├── security.py            # JWT auth (create/verify token, get_current_user, require_role)
│       ├── schemas.py             # Pydantic request/response models
│       └── api/                   # Routers: auth, schemes, applications, reviews, notifications, health
├── app/                    # Streamlit portal - thin client only, calls the API via api_client.py
│   ├── api_client.py               # BackendClient: the only thing views use to talk to the backend
│   ├── state.py                    # Session-state helpers (current user + BackendClient instance)
│   └── views/                      # auth, applicant, admin, notifications views (no business logic)
├── streamlit_app.py        # Streamlit entrypoint (streamlit run streamlit_app.py)
├── notebooks/             # Model/evaluation notebooks
├── tests/                 # Automated tests for critical paths
├── .env.example           # Model provider credentials/config template
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Architecture: API-first (FastAPI backend, thin Streamlit client)

All application-processing logic (extraction, validation, scoring, review, audit,
notifications) lives behind a [FastAPI](https://fastapi.tiangolo.com/) backend
([backend/app/](backend/app), run with `uvicorn backend.app.main:app`). The Streamlit
app is a **thin client only** — it never imports `src.db`/`src.tools`/`src.ingestion`
directly; every view calls [app/api_client.py](app/api_client.py)'s `BackendClient`, which
speaks plain REST/JSON to the API. This means Streamlit can be deleted and replaced with
React/mobile/a government portal without touching any business logic.

```
Streamlit UI  ──REST/JSON──▶  FastAPI (backend/app)  ──▶  src/db, src/tools,
(thin client)                 auth · applications ·        src/ingestion, src/agents
                               reviews · schemes ·
                               notifications · health
```

Auth is JWT-based (`backend/app/security.py`): `POST /api/v1/auth/login` returns a bearer
token carrying `id`/`username`/`role`, sent as `Authorization: Bearer <token>` on every
subsequent request; `require_role("admin")` gates admin-only endpoints. Submission ownership
is enforced server-side (`GET /api/v1/applications/{id}` 403s for non-owners/non-admins),
so the UI layer can never be the only thing protecting a permission boundary. See the
auto-generated OpenAPI docs at `http://localhost:8000/docs` once the backend is running.

## Ingestion (Heterogeneous Submissions)

[src/ingestion/document_reader.py](src/ingestion/document_reader.py) extracts plain text
from whatever mix of files an applicant submits, dispatching by extension:

| Type | Strategy |
|---|---|
| `.txt` / `.csv` | Read directly |
| `.pdf` | Extract the text layer per page (PyMuPDF); pages with little/no text (scanned) fall back to rendering the page as an image and running vision-OCR |
| `.docx` | Extract paragraph text + OCR any embedded images |
| `.pptx` | Extract slide text + OCR any embedded images |
| `.xlsx` | Dump all sheets/cells as text |
| `.png` / `.jpg` / `.jpeg` / `.bmp` / `.tiff` / `.webp` | Vision-OCR the whole image |
| `.zip` | Recursively extract every entry above (e.g. a whole submission folder), with entry-count/size/nesting-depth limits to prevent zip-bomb style DoS |

Vision-OCR ([src/ingestion/vision.py](src/ingestion/vision.py)) calls a local Ollama vision
model (`OLLAMA_HOST` + `OLLAMA_VISION_MODEL` in `.env`, default `minicpm-v` - strong OCR on
dense document scans; `moondream` is a faster/lighter alternative, `llama3.2-vision` a
heavier general-purpose one). Pull whichever model you configure, e.g. `ollama pull minicpm-v`
(the [Colab notebook](notebooks/colab_ollama_server.ipynb) has a cell for this).

## Agents, Tools & Skills (Strands Agents SDK)

AI agents are built with the [Strands Agents SDK](https://strandsagents.com/). Two distinct
SDK concepts are used together, per the [Skills plugin docs](https://strandsagents.com/docs/user-guide/concepts/plugins/skills/):

- **Tools** (`src/tools/`) – plain Python `@tool` callables passed directly via
  `Agent(tools=[...])`. These do the actual work (extract fields, score, route, etc.).
- **Skills** (`skills/`) – [Agent Skills](https://agentskills.io/specification) packages
  (`SKILL.md` + optional `scripts/`, `references/`, `assets/`). Only lightweight
  name/description metadata is injected into the system prompt up front; the agent
  loads full instructions on demand via the `AgentSkills` plugin's `skills` tool,
  keeping the context window lean.

| Agent | Tools granted | Skill activated |
|---|---|---|
| Extraction agent | `document_tools` | `document-extraction` |
| Validation agent | `validation_tools` | `completeness-validation` |
| Scoring agent | `scoring_tools` | `explainable-scoring` |
| Workflow agent | `workflow_tools` | `reviewer-workflow` |

The **orchestrator** (`src/agents/orchestrator.py`) runs the four agents as a pipeline.
Agent-to-tool/skill assignments are declared in [config/agents.yaml](config/agents.yaml) and
wired in [src/agents/base.py](src/agents/base.py) so capabilities stay auditable — no tool
can finalize an approval/rejection; human review is always required per the platform's
core constraint.

## Observability (Tracing & Telemetry)

[src/telemetry.py](src/telemetry.py) configures Strands' built-in
[OpenTelemetry tracing](https://strandsagents.com/docs/user-guide/observability-evaluation/traces/)
via `StrandsTelemetry`, giving every agent run/model call/tool call a hierarchical trace.
`build_agent()` calls it once (idempotent) before constructing any agent, and tags each
agent with `name=<agent_key>` and `trace_attributes` (`app.name`, `agent.key`) so spans are
attributable per agent. Controlled via `.env`:

- `STRANDS_TRACE_CONSOLE` (default `true`) — print spans to the console for local debugging.
- `STRANDS_TRACE_OTLP` (default `false`) — export spans to an OTLP collector (e.g. Jaeger,
  Grafana Tempo). Configure the endpoint with the standard `OTEL_EXPORTER_OTLP_ENDPOINT` /
  `OTEL_EXPORTER_OTLP_HEADERS` env vars.
- `OTEL_SERVICE_NAME` — service name attached to all spans.

## Portal (Streamlit thin client + FastAPI + SQLite)

The [Streamlit](https://streamlit.io/) portal ([streamlit_app.py](streamlit_app.py)) is a thin
client (see architecture section above) over the FastAPI backend, which persists to a local
SQLite database ([src/db/](src/db)). It provides registration/login and role-based access:

- **Applicants** (self-registered) can browse open schemes, submit applications, and track
  only their own submissions' status — including the final decision once a case is closed.
- **Admins** (provisioned via [scripts/seed_db.py](scripts/seed_db.py), not self-registration)
  can view/filter all submissions, record the human review decision (approve / reject /
  request more info) with a mandatory rationale, manage schemes, and publish notifications
  shown to all users.

Every submission runs through the real **agentic** extraction → validation → scoring
pipeline (`src/agents/orchestrator.py`, requires a configured `STRANDS_MODEL_PROVIDER`) —
each stage is a Strands `Agent` that reasons and uses its own tools/skills, finishing with
a validated structured result via `Agent.structured_output(...)` so it can still be stored
and rendered. The reviewer's decision is always what actually changes a case's status — the
agents only produce advisory output.

### Async analysis job + live AI reasoning log

The pipeline runs as a **background job** (FastAPI `BackgroundTasks`), not inline in the
request: `POST /applications` and `POST /applications/{id}/analyze` return immediately with
`analysis_status="queued"`, while the job progresses through `running` (tagged with the
current `analysis_stage`: extraction/validation/scoring) to `completed` or `failed`. Poll
`GET /applications/{id}` or the lighter `GET /applications/{id}/status` for progress.

Every stage agent streams its reasoning/tool-use back through a `callback_handler`
(`src/agents/orchestrator.py`), which is persisted to an `analysis_events` table as it
happens — so admins can watch **how** the AI reached its answer, not just the final
result, via `GET /applications/{id}/events` (history) or the live
`GET /applications/{id}/events/stream` (Server-Sent Events). In the Streamlit admin view,
each submission has a "🧠 AI reasoning & thinking" log (refresh to see progress) and a
feedback box that lets an admin steer a re-analysis with human-in-the-loop guidance
(`POST /applications/{id}/analyze` with `{"feedback": "..."}`), which gets included in the
next prompt sent to each agent.

## Getting Started

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
Copy-Item .env.example .env
# edit .env: set JWT_SECRET_KEY (any random string) for stable sessions across restarts,
# and STRANDS_MODEL_PROVIDER + credentials - required for submissions, since each one
# runs through the real agentic analysis pipeline (Ollama is the easiest local/free option)

# 3. Run unit tests (no live model/backend calls needed)
pytest

# 4. Seed the local SQLite DB with a default admin user + sample schemes
python scripts/seed_db.py

# 5. Start the FastAPI backend (owns all business logic)
uvicorn backend.app.main:app --reload

# 6. In a second terminal, launch the Streamlit thin client
streamlit run streamlit_app.py

# 7. (Optional) Run the end-to-end LLM agent pipeline demo (requires model credentials)
python scripts/run_pipeline_demo.py
```

## Status

🚧 Work in progress — POC under active development for the TCS AI Club Hackathon.
