import json
import logging
import time as _time
from typing import Dict, Any, Optional
from groq import Groq
from config import settings
from datetime import datetime

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)
    logger.propagate = False

MODEL = "llama-3.1-70b-versatile"

PACKET_SYSTEM = """You are a professional proposal writer for FaithForge Technologies & Consulting LLC — an independent, vendor-neutral program management and consulting firm.

FaithForge Core Services: Independent PMO & Governance, Project/Program Management, Training & Workforce Development, Curriculum Design, Grants Management, Technical Writing, Management Consulting, AI-Enabled Reporting, Digital Transformation, Nonprofit/Education/Healthcare support, DEI Consulting, Capacity Building, Organizational Readiness & Change Management (ADKAR-certified).

Target Markets: Maryland/DC area government agencies, nonprofits, educational institutions, healthcare organizations, federal agencies.

Primary Contact: Bernedette Atong, PMP, PgMP — Founder & CEO | 410-862-2975 | info@faithforgetech.com | www.faithforgetech.com

Standard Labor Rates:
- Executive Program Director (PMP, PgMP): $225/hr
- Domain/Industry Strategic Consultant: $250/hr
- Senior Program Manager: $185/hr
- ADKAR Certified Change Management Director: $185/hr
- PMO Manager: $135/hr
- Stakeholder Engagement Lead: $125/hr
- Risk & Performance Manager: $135/hr
- Governance Analyst: $105/hr
- Data & Reporting Analyst: $105/hr
- Project Coordinator: $75/hr

Tone: Executive, professional, no contractions. FaithForge is always the "independent, vendor-neutral" partner protecting the CLIENT's interests. Emphasize governance, accountability, executive visibility, AI-enabled program controls, organizational readiness, and benefits realization.

Key phrases to use naturally: "independent, vendor-neutral", "protect [client]'s interests", "governance-first", "disciplined program execution", "executive visibility", "benefits realization", "AI-enabled program controls", "ADKAR-certified change management"."""

# ── Stage 1: Planner — builds the consistent skeleton (structure + budget math) ──
PLAN_PROMPT = """You are planning a FaithForge proposal. Analyze the opportunity and solicitation, then design a complete, internally-consistent proposal plan.

## OPPORTUNITY DATA
{opportunity_data}

## SOLICITATION DOCUMENT EXCERPT
{document_content}
{custom_block}

Decide the engagement structure and ALL budget numbers so every later section is consistent. Pick a realistic engagement length and labor hours that produce a sensible total contract value for this opportunity's scale.

Return ONLY a valid JSON object (no prose) with this schema:
{{
  "title": "<the opportunity title>",
  "subtitle": "Independent PMO | Governance Oversight | <Domain> Advisory",
  "proposal_type": "<one-line description of FaithForge's offering>",
  "client_name": "<agency/client name>",
  "domain": "<the domain, e.g. Utility Transformation, Education and Training>",
  "engagement_months": <integer>,
  "named_consultant": {{
    "name": "<full name of a plausible senior domain consultant>",
    "title": "<their title, e.g. Senior Utility Strategic Consultant & AMI Advisor>",
    "years": "<e.g. 20+>",
    "expertise": ["<6-9 industry expertise bullets>"],
    "bio": "<2 sentence factual-sounding background relevant to this domain>"
  }},
  "workstreams": [
    {{"name":"<workstream/phase name>","objective":"<1 sentence>","timeframe":"Months X-Y"}}
  ],
  "deliverable_products": [{{"name":"<deliverable>","desc":"<1 sentence>"}}],
  "schedule": [{{"timeline":"Months X-Y","phase":"<phase>","deliverables":"<key deliverables>","completion":"<%>"}}],
  "labor": [{{"role":"<role>","rate":<int $/hr>,"hours":<int>,"cost":<int = rate*hours>}}],
  "supporting_costs": [{{"category":"<category>","amount":<int>}}],
  "workstream_costs": [{{"workstream":"<name>","roles":"<primary roles>","timeframe":"Months X-Y","cost":<int>}}],
  "optional_services": [{{"service":"<name>","roles":"<roles>","hours":<int>,"cost":<int>,"desc":"<2 sentence description>"}}]
}}

Requirements:
- Include 5-7 workstreams/phases covering mobilization/governance, planning/readiness, oversight/execution, organizational readiness/change, customer/stakeholder engagement, go-live/benefits realization (adapt names to the domain).
- Include 8-12 deliverable_products.
- "labor" MUST include these 10 roles with these rates: Executive Program Director $225, Domain Strategic Consultant $250, Senior Program Manager $185, ADKAR Certified Change Management Director $185, PMO Manager $135, Stakeholder Engagement Lead $125, Risk & Performance Manager $135, Governance Analyst $105, Data & Reporting Analyst $105, Project Coordinator $75. Choose realistic hours scaled to this opportunity.
- 4-5 supporting_costs (PMO Tools & Reporting Platform, Executive Workshops & Governance Facilitation, Travel & Onsite Support, Administrative & Quality Assurance Support).
- 4-5 optional_services.

CRITICAL: Every numeric field must be a single final integer literal (e.g. 162000). NEVER write arithmetic expressions like "100 + 200". Do not include any total fields — totals are computed separately."""

