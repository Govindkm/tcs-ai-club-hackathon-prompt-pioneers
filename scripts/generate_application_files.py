"""Generate realistic submission files from `data/synthetic_dataset.json`.

Every source document becomes a real file whose format matches how such
evidence would arrive in practice (PDF forms, DOCX plans, PPTX decks, scanned
certificate/consent images, screenshot proofs), plus a generated schematic
diagram per application. Document `quality` drives rendering: `good`/`fair`
documents keep a machine-readable text layer, while `poor`/`low` documents are
rendered as degraded scans so the OCR and quality-risk paths are exercised.

All content is derived from the JSON source - no new facts are invented.

    python scripts/generate_application_files.py
"""
from __future__ import annotations

import argparse
import io
import json
import random
import re
import shutil
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = REPO_ROOT / "data" / "synthetic_dataset.json"
OUTPUT_ROOT = REPO_ROOT / "data" / "applications"

PAGE_W, PAGE_H = 595.0, 842.0  # A4 points
MARGIN = 56.0

DOCUMENT_TITLES = {
    "application_form": "Application Form",
    "project_proposal": "Project Proposal",
    "restoration_plan": "Restoration Plan",
    "technical_concept": "Technical Concept Note",
    "itemised_budget": "Itemised Budget",
    "registration_certificate": "Registration Certificate",
    "site_ownership_or_consent": "Site Ownership and Consent Letter",
    "land_access_consent": "Land Access Consent",
    "match_funding_proof": "Match Funding Proof",
    "recent_audited_financials": "Audited Financial Statements",
    "baseline_site_report": "Baseline Site Report",
    "water_risk_baseline": "Water Risk Baseline",
    "safeguard_and_grievance_plan": "Safeguard and Grievance Plan",
    "permissions_or_no_objection": "Permissions and No-Objection Evidence",
    "monitoring_plan": "Monitoring Plan",
}

# Default carrier format per document type; "image:<style>" selects a rendered scan.
FORMAT_BY_TYPE = {
    "application_form": "pdf",
    "project_proposal": "docx",
    "restoration_plan": "docx",
    "technical_concept": "pptx",
    "itemised_budget": "pdf",
    "registration_certificate": "image:certificate",
    "site_ownership_or_consent": "pdf",
    "land_access_consent": "pdf",
    "match_funding_proof": "image:screenshot",
    "recent_audited_financials": "pdf",
    "baseline_site_report": "docx",
    "water_risk_baseline": "docx",
    "safeguard_and_grievance_plan": "pptx",
    "permissions_or_no_objection": "pdf",
    "monitoring_plan": "pptx",
}

# Per-application overrides so each submission bundle mixes carriers realistically.
FORMAT_OVERRIDES = {
    "APP-SOLAR-001": {"D3": "docx", "D7": "pptx"},
    "APP-SOLAR-002": {"D2": "pptx"},
    "APP-SOLAR-003": {"D2": "pptx", "D3": "docx"},
    "APP-SOLAR-004": {"D5": "image:letter_photo"},
    "APP-FOREST-001": {"D6": "pptx"},
    "APP-FOREST-002": {"D3": "docx", "D5": "image:letter_photo"},
    "APP-FOREST-003": {"D2": "pptx", "D6": "image:scan"},
    "APP-FOREST-004": {"D5": "docx"},
    "APP-WATER-001": {"D3": "docx", "D6": "image:letter_photo"},
    "APP-WATER-002": {"D3": "docx"},
    "APP-WATER-003": {"D2": "docx", "D6": "image:scan"},
    "APP-WATER-004": {"D2": "docx", "D6": "pdf"},
}

IMAGE_EXTENSIONS = ("png", "jpg", "webp", "tiff", "bmp")
DIAGRAM_EXTENSIONS = {"SCHEME-SOLAR": "png", "SCHEME-FOREST": "jpg", "SCHEME-WATER": "webp"}

