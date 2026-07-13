import json
import re
from typing import Dict, Any
from openai import OpenAI
from config import settings
from knowledge import load_standing_documents

MODEL = "gpt-4o-mini"

STANDING_DOCS_PREAMBLE = """FaithForge already keeps the following documents on file and can attach them to any submission without gathering them anew:

{standing_documents}

When producing "submission_checklist" below, append the marker " [ON FILE]" to the end of any checklist line whose required item matches one of these standing documents (match by meaning, not exact wording — e.g. "signed W-9" matches "W-9"). Leave unmarked only items that must be newly created, signed, or specifically tailored for this solicitation.

"""

SYSTEM_PROMPT = """You are an AI assistant for FaithForge Technologies & Consulting LLC, based in the Maryland/DC area.

FaithForge is a minority-owned program management and consulting firm — a governance and execution partner built for leaders under pressure. The firm installs structure, governance, and execution discipline where complexity and accountability intersect, helping leaders deliver rather than advising from the sidelines.

FaithForge does NOT deliver trade/vocational skills instruction, construction, IT infrastructure, or direct clinical services. FaithForge consults ON programs — it does not execute them.

## FaithForge's 4-Tier Engagement Model
- Tier 1: Immediate Advisory Support (targeted diagnostics, audits, KPI reviews)
- Tier 2: Project Recovery & Operational Remediation (stalled/failing initiative recovery)
- Tier 3: Governance & PMO Retainer (fractional PMO, executive reporting cadence)
- Tier 4: Enterprise Excellence / Managed PMO (embedded PMO leadership, portfolio governance)

## IDEAL opportunities (score 70-100):
- Government agencies or large nonprofits needing independent PMO, governance, or program oversight
- Organizations managing large-scale change, transformation, or multi-year initiatives needing a management consulting partner
- Workforce development or training PROGRAM MANAGEMENT (designing/managing a program, not delivering trade skills)
- Grants management consulting, technical assistance, or capacity building for nonprofits/public sector
- Curriculum design for professional development, certifications, or public-sector training programs
- Organizational readiness or change management engagements
- Healthcare & health systems needing compliance governance, PMO, or process improvement
- Enterprise or mid-market organizations needing structured execution support

## WEAK matches (score 40-69 — still worth seeing, but lower priority):
- Vocational or trade skill instruction (cosmetology, barbering, CDL, construction trades, etc.) unless the client is a government agency seeking program management consulting, not instructors
- IT procurement, hardware/software purchases, or infrastructure with no management consulting component
- Opportunities outside Maryland/DC/federal area unless remote/national scope is clear
- Very small dollar value or highly specialized technical work outside FaithForge's domain

## Primary target markets:
- Maryland and DC area government agencies (State, County, City)
- Nonprofits and community organizations
- Educational institutions (K-12, higher ed, workforce programs)
- Healthcare organizations and health systems
- Federal agencies with regional offices
- Enterprise and mid-market organizations

CONTRACT/PROCUREMENT INDICATORS: RFP, RFQ, RFI, IFB, Solicitation, Bid, NOFO, SOW, Request for Proposal/Quote/Information, Procurement, Source Sought, Grant opportunity, Cooperative Agreement, Task Order.

CLASSIFICATION RULES:
- RELEVANT (score 70-100): Clear procurement opportunity matching FaithForge's ICP — right client type, right service type
- POSSIBLY RELEVANT (score 40-69): Partial match, wrong industry/trade focus, unclear scope, or consulting component is secondary
- NOT RELEVANT (score 0-39): Spam, general correspondence, unrelated procurement, no consulting/management component

EMMA: emma.maryland.gov is Maryland's procurement portal. Flag any references to it."""

