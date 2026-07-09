"""Programmatic diagram generation for FaithForge proposals.

Renders PNG images that replace `[[DIAGRAM:key]]` markdown sentinel lines in
the exported HTML preview, DOCX, and PDF outputs. Every diagram is built
deterministically from the proposal `plan` dict — no LLM ever draws a
diagram or invents the data inside one, so nothing here can fabricate a
fact that isn't already in the plan.

Pillow-only by design: matplotlib (plus its numpy dependency) is too heavy
for the 512MB memory ceiling on the hosting platform and caused production
out-of-memory crashes during packet builds. Pillow is already a mandatory
transitive dependency of fpdf2, so this adds no new deployed weight.
"""
import io
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

NAVY = "#1e3a8a"
ORANGE = "#c2652a"
SLATE = "#4a5568"
LIGHT = "#f7fafc"
BORDER = "#cbd5e1"
DARK_TEXT = "#1a202c"
WHITE = "#ffffff"
MID_BLUE = "#2d4e7a"
PALE_BLUE = "#5b7aa8"
GRAY_BLUE = "#94a3b8"

_DIAGRAM_RE = re.compile(r'^\[\[DIAGRAM:(\w+)\]\]$')

# ── Font loading (cached; falls back gracefully across OS/containers) ───────
_FONT_CACHE: Dict[Tuple[int, bool], Any] = {}
_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
_REGULAR_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _font(size: int, bold: bool = False):
    key = (size, bold)
    cached = _FONT_CACHE.get(key)
    if cached is not None:
        return cached
    font = None
    for path in (_BOLD_PATHS if bold else _REGULAR_PATHS):
        try:
            font = ImageFont.truetype(path, size)
            break
        except Exception:
            continue
    if font is None:
        try:
            font = ImageFont.load_default(size=size)
        except TypeError:
            font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


_MEASURE_IMG = Image.new("RGB", (1, 1))
_MEASURE_DRAW = ImageDraw.Draw(_MEASURE_IMG)


def _wrap_px(text: str, font, max_width: float) -> str:
    """Greedy word-wrap measured in actual rendered pixels."""
    if not text:
        return text
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if _MEASURE_DRAW.textlength(trial, font=font) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def _text_width(text: str, font) -> float:
    return _MEASURE_DRAW.textlength(text, font=font)


def _centered(draw, cx, cy, text, font, fill):
    draw.multiline_text((cx, cy), text, font=font, fill=fill, anchor="mm", align="center", spacing=4)


def _right_aligned(draw, x, y, text, font, fill):
    draw.multiline_text((x, y), text, font=font, fill=fill, anchor="rm", align="right", spacing=4)


def _arrow(draw, x0, y0, x1, y1, color=BORDER, width=3):
    draw.line([(x0, y0), (x1, y1)], fill=color, width=width)
    ang = math.atan2(y1 - y0, x1 - x0)
    size = 9
    p1 = (x1 - size * math.cos(ang - 0.5), y1 - size * math.sin(ang - 0.5))
    p2 = (x1 - size * math.cos(ang + 0.5), y1 - size * math.sin(ang + 0.5))
    draw.polygon([p1, (x1, y1), p2], fill=color)


def _box_edge_point(cx: float, cy: float, half_w: float, half_h: float, dx: float, dy: float) -> Tuple[float, float]:
    """Point where a ray from an axis-aligned box's center in direction
    (dx, dy) exits through the box's boundary — used so connector lines
    start/end at box edges instead of cutting through the box interior."""
    if dx == 0 and dy == 0:
        return cx, cy
    scale = 1.0 / max(abs(dx) / half_w if half_w else 1e9, abs(dy) / half_h if half_h else 1e9)
    return cx + dx * scale, cy + dy * scale


def _connect_boxes(draw, x0, y0, half_w0, half_h0, x1, y1, half_w1, half_h1, color=BORDER, width=3):
    """Draw an arrow between two box centers, clipped to start/end at each
    box's edge rather than passing through their interiors/text."""
    dx, dy = x1 - x0, y1 - y0
    start = _box_edge_point(x0, y0, half_w0, half_h0, dx, dy)
    end = _box_edge_point(x1, y1, half_w1, half_h1, -dx, -dy)
    _arrow(draw, start[0], start[1], end[0], end[1], color=color, width=width)


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def png_size(png_bytes: bytes) -> Tuple[int, int]:
    with Image.open(io.BytesIO(png_bytes)) as img:
        return img.size