DEGRADATION = {
    "good": {"scale": 1.0, "blur": 0.0, "noise": 0, "rotate": 0.0, "contrast": 1.0, "jpeg": 92},
    "fair": {"scale": 0.85, "blur": 0.4, "noise": 6, "rotate": 0.35, "contrast": 0.96, "jpeg": 82},
    "poor": {"scale": 0.58, "blur": 1.1, "noise": 14, "rotate": 1.1, "contrast": 0.84, "jpeg": 62},
    "low": {"scale": 0.40, "blur": 1.8, "noise": 24, "rotate": 1.9, "contrast": 0.68, "jpeg": 40},
}
SCAN_QUALITIES = ("poor", "low")

# --------------------------------------------------------------------------- model


@dataclass
class DocumentModel:
    """Carrier-independent representation of one submitted document."""

    title: str
    subtitle: str
    fields: list[tuple[str, str]] = field(default_factory=list)
    sections: list[tuple[str, list[str]]] = field(default_factory=list)
    table: tuple[str, list[tuple[str, str]]] | None = None
    bullets: tuple[str, list[str]] | None = None
    footer: str = ""

    def flat_lines(self) -> list[tuple[str, str]]:
        """Flatten to (style, text) pairs for image and scan rendering."""
        lines: list[tuple[str, str]] = [("title", self.title), ("subtitle", self.subtitle), ("rule", "")]
        lines.extend(("kv", f"{key}: {value}") for key, value in self.fields)
        for heading, paragraphs in self.sections:
            lines.append(("heading", heading))
            lines.extend(("body", paragraph) for paragraph in paragraphs)
        if self.table:
            caption, rows = self.table
            lines.append(("heading", caption))
            lines.extend(("kv", f"{label} .... {amount}") for label, amount in rows)
        if self.bullets:
            caption, items = self.bullets
            lines.append(("heading", caption))
            lines.extend(("bullet", item) for item in items)
        if self.footer:
            lines.append(("rule", ""))
            lines.append(("body", self.footer))
        return lines


def _money(value: int) -> str:
    return f"INR {value:,}"


def _parse_amount_rows(text: str) -> list[tuple[str, str]]:
    """Pull `label amount` pairs out of a budget narrative."""
    rows: list[tuple[str, str]] = []
    for segment in re.split(r"[;.]\s*", text):
        match = re.match(r"^(?P<label>[A-Za-z][^\d]*?)\s*(?:INR\s*)?(?P<amount>\d[\d,]{2,})$", segment.strip())
        if match:
            label = match.group("label").strip(" ,-")
            rows.append((label[:1].upper() + label[1:], f"INR {match.group('amount')}"))
    return rows if len(rows) >= 2 else []


