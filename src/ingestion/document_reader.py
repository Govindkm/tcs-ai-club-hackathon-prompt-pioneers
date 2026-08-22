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
import json
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
    return combine_document_text(extract_documents_from_uploads(uploaded_files))


def extract_documents(files: list[tuple[str, bytes]]) -> list[dict]:
    """Extract uploads into document records while preserving file boundaries."""
    documents = []
    for filename, content in files:
        documents.extend(_extract_document_records(filename, content))
    return documents


def extract_documents_from_uploads(uploaded_files) -> list[dict]:
    """Extract Streamlit uploads into structured records suitable for persistence."""
    return extract_documents(
        [(uploaded_file.name, uploaded_file.getvalue()) for uploaded_file in uploaded_files or []]
    )


def combine_document_text(documents: list[dict]) -> str:
    """Build the legacy combined text input from structured document records."""
    sections = [f"--- {document['source_path']} ---\n{document['content']}" for document in documents]
    return "\n\n".join(sections)


def _extract_document_records(filename: str, file_bytes: bytes, source_path: str | None = None, _zip_depth: int = 0) -> list[dict]:
    path = source_path or filename
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "zip":
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            entries = [i for i in archive.infolist() if not i.is_dir() and "__MACOSX" not in i.filename]
            if len(entries) > MAX_ZIP_ENTRIES:
                raise ValueError(f"'{filename}' contains too many files (max {MAX_ZIP_ENTRIES}).")
            if sum(entry.file_size for entry in entries) > MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
                raise ValueError(f"'{filename}' would extract to more than {MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES // (1024 * 1024)}MB; rejected.")
            records = []
            for entry in entries:
                entry_path = f"{path}/{entry.filename}"
                try:
                    records.extend(_extract_document_records(entry.filename, archive.read(entry), entry_path, _zip_depth + 1))
                except ValueError as exc:
                    records.append(_document_record(entry.filename, entry_path, "", file_bytes=0, error=str(exc)))
            return records

    text = extract_text(filename, file_bytes, _zip_depth)
    return [_document_record(filename, path, text, file_bytes=len(file_bytes))]


def _document_record(filename: str, source_path: str, content: str, file_bytes: int, error: str | None = None) -> dict:
    extension = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""
    return {
        "title": filename,
        "extension": extension,
        "source_path": source_path,
        "metadata": json.dumps({"size_bytes": file_bytes}, sort_keys=True),
        "content": content,
        "status": "failed" if error else "extracted",
        "error": error,
    }


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
    sections = []

    # Extract normal paragraphs.
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            sections.append(text)

    # Extract table rows and nested tables.
    def extract_table(table):
        table_text = []

        for row in table.rows:
            values = []

            for cell in row.cells:
                cell_text = cell.text.strip().replace("\n", " ")
                if cell_text:
                    values.append(cell_text)

                for nested_table in cell.tables:
                    nested_text = extract_table(nested_table)
                    if nested_text:
                        values.append(nested_text)

            if values:
                table_text.append(" | ".join(values))

        return "\n".join(table_text)

    for table in document.tables:
        table_text = extract_table(table)
        if table_text:
            sections.append(table_text)

    # Extract OCR text from embedded images.
    processed_images = set()

    for relationship in document.part.rels.values():
        if "image" not in relationship.reltype:
            continue

        image_bytes = relationship.target_part.blob
        image_id = hash(image_bytes)

        if image_id in processed_images:
            continue

        processed_images.add(image_id)
        image_text = describe_image(image_bytes).strip()

        if image_text:
            sections.append(image_text)

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
                slide_sections.append(shape.text_frame.text.strip())

            elif shape.shape_type == MSO_SHAPE_TYPE.CHART:
                chart = shape.chart
                chart_sections = ["[Chart]"]

                if chart.has_title:
                    title = chart.chart_title.text_frame.text.strip()
                    if title:
                        chart_sections[0] = f"[Chart: {title}]"

                for plot in chart.plots:
                    try:
                        categories = list(plot.categories)
                    except (AttributeError, ValueError):
                        categories = []

                    category_values = []
                    for category in categories:
                        try:
                            value = category.label
                        except (AttributeError, ValueError):
                            value = None

                        if value is None:
                            try:
                                value = category.value
                            except (AttributeError, ValueError):
                                value = None

                        category_values.append("" if value is None else str(value))

                    for series in plot.series:
                        try:
                            series_name = series.name
                        except (AttributeError, ValueError):
                            series_name = "Unnamed series"

                        try:
                            values = list(series.values)
                        except (AttributeError, ValueError):
                            values = []

                        chart_sections.append(f"Series: {series_name}")

                        if category_values:
                            chart_sections.append(
                                "Categories: " + ", ".join(category_values)
                            )

                        chart_sections.append(
                            "Values: " + ", ".join(
                                "" if value is None else str(value)
                                for value in values
                            )
                        )

                slide_sections.append("\n".join(chart_sections))

            elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                image_text = describe_image(shape.image.blob).strip()
                if image_text:
                    slide_sections.append(image_text)

        sections.append("\n".join(slide_sections))

    return "\n\n".join(sections)


