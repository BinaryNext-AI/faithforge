"""Convert packet markdown content to a PDF using fpdf2 — FaithForge branded."""

import io
import re
import json
from typing import Optional
from fpdf import FPDF

L_MARGIN = 18
R_MARGIN = 18
PAGE_W = 210  # A4
CONTENT_W = PAGE_W - L_MARGIN - R_MARGIN  # 174mm
LINE_H = 5.5

# FaithForge brand colors
NAVY       = (30,  58, 138)   # #1e3a8a — primary navy (FaithForge brand)
ORANGE     = (194, 101,  42)  # #c2652a — accent orange
DARK_TEXT  = (26,  32,  44)   # #1a202c — body text
GRAY_TEXT  = (74,  85, 104)   # #4a5568 — secondary text
LIGHT_BG   = (247, 250, 252)  # #f7fafc — table alternating row


def _safe(text: str) -> str:
    return "".join(c if ord(c) < 256 else "-" for c in str(text))


def _clean(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",     r"\1", text)
    return _safe(text.strip())


def _reset_x(pdf):
    pdf.set_x(L_MARGIN)


class PacketPDF(FPDF):
    footer_label: str = "FaithForge Proposal"

    def header(self):
        # Thin navy top bar
        self.set_fill_color(*NAVY)
        self.rect(0, 0, PAGE_W, 3, "F")
        # Reset cursor to content start
        self.set_xy(L_MARGIN, self.t_margin)

    def footer(self):
        self.set_y(-13)
        # Orange separator line
        self.set_draw_color(*ORANGE)
        self.set_line_width(0.35)
        self.line(L_MARGIN, self.get_y(), L_MARGIN + CONTENT_W, self.get_y())
        self.ln(1.5)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*GRAY_TEXT)
        self.set_x(L_MARGIN)
        # Left: "{Opportunity Name} Proposal | Page N"  (matches WSSC sample format)
        label = f"{self.footer_label}  |  Page {self.page_no()}"
        self.cell(CONTENT_W / 2, 5, label, border=0, align="L")
        self.set_x(L_MARGIN + CONTENT_W / 2)
        self.cell(CONTENT_W / 2, 5, "CONFIDENTIAL - Internal Use Only",
                  border=0, align="R")
        self.set_text_color(0, 0, 0)


def _wrap_text(pdf, text: str, width: float):
    """Word-wrap text to fit within width mm using current font."""
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if pdf.get_string_width(trial) <= width - 1:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def _render_table(pdf, rows):
    if not rows:
        return

    ncols = max(len(r) for r in rows)
    col_w = CONTENT_W / ncols
    cell_pad = 1.5
    cell_line_h = 5.0

    for ri, row in enumerate(rows):
        cells = (row + [""] * ncols)[:ncols]
        is_header = ri == 0
        pdf.set_font("Helvetica", "B" if is_header else "", 9)

        wrapped = [_wrap_text(pdf, _clean(c), col_w - cell_pad * 2) for c in cells]
        row_lines = max(len(w) for w in wrapped)
        row_h = row_lines * cell_line_h + cell_pad * 2

        if pdf.get_y() + row_h > pdf.h - 20:
            pdf.add_page()

        x0 = L_MARGIN
        y0 = pdf.get_y()

        for ci in range(ncols):
            cx = x0 + ci * col_w
            pdf.set_xy(cx, y0)
            if is_header:
                pdf.set_fill_color(*NAVY)
            elif ri % 2 == 0:
                pdf.set_fill_color(*LIGHT_BG)
            else:
                pdf.set_fill_color(255, 255, 255)
            pdf.cell(col_w, row_h, "", border=1, fill=True)

        if is_header:
            pdf.set_text_color(255, 255, 255)
        else:
            pdf.set_text_color(*DARK_TEXT)

        for ci in range(ncols):
            cx = x0 + ci * col_w
            for li, txt in enumerate(wrapped[ci]):
                pdf.set_xy(cx + cell_pad, y0 + cell_pad + li * cell_line_h)
                pdf.cell(col_w - cell_pad * 2, cell_line_h, txt, border=0)

        pdf.set_xy(L_MARGIN, y0 + row_h)

    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(255, 255, 255)
    _reset_x(pdf)
    pdf.ln(3)


