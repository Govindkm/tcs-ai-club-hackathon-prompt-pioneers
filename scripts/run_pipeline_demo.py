"""End-to-end demo: run a synthetic application through the full agent pipeline.

Requires model credentials for the configured STRANDS_MODEL_PROVIDER (see .env.example).
"""
import sys
from pathlib import Path

# Allow running as `python scripts/run_pipeline_demo.py` from any cwd (adds repo root to sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.orchestrator import create_orchestrator

SAMPLE_DOCUMENT = """
Application for Green Energy Grant.
Applicant: Sunrise Cooperative.
Requested amount: Rs. 250,000.
Submission date: 15/03/2026.
Project description: Installation of solar micro-grids in three villages.
"""

SAMPLE_SCHEME = {
    "name": "Green Energy Grant",
    "description": "Capital grants for community-owned solar micro-grids in rural settlements.",
    "eligibility": "Registered cooperative or not-for-profit; project site is rural; no prior grant default",
    "required_documents": "application_form; project_proposal; itemised_budget; registration_certificate",
}


def _print_event(stage: str, event_type: str, content: str) -> None:
    icon = {"stage_start": "▶", "reasoning": "🧠", "text": "💬", "tool_call": "🔧", "stage_complete": "✅"}.get(
        event_type, "•"
    )
    print(f"{icon} [{stage}] {content}")


if __name__ == "__main__":
    pipeline = create_orchestrator(event_sink=_print_event)
    result = pipeline.process(
        document_text=SAMPLE_DOCUMENT,
        scheme=SAMPLE_SCHEME,
        organisation_name="Sunrise Cooperative",
    )
    for stage, output in result.items():
        print(f"\n--- {stage.upper()} ---")
        print(output)
