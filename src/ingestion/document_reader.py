"""Extract plain text from uploaded application documents (PDF, DOCX, TXT).

Kept isolated from the UI/DB layers so new formats can be added without
touching Streamlit views or the submissions schema.
"""
from __future__ import annotations

import io

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt")
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per file, avoids DoS via oversized uploads


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Extract plain text from a single uploaded file's raw bytes."""
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"'{filename}' exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB size limit.")

    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "pdf":
        return _extract_pdf_text(file_bytes)
    if suffix == "docx":
        return _extract_docx_text(file_bytes)
    if suffix == "txt":
        return file_bytes.decode("utf-8", errors="replace")

    raise ValueError(f"Unsupported file type for '{filename}'. Supported: {SUPPORTED_EXTENSIONS}")


def extract_text_from_uploads(uploaded_files) -> str:
    """Extract and concatenate text from a list of Streamlit UploadedFile objects."""
    sections = []
    for uploaded_file in uploaded_files or []:
        text = extract_text(uploaded_file.name, uploaded_file.getvalue())
        sections.append(f"--- {uploaded_file.name} ---\n{text}")
    return "\n\n".join(sections)


def _extract_pdf_text(file_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx_text(file_bytes: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in document.paragraphs)