EMAIL_SCREENING_PROMPT = """Analyze this email for contract/procurement opportunities relevant to FaithForge.

EMAIL SUBJECT: {subject}
FROM: {sender}
DATE: {date}
BODY:
{body}

SCORING RUBRIC — build the relevance_score from these factors, then justify it:
- Client-type fit (0-30): government/nonprofit/healthcare/education/enterprise needing independent PMO, governance, or program oversight scores high; wrong/no client fit scores low.
- Service-type fit (0-30): management consulting, PMO, governance, program/grants management, change management, training PROGRAM management scores high; trade/vocational instruction, IT hardware, or pure construction scores low.
- Procurement signal (0-20): a real, actionable solicitation (RFP/RFQ/RFI/IFB/NOFO/Grant/Source Sought with a due date or portal) scores high; general correspondence, newsletters, or award notices score low.
- Geography/scope fit (0-10): Maryland/DC/federal or clearly remote-national scores high; out-of-area with no remote scope scores low.
- Actionability (0-10): clear next step (link, contact, deadline) scores high; vague or expired scores low.

Respond with ONLY a valid JSON object using this exact schema:
{{
  "classification": "relevant" | "possibly_relevant" | "not_relevant",
  "relevance_score": <integer 0-100>,
  "classification_reasoning": "<2-4 sentences that JUSTIFY the exact score: name the specific factors that earned or lost points (client-type fit, service-type fit, procurement signal, geography, actionability) and explain why this lands at relevant/possibly_relevant/not_relevant. Reference concrete details from THIS email, not generic statements.>",
  "score_breakdown": "<one line: 'Client X/30, Service Y/30, Procurement Z/20, Geography G/10, Actionability A/10' using your actual sub-scores that sum to relevance_score>",
  "opportunity_title": "<title or null>",
  "agency_name": "<agency/organization or null>",
  "solicitation_number": "<number or null>",
  "due_date": "<YYYY-MM-DD or null>",
  "pre_bid_date": "<YYYY-MM-DD or null>",
  "submission_method": "<email/portal/mail/etc or null>",
  "contact_person": "<name or null>",
  "contact_email": "<email address or null>",
  "website_link": "<URL or null>",
  "emma_link": "<EMMA URL or null>",
  "has_emma_link": <true|false>,
  "opportunity_summary": "<2-3 sentence summary or null>",
  "required_services": "<comma-separated list of required services or null>",
  "faithforge_alignment": "<how FaithForge services align with this opportunity or null>",
  "recommended_action": "<specific recommended next step or null>",
  "risk_concerns": "<any risks or concerns or null>",
  "estimated_value": "<dollar range or null>",
  "contract_type": "<RFP/RFQ/RFI/IFB/Grant/etc or null>"
}}"""

