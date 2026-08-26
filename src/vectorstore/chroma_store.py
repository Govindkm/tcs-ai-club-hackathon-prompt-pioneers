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
        """Index a submission's documents, updating only documents whose content changed.

        Re-submitting the same document (identical content hash) leaves its existing
        chunks untouched instead of deleting+re-embedding everything for the
        submission, so unrelated/unchanged documents are never needlessly overwritten.
        """
        collection = self._get_collection()
        chunk_size = int(os.getenv("EMBEDDING_CHUNK_SIZE", "1000"))
        overlap = int(os.getenv("EMBEDDING_CHUNK_OVERLAP", "150"))

        existing = collection.get(where={"SubmissionID": str(submission_id)}, include=["metadatas"])
        existing_hash_by_document: dict[str, str] = {}
        existing_ids_by_document: dict[str, list[str]] = {}
        for record_id, meta in zip(existing.get("ids", []), existing.get("metadatas", [])):
            doc_id = meta.get("DocumentID")
            if not doc_id:
                continue
            existing_hash_by_document[doc_id] = meta.get("content_hash", "")
            existing_ids_by_document.setdefault(doc_id, []).append(record_id)

        ids, contents, metadatas = [], [], []
        indexed_document_count = 0
        for document_index, document in enumerate(documents):
            content = str(document.get("content", "")).strip()
            if not content or document.get("status") == "failed":
                continue
            document_id = document.get("document_id") or hashlib.sha256(
                f"{submission_id}:{document_index}:{document.get('source_path', '')}".encode()
            ).hexdigest()[:16]
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            indexed_document_count += 1
            if existing_hash_by_document.get(document_id) == content_hash:
                # Unchanged since last submission of this document - skip re-embedding it.
                existing_ids_by_document.pop(document_id, None)
                continue
            chunks = _chunk_text(content, chunk_size, overlap)
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
                        "content_hash": content_hash,
                    }
                )
            # Drop stale chunks for this document only (e.g. it shrank in chunk count).
            stale_ids = existing_ids_by_document.pop(document_id, [])
            if stale_ids:
                collection.delete(ids=stale_ids)

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
            "indexed_document_count": indexed_document_count,
            "indexed_chunk_count": len(ids),
            "collection_name": self.collection_name,
            "embedding_model": self.model_name,
            "record_ids": ids,
        }

    def check_plagiarism(
        self,
        documents: list[dict],
        submission_id: int,
        top_k: int = 3,
        similarity_threshold: float = 0.82,
    ) -> dict:
        """Query the vector store for content similar to this submission's documents,
        excluding the submission's own chunks, to flag likely copied/plagiarized content
        from previously submitted applications (or other locally-indexed material).
        """
        collection = self._get_collection()
        matches: list[dict] = []
        seen_pairs: set[tuple[str, str]] = set()
        for document in documents:
            content = str(document.get("content", "")).strip()
            if not content or document.get("status") == "failed":
                continue
            query_text = content[:2000]
            try:
                result = collection.query(
                    query_texts=[query_text],
                    n_results=top_k + 5,
                    where={"SubmissionID": {"$ne": str(submission_id)}},
                )
            except Exception:  # noqa: BLE001 - vector backend errors shouldn't break the pipeline
                continue
            ids = (result.get("ids") or [[]])[0]
            distances = (result.get("distances") or [[]])[0]
            metadatas = (result.get("metadatas") or [[]])[0]
            for record_id, distance, meta in zip(ids, distances, metadatas):
                # Chroma's default distance is cosine distance in [0, 2]; convert to a similarity in [0, 1].
                similarity = max(0.0, 1.0 - (distance / 2.0))
                if similarity < similarity_threshold:
                    continue
                pair_key = (document.get("title", ""), meta.get("SubmissionID", ""))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                matches.append(
                    {
                        "source_title": document.get("title", ""),
                        "matched_submission_id": meta.get("SubmissionID"),
                        "matched_document_title": meta.get("title"),
                        "similarity": round(similarity, 3),
                        "record_id": record_id,
                    }
                )
        matches.sort(key=lambda m: m["similarity"], reverse=True)
        return {
            "checked_document_count": sum(1 for d in documents if str(d.get("content", "")).strip()),
            "potential_matches": matches[: max(top_k, 10)],
            "flagged": bool(matches),
        }


def document_bundle_json(documents: list[dict]) -> str:
    """Serialize a document bundle for a Strands tool argument."""
    return json.dumps(documents, ensure_ascii=False)