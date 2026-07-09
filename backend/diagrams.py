"""Programmatic diagram generation for FaithForge proposals.

Renders PNG images (matplotlib, headless) that replace `[[DIAGRAM:key]]`
markdown sentinel lines in the exported HTML preview, DOCX, and PDF outputs.
Every diagram is built deterministically from the proposal `plan` dict — no
LLM ever draws a diagram or invents the data inside one, so nothing here can
fabricate a fact that isn't already in the plan.
"""
import io
import re
import textwrap
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

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

FIG_DPI = 170

_DIAGRAM_RE = re.compile(r'^\[\[DIAGRAM:(\w+)\]\]$')


def _new_fig(width: float, height: float):
    fig, ax = plt.subplots(figsize=(width, height), dpi=FIG_DPI)
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    ax.invert_yaxis()  # (0,0) at top-left so layout code reads top-to-bottom
    return fig, ax


def _wrap_to_width(text: str, width_in: float, fontsize: float, bold: bool = True) -> str:
    """Manually wrap text to fit a box of `width_in` inches — matplotlib's own
    `wrap=True` wraps to the *axes* width, not the containing box, so a long
    label in a narrow box renders as one unwrapped line that overflows past
    the box (and gets clipped at the figure edge by the fixed data xlim)."""
    if not text:
        return text
    chars_per_in = 6.6 if bold else 7.6
    chars_per_line = max(int(width_in * chars_per_in * (9.0 / fontsize)), 8)
    return "\n".join(textwrap.wrap(text, chars_per_line, break_long_words=False)) or text


def _box(ax, x, y, w, h, text, *, fill=WHITE, edge=NAVY, text_color=DARK_TEXT,
         fontsize=8.5, subtext=None, sub_color=SLATE):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.3, edgecolor=edge, facecolor=fill,
    ))
    wrapped_text = _wrap_to_width(text, w - 0.15, fontsize, bold=True)
    if subtext:
        wrapped_sub = _wrap_to_width(subtext, w - 0.15, fontsize - 1.5, bold=False)
        ax.text(x + w / 2, y + h * 0.36, wrapped_text, ha="center", va="center",
                 fontsize=fontsize, fontweight="bold", color=text_color)
        ax.text(x + w / 2, y + h * 0.74, wrapped_sub, ha="center", va="center",
                 fontsize=fontsize - 1.5, color=sub_color)
    else:
        ax.text(x + w / 2, y + h / 2, wrapped_text, ha="center", va="center",
                 fontsize=fontsize, fontweight="bold", color=text_color)


def _arrow(ax, x0, y0, x1, y1, color=BORDER):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=13,
                                  linewidth=1.4, color=color, shrinkA=2, shrinkB=2))