def fit_size_mm(iw: int, ih: int, max_w_mm: float, max_h_mm: float, dpi: float = 150.0) -> Tuple[float, float]:
    """Natural display size for a rendered diagram (assuming `dpi` pixels per
    inch), capped to max_w_mm x max_h_mm — scaled down only, never up, so a
    small diagram isn't stretched to fill the full page width."""
    natural_w = (iw / dpi) * 25.4
    natural_h = (ih / dpi) * 25.4
    scale = min(1.0, max_w_mm / natural_w, max_h_mm / natural_h)
    return natural_w * scale, natural_h * scale


def fit_size_in(iw: int, ih: int, max_w_in: float, max_h_in: float, dpi: float = 150.0) -> Tuple[float, float]:
    natural_w = iw / dpi
    natural_h = ih / dpi
    scale = min(1.0, max_w_in / natural_w, max_h_in / natural_h)
    return natural_w * scale, natural_h * scale


def _box(draw, x, y, w, h, text, *, fill=WHITE, edge=NAVY, text_color=DARK_TEXT,
         size=20, subtext=None, sub_color=SLATE):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=fill, outline=edge, width=2)
    title_font = _font(size, bold=True)
    wrapped_title = _wrap_px(text, title_font, w - 20)
    if subtext:
        sub_font = _font(max(size - 3, 9), bold=False)
        wrapped_sub = _wrap_px(subtext, sub_font, w - 20)
        _centered(draw, x + w / 2, y + h * 0.38, wrapped_title, title_font, text_color)
        _centered(draw, x + w / 2, y + h * 0.74, wrapped_sub, sub_font, sub_color)
    else:
        _centered(draw, x + w / 2, y + h / 2, wrapped_title, title_font, text_color)


# ─── Organization chart ──────────────────────────────────────────────────────

def org_chart(entries: List[Dict[str, Optional[str]]]) -> bytes:
    """entries: [{"role": str, "name": str, "reports_to": <role str or None>}]"""
    if not entries:
        return b""
    children: Dict[Optional[str], List[dict]] = {}
    for e in entries:
        children.setdefault(e.get("reports_to"), []).append(e)
    roots = children.get(None) or [entries[0]]

    levels: List[List[dict]] = []
    frontier = roots
    seen = {id(e) for e in roots}
    while frontier:
        levels.append(frontier)
        nxt = []
        for e in frontier:
            for c in children.get(e["role"], []):
                if id(c) not in seen:
                    nxt.append(c)
                    seen.add(id(c))
        frontier = nxt

    max_width = max(len(l) for l in levels)
    title_font = _font(20, bold=True)
    longest_role_px = max((_text_width(e.get("role", ""), title_font) for e in entries), default=160)
    box_w = int(max(240, min(420, longest_role_px + 40)))
    box_h, gap_x, gap_y = 100, 40, 55
    width = int(max_width * (box_w + gap_x) + gap_x)
    height = int(len(levels) * (box_h + gap_y) + gap_y)

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    anchors = {}  # role -> (center_x, top_y, bottom_y)
    for li, level in enumerate(levels):
        n = len(level)
        row_w = n * box_w + (n - 1) * gap_x
        start_x = (width - row_w) / 2
        y = gap_y + li * (box_h + gap_y)
        for i, e in enumerate(level):
            x = start_x + i * (box_w + gap_x)
            fill = NAVY if li == 0 else WHITE
            text_color = WHITE if li == 0 else DARK_TEXT
            sub_color = "#dbe4f5" if li == 0 else SLATE
            _box(draw, x, y, box_w, box_h, e["role"], subtext=e.get("name") or "[TO BE NAMED]",
                 fill=fill, edge=NAVY, text_color=text_color, sub_color=sub_color)
            anchors[e["role"]] = (x + box_w / 2, y, y + box_h)

    for e in entries:
        parent = e.get("reports_to")
        if parent and parent in anchors and e["role"] in anchors:
            pcx, _, pby = anchors[parent]
            ccx, cty, _ = anchors[e["role"]]
            _arrow(draw, pcx, pby, ccx, cty)

    return _png_bytes(img)


