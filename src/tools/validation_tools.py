"""Completeness & authenticity-indicator skills.

Checks are rule-based and explainable by design, and are always driven by the
scheme's own stated requirements rather than by hardcoded field names; they
flag issues for a human reviewer rather than making a final accept/reject
determination.
"""
from __future__ import annotations

import re

from strands import tool

_SPLIT_PATTERN = re.compile(r"[\n;,]|(?<=\))\s*/\s*")
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _requirement_tokens(requirement: str) -> set[str]:
    """Content words of a requirement, used to match it against a document."""
    stop_words = {"and", "or", "the", "a", "an", "of", "for", "with", "proof", "copy", "document", "documents"}
    return {token for token in _TOKEN_PATTERN.findall(requirement.lower()) if token not in stop_words}


def split_requirements(requirements: str | list[str]) -> list[str]:
    """Normalize a scheme's free-text requirement list into individual requirements."""
    if isinstance(requirements, list):
        items = [str(item) for item in requirements]
    else:
        items = _SPLIT_PATTERN.split(str(requirements or ""))
    return [item.strip(" -•\t") for item in items if item and item.strip(" -•\t")]


@tool
def check_scheme_requirements(required_documents: list[str], submitted_documents: list[dict]) -> dict:
    """Check a submission's documents against the documents this scheme requires.

    Args:
        required_documents: The scheme's required_documents entries, one requirement per item.
        submitted_documents: Submitted document records with title, source_path, status, and content.
    """
    requirements = split_requirements(required_documents)
    usable, unusable = [], []
    for document in submitted_documents or []:
        label = str(document.get("title") or document.get("source_path") or "document")
        content = str(document.get("content") or "").strip()
        if document.get("status") == "failed" or not content:
            unusable.append(label)
        else:
            usable.append((label, f"{label} {content}".lower()))

    matched, missing = {}, []
    for requirement in requirements:
        tokens = _requirement_tokens(requirement)
        hits = [
            label
            for label, haystack in usable
            if tokens and sum(token in haystack for token in tokens) / len(tokens) >= 0.5
        ]
        if hits:
            matched[requirement] = hits
        else:
            missing.append(requirement)

    return {
        "is_complete": not missing and not unusable,
        "required_count": len(requirements),
        "matched_requirements": matched,
        "missing_documents": missing,
        "unusable_documents": unusable,
        "unmatched_documents": [label for label, _ in usable if label not in {h for hits in matched.values() for h in hits}],
    }


@tool
def check_completeness(extracted_fields: dict, required_fields: list[str]) -> dict:
    """Check which scheme-required data points are missing from the extracted fields.

    Args:
        extracted_fields: Fields extracted from the submission.
        required_fields: Data points this scheme needs, derived from its own requirements.
    """
    missing = [field for field in required_fields if not extracted_fields.get(field)]
    return {"is_complete": len(missing) == 0, "missing_fields": missing}


@tool
def flag_authenticity_risks(extracted_fields: dict, submitted_documents: list[dict] | None = None) -> dict:
    """Flag rule-based authenticity risk indicators for human verification.

    Args:
        extracted_fields: Fields extracted from the submission.
        submitted_documents: Optional submitted document records (title, status, content).
    """
    risks = []
    if not extracted_fields:
        risks.append("no_data_extracted")
    for name, value in (extracted_fields or {}).items():
        if isinstance(value, list) and value and len(value) != len({str(item) for item in value}):
            risks.append(f"duplicate_values_in_{name}")

    for document in submitted_documents or []:
        label = str(document.get("title") or document.get("source_path") or "document")
        if document.get("status") == "failed":
            risks.append(f"unreadable_document:{label}")
        elif not str(document.get("content") or "").strip():
            risks.append(f"empty_document:{label}")

    return {"risk_flags": risks, "requires_human_review": bool(risks)}


TOOLS = [check_scheme_requirements, check_completeness, flag_authenticity_risks]
