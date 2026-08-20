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

if __name__ == "__main__":
    pipeline = create_orchestrator()
    result = pipeline.process(
        document_text=SAMPLE_DOCUMENT,
        required_fields=["amounts_found", "dates_found"],
        reviewer_pool=["reviewer_1", "reviewer_2"],
    )
    for stage, output in result.items():
        print(f"\n--- {stage.upper()} ---")
        print(output)