DOCUMENT_REVIEW_PROMPT = """You are reviewing solicitation documents for FaithForge. Extract and analyze the following from these documents.

EXISTING OPPORTUNITY DATA:
{opportunity_context}

DOCUMENTS CONTENT:
{documents_text}

Provide a comprehensive review as a JSON object:
{{
  "opportunity_title": "<confirmed or updated title>",
  "agency_name": "<confirmed or updated agency>",
  "solicitation_number": "<confirmed or updated number>",
  "due_date": "<YYYY-MM-DD>",
  "pre_bid_date": "<YYYY-MM-DD or null>",
  "questions_deadline": "<YYYY-MM-DD or null — deadline to submit questions to the agency>",
  "submission_method": "<detailed submission instructions>",
  "contact_person": "<the AGENCY's point of contact or procurement/contracting officer name and title, taken ONLY from the DOCUMENTS CONTENT below — NEVER FaithForge's own name (Bernedette Atong) or any name/detail from the standing-documents list above, which is FaithForge's own information, not the agency's. If the documents do not name an agency contact, set this to null — do not substitute FaithForge's own details.>",
  "contact_email": "<the AGENCY's contact email from the DOCUMENTS CONTENT below — NEVER info@faithforgetech.com or any FaithForge email/phone from the standing-documents list above. If the documents do not state an agency contact email, set this to null.>",
  "website_link": "<URL>",
  "emma_link": "<EMMA URL or null>",
  "has_emma_link": <true|false>,
  "opportunity_summary": "<detailed 3-5 sentence summary>",
  "required_services": "<detailed list of all required services>",
  "faithforge_alignment": "<detailed alignment analysis>",
  "recommended_action": "<specific recommended next steps>",
  "risk_concerns": "<risks, concerns, and challenges>",
  "estimated_value": "<contract value if specified>",
  "contract_type": "<type of contract/opportunity>",
  "eligibility_requirements": "<who is eligible to respond — business size, type, certifications, location, etc.>",
  "required_qualifications": "<technical qualifications and past performance required>",
  "required_forms": "<list of all required forms to include in submission>",
  "submission_checklist": "<one required item per line, each line starting with '- '. Plain text only — use real newline characters between items. Do NOT format this as a JSON array, a Postgres-style array literal, or a comma-separated list wrapped in braces/quotes. Example of the required format: '- Proposal cover sheet\\n- Signed W-9\\n- Certificate of insurance'>",
  "proposal_format": "<page limits, formatting requirements, section structure>",
  "evaluation_criteria": "<how proposals will be evaluated and weighted>",
  "insurance_requirements": "<required insurance types, coverage amounts, and certificates>",
  "certifications_required": "<required certifications, registrations, or licenses (e.g. MBE, SBE, SAM.gov)>",
  "compliance_requirements": "<regulatory, legal, or policy compliance requirements>",
  "pricing_requirements": "<how to structure pricing, rate schedules, cost proposals, budget format>",
  "required_attachments": "<list of all required attachments beyond the main proposal>",
  "disqualifying_requirements": "<anything that would automatically disqualify FaithForge from responding>",
  "period_of_performance": "<duration and dates>",
  "place_of_performance": "<location details>",
  "small_business_requirements": "<any small business/setaside requirements>",
  "key_requirements": "<summary of the most critical requirements and qualifications>",
  "review_summary": "<overall analysis and key findings>"
}}"""


TPM_LIMIT = 200000
# gpt-4o-mini's real per-request context window (input + output combined).
# This is smaller than TPM_LIMIT (a per-minute rate limit, not a per-request
# size cap) — sizing a single prompt against TPM_LIMIT alone could build a
# request that fits the rate limit but still gets rejected by the model with
# context_length_exceeded. Always bound by whichever ceiling is smaller.
MODEL_CONTEXT_LIMIT = 128000
TPM_SAFETY = 1000


def est_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token)."""
    return len(text) // 4 + 1


def fit_prompt_to_budget(system: str, prompt: str, max_tokens: int) -> str:
    """Trim `prompt` so system + prompt + completion stays under the model's context window."""
    ceiling = min(TPM_LIMIT, MODEL_CONTEXT_LIMIT)
    budget = ceiling - TPM_SAFETY - max_tokens - est_tokens(system)
    if budget < 400:
        budget = 400
    max_chars = budget * 4
    if len(prompt) > max_chars:
        prompt = prompt[:max_chars] + "\n\n[...input truncated to fit model token limit...]"
    return prompt


def doc_char_budget(system: str, prompt_overhead: str, max_tokens: int) -> int:
    """Max characters of document text that fit, given fixed prompt parts + completion."""
    ceiling = min(TPM_LIMIT, MODEL_CONTEXT_LIMIT)
    used = est_tokens(system) + est_tokens(prompt_overhead) + max_tokens + TPM_SAFETY
    return max(400, ceiling - used) * 4


def call_openai(prompt: str, system: str = SYSTEM_PROMPT, max_tokens: int = 4096) -> str:
    import traceback as _tb
    prompt = fit_prompt_to_budget(system, prompt, max_tokens)
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
    except Exception as e:
        raise RuntimeError(f"OpenAI client init failed: {e}\n{_tb.format_exc()}") from e
    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI API call failed: {e}\n{_tb.format_exc()}") from e
    return response.choices[0].message.content or ""


def extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def screen_email(
    subject: str,
    sender: str,
    date: str,
    body: str,
) -> Dict[str, Any]:
    prompt = EMAIL_SCREENING_PROMPT.format(
        subject=subject,
        sender=sender,
        date=date,
        body=body[:8000],
    )
    raw = call_openai(prompt)
    result = extract_json(raw)
    if not result:
        result = {
            "classification": "not_relevant",
            "relevance_score": 0,
            "classification_reasoning": "AI analysis failed to parse response",
        }
    return result


ACCOUNT_SCORING_PROMPT = """Score this prospective target ACCOUNT for FaithForge's outbound client-acquisition pipeline.
This is NOT an inbound solicitation — it's a company FaithForge may proactively pursue.

ACCOUNT:
Company: {company_name}
Segment: {segment}
Location: {location}
Contact: {contact_name} ({contact_title})
Known pain points: {pain_points}
Notes: {notes}

SCORING RUBRIC — build priority_score from these factors:
- Client-type fit (0-40): government/nonprofit/healthcare/education/enterprise needing independent PMO, governance, or program oversight scores high.
- Pain/need signal (0-30): clear evidence of stalled initiatives, transformation, compliance pressure, or execution gaps scores high; no known need scores low.
- Geography/scope fit (0-15): Maryland/DC/federal or clearly national/remote scores high.
- Reachability (0-15): a named decision-maker with title and contact info scores high; no contact scores low.

Respond with ONLY a valid JSON object:
{{
  "priority_score": <integer 0-100>,
  "priority_reason": "<2-3 sentences justifying the score by naming the factors that earned or lost points, referencing concrete details from THIS account>",
  "suggested_pain_points": "<likely pain points FaithForge could address for this account, or null>",
  "suggested_entry_offer": "<the single best Tier-1 entry offer (e.g. a targeted diagnostic or KPI review) to lead with, or null>"
}}"""


def score_account(
    company_name: str,
    segment: str = "",
    location: str = "",
    contact_name: str = "",
    contact_title: str = "",
    pain_points: str = "",
    notes: str = "",
) -> Dict[str, Any]:
    prompt = ACCOUNT_SCORING_PROMPT.format(
        company_name=company_name or "(unknown)",
        segment=segment or "(unspecified)",
        location=location or "(unspecified)",
        contact_name=contact_name or "(unknown)",
        contact_title=contact_title or "(unknown)",
        pain_points=pain_points or "(none provided)",
        notes=notes or "(none)",
    )
    raw = call_openai(prompt, max_tokens=800)
    result = extract_json(raw)
    if not result:
        result = {"priority_score": 0, "priority_reason": "AI scoring failed to parse response"}
    return result


COLD_EMAIL_SYSTEM = """You are Bernedette Atong, Principal of FaithForge Technologies & Consulting LLC — a program management and consulting firm in the Maryland/DC area. You write warm, credible, executive-level cold outreach: specific and confident, but never presumptuous or accusatory about the prospect's own organization. No fluff, no boilerplate, no vague "let's connect" asks — and never flatly informing a stranger that their company is struggling or has missed something, since you don't actually know that about them personally. Every email leads with a genuine, respectful observation, offers a single low-friction next step, and sounds like a busy principal wrote it personally — not a marketing team."""