# ── Stage 2: Section writers — each expands the plan into rich, submission-ready prose ──
HEADER_BRIEF_PROMPT = """Using the proposal PLAN and compliance data below, write the proposal title block and the INTERNAL DECISION BRIEF in markdown. Be specific and substantive.

## PROPOSAL PLAN (JSON)
{plan}

## COMPLIANCE & OPPORTUNITY DATA
{compliance}
{custom_block}

Output EXACTLY this markdown structure:

# REQUEST FOR PROPOSAL RESPONSE

# {{title}}
## {{subtitle}}

| Field | Response |
|-------|----------|
| Submitted by | FaithForge Technologies & Consulting LLC |
| Primary Contact | Bernedette Atong, PMP, PgMP — Founder & Chief Executive Officer |
| Phone | 410-862-2975 |
| Email / Website | info@faithforgetech.com \\| www.faithforgetech.com |
| Proposal Type | {{proposal_type}} |

*Prepared for {{client_name}}*

---

## SECTION 0: INTERNAL DECISION BRIEF
*FaithForge internal use only — remove this section before any external submission.*

### 0.1 Bid / No-Bid Recommendation
[BID / NO-BID / BID WITH CONDITIONS + a full paragraph of justification]

### 0.2 FaithForge Fit Analysis
[2-3 sentences]

### 0.3 Compliance & Required-Documents Checklist
[Use "- [ ]" checklist items — every form, registration, certification, and submission requirement from the compliance data. Flag any FaithForge may not currently hold.]

### 0.4 Key Risks
[4-6 bullets]

### 0.5 Questions for the Agency
[3-5 numbered clarifying questions]

### 0.6 Due-Date Tracker
| Milestone | Date |
|-----------|------|
[questions deadline, pre-bid/conference, submission due date — use real dates from the data or "TBD"]

### 0.7 Recommended Internal Owner & Next Steps
[Recommended owner + 3-5 numbered next steps with timing]

Replace {{placeholders}} with real values from the plan. Output only the markdown."""

SECTION1_PROMPT = """Write SECTION 1: EXECUTIVE SUMMARY of the FaithForge proposal in rich, executive markdown prose. Use the plan for consistency.

## PROPOSAL PLAN (JSON)
{plan}
{custom_block}

Output this structure (each subsection must be 2-3 substantial paragraphs of specific, non-generic prose adapted to {client_hint}):

## SECTION 1: EXECUTIVE SUMMARY

[Opening: 2-3 paragraphs — what the opportunity is, why FaithForge is the right independent/vendor-neutral partner, and how FaithForge frames its role protecting the client's interests. Distinguish FaithForge's governance/oversight role from any implementation vendor.]

### 1.2 Understanding {client_hint}'s Vision
[2 paragraphs showing deep comprehension of the client's goals, challenges, and what success looks like.]

### 1.3 FaithForge's {domain_hint} Philosophy
[Core principle paragraphs. Include an italicized positioning line beginning "*FaithForge {domain_hint} Positioning:*" followed by key value props separated by em dashes.]

### 1.4 FaithForge Commitment
[A specific closing pledge paragraph for this engagement.]

### 1.5 FaithForge Advisory Team
[3-4 paragraphs describing the team: Bernedette Atong as Executive Program Director; the named domain consultant from the plan (use their real name, title, and 20+ years experience); an ADKAR-certified Change Management Strategist. Explain what each brings.]

Output only the markdown. No contractions. Executive tone."""

