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

def tier_diagram(layers: List[Tuple[str, List[str]]], title: str = "") -> bytes:
    """Stacked authority/governance layers, each with a name and 3-6 short
    bullet points (not a single sentence) — top layer has highest authority."""
    if not layers:
        return b""
    n = len(layers)
    width = 820
    gap = 22
    top = 70 if title else 20
    name_font = _font(17, bold=True)
    bullet_font = _font(12, bold=False)

    heights = []
    for _, bullets in layers:
        h = 40
        for b in (bullets or [])[:6]:
            wrapped = _wrap_px(f"-  {b}", bullet_font, width - 100)
            h += (wrapped.count("\n") + 1) * 17 + 3
        heights.append(max(h + 12, 90))

    height = top + sum(heights) + gap * (n - 1) + 15

    img = Image.new("RGB", (width, int(height)), "white")
    draw = ImageDraw.Draw(img)
    if title:
        _centered(draw, width / 2, 32, title, _font(22, bold=True), NAVY)

    shades = [NAVY, MID_BLUE, PALE_BLUE, GRAY_BLUE]
    y = top
    for i, (name, bullets) in enumerate(layers):
        h = heights[i]
        shade = shades[min(i, len(shades) - 1)]
        w = width - i * 45
        x = (width - w) / 2
        draw.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=shade)
        _centered(draw, x + w / 2, y + 22, _wrap_px(name, name_font, w - 50), name_font, "white")
        by = y + 42
        for b in (bullets or [])[:6]:
            wrapped = _wrap_px(f"-  {b}", bullet_font, w - 90)
            draw.multiline_text((x + 45, by), wrapped, font=bullet_font, fill="#e9eef7", spacing=3)
            by += (wrapped.count("\n") + 1) * 17 + 3
        if i < n - 1:
            _arrow(draw, width / 2, y + h, width / 2, y + h + gap, color=ORANGE, width=4)
        y += h + gap
    return _png_bytes(img)


# ─── Vertical drop-down methodology figure (Bernedette's preferred style) ────
# Title bar, stacked rounded stage boxes, downward arrows, and a short bullet
# list inside each stage — used for process/lifecycle figures (QA process,
# risk escalation, communication cadence, project lifecycle).