def _parse_table_row(s: str):
    return [c.strip() for c in s.strip().strip("|").split("|")]


def _is_table_separator(s: str) -> bool:
    body = s.strip().strip("|")
    if not body:
        return False
    return all(set(c.strip()) <= set("-: ") and "-" in c for c in body.split("|"))


_DIAGRAM_LINE_RE = re.compile(r'^\[\[DIAGRAM:(\w+)\]\]$')


def _place_diagram(pdf, key: str, plan: dict) -> None:
    """Render and embed a diagram image at the current cursor position,
    page-breaking first if it wouldn't fit on the remaining page. Sized at
    its natural resolution (capped to the page) rather than always stretched
    to full content width, so small diagrams aren't blown up."""
    from diagrams import render_diagram, png_size, fit_size_mm
    png = render_diagram(key, plan)
    if not png:
        return
    try:
        iw, ih = png_size(png)
    except Exception:
        return
    display_w, display_h = fit_size_mm(iw, ih, CONTENT_W, 170.0)
    if pdf.get_y() + display_h > pdf.h - 20:
        pdf.add_page()
    y0 = pdf.get_y()
    x0 = L_MARGIN + (CONTENT_W - display_w) / 2
    pdf.image(io.BytesIO(png), x=x0, y=y0, w=display_w, h=display_h)
    pdf.set_xy(L_MARGIN, y0 + display_h + 3)


