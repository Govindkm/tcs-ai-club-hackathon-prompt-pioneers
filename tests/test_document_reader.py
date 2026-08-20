"""Unit tests for heterogeneous (PDF/DOCX/PPTX/XLSX/image/ZIP) text extraction.

Vision-model OCR calls are monkeypatched out so these tests run offline
without a live Ollama server.
"""
import io
import zipfile

import docx
import fitz
import openpyxl
import pytest
from pptx import Presentation

import src.ingestion.document_reader as document_reader
from src.ingestion.document_reader import (
    MAX_ZIP_ENTRIES,
    MAX_ZIP_NESTING_DEPTH,
    MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES,
    extract_text,
)


@pytest.fixture(autouse=True)
def stub_vision(monkeypatch):
    """Replace the real Ollama vision call with a deterministic stub."""
    monkeypatch.setattr(document_reader, "describe_image", lambda image_bytes: "OCR_STUB_TEXT")


def test_extract_text_from_txt_bytes():
    assert extract_text("notes.txt", "Hello world".encode("utf-8")) == "Hello world"


def test_extract_text_from_csv_bytes():
    assert extract_text("data.csv", "a,b,c".encode("utf-8")) == "a,b,c"


def test_extract_text_from_docx_bytes():
    buffer = io.BytesIO()
    document = docx.Document()
    document.add_paragraph("Grant application paragraph one.")
    document.add_paragraph("Second paragraph.")
    document.save(buffer)

    result = extract_text("application.docx", buffer.getvalue())
    assert "Grant application paragraph one." in result
    assert "Second paragraph." in result


def test_extract_text_from_pdf_with_text_layer():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "This page has a real text layer with plenty of characters.")
    buffer = io.BytesIO(document.tobytes())

    result = extract_text("application.pdf", buffer.getvalue())
    assert "real text layer" in result


def test_extract_text_from_scanned_pdf_falls_back_to_ocr():
    document = fitz.open()
    document.new_page()  # blank page -> below the text-length threshold
    buffer = io.BytesIO(document.tobytes())

    result = extract_text("scanned.pdf", buffer.getvalue())
    assert result == "OCR_STUB_TEXT"


def test_extract_text_from_image_uses_vision_model():
    assert extract_text("photo.png", b"fake-image-bytes") == "OCR_STUB_TEXT"


def test_extract_text_from_pptx_bytes():
    buffer = io.BytesIO()
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "Project Overview"
    presentation.save(buffer)

    result = extract_text("deck.pptx", buffer.getvalue())
    assert "Project Overview" in result
    assert "[Slide 1]" in result


def test_extract_text_from_xlsx_bytes():
    buffer = io.BytesIO()
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Budget"
    sheet.append(["Item", "Amount"])
    sheet.append(["Solar panels", 50000])
    workbook.save(buffer)

    result = extract_text("budget.xlsx", buffer.getvalue())
    assert "[Sheet: Budget]" in result
    assert "Solar panels" in result


def test_extract_text_from_zip_combines_entries():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "Text file content")
        archive.writestr("data.csv", "col1,col2")

    result = extract_text("submission.zip", buffer.getvalue())
    assert "notes.txt" in result
    assert "Text file content" in result
    assert "data.csv" in result


def test_zip_rejects_too_many_entries():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for i in range(MAX_ZIP_ENTRIES + 1):
            archive.writestr(f"file{i}.txt", "x")

    with pytest.raises(ValueError):
        extract_text("too_many.zip", buffer.getvalue())


def test_zip_rejects_oversized_total_uncompressed_size():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("huge.txt", "0" * (MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES + 1))

    with pytest.raises(ValueError):
        extract_text("huge.zip", buffer.getvalue())


def test_zip_rejects_excessive_nesting():
    def make_zip(entries: dict[str, bytes]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        return buffer.getvalue()

    innermost = make_zip({"leaf.txt": b"leaf"})
    for _ in range(MAX_ZIP_NESTING_DEPTH + 1):
        innermost = make_zip({"nested.zip": innermost})

    # Depth violations are skipped per-entry (like unsupported file types)
    # rather than failing the whole archive.
    result = extract_text("deeply_nested.zip", innermost)
    assert "[skipped:" in result
    assert "too deeply" in result


def test_extract_text_rejects_unsupported_extension():
    with pytest.raises(ValueError):
        extract_text("malware.exe", b"binary")


def test_extract_text_rejects_oversized_file():
    with pytest.raises(ValueError):
        extract_text("big.txt", b"0" * (document_reader.MAX_FILE_SIZE_BYTES + 1))
