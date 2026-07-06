import json
import logging
import time as _time
from typing import Dict, Any, Optional
from openai import OpenAI
from config import settings
from datetime import datetime

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)
    logger.propagate = False

MODEL = "gpt-4o-mini"

PACKET_FRAME = """You are a professional proposal writer for FaithForge Technologies & Consulting LLC — a minority-owned program management and consulting firm based in Elkridge, Maryland (Maryland/DC region).

{knowledge_base}

## Tone & Voice
Executive, professional, no contractions. FaithForge is a governance and execution partner, not a traditional consulting vendor — an advisor that helps leaders deliver, not one that advises from the sidelines. Use only the facts, metrics, and key phrases provided in the knowledge base above — do not invent statistics, credentials, or claims. Lean on the target-market pain points and buying triggers to tailor language to this specific client's sector."""


def build_packet_system() -> str:
    from knowledge import load_kb
    return PACKET_FRAME.format(knowledge_base=load_kb())

# ── Stage 1: Planner — builds the consistent skeleton (structure + budget math) ──
PLAN_PROMPT = """You are planning a FaithForge proposal. Analyze the opportunity and solicitation, then design a complete, internally-consistent proposal plan.

## OPPORTUNITY DATA
{opportunity_data}

## COMPLIANCE & SUBMISSION REQUIREMENTS (already extracted from the RFP — do not miss anything listed here)
{compliance}

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
- Include 8-12 deliverable_products. Every deliverable, report, plan, or document explicitly required by the RFP — whether named in the Required Forms, Required Attachments, Submission Checklist, or Evaluation Criteria above, or found in the solicitation excerpt — MUST appear as its own deliverable_products entry. Do not omit or merge any RFP-mandated deliverable into a generic catch-all line; name it explicitly (e.g. "Monthly Progress Report", "Risk Register", "Governance Charter") so nothing the RFP requires is missing from this list.
- "labor" MUST use FaithForge's real standard role rates: Program Director $220/hr, Principal Consultant $200/hr, Senior Consultant $185/hr, Project Manager $150/hr, Solution/Technical Architect $150/hr, Solution Developer $145/hr, OCM Specialist $100/hr, Business Analyst $98/hr, PMO Coordinator $95/hr, Administrative Support $65/hr. Select the subset of roles appropriate to this opportunity and choose realistic hours scaled to its size. Do not invent rates.
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
| Primary Contact | Bernedette Atong, PMP, PgMP — Founder & Principal Consultant |
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

[Opening: 2-3 paragraphs — what the opportunity is, why FaithForge is the right governance and execution partner, and how FaithForge frames its role helping the client deliver. Distinguish FaithForge's governance/oversight role from any implementation vendor.]

### 1.2 Understanding {client_hint}'s Vision
[2 paragraphs showing deep comprehension of the client's goals, challenges, and what success looks like.]

### 1.3 FaithForge's {domain_hint} Philosophy
[Core principle paragraphs. Include an italicized positioning line beginning "*FaithForge {domain_hint} Positioning:*" followed by key value props separated by em dashes.]

### 1.4 FaithForge Commitment
[A specific closing pledge paragraph for this engagement.]

### 1.5 FaithForge Advisory Team
[3-4 paragraphs describing the team: Bernedette Atong as Principal Consultant (PMP, PgMP); the named domain consultant from the plan (use their title and relevant senior experience without inventing a specific number of years); and an Organizational Change Management (OCM) specialist. Explain what each brings.]

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
[2-3 paragraphs. Open with FaithForge's identity: a governance and execution partner that installs structure, governance, and execution discipline where complexity and accountability intersect. Reference the 4-Tier engagement model. Then a bullet list of 5-6 relevant experience areas specific to this domain.]

### 3.2 Demonstrated Track Record
[2 paragraphs referencing FaithForge's proven results. Use ONLY the real engagements and metrics from the Case Studies section of the knowledge base (Amtrak, Inteleos, ASM Global, iHerb) — cite their actual figures; do not invent statistics. Tie the most relevant engagement(s) back to this specific opportunity's needs. Full references available upon request.]

### 3.3 Experience with Governance, PMO, and {domain_hint} Programs
[Intro sentence + 6-7 capability bullets. Draw from FaithForge's documented capabilities: PMO maturity audits; governance framework design; multi-stakeholder coordination; regulatory compliance and audit readiness; executive reporting and KPI dashboards; workflow automation; organizational change management (OCM). Adapt to domain.]

### 3.4 Knowledge of Organizational Change, Customer/Stakeholder Adoption, and Readiness
[2 paragraphs emphasizing organizational change management and stakeholder adoption. Reference FaithForge's documented execution model: assess execution risk → install governance and structure → enable teams with clarity and tools → transfer ownership and capability.]

### 3.5 Experience with Program Controls, Data Assessment, and Executive Reporting
[Intro line + 6-7 bullets including KPI reporting and dashboards, data quality and reporting integrity, executive dashboard cadence, RAID/risk registers, performance baselines, weekly status reporting.]

### 3.6 Key Personnel and Team Structure
| Key Role | Responsibilities |
|----------|-----------------|
[one row per role in the plan's "labor" list. The lead row must read "Principal Consultant — Bernedette Atong, MSc, PMP, PgMP". The Senior Consultant row must use the named_consultant's name. Each responsibility = 1-2 sentences specific to this engagement.]

**FaithForge Proposed Team Governance Model**

| Governance Layer | Purpose |
|-----------------|---------|
| {client_hint} Executive Sponsors | Provide strategic direction, decision authority, and executive oversight. |
| FaithForge Principal Consultant | Primary executive advisor and PMO lead — Bernedette Atong, MSc, PMP, PgMP. |
[3-4 more layers]

### 3.7 Founder & Principal Consultant Profile

**Bernedette Atong, MSc, PMP, PgMP**
*Founder & Principal Consultant — FaithForge Technologies & Consulting LLC*
**Years of Experience: 8+**
**Education:** MSc Information Technology | BBA | BSc Economics
**Certifications:** Project Management Professional (PMP) | Program Management Professional (PgMP) | Professional Scrum Master (PSM) | Lean Six Sigma | AI Prompting
**Industry Expertise:**
- Transportation & Digital Technology: Led cross-functional teams of 14+ members delivering complex digital initiatives; 12% client satisfaction improvement
- E-Commerce & Global Data: Managed end-to-end lifecycle of $12M unified data analytics platform; introduced PMBOK standards improving delivery predictability
- Food Produce & Procurement: Coordinated $16M annual procurement; implemented risk management procedures streamlining vendor negotiations
- Construction & Engineering: Strategic oversight of multidisciplinary infrastructure projects yielding $600k+ earnings; 40% savings on project costs
- Government & Healthcare: Compliance-focused governance across HIPAA, SOC2, and public-sector regulatory frameworks
**Relevant Experience:**
[2-paragraph narrative tying Bernedette's background directly to this engagement's domain and the client's specific challenges. End with her commitment to serve as Principal Consultant and engagement lead for this engagement.]

### 3.8 {domain_hint} Consultant Profile
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
        ("Evaluation Criteria", "evaluation_criteria"),
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


def _strip_code_fence(text: str) -> str:
    """Models occasionally wrap plain-markdown output in a ```markdown ... ```
    fence — strip it so the fence markers don't leak into the rendered proposal."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.split("\n")[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _openai_chat(client, system: str, user: str, max_tokens: int, retries: int = 4,
                 json_mode: bool = False, label: str = "openai_call") -> str:
    """Single OpenAI call with TPM-aware trimming and rate-limit backoff."""
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
            if not json_mode:
                content = _strip_code_fence(content)
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
            if ("rate_limit" in msg or "429" in msg or "tokens per minute" in msg
                    or "Request too large" in msg or "context_length_exceeded" in msg
                    or "maximum context length" in msg):
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
    retried with backoff.
    """
    from ai_screener import doc_char_budget
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    packet_system = build_packet_system()
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
    plan_overhead = PLAN_PROMPT.format(opportunity_data=opp_context, compliance=compliance, document_content="", custom_block=custom_block)
    max_doc_chars = doc_char_budget(packet_system, plan_overhead, plan_tokens)
    plan_doc = doc_content[:max_doc_chars]
    plan_raw = _openai_chat(
        client, packet_system,
        PLAN_PROMPT.format(opportunity_data=opp_context, compliance=compliance, document_content=plan_doc, custom_block=custom_block),
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
        result = _openai_chat(client, packet_system, _safe_format(prompt_tmpl, fmt),
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


REVISE_PROMPT = """## OPPORTUNITY CONTEXT
{opportunity_context}

