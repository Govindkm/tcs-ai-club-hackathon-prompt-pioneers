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
    is_complete: bool = Field(description="Whether every document/criterion the scheme requires is present and usable.")
    missing_documents: list[str] = Field(
        default_factory=list, description="Scheme-required documents that were not supplied."
    )
    unusable_documents: list[str] = Field(
        default_factory=list, description="Supplied documents that are illegible, unsigned, untraceable, or off-topic."
    )
    unmet_eligibility: list[str] = Field(
        default_factory=list, description="Scheme eligibility criteria the evidence does not establish."
    )
    missing_fields: list[str] = Field(
        default_factory=list, description="Data the scheme needs that the documents never state."
    )
    contradictions: list[str] = Field(
        default_factory=list, description="Material conflicts between documents or against scheme limits."
    )
    organisation_check: dict[str, Any] = Field(
        default_factory=dict, description="Result of verifying the applicant organisation online."
    )
    risk_flags: list[str] = Field(default_factory=list, description="Authenticity/consistency risk indicators.")
    risk_level: str = Field(default="medium", description="low, medium, or high.")
    requires_human_review: bool = Field(description="True if any risk was flagged.")


class ScoringResult(BaseModel):
    score: float = Field(ge=0.0, description="Explainable advisory score for the human reviewer.")
    explanation: dict[str, Any] = Field(description="Breakdown of factors contributing to the score.")
    requires_human_review: bool = Field(
        default=False, description="True when this score should not stand without a human checking it."
    )
    review_notes: list[str] = Field(
        default_factory=list,
        description="What a human should check or decide about this score, and why.",
    )


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
