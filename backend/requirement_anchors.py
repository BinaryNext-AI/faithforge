"""Deterministic, non-AI scanner for submittal-obligation language.

See extraction_rebuild_spec.md section 1. The AI extraction pass routinely
misses real requirements on long documents and occasionally invents ones that
never appear in the source. This module gives the pipeline a code-side,
regex-based memory of "every place this document literally says the offeror
must submit something" so those locations can be (a) fed to the model as
things it must account for, and (b) checked afterward for silent misses.

Pure functions only — no network calls, no external state, fully
unit-testable. Every HIGH pattern below was hand-verified against the real
WSSC Solicitation 107585 text (see ami_ground_truth.md in the project
scratchpad).
"""

import re
from typing import Any, Dict, List, Tuple

from checklist_keywords import CHECKLIST_KEYWORD_CATEGORIES

# ─── HIGH strength patterns ──────────────────────────────────────────────────
# Near-certain submittal signals. Case-insensitive.
_HIGH_PATTERN_SOURCES: List[str] = [
    r"\*\s*response required",
    r"required with all proposals",
    # Headings/rows of an explicit submittal table, e.g. MDOT's
    # "TABLE A - Attachments and Documents Required with the Proposal".
    r"(attachments?|documents?)[^\n]{0,40}required with the (proposal|bid)",
    r"documents? and information required",
    r"\b(shall|must)\s+(submit|provide|include|contain|furnish|attach|complete|upload)\b",
    r"failure to (submit|provide)",
    r"non-?responsive",
    r"(may|will) be (rejected|deemed)",
    r"please (upload|download)",
    r"complete and (submit|return)",
    r"completed and signed",
    r"duly executed",
    r"authorized signatures?",
    r"\bappendix\s+[a-z0-9]\b",
    r"\battachment\s+[a-z0-9]\b",
    r"\bexhibit\s+[a-z0-9]\b",
    # "Tab A"/"Tab 1" both occur — requiring a digit missed MDOT's entire
    # Tab A-Q proposal structure, which IS that solicitation's checklist.
    r"\btab\s+[a-z0-9]\b",
    r"[☐☑✓]",  # ☐ ☑ ✓
]
_HIGH_PATTERNS: List[Tuple[str, "re.Pattern"]] = [
    (src, re.compile(src, re.IGNORECASE)) for src in _HIGH_PATTERN_SOURCES
]

# ─── MEDIUM strength phrases ──────────────────────────────────────────────────
# Any multi-word (>= 2 words) phrase from the shared 13-category keyword
# library (imported, never retyped). Single-word keywords ("forms", "budget",
# "references") are deliberately excluded — they false-positive constantly.
_MEDIUM_PHRASES: List[str] = sorted(
    {
        phrase.lower()
        for keywords in CHECKLIST_KEYWORD_CATEGORIES.values()
        for phrase in keywords
        if len(phrase.split()) >= 2
    },
    key=len,
    reverse=True,
)


def scan_requirement_anchors(text: str) -> List[Dict[str, Any]]:
    """Every location in `text` that literally signals a submittal obligation.

    Returns one entry per matching line (deduped — one anchor per line, with
    `patterns` accumulating every pattern that hit it), sorted by offset:
    {"offset": int, "line_no": int, "line": str, "patterns": [str], "strength": "high"|"medium"}
    """
    if not text:
        return []

    lines = text.split("\n")
    offsets: List[int] = []
    running = 0
    for line in lines:
        offsets.append(running)
        running += len(line) + 1  # + the '\n' this split() consumed

    anchors: List[Dict[str, Any]] = []
    for line_no, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        matched_patterns: List[str] = []
        strength = None

        for pattern_src, regex in _HIGH_PATTERNS:
            if regex.search(raw_line):
                matched_patterns.append(pattern_src)
                strength = "high"

        for phrase in _MEDIUM_PHRASES:
            if phrase in lowered:
                matched_patterns.append(phrase)
                if strength != "high":
                    strength = "medium"

        if matched_patterns:
            anchors.append({
                "offset": offsets[line_no],
                "line_no": line_no,
                "line": stripped,
                "patterns": matched_patterns,
                "strength": strength,
            })

    anchors.sort(key=lambda a: a["offset"])
    return anchors


def render_anchors_for_prompt(anchors: List[Dict[str, Any]], start: int, end: int) -> str:
    """Anchors whose offset falls in [start, end) as numbered `line N: <text>`
    lines, capped at 120 lines (all HIGH anchors kept before any MEDIUM ones
    if capping is needed)."""
    in_range = [a for a in anchors if start <= a["offset"] < end]
    if not in_range:
        return "(none flagged in this excerpt)"

    highs = [a for a in in_range if a["strength"] == "high"]
    meds = [a for a in in_range if a["strength"] != "high"]
    ordered = (highs + meds)[:120]

    return "\n".join(f"line {a['line_no']}: {a['line']}" for a in ordered)