Here is the current FaithForge proposal, in markdown:

## CURRENT PROPOSAL
{current_markdown}

## REQUESTED CHANGE
{instruction}

Apply this change and return the COMPLETE revised proposal in the exact same markdown structure (same headings, section numbering, and formatting conventions as the current proposal — headings with #/##/###, pipe tables for budget/labor, bullet lists). Do not drop any section that isn't affected by the requested change; only change what the instruction asks for. Use ONLY facts, figures, and phrasing available in the knowledge base above — do not invent statistics, credentials, rates, or claims not already present in the current proposal or the knowledge base. If the instruction asks for something the knowledge base cannot support (e.g. a rate or stat that doesn't exist), make the best faithful adjustment using only real data and note the limitation inline where relevant.

Output only the markdown. No contractions."""


def revise_packet(
    opportunity: Dict[str, Any],
    current_markdown: str,
    instruction: str,
) -> Dict[str, Any]:
    """Apply a single conversational revision instruction to an existing packet.

    Returns the same {content_json, html_content} shape as build_packet so the
    caller can store it as a new Packet row (natural versioning).
    """
    from ai_screener import doc_char_budget
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    packet_system = build_packet_system()
    opp_context = format_opportunity_context(opportunity)

    max_tokens = 6000
    overhead = REVISE_PROMPT.format(opportunity_context=opp_context, current_markdown="", instruction=instruction)
    max_md_chars = doc_char_budget(packet_system, overhead, max_tokens)
    md_for_prompt = current_markdown[:max_md_chars]

    logger.info("[packet] revise — instruction=%r markdown_chars=%d", instruction[:120], len(current_markdown))
    revised = _openai_chat(
        client, packet_system,
        REVISE_PROMPT.format(opportunity_context=opp_context, current_markdown=md_for_prompt, instruction=instruction),
        max_tokens=max_tokens, label="revise",
    )
    revised = revised.strip()
    if not revised:
        raise RuntimeError("Revision produced no content. Please try again.")

    html_content = markdown_to_html(revised)
    return {
        "content_json": json.dumps({"markdown": revised, "revision_instruction": instruction}),
        "html_content": html_content,
    }


ANALYZE_DRAFT_PROMPT = """You are analyzing an existing draft proposal against the opportunity's requirements, on behalf of FaithForge.

## OPPORTUNITY CONTEXT
{opportunity_context}

## COMPLIANCE & SUBMISSION REQUIREMENTS
{compliance}

## RFP / SOLICITATION EXCERPTS
{rfp_content}

## EXISTING DRAFT PROPOSAL
{draft_text}

Compare the draft against the requirements above and FaithForge's knowledge base (provided in the system prompt). Pay particular attention to the "Submission Checklist" line inside COMPLIANCE & SUBMISSION REQUIREMENTS — for each item on that checklist, check whether the draft already appears to contain or satisfy it. Return ONLY a valid JSON object (no prose) with this schema:
{{
  "strengths": ["specific things the draft already does well"],
  "gaps": ["specific requirements or claims the draft does not address or supports weakly"],
  "missing_sections": ["standard proposal sections absent from the draft, e.g. Budget, Team Background, Risk Management"],
  "compliance_risks": ["specific compliance/submission requirements the draft may fail to meet"],
  "recommendations": ["concrete, specific fixes — reference exact FaithForge facts (rates, credentials, case studies) that should be used to fill each gap"],
  "checklist_items_addressed": ["for each submission-checklist item the draft appears to already satisfy, one string in the form '<checklist item text> — <one-sentence evidence from the draft>'. Only include items you found real evidence for in the draft text — do not guess. Empty array if none found or no checklist exists."]
}}

IMPORTANT on checklist_items_addressed: this is a suggestion for a human to verify, not a final determination — never claim an item is satisfied unless the draft text actually contains it. When in doubt, leave it out of this list and mention it under "gaps" instead.

Be specific — cite exact requirements not addressed, and note anywhere the draft's numbers or claims are unsupported or should be replaced with FaithForge's real knowledge-base facts."""

COMPLETE_DRAFT_PROMPT = """Here is an opportunity's context, RFP content, and an existing DRAFT proposal (possibly partial or unpolished). Rewrite and complete this draft into a submission-ready FaithForge proposal.

## OPPORTUNITY CONTEXT
{opportunity_context}

## COMPLIANCE & SUBMISSION REQUIREMENTS
{compliance}

## RFP / SOLICITATION EXCERPTS
{rfp_content}

## EXISTING DRAFT PROPOSAL
{draft_text}

## GAP ANALYSIS (address every item below)
{analysis_json}
{custom_block}

Preserve everything in the draft that is already strong and submission-ready — do not discard good existing content. Fill every gap and missing section identified above using ONLY facts, figures, and phrasing available in FaithForge's knowledge base (rates, credentials, case studies, service tiers, boilerplate) — never invent statistics, credentials, or client results that are not in the knowledge base. Produce a complete, well-structured proposal in markdown: headings (#/##/###), pipe tables for budget/labor breakdowns, and bullet lists — consistent with FaithForge's standard proposal structure (title, executive summary, scope of work, team/background, budget).

Output only the markdown. No contractions."""


def complete_draft_packet(
    opportunity: Dict[str, Any],
    rfp_texts: list[str],
    draft_text: str,
    custom_instructions: str = "",
) -> Dict[str, Any]:
    """Analyze an existing draft proposal against the RFP + knowledge base, then
    complete/polish it into a submission-ready proposal.

    Two-stage: (1) JSON gap analysis, (2) completion pass that fills gaps using
    only knowledge-base facts. Returns the same {content_json, html_content}
    shape as build_packet, plus an "analysis" dict for the UI.
    """
    from ai_screener import doc_char_budget
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    packet_system = build_packet_system()
    opp_context = format_opportunity_context(opportunity)
    compliance = _compliance_context(opportunity)
    rfp_content = "\n\n---\n\n".join(rfp_texts) if rfp_texts else "No additional RFP documents uploaded."

    custom_block = ""
    if custom_instructions and custom_instructions.strip():
        custom_block = (
            f"\n\n## ADDITIONAL INSTRUCTIONS FROM USER\n{custom_instructions.strip()}"
            "\n\nFollow these instructions carefully throughout."
        )

    def _split_budget(overhead: str, max_tokens: int) -> tuple[str, str]:
        """Fit draft_text + rfp_content into the remaining char budget, giving
        the draft priority since it's the primary input being completed."""
        max_chars = doc_char_budget(packet_system, overhead, max_tokens)
        draft_budget = min(len(draft_text), max_chars * 2 // 3) or max_chars
        rfp_budget = max(max_chars - draft_budget, 0)
        return draft_text[:draft_budget], rfp_content[:rfp_budget]

    # ── Stage 1: Analysis ──
    analysis_tokens = 2000
    analysis_overhead = ANALYZE_DRAFT_PROMPT.format(
        opportunity_context=opp_context, compliance=compliance, rfp_content="", draft_text="",
    )
    draft_for_analysis, rfp_for_analysis = _split_budget(analysis_overhead, analysis_tokens)

    logger.info("[packet] complete-draft stage 1/2: analysis — draft_chars=%d rfp_chars=%d",
                len(draft_text), len(rfp_content))
    analysis_raw = _openai_chat(
        client, packet_system,
        ANALYZE_DRAFT_PROMPT.format(
            opportunity_context=opp_context, compliance=compliance,
            rfp_content=rfp_for_analysis, draft_text=draft_for_analysis,
        ),
        max_tokens=analysis_tokens, json_mode=True, label="complete-draft-analysis",
    )
    analysis = _extract_json(analysis_raw) or {
        "strengths": [], "gaps": [], "missing_sections": [],
        "compliance_risks": [], "recommendations": [], "checklist_items_addressed": [],
    }

    # ── Stage 2: Completion ──
    completion_tokens = 6000
    analysis_json = json.dumps(analysis, indent=1)
    completion_overhead = COMPLETE_DRAFT_PROMPT.format(
        opportunity_context=opp_context, compliance=compliance, rfp_content="",
        draft_text="", analysis_json=analysis_json, custom_block=custom_block,
    )
    draft_for_completion, rfp_for_completion = _split_budget(completion_overhead, completion_tokens)

    logger.info("[packet] complete-draft stage 2/2: completion")
    completed = _openai_chat(
        client, packet_system,
        COMPLETE_DRAFT_PROMPT.format(
            opportunity_context=opp_context, compliance=compliance,
            rfp_content=rfp_for_completion, draft_text=draft_for_completion,
            analysis_json=analysis_json, custom_block=custom_block,
        ),
        max_tokens=completion_tokens, label="complete-draft-completion",
    )
    completed = completed.strip()
    if not completed:
        raise RuntimeError("Draft completion produced no content. Please try again.")

    html_content = markdown_to_html(completed)
    return {
        "content_json": json.dumps({"markdown": completed, "analysis": analysis}),
        "html_content": html_content,
        "analysis": analysis,
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


def _normalize_row(cells: list, ncols: int) -> list:
    """Force a parsed row to the header's column count. A row can end up with
    extra cells when a table cell contains an unescaped literal '|' (e.g. an
    email/website pair written as "a@b.com | example.com") — rejoin the
    overflow into the last column instead of letting it shift into a
    nonexistent column and break the table's alignment."""
    if len(cells) > ncols:
        cells = cells[:ncols - 1] + [" | ".join(cells[ncols - 1:])]
    elif len(cells) < ncols:
        cells = cells + [""] * (ncols - len(cells))
    return cells


_FF_CSS = """
<style>
.ff-doc{font-family:'Segoe UI',Arial,sans-serif;font-size:13px;color:#1a202c;line-height:1.65;background:#fff;}
.ff-h1{font-size:19px;font-weight:700;color:#1e3a8a;border-bottom:3px solid #c2652a;padding-bottom:8px;margin:28px 0 12px;letter-spacing:.3px;}
.ff-h2{font-size:13px;font-weight:700;color:#fff;background:#1e3a8a;padding:9px 14px 9px 10px;margin:28px 0 12px;letter-spacing:.6px;border-left:5px solid #c2652a;}
.ff-h3{font-size:12.5px;font-weight:700;color:#c2652a;margin:18px 0 6px;padding-bottom:3px;border-bottom:1px solid #e2e8f0;letter-spacing:.2px;}
.ff-h4{font-size:12px;font-weight:700;font-style:italic;color:#2d4e7a;margin:12px 0 4px;}
.ff-p{margin:4px 0 9px;}
.ff-italic{margin:4px 0 9px;color:#4a5568;font-style:italic;}
.ff-ul{padding-left:20px;margin:4px 0 10px;}
.ff-ul li{margin:3px 0;}
.ff-ol{padding-left:22px;margin:4px 0 10px;}
.ff-ol li{margin:3px 0;}
.ff-check-list{list-style:none;padding-left:4px;margin:4px 0 10px;}
.ff-check-list li{margin:3px 0;padding-left:2px;}
.ff-table{border-collapse:collapse;width:100%;margin:12px 0;font-size:12.5px;}
.ff-table th{background:#1e3a8a;color:#fff;font-weight:600;padding:8px 11px;text-align:left;vertical-align:top;border:1px solid #1e3a8a;}
.ff-table td{border:1px solid #e2e8f0;padding:6px 11px;text-align:left;vertical-align:top;}
.ff-table tbody tr:nth-child(even) td{background:#f7fafc;}
.ff-hr{border:none;border-top:1.5px solid #c2652a;margin:20px 0;opacity:.45;}
</style>
"""


def markdown_to_html(text: str) -> str:
    try:
        import re
        lines = text.split('\n')
        output = [_FF_CSS, '<div class="ff-doc">']
        in_list = False
        in_ol = False
        in_check = False
        i = 0

        def close_lists():
            nonlocal in_list, in_ol, in_check
            if in_list:
                output.append('</ul>')
                in_list = False
            if in_ol:
                output.append('</ol>')
                in_ol = False
            if in_check:
                output.append('</ul>')
                in_check = False

        while i < len(lines):
            line = lines[i]
            s = line.strip()

            if re.match(r'^```\w*$', s):
                i += 1
                continue

            # Table block
            if s.startswith('|') and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
                close_lists()
                header = _table_cells(s)
                output.append('<table class="ff-table"><thead><tr>')
                output.extend(f'<th>{_inline_md(c)}</th>' for c in header)
                output.append('</tr></thead><tbody>')
                i += 2
                while i < len(lines) and lines[i].strip().startswith('|'):
                    cells = _normalize_row(_table_cells(lines[i]), len(header))
                    output.append('<tr>' + ''.join(f'<td>{_inline_md(c)}</td>' for c in cells) + '</tr>')
                    i += 1
                output.append('</tbody></table>')
                continue

            i += 1

            # Checkbox item: - [ ] or - [x]
            if re.match(r'^- \[[ x]\] ', s):
                close_lists()
                if not in_check:
                    output.append('<ul class="ff-check-list">')
                    in_check = True
                checked = s[3] == 'x'
                box = '&#9745;' if checked else '&#9744;'
                output.append(f'<li>{box} {_inline_md(s[6:])}</li>')
                continue

            # Bullet list
            if re.match(r'^[-*] ', s):
                close_lists()
                if not in_list:
                    output.append('<ul class="ff-ul">')
                    in_list = True
                output.append(f'<li>{_inline_md(s[2:])}</li>')
                continue

            # Numbered list
            if re.match(r'^\d+\. ', s):
                close_lists()
                if not in_ol:
                    output.append('<ol class="ff-ol">')
                    in_ol = True
                text_part = re.sub(r'^\d+\. ', '', s)
                output.append(f'<li>{_inline_md(text_part)}</li>')
                continue

            close_lists()

            if s.startswith('#### '):
                output.append(f'<div class="ff-h4">{_inline_md(s[5:])}</div>')
            elif s.startswith('### '):
                output.append(f'<div class="ff-h3">{_inline_md(s[4:])}</div>')
            elif s.startswith('## '):
                output.append(f'<div class="ff-h2">{_inline_md(s[3:])}</div>')
            elif s.startswith('# '):
                output.append(f'<div class="ff-h1">{_inline_md(s[2:])}</div>')
            elif s == '---':
                output.append('<hr class="ff-hr">')
            elif s.startswith('*') and s.endswith('*') and len(s) > 2 and not s.startswith('**'):
                output.append(f'<p class="ff-italic">{_inline_md(s)}</p>')
            elif s:
                output.append(f'<p class="ff-p">{_inline_md(s)}</p>')
            else:
                output.append('<div style="height:4px"></div>')

        close_lists()
        output.append('</div>')
        return '\n'.join(output)
    except Exception:
        return f'<pre>{text}</pre>'