SECTION2_PROMPT = """Write SECTION 2: PROPOSED SCOPE OF WORK of the FaithForge proposal in rich markdown. Expand the plan's workstreams into a full phased scope.

## PROPOSAL PLAN (JSON)
{plan}
{custom_block}

Output this structure:

## SECTION 2: PROPOSED SCOPE OF WORK

### 2.1 Approach and Methodology
[2 paragraphs on FaithForge's structured, phased, deliverable-driven approach for this engagement.]

[Then for the first 2-3 workstreams, write a "#### 2.1.N <Workstream Name>" subsection — each with a descriptive paragraph and a bullet list of capabilities/activities.]

[Then for EACH workstream in the plan, write a phase block. Generate 5-6 specific activity bullets and 3-5 key deliverables for each, based on the workstream name and objective:]
**Phase N: <Phase Name>**
Objective: <objective>
- <activity bullets>
Key Deliverables: <comma-separated deliverables>

| Activity Area | FaithForge Responsibilities | {client_hint} Value |
|--------------|----------------------------|----------------|
| <area> | <what FaithForge does> | <benefit> |
[2-4 rows per phase]

### 2.2 Deliverable Products
| Deliverable | Description |
|-------------|-------------|
[one row per deliverable_product in the plan — 8-12 rows]

### 2.3 Implementation Schedule and Progress Milestones
| Timeline | Phase & Activities | Key Deliverables | Completion |
|----------|--------------------|------------------|------------|
[one row per schedule entry in the plan]

Output only the markdown. Be specific and detailed. No contractions."""

SECTION3_PROMPT = """Write SECTION 3: GENERAL BACKGROUND OF APPLICANT VENDOR of the FaithForge proposal in rich markdown. Use the plan.

## PROPOSAL PLAN (JSON)
{plan}
{custom_block}

Output this structure:

## SECTION 3: GENERAL BACKGROUND OF APPLICANT VENDOR

### 3.1 {domain_hint} & Program Governance Experience
[2-3 paragraphs + a bullet list of relevant experience areas.]

### 3.2 References
[Short paragraph — available upon request, including references for the named subcontractor/consultant.]

### 3.3 Experience with Governance, PMO, and {domain_hint} Programs
[Intro line + 5-6 capability bullets.]

### 3.4 Knowledge of Organizational Change, Customer/Stakeholder Adoption, and Readiness
[2 paragraphs emphasizing ADKAR-certified change management.]

### 3.5 Experience with Program Controls, Data Assessment, and Executive Reporting
[Intro line + 6-7 bullets including AI-enabled reporting.]

### 3.6 Key Personnel and Team Structure
| Key Role | Responsibilities |
|----------|-----------------|
[one row per role in the plan's "labor" list. The Executive Program Director row must read "Executive Program Director — Bernedette Atong, PMP, PgMP". The Domain Strategic Consultant row must use the named_consultant's name. Each responsibility = 1-2 sentences specific to this engagement.]

**FaithForge Proposed Team Governance Model**

| Governance Layer | Purpose |
|-----------------|---------|
| {client_hint} Executive Sponsors | Provide strategic direction, decision authority, and executive oversight. |
| FaithForge Executive Program Director | Primary executive advisor and Independent PMO lead. |
[3-4 more layers]

### 3.7 {domain_hint} Consultant Profile
[Use the named_consultant from the plan. Format:]
**<name>**
*<title>*
**Years of Experience: <years>**
**Industry Expertise:**
- <expertise bullets>
**Relevant Experience:**
[2 paragraph narrative bio based on the plan's bio, ending with their role on this engagement.]

Output only the markdown. No contractions."""