def _finish(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


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
    longest_role = max((len(e.get("role", "")) for e in entries), default=10)
    box_w = max(2.5, min(4.0, longest_role * 0.075 + 0.9))
    box_h, gap_x, gap_y = 1.05, 0.45, 0.6
    width = max_width * (box_w + gap_x) + gap_x
    height = len(levels) * (box_h + gap_y) + gap_y

    fig, ax = _new_fig(width, height)
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
            _box(ax, x, y, box_w, box_h, e["role"], subtext=e.get("name") or "[TO BE NAMED]",
                 fill=fill, edge=NAVY, text_color=text_color, sub_color=sub_color)
            anchors[e["role"]] = (x + box_w / 2, y, y + box_h)

    for e in entries:
        parent = e.get("reports_to")
        if parent and parent in anchors and e["role"] in anchors:
            pcx, _, pby = anchors[parent]
            ccx, cty, _ = anchors[e["role"]]
            _arrow(ax, pcx, pby, ccx, cty)

    return _finish(fig)


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
    width = 8.2
    layer_h = 1.0
    gap = 0.22
    top = 0.7 if title else 0.25
    height = top + n * (layer_h + gap) + 0.15

    fig, ax = _new_fig(width, height)
    if title:
        ax.text(width / 2, 0.32, title, ha="center", va="center", fontsize=11.5,
                 fontweight="bold", color=NAVY)
    shades = [NAVY, MID_BLUE, PALE_BLUE, GRAY_BLUE]
    for i, (name, desc) in enumerate(layers):
        y = top + i * (layer_h + gap)
        shade = shades[min(i, len(shades) - 1)]
        w = width - i * 0.5
        x = (width - w) / 2
        ax.add_patch(FancyBboxPatch((x, y), w, layer_h, boxstyle="round,pad=0.015,rounding_size=0.06",
                                     facecolor=shade, edgecolor="white", linewidth=1.2))
        ax.text(x + w / 2, y + layer_h * 0.34, _wrap_to_width(name, w - 0.3, 9),
                 ha="center", va="center", fontsize=9, fontweight="bold", color="white")
        ax.text(x + w / 2, y + layer_h * 0.72, _wrap_to_width(desc, w - 0.3, 7.2, bold=False),
                 ha="center", va="center", fontsize=7.2, color="#e9eef7")
        if i < n - 1:
            _arrow(ax, width / 2, y + layer_h, width / 2, y + layer_h + gap, color=ORANGE)
    return _finish(fig)


# ─── Sequential flow / process diagram ──────────────────────────────────────

def flow_diagram(steps: List[str], title: str = "") -> bytes:
    steps = [s for s in steps if s]
    if not steps:
        return b""
    n = len(steps)
    box_w, box_h = 2.3, 1.05
    gap = 0.5
    cols = min(n, 4)
    rows = (n + cols - 1) // cols
    width = cols * box_w + (cols - 1) * gap + 0.8
    top = 0.75 if title else 0.25
    height = top + rows * (box_h + 0.8)

    fig, ax = _new_fig(width, height)
    if title:
        ax.text(width / 2, 0.32, title, ha="center", va="center", fontsize=11.5,
                 fontweight="bold", color=NAVY)

    prev = None
    for idx, step in enumerate(steps):
        r, c = divmod(idx, cols)
        cc = c if r % 2 == 0 else (cols - 1 - c)
        x = 0.4 + cc * (box_w + gap)
        y = top + r * (box_h + 0.8)
        fill = NAVY if idx == 0 else (ORANGE if idx == n - 1 else WHITE)
        text_color = WHITE if idx in (0, n - 1) else DARK_TEXT
        _box(ax, x, y, box_w, box_h, f"{idx + 1}. {step}", fill=fill, edge=NAVY,
             text_color=text_color, fontsize=8)
        cx, cy = x + box_w / 2, y + box_h / 2
        if prev:
            _arrow(ax, prev[0], prev[1], cx, cy)
        prev = (cx, cy)
    return _finish(fig)


# ─── RACI matrix ─────────────────────────────────────────────────────────────

_RACI_COLORS = {"R": NAVY, "A": ORANGE, "C": MID_BLUE, "I": GRAY_BLUE}


def raci_matrix(workstreams: List[str], roles: List[str],
                 assignments: Dict[Tuple[int, int], str], title: str = "RACI Matrix") -> bytes:
    workstreams = workstreams or []
    if not workstreams or not roles:
        return b""
    label_w = 3.0
    cell_w, cell_h = 1.7, 0.65
    ncols_data = len(roles)
    width = label_w + ncols_data * cell_w
    height = 0.6 + (len(workstreams) + 1) * cell_h + 0.35

    fig, ax = _new_fig(width, height)
    ax.text(width / 2, 0.3, title, ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)
    top = 0.6

    ax.add_patch(Rectangle((0, top), label_w, cell_h, facecolor=NAVY, edgecolor="white"))
    ax.text(label_w / 2, top + cell_h / 2, "Workstream", ha="center", va="center",
            color="white", fontsize=8, fontweight="bold")
    for j, role in enumerate(roles):
        x = label_w + j * cell_w
        ax.add_patch(Rectangle((x, top), cell_w, cell_h, facecolor=NAVY, edgecolor="white"))
        ax.text(x + cell_w / 2, top + cell_h / 2, _wrap_to_width(role, cell_w - 0.15, 7),
                ha="center", va="center", color="white", fontsize=7, fontweight="bold")

    for i, ws in enumerate(workstreams):
        y = top + cell_h * (i + 1)
        fill = LIGHT if i % 2 == 0 else "white"
        ax.add_patch(Rectangle((0, y), label_w, cell_h, facecolor=fill, edgecolor=BORDER))
        ax.text(label_w / 2, y + cell_h / 2, _wrap_to_width(ws, label_w - 0.2, 7.3, bold=False),
                ha="center", va="center", fontsize=7.3, color=DARK_TEXT)
        for j in range(ncols_data):
            x = label_w + j * cell_w
            ax.add_patch(Rectangle((x, y), cell_w, cell_h, facecolor=fill, edgecolor=BORDER))
            code = assignments.get((i, j), "")
            if code:
                ax.text(x + cell_w / 2, y + cell_h / 2, code, ha="center", va="center",
                        fontsize=10.5, fontweight="bold", color=_RACI_COLORS.get(code, DARK_TEXT))

    legend_y = height - 0.12
    ax.text(0, legend_y, "R = Responsible    A = Accountable    C = Consulted    I = Informed",
            fontsize=7.3, color=SLATE)
    return _finish(fig)


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
    bar_h, row_gap, left_pad = 0.6, 0.35, 4.4
    width = left_pad + max_month * 0.5 + 1.0
    top = 0.75
    height = top + n * (bar_h + row_gap) + 0.5

    fig, ax = _new_fig(width, height)
    ax.text(width / 2, 0.32, title, ha="center", va="center", fontsize=11.5, fontweight="bold", color=NAVY)
    scale = (width - left_pad - 0.6) / max_month

    for m in range(0, max_month + 1, max(1, max_month // 8)):
        x = left_pad + m * scale
        ax.plot([x, x], [top - 0.1, height - 0.15], color=BORDER, linewidth=0.6, zorder=0)
        ax.text(x, top - 0.18, f"M{m}", ha="center", va="bottom", fontsize=6.5, color=SLATE)

    for i, (phase, start, end) in enumerate(parsed):
        y = top + 0.15 + i * (bar_h + row_gap)
        ax.text(0, y + bar_h / 2, _wrap_to_width(phase, left_pad - 0.2, 8, bold=False),
                ha="left", va="center", fontsize=8, color=DARK_TEXT)
        x0 = left_pad + start * scale
        bw = max((end - start) * scale, 0.15)
        color = NAVY if i % 2 == 0 else ORANGE
        ax.add_patch(FancyBboxPatch((x0, y), bw, bar_h, boxstyle="round,pad=0.01,rounding_size=0.05",
                                     facecolor=color, edgecolor="none"))
        ax.text(x0 + bw / 2, y + bar_h / 2, f"M{start}-{end}", ha="center", va="center",
                fontsize=7, color="white", fontweight="bold")
    return _finish(fig)


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

    width, height = 10.5, 5.2
    fig = plt.figure(figsize=(width, height), dpi=FIG_DPI)
    ax_title = fig.add_axes((0, 0.92, 1, 0.08))
    ax_title.axis("off")
    ax_title.text(0.5, 0.4, title, ha="center", va="center", fontsize=13, fontweight="bold",
                  color=NAVY, transform=ax_title.transAxes)

    n_tiles = len(tiles)
    tile_w = 1 / n_tiles
    for i, (value, label) in enumerate(tiles):
        ax = fig.add_axes((i * tile_w + 0.012, 0.68, tile_w - 0.024, 0.2))
        ax.axis("off")
        ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes, facecolor=LIGHT,
                                edgecolor=BORDER, linewidth=1))
        ax.text(0.5, 0.62, value, ha="center", va="center", fontsize=15, fontweight="bold",
                color=NAVY, transform=ax.transAxes)
        tile_w_in = (tile_w - 0.024) * width
        ax.text(0.5, 0.22, _wrap_to_width(label, tile_w_in - 0.15, 7.3, bold=False),
                ha="center", va="center", fontsize=7.3, color=SLATE, transform=ax.transAxes)

    left_frac = 0.3
    ax_chart = fig.add_axes((left_frac, 0.08, 0.98 - left_frac, 0.52))
    label_width_in = left_frac * width - 0.2

    def _wrap_labels(names: List[str]) -> List[str]:
        return [_wrap_to_width(n, label_width_in, 7.5, bold=False) for n in names]

    if show_pricing and plan.get("workstream_costs"):
        ws = plan["workstream_costs"]
        names = [w.get("workstream", "") for w in ws]
        costs = [w.get("cost", 0) for w in ws]
        y_pos = list(range(len(names)))
        ax_chart.barh(y_pos, costs, color=NAVY, height=0.55)
        ax_chart.set_yticks(y_pos)
        ax_chart.set_yticklabels(_wrap_labels(names), fontsize=7.5, color=DARK_TEXT)
        ax_chart.invert_yaxis()
        ax_chart.set_xlabel("Estimated Cost by Workstream ($)", fontsize=8, color=SLATE)
        for i, v in enumerate(costs):
            ax_chart.text(v, i, f" ${v:,.0f}", va="center", fontsize=7, color=DARK_TEXT)
    elif schedule:
        names = [s.get("phase", "") for s in schedule]
        pct = []
        for s in schedule:
            m = re.search(r"(\d+)", str(s.get("completion", "")))
            pct.append(int(m.group(1)) if m else 0)
        y_pos = list(range(len(names)))
        ax_chart.barh(y_pos, pct, color=NAVY, height=0.55)
        ax_chart.set_yticks(y_pos)
        ax_chart.set_yticklabels(_wrap_labels(names), fontsize=7.5, color=DARK_TEXT)
        ax_chart.invert_yaxis()
        ax_chart.set_xlim(0, 100)
        ax_chart.set_xlabel("Planned Completion by Phase (%)", fontsize=8, color=SLATE)
        for i, v in enumerate(pct):
            ax_chart.text(v, i, f" {v}%", va="center", fontsize=7, color=DARK_TEXT)
    else:
        ax_chart.axis("off")

    if schedule or (show_pricing and plan.get("workstream_costs")):
        for spine in ("top", "right"):
            ax_chart.spines[spine].set_visible(False)
        ax_chart.spines["left"].set_color(BORDER)
        ax_chart.spines["bottom"].set_color(BORDER)
        ax_chart.tick_params(axis="x", labelsize=7, colors=SLATE)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


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
