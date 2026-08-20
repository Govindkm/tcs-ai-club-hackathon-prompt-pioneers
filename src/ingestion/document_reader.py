"""Extract plain text from heterogeneous application submissions.

Supports TXT/CSV, PDF (text layer + vision-OCR fallback for scanned pages),
DOCX (paragraph text + embedded images via OCR), PPTX (slide text + images),
XLSX (cell data), standalone images (OCR via a local Ollama vision model -
see src/ingestion/vision.py), and ZIP archives (recursively, with size/entry
limits to avoid zip-bomb style DoS) - so a whole submission folder zipped up
can be ingested in one call.

Kept isolated from the UI/DB layers so new formats can be added without
touching Streamlit views or the submissions schema.
"""
from __future__ import annotations

import io
import zipfile

from src.ingestion.vision import describe_image

SUPPORTED_EXTENSIONS = (
    ".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".csv",
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp", ".zip",
)
_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "tiff", "webp"}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per non-archive file
MAX_ZIP_FILE_BYTES = 25 * 1024 * 1024  # 25 MB for the zip upload itself
MAX_ZIP_ENTRIES = 50  # avoids zip-bomb style DoS via huge file counts
MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # avoids zip-bomb style DoS via huge extraction
MAX_ZIP_NESTING_DEPTH = 2

_MIN_PDF_PAGE_TEXT_CHARS = 20  # below this, treat the page as scanned/image-only


def extract_text(filename: str, file_bytes: bytes, _zip_depth: int = 0) -> str:
    """Extract plain text from a single file's raw bytes, dispatching by extension."""
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if suffix == "zip":
        if len(file_bytes) > MAX_ZIP_FILE_BYTES:
            raise ValueError(f"'{filename}' exceeds the {MAX_ZIP_FILE_BYTES // (1024 * 1024)}MB zip size limit.")
        return _extract_zip_text(filename, file_bytes, _zip_depth)

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"'{filename}' exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB size limit.")

    if suffix == "pdf":
        return _extract_pdf_text(file_bytes)
    if suffix == "docx":
        return _extract_docx_text(file_bytes)
    if suffix == "pptx":
        return _extract_pptx_text(file_bytes)
    if suffix == "xlsx":
        return _extract_xlsx_text(file_bytes)
    if suffix in ("txt", "csv"):
        return file_bytes.decode("utf-8", errors="replace")
    if suffix in _IMAGE_EXTENSIONS:
        return describe_image(file_bytes)

    raise ValueError(f"Unsupported file type for '{filename}'. Supported: {SUPPORTED_EXTENSIONS}")


def extract_text_from_uploads(uploaded_files) -> str:
    """Extract and concatenate text from a list of Streamlit UploadedFile objects."""
    sections = []
    for uploaded_file in uploaded_files or []:
        text = extract_text(uploaded_file.name, uploaded_file.getvalue())
        sections.append(f"--- {uploaded_file.name} ---\n{text}")
    return "\n\n".join(sections)


def _extract_zip_text(filename: str, file_bytes: bytes, zip_depth: int) -> str:
    if zip_depth >= MAX_ZIP_NESTING_DEPTH:
        raise ValueError(f"'{filename}' nests zip archives too deeply (max {MAX_ZIP_NESTING_DEPTH} levels).")

    with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
        entries = [i for i in archive.infolist() if not i.is_dir() and "__MACOSX" not in i.filename]
        if len(entries) > MAX_ZIP_ENTRIES:
            raise ValueError(f"'{filename}' contains too many files (max {MAX_ZIP_ENTRIES}).")

        total_uncompressed = sum(entry.file_size for entry in entries)
        if total_uncompressed > MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
            raise ValueError(
                f"'{filename}' would extract to more than "
                f"{MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES // (1024 * 1024)}MB; rejected."
            )

        sections = []
        for entry in entries:
            entry_bytes = archive.read(entry)
            try:
                text = extract_text(entry.filename, entry_bytes, zip_depth + 1)
            except ValueError as exc:
                text = f"[skipped: {exc}]"
            sections.append(f"--- {filename}/{entry.filename} ---\n{text}")
        return "\n\n".join(sections)


def _extract_pdf_text(file_bytes: bytes) -> str:
    import fitz  # PyMuPDF - also renders scanned pages to images for OCR fallback

    document = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for page in document:
        text = page.get_text().strip()
        if len(text) < _MIN_PDF_PAGE_TEXT_CHARS:
            pixmap = page.get_pixmap(dpi=200)
            text = describe_image(pixmap.tobytes("png"))
        pages.append(text)
    return "\n".join(pages)


def _extract_docx_text(file_bytes: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(file_bytes))
    sections = [p.text for p in document.paragraphs]
    for rel in document.part.rels.values():
        if "image" in rel.reltype:
            sections.append(describe_image(rel.target_part.blob))
    return "\n".join(sections)


def _extract_pptx_text(file_bytes: bytes) -> str:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    presentation = Presentation(io.BytesIO(file_bytes))
    sections = []
    for slide_number, slide in enumerate(presentation.slides, start=1):
        slide_sections = [f"[Slide {slide_number}]"]
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                slide_sections.append(shape.text_frame.text)
            elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                slide_sections.append(describe_image(shape.image.blob))
        sections.append("\n".join(slide_sections))
    return "\n\n".join(sections)


def _extract_xlsx_text(file_bytes: bytes) -> str:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    sections = []
    for sheet in workbook.worksheets:
        rows = [
            ", ".join("" if cell is None else str(cell) for cell in row)
            for row in sheet.iter_rows(values_only=True)
        ]
        sections.append(f"[Sheet: {sheet.title}]\n" + "\n".join(rows))
    return "\n\n".join(sections)
