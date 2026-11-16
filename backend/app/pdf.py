from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

FONT_DIR = Path(reportlab.__file__).resolve().parent / "fonts"
BODY_FONT = "Helvetica"
BOLD_FONT = "Helvetica-Bold"


def _register_fonts() -> tuple[str, str]:
    global BODY_FONT, BOLD_FONT
    if BODY_FONT != "Helvetica":
        return BODY_FONT, BOLD_FONT
    regular = FONT_DIR / "Vera.ttf"
    bold = FONT_DIR / "VeraBd.ttf"
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("GAVera", str(regular)))
        pdfmetrics.registerFont(TTFont("GAVera-Bold", str(bold)))
        BODY_FONT = "GAVera"
        BOLD_FONT = "GAVera-Bold"
    return BODY_FONT, BOLD_FONT


def build_pdf(text: str, title: str = "Grammar Assistant") -> bytes:
    body_font, bold_font = _register_fonts()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        title=title,
        author="Grammar Assistant",
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
    )

    title_style = ParagraphStyle(
        "GATitle",
        fontName=bold_font,
        fontSize=19,
        leading=24,
        textColor=colors.HexColor("#17594a"),
        spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        "GAMeta",
        fontName=body_font,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#6b7280"),
        spaceAfter=14,
    )
    body_style = ParagraphStyle(
        "GABody",
        fontName=body_font,
        fontSize=10.5,
        leading=16,
        textColor=colors.HexColor("#1a1d23"),
        spaceAfter=8,
    )

    created = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    story = [
        Paragraph(escape(title), title_style),
        Paragraph(f"Exported from Grammar Assistant - {created}", meta_style),
    ]

    paragraphs = text.replace("\r\n", "\n").replace("\r", "\n").split("\n\n")
    if not any(paragraph.strip() for paragraph in paragraphs):
        paragraphs = [text]
    for paragraph in paragraphs:
        cleaned = paragraph.strip("\n")
        if not cleaned.strip():
            story.append(Spacer(1, 6))
            continue
        story.append(Paragraph(escape(cleaned).replace("\n", "<br/>"), body_style))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(body_font, 8)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawString(doc.leftMargin, 0.45 * inch, "Grammar Assistant")
        canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.45 * inch, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