SECTION4_PROMPT = """Write SECTION 4: BUDGET DESCRIPTION of the FaithForge proposal in rich markdown. Use the EXACT numbers from the plan — do not invent new numbers; every total must match the plan.

## PROPOSAL PLAN (JSON)
{plan}
{custom_block}

Output this structure:

## SECTION 4: BUDGET DESCRIPTION

### 4.1 Staffing Classifications and Labor Rates
| Labor Category | Proposed Rate |
|----------------|---------------|
[one row per role in plan.labor: role | $rate/hr]

**Labor Hour Assumptions**
| Labor Category | Hours | Rate | Cost |
|----------------|-------|------|------|
[one row per role: role | hours | $rate | $cost]
| **Total Direct Labor** | | | **${direct_labor_total}** |

**Supporting Costs**
| Cost Category | Amount |
|---------------|--------|
[one row per supporting cost]
| **Total Base Services** | **${base_total}** |

### 4.1.1 Basis of Estimate
[2 paragraphs on the staffing model and rationale.]

### 4.2 Program Management Services Pricing Strategy
[2 paragraphs on the value delivery model.]

**Base Services Total:**
| Cost Component | Amount |
|----------------|--------|
| Direct Labor | ${direct_labor_total} |
[supporting cost rows]
| **Total Base Services** | **${base_total}** |

### 4.3 Cost by Workstream and Total Potential Contract Value
| Workstream | Primary Roles | Timeframe | Estimated Cost |
|------------|---------------|-----------|----------------|
[one row per plan.workstream_costs]

**Supporting Cost Category**
| Supporting Cost Category | Estimated Cost |
|--------------------------|----------------|
[supporting cost rows]

**Base Services Total: ${base_total}**

**Optional Services**
| Optional Service | Primary Roles | Estimated Cost |
|-----------------|---------------|----------------|
[one row per optional service]

### 4.3.1 Optional Service Labor Assumptions
| Optional Service | Estimated Hours |
|-----------------|-----------------|
[one row per optional service]
| Total Optional Hours | <sum> Hours |

**Optional Services Description**
[For each optional service: a bold title with its price, then the 2-sentence description from the plan.]

**Pricing Summary**
| Category | Amount |
|----------|--------|
| Direct Labor | ${direct_labor_total} |
[supporting cost rows]
| Base Services Total | ${base_total} |
| Optional Services Total | ${optional_total} |
| **Total Potential Contract Value** | **${total_value}** |

### 4.4 Plans for Subcontracting and Specialized Advisory Support
[1-2 paragraphs on managing the named consultant/subcontractor under FaithForge's direct management.]

Output only the markdown. No contractions."""


def format_opportunity_context(opp: Dict[str, Any]) -> str:
    lines = []
    fields = [
        ("Title", "opportunity_title"),
        ("Agency", "agency_name"),
        ("Solicitation #", "solicitation_number"),
        ("Contract Type", "contract_type"),
        ("Estimated Value", "estimated_value"),
        ("Due Date", "due_date"),
        ("Pre-Bid Date", "pre_bid_date"),
        ("Submission Method", "submission_method"),
        ("Contact Person", "contact_person"),
        ("Contact Email", "contact_email"),
        ("Website", "website_link"),
        ("EMMA Link", "emma_link"),
        ("Summary", "opportunity_summary"),
        ("Required Services", "required_services"),
        ("FaithForge Alignment", "faithforge_alignment"),
        ("Recommended Action", "recommended_action"),
        ("Risk Concerns", "risk_concerns"),
        ("Classification", "relevance_classification"),
        ("Reasoning", "classification_reasoning"),
    ]
    for label, key in fields:
        val = opp.get(key)
        if val:
            lines.append(f"{label}: {val}")
    return "\n".join(lines)


