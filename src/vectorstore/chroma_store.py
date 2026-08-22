"""ChromaDB persistence for document chunks."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if not text.strip():
        return []
    if overlap >= chunk_size:
        raise ValueError("Embedding chunk overlap must be smaller than chunk size.")
    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(text):
            break
        start += chunk_size - overlap
    return chunks


class ChromaStore:
    """Small adapter that keeps Chroma-specific details out of agents and tools."""

    def __init__(self, client=None, embedding_function=None) -> None:
        self._client = client
        self._embedding_function = embedding_function
        self._collection = None

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        if self._client is None:
            import chromadb

            persist_directory = Path(os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chroma"))
            persist_directory.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(persist_directory))
        if self._embedding_function is None:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

            self._embedding_function = SentenceTransformerEmbeddingFunction(
                model_name=os.getenv(
                    "EMBEDDING_MODEL_NAME",
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                )
            )
        self._collection = self._client.get_or_create_collection(
            name=os.getenv("CHROMA_COLLECTION_NAME", "scheme_documents"),
            embedding_function=self._embedding_function,
        )
        return self._collection

    @property
    def collection_name(self) -> str:
        return os.getenv("CHROMA_COLLECTION_NAME", "scheme_documents")

    @property
    def model_name(self) -> str:
        return os.getenv(
            "EMBEDDING_MODEL_NAME",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )

    def replace_documents(
        self, documents: list[dict], scheme_id: int, scheme_title: str, submission_id: int
    ) -> dict:
        collection = self._get_collection()
        chunk_size = int(os.getenv("EMBEDDING_CHUNK_SIZE", "1000"))
        overlap = int(os.getenv("EMBEDDING_CHUNK_OVERLAP", "150"))
        ids, contents, metadatas = [], [], []
        for document_index, document in enumerate(documents):
            content = str(document.get("content", "")).strip()
            if not content or document.get("status") == "failed":
                continue
            chunks = _chunk_text(content, chunk_size, overlap)
            document_id = document.get("document_id") or hashlib.sha256(
                f"{submission_id}:{document_index}:{document.get('source_path', '')}".encode()
            ).hexdigest()[:16]
            for chunk_index, chunk in enumerate(chunks):
                record_id = f"submission-{submission_id}-document-{document_id}-chunk-{chunk_index:04d}"
                ids.append(record_id)
                contents.append(chunk)
                metadatas.append(
                    {
                        "SchemeID": str(scheme_id),
                        "SchemeTitle": scheme_title,
                        "SubmissionID": str(submission_id),
                        "DocumentID": document_id,
                        "title": str(document.get("title", "")),
                        "extension": str(document.get("extension", "")),
                        "source_path": str(document.get("source_path", "")),
                        "metadata": str(document.get("metadata", "{}")),
                        "chunk_index": chunk_index,
                        "chunk_count": len(chunks),
                        "embedding_model": self.model_name,
                    }
                )

        existing = collection.get(where={"SubmissionID": str(submission_id)}, include=[])
        existing_ids = existing.get("ids", [])
        if existing_ids:
            collection.delete(ids=existing_ids)
        if ids:
            batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
            for start in range(0, len(ids), batch_size):
                end = start + batch_size
                collection.upsert(
                    ids=ids[start:end],
                    documents=contents[start:end],
                    metadatas=metadatas[start:end],
                )
        return {
            "indexed_document_count": sum(
                bool(str(document.get("content", "")).strip()) and document.get("status") != "failed"
                for document in documents
            ),
            "indexed_chunk_count": len(ids),
            "collection_name": self.collection_name,
            "embedding_model": self.model_name,
            "record_ids": ids,
        }


def document_bundle_json(documents: list[dict]) -> str:
    """Serialize a document bundle for a Strands tool argument."""
    return json.dumps(documents, ensure_ascii=False)