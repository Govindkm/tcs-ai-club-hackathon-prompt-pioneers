from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.dml import MSO_THEME_COLOR
from pptx.util import Inches, Pt


OUT = Path(__file__).resolve().parents[1] / "docs" / "prompt_pioneers_application_intelligence_platform.pptx"

# A restrained civic-tech palette: ink for trust, mint for progress, amber for review.
INK = RGBColor(18, 28, 35)
INK_2 = RGBColor(31, 45, 53)
PAPER = RGBColor(246, 244, 238)
WHITE = RGBColor(255, 255, 255)
MINT = RGBColor(93, 200, 166)
MINT_DARK = RGBColor(35, 130, 103)
CYAN = RGBColor(74, 177, 205)
AMBER = RGBColor(244, 178, 74)
CORAL = RGBColor(222, 106, 91)
MUTED = RGBColor(116, 132, 136)
LINE = RGBColor(207, 216, 211)

FONT = "Aptos"
DISPLAY = "Aptos Display"


def rgb(color):
    return color


def add_text(slide, text, x, y, w, h, size=16, color=INK, bold=False,
             font=FONT, align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP,
             margin=0.04, italic=False):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin)
    tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return box


def add_rich_text(slide, runs, x, y, w, h, size=16, color=INK, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.04)
    tf.margin_right = Inches(0.04)
    p = tf.paragraphs[0]
    p.alignment = align
    for text, run_color, bold in runs:
        run = p.add_run()
        run.text = text
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = run_color
    return box


def rect(slide, x, y, w, h, fill, line_color=None, radius=False):
    shape_type = MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE if radius else MSO_AUTO_SHAPE_TYPE.RECTANGLE
    shape = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line_color or fill
    if radius:
        shape.adjustments[0] = 0.08
    return shape


def line(slide, x1, y1, x2, y2, color=LINE, width=1.2, dash=None):
    connector = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    connector.line.color.rgb = color
    connector.line.width = Pt(width)
    if dash:
        connector.line.dash_style = dash
    return connector


def circle(slide, x, y, d, fill, line_color=None):
    shape = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line_color or fill
    return shape


def title(slide, kicker, heading, number, dark=False):
    color = PAPER if dark else INK
    muted = RGBColor(178, 195, 190) if dark else MUTED
    add_text(slide, kicker.upper(), 0.65, 0.38, 4.5, 0.25, 9, MINT if dark else MINT_DARK, True)
    add_text(slide, heading, 0.65, 0.72, 11.7, 0.72, 27, color, True, DISPLAY)
    add_text(slide, f"{number:02d}", 12.25, 0.43, 0.55, 0.32, 11, muted, True, FONT, PP_ALIGN.RIGHT)
    line(slide, 0.65, 1.62, 12.65, 1.62, RGBColor(71, 91, 94) if dark else LINE, 1)


def footer(slide, dark=False, label="PROMPT PIONEERS | APPLICATION INTELLIGENCE PLATFORM"):
    add_text(slide, label, 0.65, 7.12, 8.0, 0.18, 7.5, RGBColor(147, 167, 161) if dark else MUTED, True)
    add_text(slide, "DIRECTORATE OF ENVIRONMENT AND CLIMATE CHANGE", 8.0, 7.12, 4.65, 0.18, 7.5, RGBColor(147, 167, 161) if dark else MUTED, True, FONT, PP_ALIGN.RIGHT)


def bullet_list(slide, items, x, y, w, h, size=15, color=INK, gap=0.36, marker=MINT_DARK):
    for index, item in enumerate(items):
        yy = y + index * gap
        circle(slide, x, yy + 0.08, 0.12, marker)
        add_text(slide, item, x + 0.24, yy, w - 0.24, 0.28, size, color)


def metric(slide, value, label, x, y, w, accent=MINT):
    add_text(slide, value, x, y, w, 0.52, 28, accent, True, DISPLAY)
    add_text(slide, label.upper(), x, y + 0.58, w, 0.34, 9, MUTED, True)


