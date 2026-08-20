"""Extraction & summarization skills: turn raw submission content into structured data.

These are intentionally simple/deterministic stand-ins so the pipeline is
testable without a live document-processing backend; swap the internals for
real OCR/parsing services later without changing the agent wiring.
"""
from __future__ import annotations

from strands import tool


@tool
def extract_fields(document_text: str) -> dict:
    """Extract candidate applicant/project fields (name, amount, dates) from raw document text.

    Args:
        document_text: Raw text content of the submitted document.
    """
    import re

    amounts = re.findall(r"(?:Rs\.?|INR)\s?([\d,]+)", document_text)
    dates = re.findall(r"\b\d{2}[/-]\d{2}[/-]\d{4}\b", document_text)
    return {
        "amounts_found": amounts,
        "dates_found": dates,
        "char_count": len(document_text),
    }


@tool
def summarize_document(document_text: str, max_sentences: int = 3) -> str:
    """Produce a short extractive summary of a document (first N sentences).

    Args:
        document_text: Raw text content of the submitted document.
        max_sentences: Maximum number of sentences to include in the summary.
    """
    sentences = [s.strip() for s in document_text.split(".") if s.strip()]
    return ". ".join(sentences[:max_sentences]) + ("." if sentences else "")


TOOLS = [extract_fields, summarize_document]