def _compliance_context(opp: Dict[str, Any]) -> str:
    """Compact compliance/submission data for the decision brief."""
    lines = []
    fields = [
        ("Title", "opportunity_title"), ("Agency", "agency_name"),
        ("Solicitation #", "solicitation_number"), ("Due Date", "due_date"),
        ("Questions Deadline", "questions_deadline"), ("Pre-Bid Date", "pre_bid_date"),
        ("Submission Method", "submission_method"), ("Summary", "opportunity_summary"),
        ("Eligibility", "eligibility_requirements"), ("Required Qualifications", "required_qualifications"),
        ("Required Forms", "required_forms"), ("Submission Checklist", "submission_checklist"),
        ("Certifications", "certifications_required"), ("Insurance", "insurance_requirements"),
        ("Compliance", "compliance_requirements"), ("Pricing", "pricing_requirements"),
        ("Required Attachments", "required_attachments"), ("Disqualifiers", "disqualifying_requirements"),
        ("Risk Concerns", "risk_concerns"),
    ]
    for label, key in fields:
        val = opp.get(key)
        if val:
            lines.append(f"{label}: {val}")
    return "\n".join(lines) or "No compliance data extracted."


def _groq_chat(client, system: str, user: str, max_tokens: int, retries: int = 4,
               json_mode: bool = False, label: str = "groq_call") -> str:
    """Single Groq call with TPM-aware trimming and rate-limit backoff."""
    import re as _re
    from ai_screener import fit_prompt_to_budget
    user = fit_prompt_to_budget(system, user, max_tokens)
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    last_err = None
    for attempt in range(retries):
        t0 = _time.monotonic()
        try:
            logger.info("[packet:%s] attempt %d/%d — max_tokens=%d prompt_chars=%d",
                        label, attempt + 1, retries, max_tokens, len(user))
            resp = client.chat.completions.create(
                model=MODEL,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                **kwargs,
            )
            content = resp.choices[0].message.content or ""
            elapsed = _time.monotonic() - t0
            usage = getattr(resp, "usage", None)
            usage_str = (f"in={usage.prompt_tokens} out={usage.completion_tokens}"
                         if usage else "usage=unknown")
            logger.info("[packet:%s] OK in %.1fs — %s — response_chars=%d",
                        label, elapsed, usage_str, len(content))
            return content
        except Exception as e:
            elapsed = _time.monotonic() - t0
            last_err = e
            msg = str(e)
            if "rate_limit" in msg or "Request too large" in msg or "429" in msg or "tokens per minute" in msg:
                m = _re.search(r"try again in ([\d.]+)s", msg)
                wait = float(m.group(1)) + 1 if m else min(20 * (attempt + 1), 60)
                logger.warning("[packet:%s] rate-limit hit after %.1fs (attempt %d) — waiting %.1fs: %s",
                               label, elapsed, attempt + 1, wait, msg[:200])
                _time.sleep(wait)
                continue
            logger.exception("[packet:%s] non-retryable error after %.1fs (attempt %d): %s",
                             label, elapsed, attempt + 1, msg[:300])
            raise
    logger.error("[packet:%s] all %d attempts exhausted. Last error: %s", label, retries, str(last_err)[:300])
    raise last_err