def markdown_to_pdf(markdown_text: str, output_path: str, footer_label: str = "FaithForge Proposal",
                     plan: Optional[dict] = None) -> str:
    pdf = PacketPDF()
    pdf.footer_label = footer_label
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(L_MARGIN, 14, R_MARGIN)
    pdf.add_page()

    lines = markdown_text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        s = line.strip()

        # ── Diagram sentinel ──────────────────────────────────────────────────
        diagram_match = _DIAGRAM_LINE_RE.match(s)
        if diagram_match:
            i += 1
            if plan:
                _place_diagram(pdf, diagram_match.group(1), plan)
            continue

        # ── Markdown table ────────────────────────────────────────────────────
        if s.startswith("|") and i + 1 < len(lines) and _is_table_separator(lines[i + 1]):
            table_rows = [_parse_table_row(s)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_rows.append(_parse_table_row(lines[i]))
                i += 1
            _render_table(pdf, table_rows)
            continue

        i += 1

        # ── Blank line ────────────────────────────────────────────────────────
        if not s:
            pdf.ln(2)
            continue

        # ── H1 ───────────────────────────────────────────────────────────────
        if s.startswith("# "):
            if pdf.get_y() > pdf.t_margin + 10:
                pdf.ln(4)
            pdf.set_font("Helvetica", "B", 15)
            pdf.set_text_color(*NAVY)
            _reset_x(pdf)
            pdf.multi_cell(CONTENT_W, 9, _clean(s[2:]))
            _reset_x(pdf)
            pdf.set_draw_color(*ORANGE)
            pdf.set_line_width(0.7)
            pdf.line(L_MARGIN, pdf.get_y(), L_MARGIN + CONTENT_W, pdf.get_y())
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.2)
            pdf.set_text_color(0, 0, 0)
            _reset_x(pdf)
            pdf.ln(4)

        # ── H2 — full navy section bar with orange left accent ────────────────
        elif s.startswith("## "):
            pdf.ln(5)
            if pdf.get_y() > pdf.h - 35:
                pdf.add_page()
            y0 = pdf.get_y()
            # Orange left accent strip (4mm wide)
            pdf.set_fill_color(*ORANGE)
            pdf.rect(L_MARGIN, y0, 4, 10, "F")
            # Navy main bar
            pdf.set_fill_color(*NAVY)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_xy(L_MARGIN + 4, y0)
            pdf.cell(CONTENT_W - 4, 10, _clean(s[3:]), border=0, fill=True, ln=False)
            pdf.ln(10)
            pdf.set_text_color(0, 0, 0)
            pdf.set_fill_color(255, 255, 255)
            _reset_x(pdf)
            pdf.ln(3)

        # ── H3 — orange subsection heading ───────────────────────────────────
        elif s.startswith("### "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*ORANGE)
            _reset_x(pdf)
            pdf.multi_cell(CONTENT_W, 6.5, _clean(s[4:]))
            _reset_x(pdf)
            pdf.set_draw_color(*ORANGE)
            pdf.set_line_width(0.4)
            pdf.line(L_MARGIN, pdf.get_y(), L_MARGIN + 70, pdf.get_y())
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.2)
            pdf.set_text_color(0, 0, 0)
            _reset_x(pdf)
            pdf.ln(2)

        # ── H4 ───────────────────────────────────────────────────────────────
        elif s.startswith("#### "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "BI", 10)
            pdf.set_text_color(45, 78, 122)
            _reset_x(pdf)
            pdf.multi_cell(CONTENT_W, 6, _clean(s[5:]))
            pdf.set_text_color(0, 0, 0)
            _reset_x(pdf)

        # ── Checkbox item ─────────────────────────────────────────────────────
        elif re.match(r"^- \[[ x]\] ", s):
            checked = len(s) > 3 and s[3] == "x"
            text_part = _clean(s[6:])
            mark = "[x]" if checked else "[ ]"
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*DARK_TEXT)
            pdf.set_x(L_MARGIN + 4)
            pdf.multi_cell(CONTENT_W - 4, LINE_H, f"{mark} {text_part}")
            pdf.set_text_color(0, 0, 0)
            _reset_x(pdf)

        # ── Bullet ───────────────────────────────────────────────────────────
        elif s.startswith("- ") or s.startswith("* "):
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*DARK_TEXT)
            pdf.set_x(L_MARGIN + 5)
            pdf.multi_cell(CONTENT_W - 5, LINE_H, _clean("- " + s[2:]))
            pdf.set_text_color(0, 0, 0)
            _reset_x(pdf)

        # ── Numbered list ────────────────────────────────────────────────────
        elif re.match(r"^\d+\. ", s):
            text_part = _clean(re.sub(r"^\d+\. ", "", s))
            num = re.match(r"^(\d+)\.", s).group(1)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*DARK_TEXT)
            pdf.set_x(L_MARGIN + 5)
            pdf.multi_cell(CONTENT_W - 5, LINE_H, f"{num}. {text_part}")
            pdf.set_text_color(0, 0, 0)
            _reset_x(pdf)

        # ── Horizontal rule — orange line ────────────────────────────────────
        elif s == "---":
            pdf.ln(3)
            _reset_x(pdf)
            pdf.set_draw_color(*ORANGE)
            pdf.set_line_width(0.35)
            pdf.line(L_MARGIN, pdf.get_y(), L_MARGIN + CONTENT_W, pdf.get_y())
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.2)
            _reset_x(pdf)
            pdf.ln(4)

        # ── Italic paragraph (*text*) ─────────────────────────────────────────
        elif s.startswith("*") and s.endswith("*") and len(s) > 2 and not s.startswith("**"):
            pdf.set_font("Helvetica", "I", 9.5)
            pdf.set_text_color(*GRAY_TEXT)
            _reset_x(pdf)
            pdf.multi_cell(CONTENT_W, LINE_H, _clean(s))
            pdf.set_text_color(0, 0, 0)
            _reset_x(pdf)
            pdf.ln(1)

        # ── Normal paragraph ─────────────────────────────────────────────────
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*DARK_TEXT)
            _reset_x(pdf)
            pdf.multi_cell(CONTENT_W, LINE_H, _clean(s))
            pdf.set_text_color(0, 0, 0)
            _reset_x(pdf)

    pdf.output(output_path)
    return output_path


def packet_to_pdf(content_json: str, output_path: str) -> str:
    try:
        data = json.loads(content_json)
        markdown_text = data.get("markdown", "")
        plan = data.get("plan", {})
    except Exception:
        markdown_text = str(content_json)
        plan = {}
    if not markdown_text:
        markdown_text = "No packet content available."
    # Extract opportunity title for the footer (e.g. "AMI Program Management Services Proposal")
    opp_title = plan.get("title", "") if isinstance(plan, dict) else ""
    footer_label = f"{opp_title} Proposal" if opp_title else "FaithForge Proposal"
    return markdown_to_pdf(markdown_text, output_path, footer_label=footer_label,
                            plan=plan if isinstance(plan, dict) else None)
