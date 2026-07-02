"""Render a FaithForge packet's markdown into downloadable Word/PDF bytes.

Shares the block grammar with packet_builder.markdown_to_html (headings,
bullet/numbered/checkbox lists, pipe tables, horizontal rules, paragraphs)
so exported files match what's shown on screen.
"""
import io
import re
from typing import List, Tuple

from packet_builder import _is_table_sep, _table_cells

NAVY_RGB = (0x1E, 0x3A, 0x8A)
COPPER_RGB = (0xC2, 0x65, 0x2A)


def _parse_blocks(markdown: str) -> List[Tuple]:
    lines = (markdown or "").split("\n")
    blocks: List[Tuple] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()

        if s.startswith("|") and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
            header = _table_cells(s)
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_table_cells(lines[i]))
                i += 1
            blocks.append(("table", header, rows))
            continue

        i += 1

        if re.match(r"^- \[[ x]\] ", s):
            blocks.append(("checkbox", s[3] == "x", s[6:]))
            continue
        if re.match(r"^[-*] ", s):
            blocks.append(("bullet", s[2:]))
            continue
        if re.match(r"^\d+\. ", s):
            blocks.append(("numbered", re.sub(r"^\d+\. ", "", s)))
            continue

        if s.startswith("#### "):
            blocks.append(("h4", s[5:]))
        elif s.startswith("### "):
            blocks.append(("h3", s[4:]))
        elif s.startswith("## "):
            blocks.append(("h2", s[3:]))
        elif s.startswith("# "):
            blocks.append(("h1", s[2:]))
        elif s == "---":
            blocks.append(("hr",))
        elif s.startswith("*") and s.endswith("*") and len(s) > 2 and not s.startswith("**"):
            blocks.append(("italic", s.strip("*")))
        elif s:
            blocks.append(("p", s))
        else:
            blocks.append(("blank",))
    return blocks


_INLINE_RE = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*")


def _split_inline(text: str) -> List[Tuple[str, bool, bool]]:
    """Split text into (segment, is_bold, is_italic) runs on **bold**/*italic* markers.

    Mirrors packet_builder._inline_md's precedence: bold (**) matches before
    single-star italic at each position.
    """
    runs = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            runs.append((text[pos:m.start()], False, False))
        if m.group(1) is not None:
            runs.append((m.group(1), True, False))
        else:
            runs.append((m.group(2), False, True))
        pos = m.end()
    if pos < len(text):
        runs.append((text[pos:], False, False))
    return runs or [("", False, False)]