COLD_EMAIL_PROMPT = """Write a {sequence_length}-email cold outreach sequence for this prospect.

PROSPECT:
Company: {company_name}
Segment: {segment}
Contact: {contact_name} ({contact_title})
Known pain points: {pain_points}
Planned entry offer: {entry_offer}

FAITHFORGE CONTEXT (weave in naturally, don't list):
- PMO, governance, and program oversight firm; a governance and execution partner, not a traditional consulting vendor
- Helps leaders fix the real problems behind stalled initiatives: unclear accountability, fading visibility after kickoff, misaligned teams
- Bernedette's credentials: MSc, PMP, PgMP, PSM, Lean Six Sigma — 8+ years across transportation, e-commerce/data, procurement, construction, government and healthcare programs
- Tier-1 entry offers: PMO Diagnostic (2-week audit), KPI & Reporting Health Check, Governance Readiness Assessment, Change Readiness Workshop

RULES FOR EACH EMAIL:
- Under 175 words — tight paragraphs, no fluff
- Tone: warm and respectful, like one professional reaching out to another — never blunt, accusatory, or presumptuous about THEIR company specifically
- If "Known pain points" are given, raise them as a pattern you've seen elsewhere in their space ("Many [segment] teams find that...", "It's common for organizations scaling X to run into..."), NOT as a claim about what's happening at THEIR company. Never write "I noticed you're facing/struggling with/have missed X" — you don't have evidence of that about them personally, and asserting it can come across as rude or presumptuous.
- Open with something genuine and positive about them (their role, company's work, sector) before pivoting to how FaithForge helps — this should read like a compliment or shared-interest observation, not a diagnosis
- Single, low-friction ask (not "let's explore synergies")
- Signed: Bernedette Atong | FaithForge Technologies & Consulting
- Email 1 (day 0): genuine opening observation about them + a soft bridge to a relevant capability, framed generally + specific Tier-1 ask
- Email 2 (day 5, if requested): brief, friendly follow-up referencing email 1, add one sharp insight or social proof (never a guilt-trip or "did you see my last email")
- Email 3 (day 12, if requested): final value-add — offer a relevant resource, stat, or observation; soft close
- Emails 4+ (days 21, 30): ultra-short, friendly check-ins or alternative angle

Respond with ONLY valid JSON — no markdown, no preamble:
{{
  "emails": [
    {{
      "step": 1,
      "subject": "<specific subject line — not clickbait, not generic>",
      "body": "<email body as plain text with \\n for line breaks>",
      "send_day": 0,
      "purpose": "Initial outreach"
    }}
  ]
}}"""


def generate_cold_email(
    company_name: str,
    segment: str = "",
    contact_name: str = "",
    contact_title: str = "",
    pain_points: str = "",
    entry_offer: str = "",
    sequence_length: int = 3,
) -> Dict[str, Any]:
    prompt = COLD_EMAIL_PROMPT.format(
        company_name=company_name or "(unknown)",
        segment=segment or "Government / Nonprofit / Enterprise",
        contact_name=contact_name or "the appropriate leader",
        contact_title=contact_title or "(title unknown)",
        pain_points=pain_points or "(not specified — infer likely pain from company type and segment)",
        entry_offer=entry_offer or "(not specified — choose the most appropriate Tier-1 entry offer)",
        sequence_length=sequence_length,
    )
    raw = call_openai(prompt, system=COLD_EMAIL_SYSTEM, max_tokens=2400)
    result = extract_json(raw)
    if not result or "emails" not in result:
        return {"emails": []}

    # The model reliably includes send_day/purpose for email 1 (shown in the
    # prompt's example) but sometimes drops them for emails 2+ — backfill from
    # the fixed cadence defined in COLD_EMAIL_PROMPT's own rules rather than
    # trust the model to repeat them correctly every time.
    step_defaults = {
        1: (0, "Initial outreach"),
        2: (5, "Follow-up"),
        3: (12, "Final value-add"),
        4: (21, "Check-in"),
        5: (30, "Check-in"),
    }
    for email in result.get("emails") or []:
        step = email.get("step")
        default_day, default_purpose = step_defaults.get(step, (7 * max(int(step or 1) - 1, 0), "Follow-up"))
        if email.get("send_day") is None:
            email["send_day"] = default_day
        if not email.get("purpose"):
            email["purpose"] = default_purpose
    return result