def default_org_chart(plan: Dict[str, Any]) -> List[Dict[str, Optional[str]]]:
    """Fallback org chart built from the plan's labor roles when no explicit
    org_chart was supplied (e.g. via custom instructions for a specific bid)."""
    labor = plan.get("labor", []) or []
    top_role = "Principal Consultant"
    entries: List[Dict[str, Optional[str]]] = [
        {"role": top_role, "name": "Bernedette Atong, PMP, PgMP", "reports_to": None}
    ]
    for row in labor:
        role = row.get("role")
        if role and role != top_role:
            entries.append({"role": role, "name": "[TO BE NAMED]", "reports_to": top_role})
    return entries


# ─── Tiered governance / stakeholder model (stacked layers) ─────────────────

def tier_diagram(layers: List[Tuple[str, str]], title: str = "") -> bytes:
    if not layers:
        return b""
    n = len(layers)
    width = 820
    layer_h = 110
    gap = 22
    top = 70 if title else 20
    height = top + n * (layer_h + gap) + 10

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    if title:
        _centered(draw, width / 2, 32, title, _font(22, bold=True), NAVY)

    shades = [NAVY, MID_BLUE, PALE_BLUE, GRAY_BLUE]
    for i, (name, desc) in enumerate(layers):
        y = top + i * (layer_h + gap)
        shade = shades[min(i, len(shades) - 1)]
        w = width - i * 45
        x = (width - w) / 2
        draw.rounded_rectangle([x, y, x + w, y + layer_h], radius=8, fill=shade)
        name_font = _font(17, bold=True)
        desc_font = _font(13, bold=False)
        _centered(draw, x + w / 2, y + layer_h * 0.34, _wrap_px(name, name_font, w - 40), name_font, "white")
        _centered(draw, x + w / 2, y + layer_h * 0.72, _wrap_px(desc, desc_font, w - 40), desc_font, "#e9eef7")
        if i < n - 1:
            _arrow(draw, width / 2, y + layer_h, width / 2, y + layer_h + gap, color=ORANGE, width=4)
    return _png_bytes(img)


# ─── Sequential flow / process diagram ──────────────────────────────────────

def flow_diagram(steps: List[str], title: str = "") -> bytes:
    steps = [s for s in steps if s]
    if not steps:
        return b""
    n = len(steps)
    box_w, box_h = 220, 100
    gap = 45
    cols = min(n, 4)
    rows = (n + cols - 1) // cols
    width = cols * box_w + (cols - 1) * gap + 60
    top = 70 if title else 20
    height = top + rows * (box_h + 70)

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    if title:
        _centered(draw, width / 2, 32, title, _font(22, bold=True), NAVY)

    prev = None
    for idx, step in enumerate(steps):
        r, c = divmod(idx, cols)
        cc = c if r % 2 == 0 else (cols - 1 - c)
        x = 30 + cc * (box_w + gap)
        y = top + r * (box_h + 70)
        fill = NAVY if idx == 0 else (ORANGE if idx == n - 1 else WHITE)
        text_color = WHITE if idx in (0, n - 1) else DARK_TEXT
        _box(draw, x, y, box_w, box_h, f"{idx + 1}. {step}", fill=fill, edge=NAVY,
             text_color=text_color, size=14)
        cx, cy = x + box_w / 2, y + box_h / 2
        if prev:
            _connect_boxes(draw, prev[0], prev[1], box_w / 2, box_h / 2, cx, cy, box_w / 2, box_h / 2)
        prev = (cx, cy)
    return _png_bytes(img)


# ─── RACI matrix ─────────────────────────────────────────────────────────────

_RACI_COLORS = {"R": NAVY, "A": ORANGE, "C": MID_BLUE, "I": GRAY_BLUE}


