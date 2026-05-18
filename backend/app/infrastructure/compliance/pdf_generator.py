"""PDF report generator using reportlab."""

from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_pdf(report_data: dict, regulation: str) -> bytes:
    """Generate formatted PDF from compliance report data."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=20, spaceAfter=20)
    elements.append(Paragraph(f"DataWrangler — {regulation} Compliance Report", title_style))
    elements.append(Paragraph(f"Generated: {report_data.get('generated_at', datetime.now().isoformat())}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    # Sections
    for section_key, section in report_data.get("sections", {}).items():
        if not isinstance(section, dict):
            continue

        # Section header
        elements.append(Paragraph(section.get("title", section_key), styles["Heading2"]))
        elements.append(Spacer(1, 8))

        # Description
        if "description" in section:
            elements.append(Paragraph(str(section["description"]), styles["Normal"]))
            elements.append(Spacer(1, 6))

        # Key-value pairs
        for key, value in section.items():
            if key in ("title", "description", "columns", "detail", "categories"):
                continue
            if isinstance(value, (str, int, float, bool)):
                elements.append(Paragraph(f"<b>{key.replace('_', ' ').title()}:</b> {value}", styles["Normal"]))

        # Column tables
        if "columns" in section and isinstance(section["columns"], list) and section["columns"]:
            cols = section["columns"][:50]  # Cap at 50 rows for PDF
            table_data = [["Table", "Column", "PII Type", "Confidence"]]
            for col in cols:
                table_data.append([
                    str(col.get("table", "")),
                    str(col.get("column", "")),
                    str(col.get("pii_type", "")),
                    f"{col.get('confidence', 0):.0%}",
                ])

            t = Table(table_data, colWidths=[1.5 * inch, 1.5 * inch, 1.2 * inch, 1 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B65A6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
            ]))
            elements.append(t)

        elements.append(Spacer(1, 15))

    # Summary
    summary = report_data.get("summary", {})
    if summary:
        elements.append(Paragraph("Summary", styles["Heading2"]))
        for k, v in summary.items():
            elements.append(Paragraph(f"<b>{k.replace('_', ' ').title()}:</b> {v}", styles["Normal"]))

    doc.build(elements)
    return buffer.getvalue()