GONOGO_PROMPT = """Perform a formal Bid / No-Bid assessment for FaithForge Technologies & Consulting LLC on this solicitation.

FaithForge offers: PMO leadership, governance, program oversight, enterprise transformation, workflow automation, business analytics, governance/risk/compliance, organizational change management, and staff augmentation. Principal Bernedette Atong holds PMP and PgMP certifications, 8+ years experience. Headquartered in Elkridge, MD (Maryland/DC region); registered for federal awards via SAM.gov.

OPPORTUNITY DATA:
{opportunity_data}

SCORING RUBRIC — compute each factor, then sum:
- Service Alignment (0-25): required services match FaithForge's core offerings? 20-25=exact PMO/governance/change match; 10-19=partial; 0-9=poor fit, purely trade/construction/vocational
- Eligibility & Compliance (0-25): can FaithForge meet certifications, registrations, eligibility? 20-25=all requirements met; 10-19=most met, minor gaps; 0-9=significant gaps or likely disqualifiers
- Risk Level (0-20): score HIGH when risk is LOW: 16-20=manageable risks, no disqualifiers; 8-15=some risk, manageable; 0-7=tight timeline, disqualifying clauses, major red flags
- Contract Value & Scope (0-15): 12-15=strong value and clear scope; 6-11=moderate or unclear; 0-5=too small, out of scope, or undefined
- Competitive Position (0-15): 12-15=strong differentiators (PgMP-led governance, minority-owned, senior-led delivery); 6-11=competitive; 0-5=commoditized or high incumbent advantage

Verdict rules: score ≥ 70 → BID | score 45-69 → BID WITH CONDITIONS | score ≤ 44 → NO-BID

Respond ONLY with valid JSON:
{{
  "verdict": "BID",
  "score": <integer 0-100>,
  "factors": {{
    "alignment": <int 0-25>,
    "eligibility": <int 0-25>,
    "risk": <int 0-20>,
    "value": <int 0-15>,
    "competitive": <int 0-15>
  }},
  "recommendation": "<2-3 sentence executive recommendation specific to THIS opportunity>",
  "conditions": ["<condition to resolve before bidding — empty list if BID or NO-BID>"],
  "next_steps": ["<3-5 specific actionable next steps>"],
  "red_flags": ["<specific red flags — empty list if none>"]
}}"""


def score_gonogo(opportunity_data: str) -> Dict[str, Any]:
    prompt = GONOGO_PROMPT.format(opportunity_data=opportunity_data[:6000])
    raw = call_openai(prompt, max_tokens=1200)
    result = extract_json(raw)
    if not result:
        result = {
            "verdict": "BID WITH CONDITIONS",
            "score": 50,
            "factors": {"alignment": 15, "eligibility": 12, "risk": 10, "value": 7, "competitive": 6},
            "recommendation": "AI assessment failed to parse. Run assessment again.",
            "conditions": [], "next_steps": [], "red_flags": [],
        }
    return result


def review_documents(
    opportunity_context: str,
    documents_text: str,
) -> Dict[str, Any]:
    max_tokens = 4096
    preamble = STANDING_DOCS_PREAMBLE.format(standing_documents=load_standing_documents())
    overhead = preamble + DOCUMENT_REVIEW_PROMPT.format(
        opportunity_context=opportunity_context, documents_text=""
    )
    max_doc_chars = doc_char_budget(SYSTEM_PROMPT, overhead, max_tokens)
    prompt = preamble + DOCUMENT_REVIEW_PROMPT.format(
        opportunity_context=opportunity_context,
        documents_text=documents_text[:max_doc_chars],
    )
    raw = call_openai(prompt, max_tokens=max_tokens)
    result = extract_json(raw)
    if not result:
        result = {
            "review_summary": "Document review failed to parse AI response.",
            "opportunity_summary": raw[:1000] if raw else "No response",
        }
    return result
