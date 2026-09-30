"""ReportLab PDF renderer for the 17-section assurance report.

Layout: navy/white cover page (title, experiment id, date), then one headed
block per section. Findings are rendered as a real table (no invented
values — the report dict is rendered as-is). Limitations and unsupported
tests are placed in visually distinct panels so reviewers cannot miss
what was NOT tested. No charts are rendered (no fake graphics).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

NAVY = colors.HexColor("#1B2A4A")
NAVY_LIGHT = colors.HexColor("#EAF0F8")
AMBER = colors.HexColor("#8A6D00")
AMBER_BG = colors.HexColor("#FFF8E1")
GREY = colors.HexColor("#5A5A5A")
WHITE = colors.white


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "section": ParagraphStyle(
            "section", parent=base["Heading2"], textColor=NAVY,
            fontSize=14, spaceBefore=14, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontSize=10, leading=14,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontSize=9, leading=12,
            textColor=GREY, spaceAfter=4,
        ),
        "mono": ParagraphStyle(
            "mono", parent=base["Normal"], fontName="Courier",
            fontSize=9, leading=12, spaceAfter=4,
        ),
        "panel": ParagraphStyle(
            "panel", parent=base["Normal"], fontSize=10, leading=14,
            spaceAfter=3, backColor=AMBER_BG,
        ),
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], textColor=WHITE,
            fontSize=34, leading=40, alignment=1, spaceAfter=12,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"], textColor=WHITE,
            fontSize=13, leading=18, alignment=1, spaceAfter=4,
        ),
        "cover_small": ParagraphStyle(
            "cover_small", parent=base["Normal"], textColor=WHITE,
            fontSize=10, leading=14, alignment=1,
        ),
    }


def _cover_canvas(canvas, doc):  # noqa: ANN001, ANN202
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 9)
    canvas.drawCentredString(A4[0] / 2, 30 * mm, "Prototype — SIH 2026 · Team SRIJAN")
    canvas.restoreState()


def _body_canvas(canvas, doc):  # noqa: ANN001, ANN202
    canvas.saveState()
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 15 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _para(text: str, style: ParagraphStyle) -> Paragraph:
    safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


def _panel(title: str, items: list[str], styles) -> list:
    flow = [_para(f"<b>{title}</b>", styles["section"])]
    rows = [[_para(f"•  {item}", styles["panel"])] for item in items]
    table = Table(rows, colWidths=[170 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), AMBER_BG),
                ("BOX", (0, 0), (-1, -1), 0.75, AMBER),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, AMBER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    flow.append(table)
    flow.append(Spacer(1, 8))
    return flow


def render_report_pdf(report: dict, out_path: str | Path) -> Path:
    """Render ``report`` (as produced by build_report) to a PDF file.

    Returns the output path. Raises ValueError if the report does not
    contain the 17 expected sections.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    missing = [k for k in (
        "executive_summary", "dataset_information", "model_information",
        "model_hash", "dataset_hash", "findings", "evidence",
        "severity_summary", "confidence_notes", "provenance_verification",
        "distribution_shift", "supported_attack_classes", "unsupported_tests",
        "limitations", "recommended_disposition", "audit_trail",
        "reproducibility",
    ) if k not in report]
    if missing:
        raise ValueError(f"report is missing sections: {missing}")

    styles = _styles()
    story: list = []

    # -- cover ---------------------------------------------------------
    exp_id = str(report.get("experiment_id", "Not evaluated yet"))
    story.append(Spacer(1, 70 * mm))
    story.append(_para("KavachAI", styles["cover_title"]))
    story.append(_para("AI-Assurance Prototype — Report", styles["cover_sub"]))
    story.append(Spacer(1, 10 * mm))
    story.append(_para(f"Experiment: <b>{exp_id}</b>", styles["cover_sub"]))
    story.append(
        _para(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}".strip(),
              styles["cover_small"])
    )
    story.append(Spacer(1, 8 * mm))
    story.append(
        _para(
            "Per-module assurance report. No single trust score is computed; "
            "verdicts are rule-based and every claim is backed by listed evidence.",
            styles["cover_small"],
        )
    )
    story.append(PageBreak())

    def _add_section(title: str, value: Any) -> None:
        story.append(_para(title, styles["section"]))
        if isinstance(value, str):
            story.append(_para(value, styles["body"]))
        elif isinstance(value, dict):
            for k, v in value.items():
                story.append(_para(f"<b>{k}</b>: {v}", styles["body"]))
        elif isinstance(value, list):
            if not value:
                story.append(_para("Not evaluated yet", styles["body"]))
            else:
                for item in value:
                    story.append(_para(f"•  {item}", styles["body"]))
        else:
            story.append(_para(str(value), styles["body"]))
        story.append(Spacer(1, 6))

    # -- executive summary ---------------------------------------------
    _add_section("1 · Executive summary", report["executive_summary"])

    # -- per-module status / disposition (no single score) --------------
    sev = report["severity_summary"]
    if isinstance(sev, dict):
        story.append(_para("Severity summary", styles["section"]))
        counts = sev.get("severity_counts", {})
        for k, v in counts.items():
            story.append(_para(f"<b>{k}</b>: {v}", styles["body"]))
        for rule in sev.get("rules_applied", []):
            story.append(_para(f"•  {rule}", styles["small"]))
        story.append(Spacer(1, 6))

    story.append(_para("Recommended disposition", styles["section"]))
    story.append(
        _para(f"<b>{report['recommended_disposition']}</b>", styles["body"])
    )
    story.append(Spacer(1, 6))

    # -- findings table --------------------------------------------------
    story.append(_para("Findings", styles["section"]))
    findings = report["findings"] if isinstance(report["findings"], list) else []
    if not findings:
        story.append(_para("Not evaluated yet", styles["body"]))
    else:
        header = ["ID", "Category", "Severity", "Confidence", "Disposition", "Method"]
        rows = [header]
        for f in findings:
            rows.append(
                [
                    _para(f.get("id", ""), styles["mono"]),
                    _para(str(f.get("category", "")), styles["small"]),
                    _para(str(f.get("severity", "")), styles["small"]),
                    _para(f"{float(f.get('confidence', 0.0)):.2f}", styles["small"]),
                    _para(str(f.get("disposition", "")), styles["small"]),
                    _para(str(f.get("detection_method", "")), styles["small"]),
                ]
            )
        rows[0] = [_para(f"<b>{h}</b>", styles["small"]) for h in header]
        widths = [18 * mm, 25 * mm, 24 * mm, 24 * mm, 32 * mm, 47 * mm]
        table = Table(rows, colWidths=widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), NAVY_LIGHT),
                    ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
                    ("GRID", (0, 0), (-1, -1), 0.5, GREY),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(table)
    story.append(Spacer(1, 8))

    # -- evidence ---------------------------------------------------------
    story.append(_para("Evidence per finding", styles["section"]))
    evidence = report["evidence"] if isinstance(report["evidence"], list) else []
    if not evidence:
        story.append(_para("Not evaluated yet", styles["body"]))
    else:
        for e in evidence:
            story.append(
                _para(
                    f"<b>{e.get('finding_id')}</b> "
                    f"({e.get('detection_method')}): {e.get('evidence')}",
                    styles["body"],
                )
            )
    story.append(Spacer(1, 6))

    story.append(_para("Confidence notes", styles["section"]))
    story.append(_para(str(report["confidence_notes"]), styles["body"]))
    story.append(Spacer(1, 6))

    # -- provenance / shift -------------------------------------------------
    story.append(_para("Provenance verification", styles["section"]))
    story.append(_para(str(report["provenance_verification"]), styles["body"]))
    story.append(Spacer(1, 6))

    story.append(_para("Distribution shift", styles["section"]))
    story.append(_para(str(report["distribution_shift"]), styles["body"]))
    story.append(Spacer(1, 6))

    # -- hashes / dataset / model --------------------------------------------
    _add_section("Dataset information", report["dataset_information"])
    _add_section("Model information", report["model_information"])
    story.append(_para("Hashes", styles["section"]))
    story.append(_para(f"Model hash: {report['model_hash']}", styles["mono"]))
    story.append(_para(f"Dataset hash: {report['dataset_hash']}", styles["mono"]))
    story.append(Spacer(1, 6))

    story.append(_para("Supported attack classes", styles["section"]))
    _add_section("", report["supported_attack_classes"])

    # -- prominent "NOT tested" panels ----------------------------------------
    story.extend(
        _panel(
            "⚠ Unsupported tests — what was NOT evaluated",
            list(report["unsupported_tests"]),
            styles,
        )
    )
    story.extend(
        _panel(
            "⚠ Limitations",
            list(report["limitations"]),
            styles,
        )
    )

    # -- audit trail / reproducibility -----------------------------------------
    _add_section("Audit trail", report["audit_trail"])
    _add_section("Reproducibility", report["reproducibility"])

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        title=f"KavachAI Assurance Report — {exp_id}",
        author="KavachAI prototype (Team SRIJAN)",
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    doc.build(
        story,
        onFirstPage=_cover_canvas,
        onLaterPages=_body_canvas,
    )
    return out_path
