"""Structured output schemas the extraction/validation/scoring agents return.

Passed to Agent.structured_output(...) so each agent can still reason and use
its tools/skills however it decides, but must finish with a validated,
machine-usable result that can be persisted to the submissions table.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    extracted_fields: dict[str, Any] = Field(description="Structured fields pulled from the document.")
    summary: str = Field(description="A short (2-3 sentence) summary of the submission.")


class ValidationResult(BaseModel):
    is_complete: bool = Field(description="Whether all required fields were present.")
    missing_fields: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list, description="Authenticity/consistency risk indicators.")
    requires_human_review: bool = Field(description="True if any risk was flagged.")


class ScoringResult(BaseModel):
    score: float = Field(ge=0.0, description="Explainable advisory score for the human reviewer.")
    explanation: dict[str, Any] = Field(description="Breakdown of factors contributing to the score.")


class ScoringCriterion(BaseModel):
    name: str = Field(description="Short label for this scoring criterion.")
    weight: float = Field(ge=0.0, le=100.0, description="Weight out of 100; all criteria weights sum to 100.")
    rationale: str = Field(
        description="Why this criterion matters for this scheme and how an applicant earns points on it."
    )


class ScoringPatternResult(BaseModel):
    criteria: list[ScoringCriterion] = Field(
        description="4-8 weighted, rationale-backed scoring criteria for this scheme."
    )
    summary: str = Field(description="Short human-readable summary of the overall scoring approach.")


class EmbeddingIndexResult(BaseModel):
    scheme_id: int
    submission_id: int
    indexed_document_count: int = Field(ge=0)
    indexed_chunk_count: int = Field(ge=0)
    collection_name: str
    embedding_model: str
    record_ids: list[str] = Field(default_factory=list)