def _extract_xlsx_text(file_bytes: bytes) -> str:
    import re

    from openpyxl import load_workbook
    from openpyxl.utils.cell import range_boundaries

    values_workbook = load_workbook(
        io.BytesIO(file_bytes),
        data_only=True,
        read_only=False,
    )

    formulas_workbook = load_workbook(
        io.BytesIO(file_bytes),
        data_only=False,
        read_only=False,
    )

    def calculate_cell(values_sheet, formulas_sheet, coordinate, stack=None):
        stack = stack or set()

        if coordinate in stack:
            return formulas_sheet[coordinate].value

        cached_value = values_sheet[coordinate].value
        formula_value = formulas_sheet[coordinate].value

        if cached_value is not None:
            return cached_value

        if not isinstance(formula_value, str) or not formula_value.startswith("="):
            return formula_value

        stack.add(coordinate)
        expression = formula_value[1:].strip()

        def calculate_sum(match):
            start_cell = match.group(1)
            end_cell = match.group(2)

            min_col, min_row, max_col, max_row = range_boundaries(
                f"{start_cell}:{end_cell}"
            )

            total = 0
            for row in range(min_row, max_row + 1):
                for column in range(min_col, max_col + 1):
                    cell = formulas_sheet.cell(row=row, column=column)
                    value = calculate_cell(
                        values_sheet,
                        formulas_sheet,
                        cell.coordinate,
                        stack,
                    )

                    if isinstance(value, (int, float)):
                        total += value

            return str(total)

        expression = re.sub(
            r"SUM\(\s*\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)\s*\)",
            lambda match: calculate_sum(
                re.match(
                    r"([A-Z]+\d+):([A-Z]+\d+)",
                    f"{match.group(1)}{match.group(2)}:{match.group(3)}{match.group(4)}",
                )
            ),
            expression,
            flags=re.IGNORECASE,
        )

        def replace_cell_reference(match):
            column = match.group(1)
            row = match.group(2)
            referenced_cell = f"{column}{row}"

            value = calculate_cell(
                values_sheet,
                formulas_sheet,
                referenced_cell,
                stack,
            )

            return str(value) if isinstance(value, (int, float)) else "0"

        expression = re.sub(
            r"\$?([A-Z]{1,3})\$?(\d+)",
            replace_cell_reference,
            expression,
            flags=re.IGNORECASE,
        )

        stack.remove(coordinate)

        if not re.fullmatch(r"[0-9eE+\-*/().\s]+", expression):
            return formula_value

        try:
            return eval(expression, {"__builtins__": {}}, {})
        except (TypeError, ValueError, SyntaxError, ZeroDivisionError):
            return formula_value

    sections = []

    try:
        for values_sheet, formulas_sheet in zip(
            values_workbook.worksheets,
            formulas_workbook.worksheets,
        ):
            rows = []

            for value_row, formula_row in zip(
                values_sheet.iter_rows(),
                formulas_sheet.iter_rows(),
            ):
                cells = []

                for value_cell, formula_cell in zip(value_row, formula_row):
                    value = calculate_cell(
                        values_sheet,
                        formulas_sheet,
                        formula_cell.coordinate,
                    )

                    cells.append("" if value is None else str(value))

                if any(cell != "" for cell in cells):
                    rows.append(", ".join(cells))

            sections.append(
                f"[Sheet: {values_sheet.title}]\n" + "\n".join(rows)
            )

    finally:
        values_workbook.close()
        formulas_workbook.close()

    return "\n\n".join(sections)