def build_model(application: dict, scheme: dict, document: dict) -> DocumentModel:
    applicant = application["applicant"]
    doc_type = document["type"]

    fields = [
        ("Application reference", application["application_id"]),
        ("Document reference", f"{application['application_id']}/{document['document_id']}"),
        ("Scheme", f"{scheme['name']} ({scheme['scheme_id']})"),
        ("Applicant", applicant["name"]),
        ("Applicant type", applicant["type"].replace("_", " ")),
        ("District", applicant["district"]),
        ("Requested grant", _money(applicant["requested_amount"])),
    ]
    if applicant.get("match_funding") is not None:
        fields.append(("Declared match funding", _money(applicant["match_funding"])))
    fields.append(("Document type", doc_type))
    fields.append(("Submitted evidence quality", document["quality"]))

    model = DocumentModel(
        title=DOCUMENT_TITLES.get(doc_type, doc_type.replace("_", " ").title()),
        subtitle=f"{applicant['name']} - {scheme['name']}",
        fields=fields,
        sections=[("Statement of record", [document["text"]])],
        footer=(
            "Synthetic benchmark document generated from data/synthetic_dataset.json. "
            "No real person, organisation, or certificate is represented."
        ),
    )

    if doc_type == "application_form":
        funding = scheme["funding"]
        rows = [
            ("Requested grant", _money(applicant["requested_amount"])),
            ("Scheme minimum", _money(funding["min_amount"])),
            ("Scheme maximum", _money(funding["max_amount"])),
        ]
        if funding.get("match_funding_required"):
            rows.append(("Match funding required", f"{funding.get('match_funding_percent', 0)} percent"))
            rows.append(("Match funding declared", _money(applicant.get("match_funding", 0))))
        model.table = ("Funding declaration", rows)
        model.bullets = ("Documents declared with this application", list(scheme["required_documents"]))
        model.sections.append(
            (
                "Applicant declaration",
                [
                    (
                        f"{applicant['name']} confirms that the information supplied in this application "
                        f"is complete and accurate to the best of its knowledge, and that the supporting "
                        f"evidence listed below accompanies this form."
                    ),
                ],
            )
        )
    elif doc_type == "itemised_budget":
        rows = _parse_amount_rows(document["text"])
        if rows:
            model.table = ("Cost breakdown as submitted", rows)
    elif doc_type == "registration_certificate":
        model.sections.append(
            (
                "Certificate particulars",
                [
                    (
                        f"Produced by {applicant['name']} as evidence of its status as a "
                        f"{applicant['type'].replace('_', ' ')} operating in {applicant['district']}."
                    ),
                ],
            )
        )
    elif doc_type in ("safeguard_and_grievance_plan", "monitoring_plan"):
        model.bullets = (
            "Assessment relevance",
            [criterion["criterion"].replace("_", " ") for criterion in scheme["scoring_rubric"]],
        )
    elif doc_type in ("site_ownership_or_consent", "land_access_consent", "permissions_or_no_objection"):
        model.sections.append(
            (
                "Basis of authority",
                [
                    (
                        f"Issued in respect of the proposed activity of {applicant['name']} in "
                        f"{applicant['district']} under {scheme['name']}."
                    ),
                ],
            )
        )
    elif doc_type == "match_funding_proof":
        model.sections.append(
            (
                "Balance summary",
                [f"Committed to {application['application_id']}: {_money(applicant.get('match_funding', 0))}"],
            )
        )

    return model


# --------------------------------------------------------------------------- PDF


class _PdfWriter:
    """Minimal flowing-text layout engine over PyMuPDF."""

    def __init__(self) -> None:
        self.doc = pymupdf.open()
        self._new_page()

    def _new_page(self) -> None:
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.y = MARGIN

    def _wrap(self, text: str, fontname: str, size: float, width: float) -> list[str]:
        lines: list[str] = []
        current = ""
        for word in text.split():
            trial = f"{current} {word}".strip()
            if pymupdf.get_text_length(trial, fontname=fontname, fontsize=size) <= width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    def text(self, text: str, size: float = 10.5, bold: bool = False, indent: float = 0.0, gap: float = 5.0) -> None:
        fontname = "hebo" if bold else "helv"
        for line in self._wrap(text, fontname, size, PAGE_W - 2 * MARGIN - indent):
            if self.y + size * 1.5 > PAGE_H - MARGIN:
                self._new_page()
            self.page.insert_text((MARGIN + indent, self.y + size), line, fontname=fontname, fontsize=size)
            self.y += size * 1.45
        self.y += gap

    def rule(self) -> None:
        if self.y + 12 > PAGE_H - MARGIN:
            self._new_page()
        self.page.draw_line((MARGIN, self.y), (PAGE_W - MARGIN, self.y), color=(0.45, 0.45, 0.45), width=0.7)
        self.y += 12

    def save(self, path: Path) -> None:
        self.doc.save(path, garbage=3, deflate=True)
        self.doc.close()


def write_pdf(model: DocumentModel, path: Path, quality: str, rng: random.Random) -> None:
    if quality in SCAN_QUALITIES:
        _write_scanned_pdf(model, path, quality, rng)
        return

    writer = _PdfWriter()
    writer.text(model.title, size=17, bold=True, gap=2)
    writer.text(model.subtitle, size=11, gap=6)
    writer.rule()
    for key, value in model.fields:
        writer.text(f"{key}: {value}", size=9.5, gap=1)
    writer.y += 8
    for heading, paragraphs in model.sections:
        writer.text(heading.upper(), size=10, bold=True, gap=3)
        for paragraph in paragraphs:
            writer.text(paragraph, size=10.5, gap=7)
    if model.table:
        caption, rows = model.table
        writer.text(caption.upper(), size=10, bold=True, gap=4)
        for label, amount in rows:
            writer.text(f"{label:<44}{amount}", size=10, indent=10, gap=1)
        writer.y += 8
    if model.bullets:
        caption, items = model.bullets
        writer.text(caption.upper(), size=10, bold=True, gap=4)
        for item in items:
            writer.text(f"- {item.replace('_', ' ')}", size=10, indent=10, gap=1)
        writer.y += 8
    writer.rule()
    writer.text(model.footer, size=8)
    writer.save(path)