def raci_matrix(workstreams: List[str], roles: List[str],
                 assignments: Dict[Tuple[int, int], str], title: str = "RACI Matrix") -> bytes:
    workstreams = workstreams or []
    if not workstreams or not roles:
        return b""
    label_w = 260
    cell_w, cell_h = 150, 65
    ncols_data = len(roles)
    width = label_w + ncols_data * cell_w
    height = 60 + (len(workstreams) + 1) * cell_h + 35

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    _centered(draw, width / 2, 26, title, _font(20, bold=True), NAVY)
    top = 55

    draw.rectangle([0, top, label_w, top + cell_h], fill=NAVY, outline="white")
    _centered(draw, label_w / 2, top + cell_h / 2, "Workstream", _font(15, bold=True), "white")
    role_font = _font(13, bold=True)
    for j, role in enumerate(roles):
        x = label_w + j * cell_w
        draw.rectangle([x, top, x + cell_w, top + cell_h], fill=NAVY, outline="white")
        _centered(draw, x + cell_w / 2, top + cell_h / 2, _wrap_px(role, role_font, cell_w - 16),
                  role_font, "white")

    ws_font = _font(13, bold=False)
    raci_font = _font(19, bold=True)
    for i, ws in enumerate(workstreams):
        y = top + cell_h * (i + 1)
        fill = LIGHT if i % 2 == 0 else "white"
        draw.rectangle([0, y, label_w, y + cell_h], fill=fill, outline=BORDER)
        _centered(draw, label_w / 2, y + cell_h / 2, _wrap_px(ws, ws_font, label_w - 24), ws_font, DARK_TEXT)
        for j in range(ncols_data):
            x = label_w + j * cell_w
            draw.rectangle([x, y, x + cell_w, y + cell_h], fill=fill, outline=BORDER)
            code = assignments.get((i, j), "")
            if code:
                _centered(draw, x + cell_w / 2, y + cell_h / 2, code, raci_font,
                          _RACI_COLORS.get(code, DARK_TEXT))

    draw.text((10, height - 18), "R = Responsible    A = Accountable    C = Consulted    I = Informed",
              font=_font(13, bold=False), fill=SLATE, anchor="lm")
    return _png_bytes(img)


def default_raci(plan: Dict[str, Any]) -> bytes:
    workstreams = [w.get("name", "Workstream") for w in (plan.get("workstreams") or [])][:8]
    if not workstreams:
        return b""
    roles = ["Client Sponsor", "Program Director", "Project Manager", "Workstream Lead", "QA Manager"]
    assignments = {}
    for i in range(len(workstreams)):
        assignments[(i, 0)] = "I"
        assignments[(i, 1)] = "A"
        assignments[(i, 2)] = "R"
        assignments[(i, 3)] = "R"
        assignments[(i, 4)] = "C"
    return raci_matrix(workstreams, roles, assignments,
                        title="RACI Matrix — Roles & Responsibilities by Workstream")


# ─── Gantt / high-level schedule chart ───────────────────────────────────────

