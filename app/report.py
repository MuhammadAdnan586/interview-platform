"""
report.py
----------
Generates the final "Readiness Report" PDF for a completed interview
attempt: an overall score, a horizontal bar breakdown by category, and
the full question-by-question transcript with sub-scores.

Built with reportlab Platypus (not raw canvas) — this gives clean
multi-page flow without manually tracking y-coordinates. The bar chart
uses reportlab's own graphics module, so no extra charting dependency
(matplotlib) is required just to render one simple chart.
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import HorizontalBarChart

ACCENT = colors.HexColor("#D9A441")
TEAL = colors.HexColor("#2E7D74")
DARK = colors.HexColor("#1B232C")
GREY = colors.HexColor("#5A6573")


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", fontSize=22, leading=26, textColor=DARK,
        fontName="Helvetica-Bold", spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="Eyebrow", fontSize=10, textColor=TEAL, fontName="Helvetica-Bold",
        spaceAfter=14,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading", fontSize=14, textColor=DARK, fontName="Helvetica-Bold",
        spaceBefore=18, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="QuestionText", fontSize=11, textColor=DARK, fontName="Helvetica-Bold",
        spaceBefore=10, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="AnswerText", fontSize=10, textColor=colors.HexColor("#333333"),
        fontName="Helvetica", spaceAfter=4, leftIndent=12,
    ))
    styles.add(ParagraphStyle(
        name="ScoreNote", fontSize=9, textColor=GREY, fontName="Helvetica-Oblique",
        leftIndent=12, spaceAfter=10,
    ))
    return styles


_LABEL_MAP = {
    "technical": "Technical",
    "communication": "Communication",
    "confidence": "Confidence",
    "body_language": "Body Language",
    "custom": "Custom Questions",
    "awareness": "Awareness",
}


def _breakdown_chart(score_breakdown: dict) -> Drawing:
    labels = [_LABEL_MAP.get(k, k.replace("_", " ").title()) for k in score_breakdown.keys()]
    values = [v if v is not None else 0 for v in score_breakdown.values()]

    drawing = Drawing(440, 30 * len(labels) + 20)
    chart = HorizontalBarChart()
    chart.x, chart.y = 110, 10
    chart.width, chart.height = 300, 22 * len(labels)
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 9
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 100
    chart.valueAxis.valueStep = 20
    chart.bars[0].fillColor = ACCENT
    chart.barWidth = 12
    drawing.add(chart)
    return drawing


def generate_report_pdf(attempt: dict, output_path: str) -> str:
    """
    attempt: {
      "candidate_name": str, "company_name": str | None,
      "overall_score": float, "score_breakdown": {category: score|None},
      "answers": [{"question": str, "type": str, "transcript": str,
                    "relevance_score": float|None, "clarity_score": float|None,
                    "confidence_score": float|None}],
      "created_at": str,
    }
    """
    styles = _build_styles()
    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )
    story = []

    # --- Header ---
    story.append(Paragraph("INTERVIEW READINESS REPORT", styles["Eyebrow"]))
    story.append(Paragraph(attempt["candidate_name"], styles["ReportTitle"]))
    meta_bits = []
    if attempt.get("company_name"):
        meta_bits.append(f"For: {attempt['company_name']}")
    meta_bits.append(f"Generated: {attempt.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M'))}")
    story.append(Paragraph("  |  ".join(meta_bits), ParagraphStyle(
        "meta", fontSize=9, textColor=GREY, spaceAfter=16)))

    # --- Overall score ---
    overall = attempt.get("overall_score")
    overall_str = f"{overall:.0f}%" if overall is not None else "N/A"
    story.append(Paragraph(f"Overall Readiness: <font color='#D9A441'>{overall_str}</font>",
                            ParagraphStyle("overall", fontSize=18, fontName="Helvetica-Bold",
                                           textColor=DARK, spaceAfter=4)))
    story.append(Paragraph(
        "This is a multi-dimensional readiness signal, not a hire/reject decision. "
        "The final call belongs to a human reviewer.",
        ParagraphStyle("disclaimer", fontSize=9, textColor=GREY, spaceAfter=18)
    ))

    # --- Breakdown chart ---
    story.append(Paragraph("Score Breakdown", styles["SectionHeading"]))
    breakdown = {k: v for k, v in attempt.get("score_breakdown", {}).items()}
    if breakdown:
        story.append(_breakdown_chart(breakdown))
        not_assessed = [_LABEL_MAP.get(k, k) for k, v in breakdown.items() if v is None]
        if not_assessed:
            story.append(Paragraph(
                f"Not assessed (optional module not set up): {', '.join(not_assessed)}.",
                ParagraphStyle("notassessed", fontSize=8.5, textColor=GREY, spaceBefore=4)
            ))
    else:
        story.append(Paragraph("No breakdown available.", styles["AnswerText"]))

    story.append(PageBreak())

    # --- Question-by-question detail ---
    story.append(Paragraph("Question-by-Question Detail", styles["SectionHeading"]))
    for i, ans in enumerate(attempt.get("answers", []), start=1):
        story.append(Paragraph(f"{i}. {ans['question']}  <font color='#2E7D74'>[{ans.get('type','')}]</font>",
                                styles["QuestionText"]))
        transcript = ans.get("transcript") or "(no answer recorded)"
        story.append(Paragraph(transcript, styles["AnswerText"]))

        score_parts = []
        if ans.get("relevance_score") is not None:
            score_parts.append(f"Relevance: {ans['relevance_score']:.0f}%")
        if ans.get("clarity_score") is not None:
            score_parts.append(f"Clarity: {ans['clarity_score']:.0f}%")
        if ans.get("confidence_score") is not None:
            score_parts.append(f"Voice confidence: {ans['confidence_score']:.0f}%")
        if score_parts:
            story.append(Paragraph("  •  ".join(score_parts), styles["ScoreNote"]))

    doc.build(story)
    return output_path
