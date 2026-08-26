# Developer Guide

This guide covers the local workflow for running, testing, debugging, and extending the platform.

## 1. Prerequisites

- Python 3.10 or newer
- PowerShell on Windows
- A configured model provider for live analysis; Ollama is the simplest local option
- Enough disk for the embedding model cache, `data/chroma/`, and uploaded files

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e ".[dev]"
```

Copy `.env.example` to `.env`. At minimum, set a stable `JWT_SECRET_KEY`, `API_BASE_URL`, and the model-provider settings you intend to use. Keep restricted or synthetic data within the approved processing boundary.

## 2. Run the Stack

The backend owns the database initialization and all business logic. Start it first in one terminal:

```powershell
uvicorn backend.app.main:app --reload
```

Start the UI in another:

```powershell
streamlit run streamlit_app.py
```

Open `http://localhost:8501` for the UI and `http://localhost:8000/docs` for the OpenAPI explorer. The API health check is `http://localhost:8000/api/v1/health`.

The convenience launcher performs seeding and opens both processes in separate windows:

```powershell
.\scripts\run_dev.ps1
.\scripts\run_dev.ps1 -SkipSeed
.\scripts\run_dev.ps1 -ApiPort 8080
.\scripts\run_dev.ps1 -RunAgentDemo
```

The launcher sets `API_BASE_URL` for the Streamlit process when a non-default API port is used.

## 3. First Demo Walkthrough

1. Run `python scripts/seed_db.py` to initialize the database and create the development admin account.
2. Register an applicant in the UI, or use the API login/register routes.
3. As an admin, create or inspect a scheme. Scheme creation generates a transparent weighted scoring pattern.
4. As an applicant, submit pasted text or supported files. The request returns while ingestion runs in a background thread.
5. As an admin, assign the submission, inspect extraction and validation, and either give validation feedback or complete validation.
6. Review the advisory score. A score may request human review; any two distinct admins must approve it.
7. Record the final human decision with a rationale. This is the only action that changes the submission to approved or rejected.

For a model-backed, UI-independent run, use:

```powershell
python scripts/run_pipeline_demo.py
```

## 4. Testing and Quality Checks

Run the offline test suite:

```powershell
python -m pytest
```

The API tests replace the live orchestrator with a deterministic fake and run background jobs synchronously. This makes auth, ownership, staged transitions, persistence, and notification assertions fast and network-independent. Tests that exercise Exa clear `EXA_API_KEY` and reset the verification client.

Run lint on changed Python files or the full test suite when appropriate:

```powershell
ruff check app backend src tests
```

The repository has a known pre-existing `I001` import-order baseline in several test files; do not broaden an unrelated cleanup into a feature change.

## 5. Configuration Reference

| Variable | Purpose | Default |
| --- | --- | --- |
| `STRANDS_MODEL_PROVIDER` | `ollama`, `bedrock`, `anthropic`, or `openai` | `ollama` |
| `OLLAMA_HOST` | Ollama endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL_ID` | Text model identifier | `gemma4:31b-cloud` in `.env.example` |
| `OLLAMA_VISION_MODEL` | OCR/vision model | same cloud model in `.env.example` |
| `APP_DB_BACKEND` | `sqlite` or `postgres` | `sqlite` |
| `APP_DB_PATH` | SQLite path | `data/app.db` |
| `API_BASE_URL` | Backend URL used by Streamlit | `http://localhost:8000` |
| `CHROMA_PERSIST_DIRECTORY` | Local vector-store directory | `./data/chroma` |
| `UPLOAD_STORAGE_DIR` | Retryable raw-upload directory | `./data/uploads` |
| `EXA_API_KEY` | Optional organisation verification | unset |

Use `pip install -e ".[postgres]"` plus the PostgreSQL variables in `.env.example` when selecting the PostgreSQL adapter.

## 6. How to Extend the System

### Add a backend endpoint

1. Add request/response models to `backend/app/schemas.py`.
2. Add the route to the owning module under `backend/app/api/`.
3. Use `get_current_user` or `require_role` and enforce ownership in the backend.
4. Call repository functions rather than embedding SQL in the route when the operation is durable.
5. Add the matching method to `app/api_client.py`.
6. Keep the Streamlit view focused on rendering and input handling.
7. Add an API test using the isolated environment fixture.

### Add or change an agent capability

The normal extension path is to add a `@tool` function in a domain module, add its module to the relevant `tools` list in `config/agents.yaml`, and update the matching skill instructions. Keep tool inputs and outputs JSON-serializable and deterministic where possible.

```python
# src/tools/example_tools.py
from strands import tool

@tool
def check_example(value: str) -> dict:
    """Return a structured, auditable check for one value."""
    return {"value": value, "passed": bool(value.strip())}
```

For a new pipeline stage, add a result model in `src/agents/results.py`, create the agent factory, wire its callback in `ApplicationPipeline`, persist the result from the backend job, and cover the stage transition with a test. Do not let an agent write final review decisions.

### Add a database field

Update the canonical schema in `src/db/schema.py` and add the field to `_MIGRATIONS` so existing local databases receive it. Then update repository queries, Pydantic schemas, API serialization, and tests together. Use adapter-neutral SQL and parameterized values.

### Add a Streamlit view

Put presentation code in `app/views/`, obtain the client through `get_client()`, and use explicit widget keys for repeated forms. Streamlit reruns the script after interactions, so clear widget state only after a successful request; the existing helpers in `app/forms.py` handle this for submission forms.

## 7. Debugging Checklist

- `401`: confirm the UI has a token and `JWT_SECRET_KEY` is stable across backend restarts.
- `403`: check role, applicant ownership, or assigned-admin ownership; these are server-side checks.
- UI cannot reach API: verify `API_BASE_URL`, port, and `http://localhost:8000/api/v1/health`.
- Analysis remains queued/running: inspect the backend terminal, then refresh the admin event log and submission status endpoint.
- Ingestion fails: inspect `analysis_error`, the ingestion event, Ollama connectivity, and `UPLOAD_STORAGE_DIR`.
- Empty or duplicate embedding result: inspect `CHROMA_PERSIST_DIRECTORY` and the document manifest; unchanged document hashes are intentionally not re-indexed.
- Test contamination: ensure tests use a temporary `APP_DB_PATH` and `UPLOAD_STORAGE_DIR`, and do not allow `EXA_API_KEY` to reach the network.

## 8. Contribution Boundaries

Keep changes small and layered: UI changes stay in `app/`, HTTP and authorization in `backend/app/`, domain behavior in `src/`, declarative behavior in `config/` or `skills/`, and verification in `tests/`. Update the architecture guide when a trust boundary, persistence location, workflow transition, or provider contract changes.