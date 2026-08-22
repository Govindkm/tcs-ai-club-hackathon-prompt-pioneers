"""Orchestrator: runs each pipeline stage as a real agentic (LLM + tools) step.

Each stage agent is free to reason and use its own tools/skills however it
decides - it is not a fixed sequence of deterministic function calls - but it
must finish with a validated structured result (via Agent.structured_output),
so the outputs stay machine-usable (persisted to the submissions table).

An optional event_sink(stage, event_type, content) callback receives every
streamed reasoning/text/tool-use event from every stage agent as it happens
(see strands.handlers.callback_handler for the underlying event shape), so a
caller (e.g. the backend's background analysis job) can persist/display the
AI's "thinking" for human review - not just the final answer.
"""
from __future__ import annotations

import json
from typing import Callable

from src.agents.extraction_agent import create_extraction_agent
from src.agents.embedding_agent import create_embedding_agent
from src.agents.results import EmbeddingIndexResult, ExtractionResult, ScoringResult, ValidationResult
from src.agents.scoring_agent import create_scoring_agent
from src.agents.validation_agent import create_validation_agent
from src.agents.workflow_agent import create_workflow_agent
from src.tools.embedding_tools import index_document_bundle

EventSink = Callable[[str, str, str], None]


def _noop_sink(stage: str, event_type: str, content: str) -> None:
    return None


class ApplicationPipeline:
    """Runs a single application submission through the agentic pipeline."""

    def __init__(self, event_sink: EventSink | None = None) -> None:
        self._event_sink = event_sink or _noop_sink
        self.embedding_agent = create_embedding_agent(self._stage_callback("embedding"))
        self.extraction_agent = create_extraction_agent(self._stage_callback("extraction"))
        self.validation_agent = create_validation_agent(self._stage_callback("validation"))
        self.scoring_agent = create_scoring_agent(self._stage_callback("scoring"))
        self.workflow_agent = create_workflow_agent()

    def _stage_callback(self, stage: str):
        def _callback(**kwargs) -> None:
            reasoning_text = kwargs.get("reasoningText")
            data = kwargs.get("data")
            tool_use = (
                kwargs.get("event", {}).get("contentBlockStart", {}).get("start", {}).get("toolUse")
            )
            if reasoning_text:
                self._event_sink(stage, "reasoning", reasoning_text)
            if data:
                self._event_sink(stage, "text", data)
            if tool_use:
                self._event_sink(stage, "tool_call", tool_use.get("name", "unknown_tool"))

        return _callback

    def process(
        self,
        document_text: str,
        required_fields: list[str],
        admin_feedback: str = "",
        document_bundle: list[dict] | None = None,
        scheme_id: int | None = None,
        scheme_title: str = "",
        submission_id: int | None = None,
    ) -> dict:
        feedback_note = f"\n\nAdmin feedback to incorporate: {admin_feedback}" if admin_feedback else ""

        if document_bundle is not None:
            if scheme_id is None or submission_id is None:
                raise ValueError("scheme_id and submission_id are required when indexing documents.")
            self._event_sink("embedding", "stage_start", "Indexing extracted documents in ChromaDB.")
            # Storage is the required side effect of this stage. Call the registered
            # tool directly so a typed LLM response cannot falsely imply indexing.
            embedding = EmbeddingIndexResult(
                **index_document_bundle(
                    document_bundle=json.dumps(document_bundle, ensure_ascii=False),
                    scheme_id=scheme_id,
                    scheme_title=scheme_title,
                    submission_id=submission_id,
                )
            )
            self._event_sink("embedding", "stage_complete", embedding.model_dump_json())

        self._event_sink("extraction", "stage_start", "Extracting fields and summarizing the document.")
        extraction = self.extraction_agent.structured_output(
            ExtractionResult,
            f"Extract fields and summarize this application document:\n\n{document_text}{feedback_note}",
        )
        self._event_sink("extraction", "stage_complete", extraction.model_dump_json())

        self._event_sink("validation", "stage_start", "Checking completeness and authenticity risk.")
        validation = self.validation_agent.structured_output(
            ValidationResult,
            "Validate completeness of these extracted fields against the required "
            f"fields {required_fields}, and flag any authenticity risks. "
            f"Extracted fields: {extraction.extracted_fields}{feedback_note}",
        )
        self._event_sink("validation", "stage_complete", validation.model_dump_json())

        self._event_sink("scoring", "stage_start", "Computing an explainable advisory score.")
        scoring = self.scoring_agent.structured_output(
            ScoringResult,
            f"Compute an explainable score from this validation result: {validation.model_dump()}{feedback_note}",
        )
        self._event_sink("scoring", "stage_complete", scoring.model_dump_json())

        result = {"extraction": extraction, "validation": validation, "scoring": scoring}
        if document_bundle is not None:
            result["embedding"] = embedding
        return result


def create_orchestrator(event_sink: EventSink | None = None) -> ApplicationPipeline:
    return ApplicationPipeline(event_sink=event_sink)