def _write_scanned_pdf(model: DocumentModel, path: Path, quality: str, rng: random.Random) -> None:
    buffer = io.BytesIO()
    render_page_image(model, quality, rng, style="scan").save(buffer, format="PNG")
    doc = pymupdf.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    page.insert_image(pymupdf.Rect(0, 0, PAGE_W, PAGE_H), stream=buffer.getvalue())
    doc.save(path, garbage=3, deflate=True)
    doc.close()


# --------------------------------------------------------------------------- DOCX


def write_docx(model: DocumentModel, path: Path, quality: str, rng: random.Random) -> None:
    import docx
    from docx.shared import Inches, Pt

    document = docx.Document()
    document.add_heading(model.title, level=0)
    document.add_paragraph(model.subtitle)

    if quality in SCAN_QUALITIES:
        document.add_paragraph(
            f"Scanned attachment for {model.fields[1][1]}. The page below was submitted as an image; "
            f"the recorded evidence quality is '{quality}'."
        )
        buffer = io.BytesIO()
        render_page_image(model, quality, rng, style="scan").save(buffer, format="PNG")
        buffer.seek(0)
        document.add_picture(buffer, width=Inches(6.2))
        document.save(path)
        return

    info = document.add_table(rows=0, cols=2)
    info.style = "Table Grid"
    for key, value in model.fields:
        cells = info.add_row().cells
        cells[0].text = key
        cells[1].text = value

    for heading, paragraphs in model.sections:
        document.add_heading(heading, level=1)
        for paragraph in paragraphs:
            document.add_paragraph(paragraph)

    if model.table:
        caption, rows = model.table
        document.add_heading(caption, level=1)
        table = document.add_table(rows=1, cols=2)
        table.style = "Table Grid"
        header = table.rows[0].cells
        header[0].text = "Line item"
        header[1].text = "Amount"
        for label, amount in rows:
            cells = table.add_row().cells
            cells[0].text = label
            cells[1].text = amount

    if model.bullets:
        caption, items = model.bullets
        document.add_heading(caption, level=1)
        for item in items:
            document.add_paragraph(item.replace("_", " "), style="List Bullet")

    document.add_paragraph().add_run(model.footer).font.size = Pt(8)
    document.save(path)


# --------------------------------------------------------------------------- PPTX


def write_pptx(model: DocumentModel, path: Path, quality: str, rng: random.Random) -> None:
    from pptx import Presentation
    from pptx.util import Inches, Pt

    presentation = Presentation()
    title_slide = presentation.slides.add_slide(presentation.slide_layouts[0])
    title_slide.shapes.title.text = model.title
    title_slide.placeholders[1].text = model.subtitle

    def bullet_slide(heading: str, items: list[str]) -> None:
        slide = presentation.slides.add_slide(presentation.slide_layouts[1])
        slide.shapes.title.text = heading
        frame = slide.placeholders[1].text_frame
        frame.word_wrap = True
        frame.text = items[0]
        for item in items[1:]:
            frame.add_paragraph().text = item
        for paragraph in frame.paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(15)

    bullet_slide("Submission details", [f"{key}: {value}" for key, value in model.fields])
    for heading, paragraphs in model.sections:
        bullet_slide(heading, paragraphs)
    if model.table:
        caption, rows = model.table
        bullet_slide(caption, [f"{label}: {amount}" for label, amount in rows])
    if model.bullets:
        caption, items = model.bullets
        bullet_slide(caption, [item.replace("_", " ") for item in items])

    if quality in SCAN_QUALITIES:
        slide = presentation.slides.add_slide(presentation.slide_layouts[5])
        slide.shapes.title.text = "Scanned annexure"
        buffer = io.BytesIO()
        render_page_image(model, quality, rng, style="scan").save(buffer, format="PNG")
        buffer.seek(0)
        slide.shapes.add_picture(buffer, Inches(2.6), Inches(1.6), height=Inches(5.2))

    bullet_slide("Notice", [model.footer])
    presentation.save(path)


