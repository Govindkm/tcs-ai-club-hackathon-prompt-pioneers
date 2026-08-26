"""Tests for embedding-tool input validation without loading a real model."""
from __future__ import annotations

import json

import pytest

import src.tools.embedding_tools as embedding_tools


def test_index_document_bundle_rejects_invalid_json():
    with pytest.raises(ValueError, match="valid JSON"):
        embedding_tools.index_document_bundle("not-json", 1, "Scheme", 2)


def test_index_document_bundle_rejects_incomplete_documents():
    with pytest.raises(ValueError, match="title, extension, metadata, and content"):
        embedding_tools.index_document_bundle('[{"title": "file.txt"}]', 1, "Scheme", 2)


class _FakeStore:
    def __init__(self, indexed_document_count: int, indexed_chunk_count: int) -> None:
        self._result = {
            "indexed_document_count": indexed_document_count,
            "indexed_chunk_count": indexed_chunk_count,
            "collection_name": "test",
            "embedding_model": "test-model",
            "record_ids": [],
        }

    def replace_documents(self, documents, scheme_id, scheme_title, submission_id) -> dict:
        return self._result


_FAILED_BUNDLE = json.dumps(
    [
        {
            "title": "scan.pdf",
            "extension": ".pdf",
            "metadata": "{}",
            "content": "[extraction failed: vision model unreachable]",
            "status": "failed",
            "error": "vision model unreachable",
        }
    ]
)
_USABLE_BUNDLE = json.dumps(
    [{"title": "notes.txt", "extension": ".txt", "metadata": "{}", "content": "Rs. 1,000", "status": "extracted"}]
)


def test_index_document_bundle_reports_why_nothing_was_indexable(monkeypatch):
    monkeypatch.setattr(embedding_tools, "_STORE", _FakeStore(0, 0))
    with pytest.raises(ValueError, match="scan.pdf: vision model unreachable"):
        embedding_tools.index_document_bundle(_FAILED_BUNDLE, 1, "Scheme", 2)


def test_reindexing_unchanged_documents_is_not_a_failure(monkeypatch):
    """Re-ingesting identical content embeds zero new chunks, which is success, not failure."""
    monkeypatch.setattr(embedding_tools, "_STORE", _FakeStore(1, 0))
    result = embedding_tools.index_document_bundle(_USABLE_BUNDLE, 1, "Scheme", 2)
    assert result["indexed_document_count"] == 1
    assert result["indexed_chunk_count"] == 0
    assert result["submission_id"] == 2