def dropdown_diagram(stages: List[Tuple[str, List[str]]], title: str = "") -> bytes:
    if not stages:
        return b""
    width = 760
    title_bar_h = 60 if title else 0
    box_w = width - 80
    pad_x = (width - box_w) / 2
    gap = 30
    name_font = _font(16, bold=True)
    bullet_font = _font(13, bold=False)

    heights = []
    for _, bullets in stages:
        h = 46
        for b in (bullets or [])[:6]:
            wrapped = _wrap_px(f"-  {b}", bullet_font, box_w - 50)
            h += (wrapped.count("\n") + 1) * 20 + 4
        heights.append(max(h + 12, 70))

    height = title_bar_h + 20 + sum(heights) + gap * (len(stages) - 1) + 20

    img = Image.new("RGB", (width, int(height)), "white")
    draw = ImageDraw.Draw(img)

    if title:
        draw.rectangle([0, 0, width, title_bar_h], fill=NAVY)
        _centered(draw, width / 2, title_bar_h / 2, title, _font(20, bold=True), "white")

    y = title_bar_h + 20
    prev_bottom = None
    for i, (name, bullets) in enumerate(stages):
        h = heights[i]
        if prev_bottom is not None:
            _arrow(draw, width / 2, prev_bottom, width / 2, y, color=ORANGE, width=4)
        x = pad_x
        fill = WHITE if i % 2 == 0 else LIGHT
        draw.rounded_rectangle([x, y, x + box_w, y + h], radius=10, outline=NAVY, width=2, fill=fill)
        _centered(draw, x + box_w / 2, y + 24, f"{i + 1}. {name}", name_font, NAVY)
        by = y + 46
        for b in (bullets or [])[:6]:
            wrapped = _wrap_px(f"-  {b}", bullet_font, box_w - 50)
            draw.multiline_text((x + 25, by), wrapped, font=bullet_font, fill=DARK_TEXT, spacing=4)
            by += (wrapped.count("\n") + 1) * 20 + 4
        prev_bottom = y + h
        y += h + gap

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
                (f"{client} Executive Sponsors", [
                    "Provide strategic direction and decision authority",
                    "Approve major scope, schedule, or budget changes",
                    "Serve as final escalation point for critical issues",
                ]),
                ("FaithForge Principal Consultant / Program Director", [
                    "Own overall program governance and executive advisory",
                    "Chair the steering committee and executive reporting",
                    "Hold escalation authority for program-level risks",
                ]),
                ("FaithForge Project Manager & Workstream Leads", [
                    "Manage day-to-day execution and deliverable quality",
                    "Control schedule, scope, and resource allocation",
                    "Coordinate across workstreams and dependencies",
                ]),
                ("Delivery & Support Team", [
                    "Execute assigned tasks and produce deliverables",
                    "Maintain documentation and status reporting",
                    "Provide direct stakeholder support",
                ]),
            ], title="Executive Governance & PMO Framework")
        if key == "qa_process":
            return dropdown_diagram([
                ("Define Quality Standards & Acceptance Criteria", [
                    "Establish deliverable-specific quality criteria",
                    "Align standards to solicitation requirements",
                    "Assign quality ownership by workstream",
                ]),
                ("Deliverable Produced", [
                    "Draft prepared against approved templates",
                    "Internal consistency and completeness check",
                    "Data and source validation",
                ]),
                ("Internal QA Review", [
                    "Peer review by a non-author team member",
                    "Checklist-based quality verification",
                    "Findings logged and routed for correction",
                ]),
                ("Revisions (If Needed)", [
                    "Author addresses reviewer findings",
                    "Re-verification of corrected content",
                    "Version control and change tracking",
                ]),
                ("Client/Stakeholder Review", [
                    "Deliverable submitted for client feedback",
                    "Feedback consolidated and triaged",
                    "Response plan confirmed with client",
                ]),
                ("Final Approval & Sign-Off", [
                    "Formal client acceptance obtained",
                    "Deliverable baselined and archived",
                    "Acceptance recorded in the project log",
                ]),
                ("Lessons Learned Captured", [
                    "Review outcomes documented",
                    "Process improvements identified",
                    "Updates applied to QA templates",
                ]),
            ], title="Quality Assurance Process")
        if key == "risk_escalation":
            return dropdown_diagram([
                ("Risk/Issue Identified", [
                    "Identified by any team member or stakeholder",
                    "Initial description and context captured",
                    "Reported to the Project Manager",
                ]),
                ("Logged in RAID Register", [
                    "Entry created with category and description",
                    "Owner and target resolution date set",
                    "Initial severity assigned",
                ]),
                ("Severity Triaged", [
                    "Likelihood and impact assessed",
                    "Priority level assigned (Low/Medium/High/Critical)",
                    "Response strategy selected",
                ]),
                ("Resolved at PM Level (Low/Medium)", [
                    "Mitigation actions assigned and tracked",
                    "Progress monitored in weekly status",
                    "Resolution confirmed and closed",
                ]),
                ("Escalated to Program Director (High/Critical)", [
                    "Executive briefing prepared",
                    "Options and recommendations presented",
                    "Decision and direction documented",
                ]),
                ("Executive Sponsor Briefed", [
                    "Client executive informed of risk/issue",
                    "Impact to schedule, scope, or budget reviewed",
                    "Joint resolution path agreed",
                ]),
                ("Resolution Tracked to Closure", [
                    "Corrective actions verified complete",
                    "RAID register updated and closed",
                    "Lessons captured for future risk planning",
                ]),
            ], title="Risk & Issue Escalation Workflow")
        if key == "communication_framework":
            return dropdown_diagram([
                ("Weekly Status (PM & Client Team)", [
                    "Progress against schedule and deliverables",
                    "Open risks, issues, and action items",
                    "Upcoming milestones and dependencies",
                ]),
                ("Bi-Weekly Steering Committee", [
                    "Cross-functional alignment on priorities",
                    "Decision points requiring committee input",
                    "Resource and scope adjustments reviewed",
                ]),
                ("Monthly Executive Briefing", [
                    "High-level program health summary",
                    "KPI and performance dashboard review",
                    "Strategic risks and escalations",
                ]),
                ("Ad Hoc Issue Escalation", [
                    "Triggered by urgent risks or blockers",
                    "Direct notification to the accountable owner",
                    "Resolution tracked outside the standard cadence",
                ]),
                ("Quarterly Governance Review", [
                    "Program performance against baseline",
                    "Governance framework effectiveness review",
                    "Strategic direction and priorities confirmed",
                ]),
            ], title="Communication Framework & Cadence")
        if key == "stakeholder_engagement":
            return tier_diagram([
                ("Executive Sponsors & Decision-Makers", [
                    "Set strategic direction and priorities",
                    "Approve funding and major decisions",
                    "Champion the initiative across the organization",
                ]),
                ("Program & Department Leadership", [
                    "Provide operational direction and resource commitment",
                    "Coordinate departmental participation",
                    "Resolve cross-functional conflicts",
                ]),
                ("Operational Stakeholders & End Users", [
                    "Provide day-to-day input and subject matter expertise",
                    "Participate in workshops and requirements sessions",
                    "Adopt new processes, tools, and workflows",
                ]),
                ("External Partners & Oversight Bodies", [
                    "Coordinate regulatory and compliance requirements",
                    "Participate in oversight reviews",
                    "Provide external validation and audit support",
                ]),
            ], title="Stakeholder Engagement Model")
        if key == "project_lifecycle":
            workstreams = plan.get("workstreams") or []
            if workstreams:
                stages = [(w.get("name", "Phase"),
                          [w["objective"]] if w.get("objective") else []) for w in workstreams]
            else:
                stages = [(n, []) for n in
                          ["Mobilization", "Planning", "Execution", "Change & Adoption", "Closeout"]]
            return dropdown_diagram(stages, title="Project Lifecycle")
        if key == "raci_matrix":
            return default_raci(plan)
        if key == "gantt_chart":
            return gantt_chart(plan.get("schedule") or [])
        if key == "executive_dashboard":
            return executive_dashboard(plan, show_pricing=not plan.get("separate_pricing_volume"))
    except Exception:
        return b""
    return b""