def _strip_bold(text: str) -> str:
    """Strip ** and * markup, leaving plain text (used for table cells)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    return text


# ─── DOCX export ─────────────────────────────────────────────────────────────

def markdown_to_docx_bytes(markdown: str, title: str = "FaithForge Proposal") -> bytes:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor

    doc = Document()
    doc.core_properties.title = title
    for section in doc.sections:
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)

    navy = RGBColor(*NAVY_RGB)
    copper = RGBColor(*COPPER_RGB)

    def add_inline_runs(paragraph, text):
        for segment, bold, italic in _split_inline(text):
            if not segment:
                continue
            run = paragraph.add_run(segment)
            run.bold = bold
            run.italic = italic

    for block in _parse_blocks(markdown):
        kind = block[0]
        if kind == "h1":
            p = doc.add_paragraph()
            run = p.add_run(block[1])
            run.bold = True
            run.font.size = Pt(18)
            run.font.color.rgb = navy
        elif kind == "h2":
            p = doc.add_paragraph()
            run = p.add_run(block[1])
            run.bold = True
            run.font.size = Pt(13)
            run.font.color.rgb = navy
        elif kind == "h3":
            p = doc.add_paragraph()
            run = p.add_run(block[1])
            run.bold = True
            run.font.size = Pt(12)
            run.font.color.rgb = copper
        elif kind == "h4":
            p = doc.add_paragraph()
            run = p.add_run(block[1])
            run.bold = True
            run.italic = True
            run.font.size = Pt(11)
        elif kind == "hr":
            p = doc.add_paragraph("_" * 60)
            p.runs[0].font.color.rgb = copper
        elif kind == "table":
            header, rows = block[1], block[2]
            if not header:
                continue
            table = doc.add_table(rows=1, cols=len(header))
            try:
                table.style = "Light Grid Accent 1"
            except KeyError:
                pass
            for cell, text in zip(table.rows[0].cells, header):
                run = cell.paragraphs[0].add_run(_strip_bold(text))
                run.bold = True
            for row in rows:
                cells = table.add_row().cells
                for cell, text in zip(cells, row):
                    cell.paragraphs[0].add_run(_strip_bold(text))
        elif kind == "bullet":
            p = doc.add_paragraph(style="List Bullet")
            add_inline_runs(p, block[1])
        elif kind == "numbered":
            p = doc.add_paragraph(style="List Number")
            add_inline_runs(p, block[1])
        elif kind == "checkbox":
            checked, text = block[1], block[2]
            p = doc.add_paragraph(style="List Bullet")
            box = "☑ " if checked else "☐ "
            add_inline_runs(p, box + text)
        elif kind == "italic":
            p = doc.add_paragraph()
            run = p.add_run(block[1])
            run.italic = True
        elif kind == "p":
            p = doc.add_paragraph()
            add_inline_runs(p, block[1])
        # blank: paragraph spacing already provides separation

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ─── PDF export ──────────────────────────────────────────────────────────────

_SINGLE_STAR_RE = re.compile(r"(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)")


def _fpdf_markdown(text: str) -> str:
    """fpdf2's native markdown uses **bold**/__italic__; our source uses
    **bold**/single *italic* — convert single-star italics for fpdf2."""
    return _SINGLE_STAR_RE.sub(r"__\1__", text)


def markdown_to_pdf_bytes(markdown: str, title: str = "FaithForge Proposal") -> bytes:
    from fpdf import FPDF

    pdf = FPDF(format="Letter")
    pdf.set_title(title)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()

    black = (20, 20, 20)
    usable_width = pdf.w - pdf.l_margin - pdf.r_margin

    for block in _parse_blocks(markdown):
        kind = block[0]
        if kind == "h1":
            pdf.set_text_color(*NAVY_RGB)
            pdf.set_font("Helvetica", "B", 15)
            pdf.multi_cell(0, 8, block[1])
            pdf.set_draw_color(*COPPER_RGB)
            pdf.set_line_width(0.6)
            y = pdf.get_y()
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(3)
        elif kind == "h2":
            pdf.set_text_color(*NAVY_RGB)
            pdf.set_font("Helvetica", "B", 12)
            pdf.ln(2)
            pdf.multi_cell(0, 7, block[1])
        elif kind == "h3":
            pdf.set_text_color(*COPPER_RGB)
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(0, 6, block[1])
        elif kind == "h4":
            pdf.set_text_color(*black)
            pdf.set_font("Helvetica", "BI", 10)
            pdf.multi_cell(0, 6, block[1])
        elif kind == "hr":
            pdf.set_draw_color(*COPPER_RGB)
            y = pdf.get_y() + 2
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(6)
        elif kind == "table":
            header, rows = block[1], block[2]
            if not header:
                continue
            col_width = usable_width / len(header)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(*NAVY_RGB)
            pdf.set_text_color(255, 255, 255)
            for h in header:
                pdf.cell(col_width, 7, _strip_bold(h), border=1, fill=True)
            pdf.ln()
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*black)
            for row in rows:
                for cell_text in row:
                    pdf.cell(col_width, 6.5, _strip_bold(cell_text)[:60], border=1)
                pdf.ln()
            pdf.ln(3)
        elif kind in ("bullet", "numbered", "checkbox"):
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*black)
            if kind == "checkbox":
                checked, text = block[1], block[2]
                prefix = "[x] " if checked else "[ ] "
            else:
                text = block[1]
                prefix = "-  "
            pdf.set_x(pdf.l_margin + 4)
            pdf.multi_cell(usable_width - 4, 5.5, _fpdf_markdown(prefix + text), markdown=True)
        elif kind == "italic":
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(*black)
            pdf.multi_cell(0, 5.5, block[1])
        elif kind == "p":
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*black)
            pdf.multi_cell(0, 5.5, _fpdf_markdown(block[1]), markdown=True)
        elif kind == "blank":
            pdf.ln(2)

    return bytes(pdf.output())
