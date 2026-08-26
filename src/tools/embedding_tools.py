"""Tools used by the embedding agent to index complete document bundles."""
from __future__ import annotations

import json

from strands import tool

from src.vectorstore.chroma_store import ChromaStore

_STORE = ChromaStore()

_MAX_REPORTED_FAILURES = 5
_MAX_REASON_CHARS = 200


def _unusable_summary(documents: list[dict]) -> str:
    """Explain why a bundle had nothing to index - usually a failed extraction/OCR."""
    reasons = []
    for document in documents:
        title = str(document.get("title") or document.get("source_path") or "document")
        if document.get("status") == "failed":
            reason = str(document.get("error") or "extraction failed")[:_MAX_REASON_CHARS]
            reasons.append(f"{title}: {reason}")
        elif not str(document.get("content", "")).strip():
            reasons.append(f"{title}: empty after extraction")
    if not reasons:
        return "The bundle contained no document content."
    listed = "; ".join(reasons[:_MAX_REPORTED_FAILURES])
    remaining = len(reasons) - _MAX_REPORTED_FAILURES
    return f"{listed}{f' (+{remaining} more)' if remaining > 0 else ''}"


@tool
def index_document_bundle(
    document_bundle: str, scheme_id: int, scheme_title: str, submission_id: int
) -> dict:
    """Validate and index every extracted document in a JSON document bundle.

    Args:
        document_bundle: JSON array containing title, extension, metadata, and content.
        scheme_id: SQLite scheme identifier.
        scheme_title: Human-readable scheme title.
        submission_id: SQLite submission identifier.
    """
    try:
        documents = json.loads(document_bundle)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("document_bundle must be valid JSON.") from exc
    if not isinstance(documents, list) or not documents or any(not isinstance(document, dict) for document in documents):
        raise ValueError("document_bundle must be a non-empty JSON array.")
    required = {"title", "extension", "metadata", "content"}
    if any(not required.issubset(document) for document in documents):
        raise ValueError("Every document must contain title, extension, metadata, and content.")
    result = _STORE.replace_documents(documents, scheme_id, scheme_title, submission_id)
    # A re-ingestion of unchanged documents legitimately writes zero chunks, so failure
    # is judged on usable documents instead of on newly embedded chunks.
    if result["indexed_document_count"] == 0:
        raise ValueError(
            f"No usable document content was available for indexing. {_unusable_summary(documents)}"
        )
    return {"scheme_id": scheme_id, "submission_id": submission_id, **result}


@tool
def check_document_similarity(document_bundle: str, submission_id: int, similarity_threshold: float = 0.82) -> dict:
    """Check a submission's documents for plagiarized/copied content against everything
    else already indexed locally (other submissions), excluding the submission itself.

    Args:
        document_bundle: JSON array containing title, extension, metadata, and content.
        submission_id: SQLite submission identifier (excluded from the similarity search).
        similarity_threshold: Minimum cosine similarity (0-1) to flag as a potential match.
    """
    try:
        documents = json.loads(document_bundle)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("document_bundle must be valid JSON.") from exc
    if not isinstance(documents, list):
        raise ValueError("document_bundle must be a JSON array.")
    return _STORE.check_plagiarism(documents, submission_id, similarity_threshold=similarity_threshold)


TOOLS = [index_document_bundle, check_document_similarity]