def build_packet(
    opportunity: Dict[str, Any],
    document_texts: list[str],
    custom_instructions: str = "",
) -> Dict[str, Any]:
    """
    Multi-pass proposal generation for WSSC-grade depth:
      1) Planner call builds a consistent skeleton (structure + budget math).
      2) Five section-writer calls expand the plan into rich, submission-ready prose.
    Each call stays within the model's per-request token budget; rate limits are
    retried with backoff so this also works on the Groq free tier (just slower).
    """
    from ai_screener import doc_char_budget
    client = Groq(api_key=settings.GROQ_API_KEY)
    opp_context = format_opportunity_context(opportunity)
    compliance = _compliance_context(opportunity)
    doc_content = "\n\n---\n\n".join(document_texts) if document_texts else "No documents uploaded."

    custom_block = ""
    if custom_instructions and custom_instructions.strip():
        custom_block = (
            f"\n\n## ADDITIONAL INSTRUCTIONS FROM USER\n{custom_instructions.strip()}"
            "\n\nFollow these instructions carefully throughout."
        )

    opp_title = opportunity.get("opportunity_title") or opportunity.get("email_subject") or f"opp#{opportunity.get('id','?')}"
    logger.info("[packet] starting build for: %s", opp_title)
    t_start = _time.monotonic()

    # ── Stage 1: Plan ────────────────────────────────────────────────────────
    logger.info("[packet] stage 1/6: planner")
    plan_tokens = 5000
    plan_overhead = PLAN_PROMPT.format(opportunity_data=opp_context, document_content="", custom_block=custom_block)
    max_doc_chars = doc_char_budget(PACKET_SYSTEM, plan_overhead, plan_tokens)
    plan_doc = doc_content[:max_doc_chars]
    plan_raw = _groq_chat(
        client, PACKET_SYSTEM,
        PLAN_PROMPT.format(opportunity_data=opp_context, document_content=plan_doc, custom_block=custom_block),
        max_tokens=plan_tokens, json_mode=True, label="plan",
    )
    plan = _extract_json(plan_raw) or {}
    if not plan.get("labor"):
        logger.error("[packet] planner returned invalid plan. raw response (first 500 chars): %s", plan_raw[:500])
        raise RuntimeError("Proposal planner did not return a valid budget plan. Please rebuild the packet.")
    _compute_totals(plan)
    plan_json = json.dumps(plan, indent=1)
    logger.info("[packet] plan OK — %d workstreams, %d labor rows, total_value=$%s",
                len(plan.get("workstreams", [])), len(plan.get("labor", [])),
                f"{plan.get('total_value', 0):,}")

    client_hint = plan.get("client_name") or opportunity.get("agency_name") or "the Agency"
    domain_hint = plan.get("domain") or "Program Management"

    fmt = {
        "plan": plan_json,
        "custom_block": custom_block,
        "client_hint": client_hint,
        "domain_hint": domain_hint,
        "compliance": compliance,
        "direct_labor_total": f"{plan.get('direct_labor_total', 0):,}",
        "base_total": f"{plan.get('base_total', 0):,}",
        "optional_total": f"{plan.get('optional_total', 0):,}",
        "total_value": f"{plan.get('total_value', 0):,}",
    }

    # ── Stage 2: Sections ────────────────────────────────────────────────────
    SECTION_LABELS = [
        ("header+brief", HEADER_BRIEF_PROMPT, 2500),
        ("section1-exec-summary", SECTION1_PROMPT, 3000),
        ("section2-scope", SECTION2_PROMPT, 4500),
        ("section3-background", SECTION3_PROMPT, 4000),
        ("section4-budget", SECTION4_PROMPT, 4000),
    ]

    parts = []
    for i, (label, prompt_tmpl, max_tokens) in enumerate(SECTION_LABELS, start=2):
        logger.info("[packet] stage %d/6: %s", i, label)
        result = _groq_chat(client, PACKET_SYSTEM, _safe_format(prompt_tmpl, fmt),
                            max_tokens=max_tokens, label=label)
        if not result or not result.strip():
            logger.warning("[packet] %s returned empty content — section will be omitted", label)
        else:
            logger.info("[packet] %s complete — %d chars", label, len(result))
        parts.append(result)

    non_empty = [p.strip() for p in parts if p and p.strip()]
    logger.info("[packet] all stages done in %.1fs — %d/%d sections have content",
                _time.monotonic() - t_start, len(non_empty), len(parts))
    if len(non_empty) < len(parts):
        missing = [SECTION_LABELS[i][0] for i, p in enumerate(parts) if not (p and p.strip())]
        logger.warning("[packet] missing sections: %s", ", ".join(missing))

    full_text = "\n\n---\n\n".join(non_empty)
    html_content = markdown_to_html(full_text)
    return {
        "content_json": json.dumps({"markdown": full_text, "plan": plan}),
        "html_content": html_content,
    }


