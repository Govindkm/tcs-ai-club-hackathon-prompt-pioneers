"""Tests for embedding-tool input validation without loading a real model."""
from __future__ import annotations

import pytest

import src.tools.embedding_tools as embedding_tools


def test_index_document_bundle_rejects_invalid_json():
    with pytest.raises(ValueError, match="valid JSON"):
        embedding_tools.index_document_bundle("not-json", 1, "Scheme", 2)


def test_index_document_bundle_rejects_incomplete_documents():
    with pytest.raises(ValueError, match="title, extension, metadata, and content"):
        embedding_tools.index_document_bundle('[{"title": "file.txt"}]', 1, "Scheme", 2)