---
name: embedding-storage
description: Index a complete extracted document bundle in the local Chroma vector database.
allowed-tools: index_document_bundle
---

# Embedding and storage

Index the complete structured document bundle without changing its content.

1. Ensure `index_document_bundle` is called exactly once with every extracted document.
2. Pass each document's title, extension, metadata, and content unchanged.
3. Never summarize, rewrite, filter, or omit a document.
4. Preserve the supplied scheme and submission identifiers so records remain isolated.
5. Report the returned document count, chunk count, collection, model, and record IDs.
6. The orchestrator treats the tool result, not an LLM response, as proof of indexing.
7. If the tool fails, report the failure and do not claim that indexing completed.