def add_slide(prs, bg=PAPER):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    rect(slide, 0, 0, 13.333, 7.5, bg)
    return slide


def stage_card(slide, x, y, w, label, detail, accent, num):
    rect(slide, x, y, w, 1.12, WHITE, LINE, True)
    circle(slide, x + 0.18, y + 0.18, 0.34, accent)
    add_text(slide, str(num), x + 0.18, y + 0.18, 0.34, 0.34, 10, WHITE, True, FONT, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    add_text(slide, label, x + 0.64, y + 0.16, w - 0.8, 0.25, 13, INK, True)
    add_text(slide, detail, x + 0.64, y + 0.49, w - 0.8, 0.4, 10.5, MUTED)


def build_deck():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # 1. Cover
    slide = add_slide(prs, INK)
    rect(slide, 0, 0, 0.28, 7.5, MINT)
    add_text(slide, "PROMPT PIONEERS", 0.78, 0.7, 4.5, 0.3, 11, MINT, True)
    add_text(slide, "Application\nIntelligence\nPlatform", 0.78, 1.45, 7.0, 2.25, 42, PAPER, True, DISPLAY)
    add_text(slide, "A human-led evaluation system for environmental and climate scheme applications", 0.82, 4.15, 6.6, 0.62, 18, RGBColor(196, 215, 208))
    line(slide, 0.82, 5.2, 5.2, 5.2, MINT, 2)
    add_text(slide, "Directorate of Environment and Climate Change", 0.82, 5.46, 5.9, 0.3, 12, PAPER, True)
    add_text(slide, "POC presentation | Synthetic data only", 0.82, 5.86, 5.9, 0.28, 10, RGBColor(147, 167, 161))
    # abstract pipeline motif
    for i, (label, color) in enumerate([("INGEST", CYAN), ("VALIDATE", AMBER), ("REVIEW", MINT)]):
        xx = 8.4 + i * 1.36
        circle(slide, xx, 2.0, 0.78, color)
        add_text(slide, str(i + 1), xx, 2.16, 0.78, 0.3, 18, INK, True, DISPLAY, PP_ALIGN.CENTER)
        add_text(slide, label, xx - 0.28, 2.98, 1.34, 0.24, 8.5, PAPER, True, FONT, PP_ALIGN.CENTER)
        if i < 2:
            line(slide, xx + 0.78, 2.39, xx + 1.33, 2.39, RGBColor(101, 128, 127), 2)
    add_text(slide, "AI advises. Authorized reviewers decide.", 8.25, 4.2, 4.1, 0.5, 17, MINT, True, DISPLAY, PP_ALIGN.CENTER)
    footer(slide, True)

    # 2. Why this matters
    slide = add_slide(prs)
    title(slide, "The opportunity", "Make every application explainable before it reaches a decision", 2)
    add_text(slide, "Today, evidence is heterogeneous, review effort is uneven, and risk signals can hide in the gaps between documents.", 0.68, 1.95, 7.0, 0.52, 17, INK_2)
    rect(slide, 0.68, 2.82, 5.74, 3.3, INK, INK, True)
    add_text(slide, "REVIEW FRICTION", 1.03, 3.16, 2.5, 0.25, 10, AMBER, True)
    bullet_list(slide, ["Forms, proposals, certificates, budgets, images", "Missing or unusable evidence", "Conflicting claims across files", "Manual duplicate and authenticity checks", "Decisions that are hard to reconstruct later"], 1.03, 3.62, 4.8, 1.9, 14, PAPER, 0.43, AMBER)
    rect(slide, 6.84, 2.82, 5.8, 3.3, MINT, MINT, True)
    add_text(slide, "THE POC RESPONSE", 7.2, 3.16, 2.5, 0.25, 10, INK, True)
    bullet_list(slide, ["One pipeline from submission to reviewer queue", "Evidence-linked extraction and validation", "Configurable weighted scoring with uncertainty", "Audit events, feedback loops, and retryable stages", "Human-owned final decision with rationale"], 7.2, 3.62, 4.8, 1.9, 14, INK, 0.43, INK)
    footer(slide)

    # 3. End-to-end journey
    slide = add_slide(prs)
    title(slide, "One case, one trace", "From mixed documents to a defensible reviewer action", 3)
    add_text(slide, "The platform turns a submission bundle into structured evidence, signals, and a next-best human action.", 0.68, 1.92, 8.0, 0.38, 15, INK_2)
    xs = [0.72, 3.15, 5.58, 8.01, 10.44]
    cards = [("Submit", "Files, notes, pasted text", CYAN), ("Extract", "Text, fields, summary", MINT), ("Validate", "Completeness, conflicts, risk", AMBER), ("Score", "Weighted, explainable aid", CORAL), ("Review", "Route, override, decide", MINT_DARK)]
    for i, (label, detail, accent) in enumerate(cards):
        stage_card(slide, xs[i], 2.72, 2.1, label, detail, accent, i + 1)
        if i < 4:
            line(slide, xs[i] + 2.1, 3.28, xs[i] + 2.38, 3.28, MUTED, 1.5)
    rect(slide, 0.72, 4.55, 11.82, 1.25, WHITE, LINE, True)
    add_text(slide, "CASE OUTPUT", 1.04, 4.85, 1.35, 0.22, 9, MINT_DARK, True)
    add_rich_text(slide, [("Route: ", INK, True), ("manual verification", CORAL, True), ("  |  Score: ", INK, True), ("72 / 100", INK, True), ("  |  Flags: ", INK, True), ("unusable certificate + duplicate similarity", CORAL, False)], 2.33, 4.82, 9.6, 0.3, 15)
    add_text(slide, "Every output remains advisory until an authorized reviewer records a decision and rationale.", 1.04, 5.25, 10.8, 0.26, 11, MUTED, italic=True)
    footer(slide)

    # 4. Experience
    slide = add_slide(prs)
    title(slide, "Two connected experiences", "A replaceable portal for applicants and reviewers", 4)
    rect(slide, 0.72, 2.05, 5.72, 4.25, WHITE, LINE, True)
    add_text(slide, "APPLICANT PORTAL", 1.08, 2.4, 2.8, 0.24, 10, CYAN, True)
    add_text(slide, "Submit once. See what happens next.", 1.08, 2.78, 4.7, 0.45, 22, INK, True, DISPLAY)
    bullet_list(slide, ["Browse schemes and required documents", "Upload PDF, DOCX, PPTX, XLSX, images, or ZIP", "Track timeline and review status", "Respond to requests and ask for re-evaluation"], 1.08, 3.58, 4.6, 1.55, 13, INK_2, 0.42, CYAN)
    rect(slide, 1.08, 5.48, 3.25, 0.46, RGBColor(230, 246, 242), RGBColor(230, 246, 242), True)
    add_text(slide, "Status: Awaiting validation review", 1.28, 5.59, 2.9, 0.18, 10, MINT_DARK, True)
    rect(slide, 6.88, 2.05, 5.72, 4.25, INK, INK, True)
    add_text(slide, "REVIEWER WORKBENCH", 7.24, 2.4, 3.0, 0.24, 10, AMBER, True)
    add_text(slide, "See evidence, not just a score.", 7.24, 2.78, 4.7, 0.45, 22, PAPER, True, DISPLAY)
    bullet_list(slide, ["Queue, assignment, and stage-aware timeline", "Extracted fields, summary, and source files", "Missing evidence, contradictions, and risk flags", "Score breakdown, feedback, approvals, audit log"], 7.24, 3.58, 4.6, 1.55, 13, PAPER, 0.42, AMBER)
    rect(slide, 7.24, 5.48, 3.25, 0.46, RGBColor(63, 78, 80), RGBColor(63, 78, 80), True)
    add_text(slide, "Action: Request more information", 7.44, 5.59, 3.0, 0.18, 10, AMBER, True)
    footer(slide)

    # 5. Architecture
    slide = add_slide(prs, INK)
    title(slide, "On-premise-ready by design", "A modular API boundary keeps data, models, and decisions governable", 5, True)
    # layers
    rect(slide, 0.78, 2.05, 2.18, 3.55, RGBColor(42, 61, 66), RGBColor(72, 95, 97), True)
    add_text(slide, "USER LAYER", 1.08, 2.36, 1.5, 0.22, 9, CYAN, True)
    add_text(slide, "Browser", 1.08, 2.86, 1.5, 0.3, 16, PAPER, True)
    add_text(slide, "Streamlit portal\nApplicant + admin views", 1.08, 3.35, 1.55, 0.7, 12, RGBColor(190, 211, 205))
    rect(slide, 3.35, 2.05, 2.18, 3.55, RGBColor(42, 61, 66), RGBColor(72, 95, 97), True)
    add_text(slide, "TRUST BOUNDARY", 3.65, 2.36, 1.75, 0.22, 9, MINT, True)
    add_text(slide, "FastAPI", 3.65, 2.86, 1.5, 0.3, 16, PAPER, True)
    add_text(slide, "JWT auth\nRole + ownership guards\nREST / OpenAPI", 3.65, 3.35, 1.55, 1.0, 12, RGBColor(190, 211, 205))
    rect(slide, 5.92, 2.05, 3.15, 3.55, RGBColor(42, 61, 66), RGBColor(72, 95, 97), True)
    add_text(slide, "LOCAL PROCESSING", 6.23, 2.36, 2.1, 0.22, 9, AMBER, True)
    add_text(slide, "Pipeline", 6.23, 2.86, 1.5, 0.3, 16, PAPER, True)
    add_text(slide, "Ingestion + OCR\nAgents + tools\nChroma duplicate check\nSQLite / PostgreSQL", 6.23, 3.35, 2.25, 1.3, 12, RGBColor(190, 211, 205))
    rect(slide, 9.46, 2.05, 3.15, 3.55, RGBColor(42, 61, 66), RGBColor(72, 95, 97), True)
    add_text(slide, "CONTROLLED ADAPTERS", 9.78, 2.36, 2.4, 0.22, 9, CORAL, True)
    add_text(slide, "Providers", 9.78, 2.86, 1.5, 0.3, 16, PAPER, True)
    add_text(slide, "Ollama local default\nBedrock / Anthropic / OpenAI\nOptional organisation check\nMock portal integrations", 9.78, 3.35, 2.35, 1.3, 12, RGBColor(190, 211, 205))
    for x in [2.96, 5.53, 9.08]:
        line(slide, x, 3.83, x + 0.39, 3.83, MINT, 2)
    add_text(slide, "Raw files, extracted content, embeddings, events, and human decisions stay in durable, auditable stores.", 0.82, 6.18, 11.7, 0.3, 13, RGBColor(192, 212, 206), italic=True)
    footer(slide, True)

    # 6. Agent system
    slide = add_slide(prs)
    title(slide, "Bounded intelligence", "Agents are configured capabilities, not autonomous decision-makers", 6)
    add_text(slide, "Each stage has a narrow purpose, declared tools, structured output, and a durable event trail.", 0.68, 1.92, 8.5, 0.36, 15, INK_2)
    agent_data = [("Embedding", "Index bundles\nFind duplicates", CYAN), ("Extraction", "Fields +\nsummary", MINT), ("Validation", "Completeness\n+ risk", AMBER), ("Scoring", "Weighted\nexplanation", CORAL), ("Workflow", "Route +\naudit", MINT_DARK)]
    for i, (label, detail, accent) in enumerate(agent_data):
        x = 0.78 + i * 2.45
        circle(slide, x + 0.53, 2.72, 0.78, accent)
        add_text(slide, str(i + 1), x + 0.53, 2.92, 0.78, 0.22, 16, WHITE, True, DISPLAY, PP_ALIGN.CENTER)
        add_text(slide, label, x, 3.78, 1.85, 0.25, 14, INK, True, FONT, PP_ALIGN.CENTER)
        add_text(slide, detail, x, 4.2, 1.85, 0.55, 11, MUTED, False, FONT, PP_ALIGN.CENTER)
        if i < 4:
            line(slide, x + 1.85, 3.11, x + 2.32, 3.11, LINE, 1.5)
    rect(slide, 0.78, 5.28, 11.78, 0.78, RGBColor(231, 243, 239), RGBColor(231, 243, 239), True)
    add_text(slide, "Structured Pydantic results", 1.08, 5.53, 2.35, 0.22, 12, MINT_DARK, True)
    add_text(slide, "Extraction fields | validation flags | scoring explanation | review notes", 3.35, 5.53, 7.2, 0.22, 12, INK_2)
    add_text(slide, "Skills provide policy context; tools perform bounded domain operations; API authorization remains the control plane.", 1.08, 5.86, 10.5, 0.2, 10, MUTED, italic=True)
    footer(slide)

    # 7. Explainability
    slide = add_slide(prs)
    title(slide, "Evidence before arithmetic", "Validation and scoring expose uncertainty instead of hiding it", 7)
    rect(slide, 0.72, 2.0, 5.76, 4.48, INK, INK, True)
    add_text(slide, "VALIDATION SIGNALS", 1.08, 2.38, 2.6, 0.23, 10, AMBER, True)
    signals = [("Required documents", "8 / 10 usable", MINT), ("Material conflicts", "2 found", CORAL), ("Authenticity risk", "High", CORAL), ("Human review", "Required", AMBER)]
    for i, (label, value, accent) in enumerate(signals):
        yy = 2.92 + i * 0.72
        add_text(slide, label, 1.08, yy, 2.2, 0.22, 12, RGBColor(194, 211, 205))
        add_text(slide, value, 3.68, yy, 1.95, 0.22, 13, accent, True, FONT, PP_ALIGN.RIGHT)
        line(slide, 1.08, yy + 0.36, 5.98, yy + 0.36, RGBColor(64, 83, 86), 0.7)
    rect(slide, 6.86, 2.0, 5.76, 4.48, WHITE, LINE, True)
    add_text(slide, "ADVISORY SCORE", 7.22, 2.38, 2.6, 0.23, 10, CORAL, True)
    add_text(slide, "72", 7.22, 2.8, 1.4, 0.68, 42, INK, True, DISPLAY)
    add_text(slide, "/ 100", 8.5, 3.16, 1.2, 0.25, 15, MUTED, True)
    score_rows = [("Impact", "28 / 35", 0.80, MINT), ("Feasibility", "22 / 30", 0.64, CYAN), ("Value for money", "14 / 20", 0.70, AMBER), ("Readiness", "8 / 15", 0.53, CORAL)]
    for i, (label, value, pct, accent) in enumerate(score_rows):
        yy = 4.02 + i * 0.48
        add_text(slide, label, 7.22, yy, 1.52, 0.2, 11, INK_2)
        rect(slide, 8.83, yy + 0.02, 2.25, 0.15, RGBColor(231, 235, 231), RGBColor(231, 235, 231), True)
        rect(slide, 8.83, yy + 0.02, 2.25 * pct, 0.15, accent, accent, True)
        add_text(slide, value, 11.3, yy - 0.02, 0.82, 0.2, 10, INK, True, FONT, PP_ALIGN.RIGHT)
    add_text(slide, "Score is not a final decision. Flags and source evidence travel with it.", 7.22, 5.98, 4.7, 0.25, 11, MUTED, italic=True)
    footer(slide)

    # 8. Human workflow
    slide = add_slide(prs, INK)
    title(slide, "Human control is a product feature", "The workflow makes intervention, override, and accountability explicit", 8, True)
    steps = [("1", "Assign", "An admin claims the case", CYAN), ("2", "Review", "Assigned admin validates evidence", AMBER), ("3", "Approve score", "Two distinct admins approve", MINT), ("4", "Decide", "Authorized human records rationale", CORAL)]
    for i, (num, label, detail, accent) in enumerate(steps):
        x = 0.83 + i * 3.05
        circle(slide, x, 2.36, 0.56, accent)
        add_text(slide, num, x, 2.5, 0.56, 0.18, 13, INK, True, DISPLAY, PP_ALIGN.CENTER)
        add_text(slide, label, x, 3.18, 2.45, 0.28, 18, PAPER, True, DISPLAY)
        add_text(slide, detail, x, 3.62, 2.35, 0.45, 12, RGBColor(183, 205, 198))
        if i < 3:
            line(slide, x + 1.7, 2.64, x + 2.68, 2.64, RGBColor(91, 119, 117), 2)
    rect(slide, 0.83, 5.05, 11.55, 0.95, RGBColor(42, 61, 66), RGBColor(72, 95, 97), True)
    add_text(slide, "GUARDRAIL", 1.15, 5.35, 1.2, 0.22, 9, MINT, True)
    add_text(slide, "No agent or score endpoint can persist approved or rejected without an authorized human review record.", 2.5, 5.31, 9.2, 0.28, 14, PAPER, True)
    add_text(slide, "Feedback can restart validation or rescore the case; approvals are cleared when the underlying analysis changes.", 1.15, 6.18, 10.5, 0.22, 11, RGBColor(183, 205, 198), italic=True)
    footer(slide, True)

    # 9. Dataset
    slide = add_slide(prs)
    title(slide, "Built to be challenged", "A synthetic benchmark exercises the failure modes that matter", 9)
    metric(slide, "3", "schemes", 0.78, 2.0, 1.5, CYAN)
    metric(slide, "12", "applications", 2.48, 2.0, 2.0, MINT)
    metric(slide, "7", "case types", 4.72, 2.0, 1.8, AMBER)
    metric(slide, "0", "AI-only final decisions", 6.72, 2.0, 2.8, CORAL)
    rect(slide, 0.78, 3.05, 11.82, 2.75, WHITE, LINE, True)
    case_rows = [("Complete", "Proceed to scoring", MINT), ("Incomplete", "Request more information", AMBER), ("Contradictory", "Clarify before scoring", CORAL), ("Low-quality / suspicious", "Manual verification", CORAL), ("Duplicate", "Duplicate review", CYAN), ("Borderline", "Conditional human review", AMBER)]
    for i, (case, action, accent) in enumerate(case_rows):
        col = 0 if i < 3 else 1
        row = i if i < 3 else i - 3
        x = 1.15 + col * 5.7
        y = 3.46 + row * 0.65
        circle(slide, x, y + 0.04, 0.13, accent)
        add_text(slide, case, x + 0.27, y, 1.95, 0.22, 12, INK, True)
        add_text(slide, action, x + 2.22, y, 2.9, 0.22, 11, MUTED)
    add_text(slide, "Acceptance targets include 100% required-document classification, contradiction recall, duplicate recall, and zero AI-only final decisions.", 0.82, 6.18, 11.5, 0.3, 13, INK_2, True)
    footer(slide)

    # 10. Sovereignty
    slide = add_slide(prs, INK)
    title(slide, "Restricted means local", "The target operating model protects sensitive evidence at the boundary", 10, True)
    rect(slide, 0.8, 2.0, 5.55, 3.95, RGBColor(42, 61, 66), RGBColor(72, 95, 97), True)
    add_text(slide, "RESTRICTED ZONE", 1.15, 2.38, 2.0, 0.22, 10, MINT, True)
    bullet_list(slide, ["Synthetic government/citizen records", "Raw uploads and extracted text", "Embeddings and duplicate checks", "Analysis events and reviewer decisions", "Local Ollama or approved on-prem model"], 1.15, 2.92, 4.5, 2.0, 14, PAPER, 0.46, MINT)
    rect(slide, 6.8, 2.0, 5.75, 3.95, RGBColor(42, 61, 66), RGBColor(72, 95, 97), True)
    add_text(slide, "CONTROLLED EGRESS", 7.15, 2.38, 2.2, 0.22, 10, AMBER, True)
    bullet_list(slide, ["Provider abstraction selects the model", "Cloud use limited to approved non-sensitive data", "Optional organisation check sends name only", "Portal and identity services represented by adapters", "CORS and secrets require hardening before production"], 7.15, 2.92, 4.65, 2.0, 14, PAPER, 0.46, AMBER)
    add_text(slide, "The architecture can move from POC defaults to an isolated deployment without changing the reviewer workflow.", 0.85, 6.3, 11.6, 0.26, 13, RGBColor(192, 212, 206), italic=True)
    footer(slide, True)

    # 11. Demo
    slide = add_slide(prs)
    title(slide, "Reviewer demo", "A five-minute path through the working POC", 11)
    demo = [("01", "Log in", "Applicant and admin roles are enforced server-side."), ("02", "Submit", "Choose a scheme and upload a mixed document bundle."), ("03", "Inspect", "Watch ingestion, extraction, validation, and duplicate checks."), ("04", "Intervene", "Give validation or scoring feedback; see the case resume."), ("05", "Decide", "Approve the score, then record a rationale-backed decision.")]
    for i, (num, label, detail) in enumerate(demo):
        y = 2.0 + i * 0.82
        rect(slide, 0.78, y, 0.7, 0.48, INK, INK, True)
        add_text(slide, num, 0.78, y + 0.13, 0.7, 0.18, 11, MINT, True, FONT, PP_ALIGN.CENTER)
        add_text(slide, label, 1.82, y + 0.06, 1.6, 0.25, 16, INK, True, DISPLAY)
        add_text(slide, detail, 3.55, y + 0.08, 7.8, 0.26, 13, INK_2)
        line(slide, 1.48, y + 0.24, 1.72, y + 0.24, LINE, 1.4)
    rect(slide, 0.78, 6.25, 11.75, 0.42, RGBColor(231, 243, 239), RGBColor(231, 243, 239), True)
    add_text(slide, "Demo data: data/applications/ | Local run: scripts/run_dev.ps1 | API docs: /docs", 1.08, 6.36, 10.8, 0.18, 10.5, MINT_DARK, True)
    footer(slide)

    # 12. Close
    slide = add_slide(prs, MINT)
    add_text(slide, "THE PROMISE", 0.82, 0.78, 2.0, 0.25, 10, INK, True)
    add_text(slide, "Faster review.\nStronger evidence.\nHuman accountability.", 0.82, 1.48, 7.4, 1.95, 36, INK, True, DISPLAY)
    add_text(slide, "Prompt Pioneers turns application intelligence into a transparent, traceable service for the people who still own the decision.", 0.86, 4.18, 6.8, 0.62, 17, INK_2)
    rect(slide, 8.5, 1.55, 3.3, 3.3, INK, INK, True)
    add_text(slide, "READY FOR", 8.9, 1.98, 2.4, 0.22, 10, AMBER, True, FONT, PP_ALIGN.CENTER)
    add_text(slide, "the next\nreview", 8.9, 2.52, 2.4, 1.0, 29, PAPER, True, DISPLAY, PP_ALIGN.CENTER)
    line(slide, 9.2, 4.05, 11.1, 4.05, MINT, 2)
    add_text(slide, "Synthetic POC\nOn-premise-ready architecture\nHuman-led decisions", 8.9, 4.28, 2.4, 0.75, 11, RGBColor(190, 211, 205), False, FONT, PP_ALIGN.CENTER)
    add_text(slide, "PROMPT PIONEERS | DIRECTORATE OF ENVIRONMENT AND CLIMATE CHANGE", 0.82, 7.08, 8.8, 0.18, 8, INK_2, True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"Created {OUT}")


if __name__ == "__main__":
    build_deck()