def _safe_format(template: str, values: Dict[str, Any]) -> str:
    """Format only the known {keys}; leave any other braces untouched."""
    out = template
    for k, v in values.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def _int(v) -> int:
    try:
        return int(round(float(v)))
    except Exception:
        return 0


def _compute_totals(plan: Dict[str, Any]) -> None:
    """Recompute every cost in Python so the budget math is always correct."""
    # Each labor row: cost = rate * hours
    for row in plan.get("labor", []):
        row["rate"] = _int(row.get("rate"))
        row["hours"] = _int(row.get("hours"))
        row["cost"] = row["rate"] * row["hours"]
    for row in plan.get("supporting_costs", []):
        row["amount"] = _int(row.get("amount"))
    for row in plan.get("optional_services", []):
        row["cost"] = _int(row.get("cost"))
        row["hours"] = _int(row.get("hours"))
    direct = sum(r["cost"] for r in plan.get("labor", []))
    supporting = sum(r["amount"] for r in plan.get("supporting_costs", []))
    optional = sum(r["cost"] for r in plan.get("optional_services", []))
    plan["direct_labor_total"] = direct
    plan["supporting_total"] = supporting
    plan["base_total"] = direct + supporting
    plan["optional_total"] = optional
    plan["total_value"] = direct + supporting + optional


def _extract_json(text: str) -> Optional[dict]:
    import re as _re
    if not text:
        return None
    m = _re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except Exception:
        return None


def _inline_md(text: str) -> str:
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text


def _is_table_sep(line: str) -> bool:
    body = line.strip().strip('|')
    return bool(body) and all(set(c.strip()) <= set('-: ') and '-' in c for c in body.split('|'))


def _table_cells(line: str):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def markdown_to_html(text: str) -> str:
    try:
        import re
        lines = text.split('\n')
        output = []
        in_list = False
        i = 0

        def close_list():
            nonlocal in_list
            if in_list:
                output.append('</ul>')
                in_list = False

        while i < len(lines):
            line = lines[i]
            s = line.strip()

            # Table block: header row + separator
            if s.startswith('|') and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
                close_list()
                header = _table_cells(s)
                output.append('<table class="ff-table"><thead><tr>')
                output.extend(f'<th>{_inline_md(c)}</th>' for c in header)
                output.append('</tr></thead><tbody>')
                i += 2
                while i < len(lines) and lines[i].strip().startswith('|'):
                    cells = _table_cells(lines[i])
                    output.append('<tr>' + ''.join(f'<td>{_inline_md(c)}</td>' for c in cells) + '</tr>')
                    i += 1
                output.append('</tbody></table>')
                continue

            i += 1

            if re.match(r'^[-*] ', s):
                if not in_list:
                    output.append('<ul>')
                    in_list = True
                output.append(f'<li>{_inline_md(s[2:])}</li>')
                continue

            close_list()
            if s.startswith('#### '):
                output.append(f'<h4>{_inline_md(s[5:])}</h4>')
            elif s.startswith('### '):
                output.append(f'<h3>{_inline_md(s[4:])}</h3>')
            elif s.startswith('## '):
                output.append(f'<h2>{_inline_md(s[3:])}</h2>')
            elif s.startswith('# '):
                output.append(f'<h1>{_inline_md(s[2:])}</h1>')
            elif s == '---':
                output.append('<hr>')
            elif s:
                output.append(f'<p>{_inline_md(s)}</p>')

        close_list()
        html = '\n'.join(output)
        style = (
            '<style>'
            '.ff-table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px;}'
            '.ff-table th,.ff-table td{border:1px solid #d1d5db;padding:6px 10px;text-align:left;vertical-align:top;}'
            '.ff-table th{background:#1e3a8a;color:#fff;font-weight:600;}'
            '.ff-table tbody tr:nth-child(even){background:#f8fafc;}'
            '</style>'
        )
        return style + html
    except Exception:
        return f'<pre>{text}</pre>'