# --------------------------------------------------------------------------- images


@cache
def _font(size: int, bold: bool = False):
    candidates = (
        ("arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf")
        if bold
        else ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf")
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _wrap_pil(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _degrade(image: Image.Image, quality: str, rng: random.Random) -> Image.Image:
    settings = DEGRADATION[quality]
    if settings["scale"] < 1.0:
        small = (max(1, int(image.width * settings["scale"])), max(1, int(image.height * settings["scale"])))
        image = image.resize(small, Image.BILINEAR).resize(image.size, Image.BILINEAR)
    if settings["blur"]:
        image = image.filter(ImageFilter.GaussianBlur(settings["blur"]))
    if settings["noise"]:
        level = settings["noise"]
        noise = Image.frombytes(
            "L", image.size, bytes(rng.randint(0, 255) for _ in range(image.width * image.height))
        )
        noise = noise.point(lambda value: int(128 + (value - 128) * level / 255))
        image = Image.blend(image, Image.merge("RGB", (noise, noise, noise)), 0.16)
    if settings["contrast"] != 1.0:
        image = ImageEnhance.Contrast(image).enhance(settings["contrast"])
    if settings["rotate"]:
        image = image.rotate(
            rng.uniform(-settings["rotate"], settings["rotate"]),
            resample=Image.BILINEAR,
            fillcolor=(226, 223, 214),
        )
    return image


def render_page_image(
    model: DocumentModel,
    quality: str,
    rng: random.Random,
    style: str = "scan",
    size: tuple[int, int] = (1240, 1754),
) -> Image.Image:
    """Render a document model as a paper-like page image."""
    image = Image.new("RGB", size, (247, 249, 252) if style == "screenshot" else (250, 249, 245))
    draw = ImageDraw.Draw(image)
    left, right = 90, size[0] - 90
    y = 90

    if style == "screenshot":
        draw.rectangle((0, 0, size[0], 96), fill=(33, 66, 122))
        draw.text((40, 32), "Banking Portal - Account Statement", font=_font(30, bold=True), fill=(255, 255, 255))
        y = 150
    elif style == "certificate":
        draw.rectangle((40, 40, size[0] - 40, size[1] - 40), outline=(90, 74, 40), width=8)
        draw.rectangle((62, 62, size[0] - 62, size[1] - 62), outline=(150, 128, 78), width=2)
        y = 140
    elif style == "letter_photo":
        draw.rectangle((0, 0, size[0], size[1]), fill=(206, 201, 188))
        draw.rectangle((70, 110, size[0] - 55, size[1] - 130), fill=(248, 246, 240))
        left, right = 130, size[0] - 120
        y = 170

    for kind, text in model.flat_lines():
        if y > size[1] - 200:
            break
        if kind == "rule":
            draw.line((left, y, right, y), fill=(140, 140, 140), width=2)
            y += 26
            continue
        if kind == "title":
            font = _font(46, bold=True)
            if style == "certificate":
                heading = text.upper()
                draw.text(
                    ((size[0] - draw.textlength(heading, font=font)) / 2, y),
                    heading,
                    font=font,
                    fill=(40, 34, 22),
                )
                y += 78
                continue
        elif kind == "subtitle":
            font = _font(26)
        elif kind == "heading":
            font = _font(24, bold=True)
            text = text.upper()
            y += 12
        elif kind == "bullet":
            font = _font(22)
            text = f"- {text.replace('_', ' ')}"
        elif kind == "kv":
            font = _font(22)
        else:
            font = _font(23)
        for line in _wrap_pil(draw, text, font, right - left):
            draw.text((left, y), line, font=font, fill=(28, 28, 32))
            y += int(font.size * 1.5)
        y += 10

    if style == "certificate":
        centre = (size[0] - 230, size[1] - 230)
        draw.ellipse(
            (centre[0] - 100, centre[1] - 100, centre[0] + 100, centre[1] + 100), outline=(120, 40, 40), width=5
        )
        draw.text((centre[0] - 78, centre[1] - 18), "SYNTHETIC", font=_font(24, bold=True), fill=(120, 40, 40))
        draw.text((centre[0] - 68, centre[1] + 14), "REGISTRY", font=_font(24, bold=True), fill=(120, 40, 40))
    elif style == "screenshot":
        draw.rectangle((60, size[1] - 150, size[0] - 60, size[1] - 60), outline=(180, 190, 205), width=2)
        draw.text(
            (80, size[1] - 128),
            "Captured from screen - not a certified statement.",
            font=_font(22),
            fill=(90, 100, 115),
        )

    return _degrade(image, quality, rng)


def save_image(image: Image.Image, path: Path, quality: str) -> None:
    extension = path.suffix.lower().lstrip(".")
    if extension in ("jpg", "jpeg"):
        image.save(path, format="JPEG", quality=DEGRADATION[quality]["jpeg"], subsampling=2)
    elif extension == "webp":
        image.save(path, format="WEBP", quality=DEGRADATION[quality]["jpeg"])
    elif extension == "tiff":
        image.save(path, format="TIFF", compression="tiff_lzw")
    elif extension == "bmp":
        image.save(path, format="BMP")
    else:
        image.save(path, format="PNG")


def write_image(model: DocumentModel, path: Path, style: str, quality: str, rng: random.Random) -> None:
    save_image(render_page_image(model, quality, rng, style=style), path, quality)


# --------------------------------------------------------------------------- diagrams


def _find(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _diagram_spec(application: dict, scheme: dict) -> tuple[str, list[str], list[str]]:
    """Build (title, flow nodes, legend lines) from the application's own document text."""
    applicant = application["applicant"]
    corpus = " ".join(document["text"] for document in application["documents"])
    legend = [
        f"Application: {application['application_id']}",
        f"Applicant: {applicant['name']} ({applicant['district']})",
        f"Requested grant: {_money(applicant['requested_amount'])}",
    ]
    if applicant.get("match_funding"):
        legend.append(f"Declared match funding: {_money(applicant['match_funding'])}")

    if scheme["scheme_id"] == "SCHEME-SOLAR":
        kw = _find(r"(\d[\d,]*)\s*kW\b", corpus)
        kwh = _find(r"(\d[\d,]*)\s*kWh", corpus)
        homes = _find(r"([\d,]+)\s*(?:households|homes)", corpus)
        title = "Microgrid single-line schematic"
        nodes = [
            f"Solar PV array{f' - {kw} kW' if kw else ''}",
            "Inverter and controller",
            f"Battery storage{f' - {kwh} kWh' if kwh else ''}",
            "Distribution and metering",
            f"Community loads{f' - {homes} households' if homes else ''}",
        ]
    elif scheme["scheme_id"] == "SCHEME-FOREST":
        hectares = _find(r"([\d,]+)\s*hectares", corpus)
        seedlings = _find(r"([\d,]+)\s*seedlings", corpus)
        title = "Restoration site and activity layout"
        nodes = [
            f"Restoration blocks{f' - {hectares} hectares' if hectares else ''}",
            "Community nursery",
            f"Native planting{f' - {seedlings} seedlings' if seedlings else ''}",
            "Maintenance and protection",
            "Survival and canopy monitoring",
        ]
    else:
        dams = _find(r"(\d+)\s*check dams", corpus)
        structures = _find(r"(\d+)\s*recharge structures", corpus)
        area = _find(r"([\d,]+)\s*hectares", corpus)
        title = "Watershed intervention schematic"
        nodes = [
            f"Catchment area{f' - {area} hectares' if area else ''}",
            f"Check dams{f' - {dams}' if dams else ''}",
            f"Recharge structures{f' - {structures}' if structures else ''}",
            "Storage and distribution",
            "Monitoring and reporting",
        ]

    return title, nodes, legend


def write_diagram(application: dict, scheme: dict, path: Path) -> None:
    title, nodes, legend = _diagram_spec(application, scheme)
    width = 1100
    height = 300 + len(nodes) * 150 + len(legend) * 34
    image = Image.new("RGB", (width, height), (252, 252, 250))
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, width, 96), fill=(23, 74, 88))
    draw.text((40, 18), title, font=_font(34, bold=True), fill=(255, 255, 255))
    draw.text((42, 62), f"{scheme['name']} - {application['application_id']}", font=_font(20), fill=(198, 224, 230))

    y = 140
    node_font = _font(24, bold=True)
    for index, node in enumerate(nodes):
        draw.rounded_rectangle(
            (140, y, width - 140, y + 96), radius=16, fill=(233, 242, 244), outline=(23, 74, 88), width=3
        )
        draw.text(((width - draw.textlength(node, font=node_font)) / 2, y + 32), node, font=node_font, fill=(18, 46, 56))
        if index < len(nodes) - 1:
            draw.line((width / 2, y + 96, width / 2, y + 138), fill=(23, 74, 88), width=4)
            draw.polygon(
                [(width / 2 - 12, y + 132), (width / 2 + 12, y + 132), (width / 2, y + 148)], fill=(23, 74, 88)
            )
        y += 150

    y += 20
    draw.line((140, y, width - 140, y), fill=(150, 160, 165), width=2)
    y += 18
    for line in legend:
        draw.text((140, y), line, font=_font(21), fill=(60, 66, 70))
        y += 34

    save_image(image, path, "good")


# --------------------------------------------------------------------------- driver


def _resolve_format(application_id: str, document: dict) -> str:
    override = FORMAT_OVERRIDES.get(application_id, {}).get(document["document_id"])
    carrier = override or FORMAT_BY_TYPE.get(document["type"], "pdf")
    if (
        document["quality"] in SCAN_QUALITIES
        and carrier == "pdf"
        and document["type"] in ("site_ownership_or_consent", "land_access_consent")
    ):
        carrier = "image:letter_photo"
    return carrier


def _image_extension(application_id: str, document_id: str) -> str:
    seed = sum(ord(character) for character in f"{application_id}{document_id}")
    return IMAGE_EXTENSIONS[seed % len(IMAGE_EXTENSIONS)]


def generate(dataset: dict, output_root: Path, clean: bool) -> list[Path]:
    schemes = {scheme["scheme_id"]: scheme for scheme in dataset["schemes"]}
    if clean and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for application in dataset["applications"]:
        scheme = schemes[application["scheme_id"]]
        directory = output_root / application["application_id"]
        directory.mkdir(parents=True, exist_ok=True)

        for document in application["documents"]:
            rng = random.Random(f"{application['application_id']}:{document['document_id']}")
            model = build_model(application, scheme, document)
            carrier = _resolve_format(application["application_id"], document)
            stem = f"{document['document_id']}_{document['type']}"

            if carrier.startswith("image:"):
                extension = _image_extension(application["application_id"], document["document_id"])
                path = directory / f"{stem}.{extension}"
                write_image(model, path, carrier.split(":", 1)[1], document["quality"], rng)
            elif carrier == "docx":
                path = directory / f"{stem}.docx"
                write_docx(model, path, document["quality"], rng)
            elif carrier == "pptx":
                path = directory / f"{stem}.pptx"
                write_pptx(model, path, document["quality"], rng)
            else:
                path = directory / f"{stem}.pdf"
                write_pdf(model, path, document["quality"], rng)
            written.append(path)

        diagram_path = directory / f"D0_site_diagram.{DIAGRAM_EXTENSIONS[scheme['scheme_id']]}"
        write_diagram(application, scheme, diagram_path)
        written.append(diagram_path)

        labels_path = directory / "BENCHMARK_LABELS.txt"
        labels_path.write_text(
            "EVALUATION METADATA ONLY - do not upload as an application document\n"
            "and do not use as runtime analysis input.\n\n"
            + json.dumps(application["benchmark_labels"], indent=2),
            encoding="utf-8",
        )
        written.append(labels_path)

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic application submission files.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--keep-existing", action="store_true", help="do not delete the output directory first")
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    written = generate(dataset, args.output, clean=not args.keep_existing)
    print(f"Wrote {len(written)} files under {args.output}")


if __name__ == "__main__":
    main()