def _parse_months(timeline: str) -> Tuple[int, int]:
    m = re.search(r"(\d+)\s*-\s*(\d+)", timeline or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    m2 = re.search(r"(\d+)", timeline or "")
    if m2:
        v = int(m2.group(1))
        return v, v + 1
    return 0, 1


def gantt_chart(schedule: List[Dict[str, Any]], title: str = "High-Level Program Schedule") -> bytes:
    if not schedule:
        return b""
    parsed = []
    max_month = 1
    for row in schedule:
        start, end = _parse_months(row.get("timeline", ""))
        end = max(end, start + 1)
        max_month = max(max_month, end)
        parsed.append((row.get("phase") or "Phase", start, end))

    n = len(parsed)
    bar_h, row_gap, left_pad = 45, 25, 300
    width = int(left_pad + max_month * 35 + 60)
    top = 65
    height = int(top + n * (bar_h + row_gap) + 30)

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    _centered(draw, width / 2, 28, title, _font(20, bold=True), NAVY)
    scale = (width - left_pad - 40) / max_month

    tick_font = _font(11, bold=False)
    step = max(1, max_month // 8)
    for m in range(0, max_month + 1, step):
        x = left_pad + m * scale
        draw.line([(x, top - 8), (x, height - 15)], fill=BORDER, width=1)
        draw.text((x, top - 12), f"M{m}", font=tick_font, fill=SLATE, anchor="mb")

    phase_font = _font(14, bold=False)
    bar_font = _font(13, bold=True)
    for i, (phase, start, end) in enumerate(parsed):
        y = top + 10 + i * (bar_h + row_gap)
        _right_aligned(draw, left_pad - 15, y + bar_h / 2, _wrap_px(phase, phase_font, left_pad - 30),
                       phase_font, DARK_TEXT)
        x0 = left_pad + start * scale
        bw = max((end - start) * scale, 10)
        color = NAVY if i % 2 == 0 else ORANGE
        draw.rounded_rectangle([x0, y, x0 + bw, y + bar_h], radius=6, fill=color)
        _centered(draw, x0 + bw / 2, y + bar_h / 2, f"M{start}-{end}", bar_font, "white")
    return _png_bytes(img)


# ─── Executive dashboard mockup ──────────────────────────────────────────────

def executive_dashboard(plan: Dict[str, Any], title: str = "Program Delivery Overview",
                         show_pricing: bool = True) -> bytes:
    months = plan.get("engagement_months", 0)
    n_workstreams = len(plan.get("workstreams") or [])
    n_deliverables = len(plan.get("deliverable_products") or [])
    schedule = plan.get("schedule") or []

    if show_pricing:
        total_value = plan.get("total_value", 0)
        tiles = [
            (f"${total_value:,.0f}", "Total Potential Contract Value"),
            (f"{months}", "Engagement Duration (Months)"),
            (f"{n_workstreams}", "Program Workstreams"),
            (f"{n_deliverables}", "Contract Deliverables"),
        ]
    else:
        tiles = [
            (f"{months}", "Engagement Duration (Months)"),
            (f"{n_workstreams}", "Program Workstreams"),
            (f"{n_deliverables}", "Contract Deliverables"),
            (f"{len(schedule)}", "Delivery Phases"),
        ]

    width, height = 1050, 520
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    _centered(draw, width / 2, 30, title, _font(24, bold=True), NAVY)

    n_tiles = len(tiles)
    tile_gap = 14
    tile_w = (width - tile_gap * (n_tiles + 1)) / n_tiles
    tile_top, tile_h = 65, 110
    value_font = _font(26, bold=True)
    label_font = _font(13, bold=False)
    for i, (value, label) in enumerate(tiles):
        x = tile_gap + i * (tile_w + tile_gap)
        draw.rounded_rectangle([x, tile_top, x + tile_w, tile_top + tile_h], radius=6,
                               fill=LIGHT, outline=BORDER)
        _centered(draw, x + tile_w / 2, tile_top + tile_h * 0.4, value, value_font, NAVY)
        _centered(draw, x + tile_w / 2, tile_top + tile_h * 0.75,
                  _wrap_px(label, label_font, tile_w - 16), label_font, SLATE)

    chart_top = tile_top + tile_h + 40
    chart_left = 280
    chart_right = width - 60
    chart_bottom = height - 50
    chart_w = chart_right - chart_left

    names_font = _font(13, bold=False)
    bar_label_font = _font(12, bold=False)
    axis_font = _font(11, bold=False)

    values: List[Tuple[str, float, str]] = []
    max_val = 1.0
    axis_label = ""
    if show_pricing and plan.get("workstream_costs"):
        rows = plan["workstream_costs"]
        max_val = max((r.get("cost", 0) for r in rows), default=1) or 1
        axis_label = "Estimated Cost by Workstream ($)"
        values = [(r.get("workstream", ""), r.get("cost", 0), f"${r.get('cost', 0):,.0f}") for r in rows]
    elif schedule:
        for s in schedule:
            m = re.search(r"(\d+)", str(s.get("completion", "")))
            pct = int(m.group(1)) if m else 0
            values.append((s.get("phase", ""), pct, f"{pct}%"))
        max_val = 100
        axis_label = "Planned Completion by Phase (%)"

    if values:
        n_rows = len(values)
        row_h = (chart_bottom - chart_top) / n_rows
        bar_h = min(row_h * 0.55, 40)
        draw.line([(chart_left, chart_top - 5), (chart_left, chart_bottom)], fill=BORDER, width=1)
        for i, (name, val, label) in enumerate(values):
            y = chart_top + i * row_h + (row_h - bar_h) / 2
            _right_aligned(draw, chart_left - 10, y + bar_h / 2, _wrap_px(name, names_font, chart_left - 30),
                          names_font, DARK_TEXT)
            bw = (val / max_val) * chart_w if max_val else 0
            draw.rectangle([chart_left, y, chart_left + bw, y + bar_h], fill=NAVY)
            draw.text((chart_left + bw + 6, y + bar_h / 2), label, font=bar_label_font, fill=DARK_TEXT, anchor="lm")
        draw.line([(chart_left, chart_bottom), (chart_right, chart_bottom)], fill=BORDER, width=1)
        _centered(draw, (chart_left + chart_right) / 2, chart_bottom + 22, axis_label, axis_font, SLATE)

    return _png_bytes(img)


# ─── Dispatch ─────────────────────────────────────────────────────────────────

def render_diagram(key: str, plan: Dict[str, Any]) -> bytes:
    """Render a diagram by sentinel key using only data already in `plan`.
    Returns b"" (silently) on any failure or unknown key — a missing diagram
    should never break document generation."""
    try:
        client = plan.get("client_name") or "the Agency"
        if key == "org_chart":
            entries = plan.get("org_chart") or default_org_chart(plan)
            return org_chart(entries)
        if key == "governance_framework":
            return tier_diagram([
                (f"{client} Executive Sponsors", "Strategic direction, decision authority, executive oversight"),
                ("FaithForge Principal Consultant / Program Director", "Program governance, executive advisory, escalation authority"),
                ("FaithForge Project Manager & Workstream Leads", "Day-to-day execution oversight, deliverable quality, schedule control"),
                ("Delivery & Support Team", "Task execution, reporting, documentation, stakeholder support"),
            ], title="Executive Governance & PMO Framework")
        if key == "qa_process":
            return flow_diagram([
                "Define Quality Standards & Acceptance Criteria", "Deliverable Produced",
                "Internal QA Review", "Revisions (If Needed)", "Client/Stakeholder Review",
                "Final Approval & Sign-Off", "Lessons Learned Captured",
            ], title="Quality Assurance Process")
        if key == "risk_escalation":
            return flow_diagram([
                "Risk/Issue Identified", "Logged in RAID Register", "Severity Triaged",
                "Resolved at PM Level (Low/Medium)", "Escalated to Program Director (High/Critical)",
                "Executive Sponsor Briefed", "Resolution Tracked to Closure",
            ], title="Risk & Issue Escalation Workflow")
        if key == "communication_framework":
            return flow_diagram([
                "Weekly Status (PM & Client Team)", "Bi-Weekly Steering Committee",
                "Monthly Executive Briefing", "Ad Hoc Issue Escalation", "Quarterly Governance Review",
            ], title="Communication Framework & Cadence")
        if key == "stakeholder_engagement":
            return tier_diagram([
                ("Executive Sponsors & Decision-Makers", "Strategic alignment, funding, go/no-go decisions"),
                ("Program & Department Leadership", "Operational direction, resource commitment"),
                ("Operational Stakeholders & End Users", "Day-to-day input, adoption, feedback"),
                ("External Partners & Oversight Bodies", "Regulatory, oversight, and partner coordination"),
            ], title="Stakeholder Engagement Model")
        if key == "project_lifecycle":
            names = [w.get("name", "Phase") for w in (plan.get("workstreams") or [])]
            names = names or ["Mobilization", "Planning", "Execution", "Change & Adoption", "Closeout"]
            return flow_diagram(names, title="Project Lifecycle")
        if key == "raci_matrix":
            return default_raci(plan)
        if key == "gantt_chart":
            return gantt_chart(plan.get("schedule") or [])
        if key == "executive_dashboard":
            return executive_dashboard(plan, show_pricing=not plan.get("separate_pricing_volume"))
    except Exception:
        return b""
    return b""
