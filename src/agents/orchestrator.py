"""Orchestrator: coordinates extraction -> validation -> scoring -> workflow agents.

Kept as a plain Python pipeline (agents-as-tools style) rather than a single
mega-prompt, so each stage stays independently testable and auditable.
"""
from __future__ import annotations

from src.agents.extraction_agent import create_extraction_agent
from src.agents.scoring_agent import create_scoring_agent
from src.agents.validation_agent import create_validation_agent
from src.agents.workflow_agent import create_workflow_agent


class ApplicationPipeline:
    """Runs a single application submission through all processing agents."""

    def __init__(self) -> None:
        self.extraction_agent = create_extraction_agent()
        self.validation_agent = create_validation_agent()
        self.scoring_agent = create_scoring_agent()
        self.workflow_agent = create_workflow_agent()

    def process(self, document_text: str, required_fields: list[str], reviewer_pool: list[str]):
        extraction_result = self.extraction_agent(
            f"Extract fields and summarize this document:\n\n{document_text}"
        )
        validation_result = self.validation_agent(
            f"Validate completeness against required fields {required_fields} "
            f"and check authenticity risks for: {extraction_result}"
        )
        scoring_result = self.scoring_agent(
            f"Score this validation result: {validation_result}"
        )
        routing_result = self.workflow_agent(
            f"Route this case to a reviewer from pool {reviewer_pool} "
            f"given scoring result: {scoring_result}"
        )
        return {
            "extraction": extraction_result,
            "validation": validation_result,
            "scoring": scoring_result,
            "routing": routing_result,
        }


def create_orchestrator() -> ApplicationPipeline:
    return ApplicationPipeline()
