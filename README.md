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
│   ├── ingestion/         # Submission intake & heterogeneous document handling
│   ├── analytics/         # Operational analytics & reporting
│   └── adapters/          # Mock adapters (schemes portal, messaging, identity)
├── scripts/
│   ├── seed_db.py             # Creates a default admin user + sample schemes
│   └── run_pipeline_demo.py  # End-to-end demo of the agent pipeline
├── notebooks/             # Model/evaluation notebooks
├── tests/                 # Automated tests for critical paths
├── .env.example           # Model provider credentials/config template
├── pyproject.toml
├── requirements.txt
└── README.md
```

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

## Portal (Streamlit + SQLite)

A [Streamlit](https://streamlit.io/) portal ([streamlit_app.py](streamlit_app.py)) backed by a
local SQLite database ([src/db/](src/db)) provides registration/login and role-based access:

- **Applicants** (self-registered) can browse open schemes, submit applications, and track
  only their own submissions' status — including the final decision once a case is closed.
- **Admins** (provisioned via [scripts/seed_db.py](scripts/seed_db.py), not self-registration)
  can view/filter all submissions, record the human review decision (approve / reject /
  request more info) with a mandatory rationale, manage schemes, and publish notifications
  shown to all users.

On submission, the deterministic `document_tools` / `validation_tools` / `scoring_tools`
functions run automatically (no LLM credentials needed) to pre-fill extraction, validation,
and an explainable advisory score for the reviewer — the reviewer's decision is always what
actually changes a case's status.

## Getting Started

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure model provider credentials (only needed for the agent/LLM demo, not the portal)
Copy-Item .env.example .env
# edit .env: set STRANDS_MODEL_PROVIDER and the matching credentials
# (use Ollama/Bedrock with local/on-prem access for restricted data)

# 3. Run unit tests (no live model calls)
pytest

# 4. Seed the local SQLite DB with a default admin user + sample schemes
python scripts/seed_db.py

# 5. Launch the Streamlit portal
streamlit run streamlit_app.py

# 6. (Optional) Run the end-to-end LLM agent pipeline demo (requires model credentials)
python scripts/run_pipeline_demo.py
```

## Status

🚧 Work in progress — POC under active development for the TCS AI Club Hackathon.
