import json
import os
import re
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
from config import settings
from knowledge import load_standing_documents
from checklist_keywords import render_keyword_library_for_prompt
from requirement_anchors import scan_requirement_anchors, render_anchors_for_prompt

MODEL = "gpt-4o-mini"
# Requirement extraction is the safety-critical path (missed/invented items on
# a real government bid) — it alone gets the stronger, more expensive model.
# Screening, outreach, and packet building keep MODEL; do not change them.
# Same model packet_builder.py uses to write entire proposals — a harder job
# than structured extraction, which here also has anchor hints, mandatory
# verbatim source_quotes, and code-side quote verification backing it up.
# Briefly ran on gpt-4o (~17x the price) and pushed a 39-file package over
# $1.50; env-overridable if a specific bid ever justifies paying for it.
EXTRACTION_MODEL = os.getenv("FAITHFORGE_EXTRACTION_MODEL", "gpt-4o-mini")

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


# High-signal, multi-word phrases from PROPOSAL_SECTION_KEYWORDS (never the
# single generic words like "forms"/"attachments" — those false-positive
# throughout a document). Used as anchors so the section that actually states
# submission requirements is preserved regardless of where it falls, instead
# of surviving or not by the luck of head/tail position.
_REQUIREMENTS_SECTION_ANCHORS = [
    "proposal requirements", "submission instructions", "proposal format",
    "proposal organization", "proposal contents", "required attachments",
    "administrative requirements", "compliance requirements",
]


def _find_priority_windows(text: str, window_chars: int = 45000) -> "list[tuple[int, int]]":
    """Spans around every occurrence of a requirements-section anchor phrase,
    merged where they overlap. A document's own table of contents can trigger
    a spurious early match, so this keeps ALL occurrences (a real section
    heading tends to repeat the phrase again later) rather than only the
    first — see the caller docstring for why this is a mitigation, not a
    guarantee."""
    lower = text.lower()
    spans = []
    for phrase in _REQUIREMENTS_SECTION_ANCHORS:
        start = 0
        while True:
            idx = lower.find(phrase, start)
            if idx == -1:
                break
            spans.append((idx, min(len(text), idx + window_chars)))
            start = idx + len(phrase)
    if not spans:
        return []
    spans.sort()
    merged = [spans[0]]
    for s, e in spans[1:]:
        last_s, last_e = merged[-1]
        if s <= last_e:
            merged[-1] = (last_s, max(last_e, e))
        else:
            merged.append((s, e))
    return merged


def fit_documents_to_budget(documents_text: str, max_chars: int) -> "tuple[str, bool]":
    """Fit combined document text to max_chars for a single LLM call — the
    LAST-RESORT safety net for the rare case where a single document (or a
    caller that didn't process documents individually) still exceeds budget
    on its own. The PRIMARY defense against losing content is
    extract_structured_checklist_for_documents() processing each uploaded
    document as its own call, so this function should rarely fire in
    practice — but it must never fail silently when it does.

    Rather than a blind documents_text[:max_chars] (which drops everything
    after the cut — with no ordering guarantee on multi-document input, that
    could be exactly the amendment or attachments section that was added
    because it mattered), this locates the requirements-section anchor
    phrases and preserves text around them first, filling remaining budget
    with head+tail of the rest. This is a heuristic, not a guarantee — a
    document with no recognizable section headers, or one where the true
    section falls entirely outside every anchor's window, can still lose
    content. The visible marker exists specifically so that risk is never
    silent.
    """
    if len(documents_text) <= max_chars:
        return documents_text, False

    windows = _find_priority_windows(documents_text)
    dropped = len(documents_text) - max_chars
    warn = (
        f"[... {dropped:,}+ characters cut to fit this review's size limit. "
    )
    if windows:
        priority_budget = int(max_chars * 0.65)
        head_tail_budget = max_chars - priority_budget
        priority_parts, used = [], 0
        for s, e in windows:
            if used >= priority_budget:
                break
            chunk = documents_text[s:e]
            remaining = priority_budget - used
            if len(chunk) > remaining:
                chunk = chunk[:remaining]
            priority_parts.append(chunk)
            used += len(chunk)
        half = head_tail_budget // 2
        head = documents_text[:half]
        tail = documents_text[-half:] if half else ""
        marker = (
            warn + "Sections matching known proposal-requirements language were located and "
            "preserved below, but other content — and possibly some requirements language this "
            "scan didn't match — may be missing. Do not treat this as complete coverage if "
            "anything looks incomplete. ...]"
        )
        fitted = (
            head + "\n\n" + marker + "\n\n=== PRESERVED REQUIREMENTS-SECTION CONTENT ===\n"
            + "\n\n[... other preserved section ...]\n\n".join(priority_parts)
            + "\n\n=== DOCUMENT TAIL ===\n" + tail
        )
        return fitted, True

    half = max_chars // 2
    marker = (
        warn + "No recognizable proposal-requirements section heading was found to prioritize, "
        "so this is a plain head/tail cut — some requirements, sections, or attachments this "
        "solicitation contains may NOT be reflected in what follows. Do not treat this as "
        "complete coverage. ...]"
    )
    return documents_text[:half] + "\n\n" + marker + "\n\n" + documents_text[-half:], True


RETRY_ATTEMPTS = 4
RETRY_BACKOFF_SECONDS = 2

# Chunk size for anchor-narrowed text. The 3/31 recall collapse came from
# 161k chars of MIXED content in one call, most of it irrelevant; narrowed
# text is dense with actual obligations, so a larger window stays reliable
# while cutting call count several-fold. Env-overridable so the recall/cost
# tradeoff can be retuned without a deploy.
NARROWED_CHUNK_CHARS = int(os.getenv("FAITHFORGE_CHUNK_CHARS", "35000"))

# Documents at or below this size skip chunking and get batched together into
# one call. The extraction prompt is ~14k chars of fixed overhead, so a 1k-char
# amendment analysed alone pays 14x its own size in instructions — a real
# 39-file package had 32 files smaller than the prompt itself.
SMALL_DOC_CHARS = int(os.getenv("FAITHFORGE_SMALL_DOC_CHARS", "12000"))
SMALL_DOC_BATCH_CHARS = int(os.getenv("FAITHFORGE_SMALL_BATCH_CHARS", "30000"))

# Error classes worth retrying: a blip, a rate limit, or a server-side 5xx.
# Matched on the exception's type name and message so this keeps working
# across openai-python versions without pinning to their exception tree.
_TRANSIENT_ERROR_MARKERS = (
    "connection error", "connection reset", "connection aborted",
    "timeout", "timed out", "rate limit", "429",
    "500", "502", "503", "504", "bad gateway", "service unavailable",
    "overloaded", "temporarily unavailable", "remote end closed",
)


def _is_transient_error(e: Exception) -> bool:
    """True for failures a retry can plausibly fix. Auth errors, malformed
    requests, and context_length_exceeded are permanent — retrying those just
    burns time and money, so they fall through and raise on the first try."""
    text = f"{type(e).__name__} {e}".lower()
    if "context_length" in text or "invalid_api_key" in text or "authentication" in text:
        return False
    return any(marker in text for marker in _TRANSIENT_ERROR_MARKERS)


def call_openai(
    prompt: str,
    system: str = SYSTEM_PROMPT,
    max_tokens: int = 4096,
    model: str = None,
    temperature: float = None,
) -> str:
    import traceback as _tb
    import time as _time
    prompt = fit_prompt_to_budget(system, prompt, max_tokens)
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
    except Exception as e:
        raise RuntimeError(f"OpenAI client init failed: {e}\n{_tb.format_exc()}") from e
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature

    # Retry transient failures before giving up. A real audit caught a single
    # "Connection error" silently destroying an entire 35k chunk of a
    # solicitation — the chunk holding the whole Vendor Questionnaire (20
    # mandatory submittals). Recall must not depend on network luck: on the
    # compliance path a dropped chunk means a bid goes out missing forms.
    # Only transient classes are retried; auth failures and
    # context_length_exceeded are permanent and re-raise immediately.
    last_error = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = client.chat.completions.create(
                model=model or MODEL,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                **kwargs,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            last_error = e
            if not _is_transient_error(e) or attempt == RETRY_ATTEMPTS - 1:
                break
            _time.sleep(RETRY_BACKOFF_SECONDS * (2 ** attempt))
    raise RuntimeError(
        f"OpenAI API call failed after {RETRY_ATTEMPTS} attempt(s): {last_error}\n{_tb.format_exc()}"
    ) from last_error


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
    fitted_text, was_truncated = fit_documents_to_budget(documents_text, max_doc_chars)
    prompt = preamble + DOCUMENT_REVIEW_PROMPT.format(
        opportunity_context=opportunity_context,
        documents_text=fitted_text,
    )
    raw = call_openai(prompt, max_tokens=max_tokens)
    result = extract_json(raw)
    if not result:
        result = {
            "review_summary": "Document review failed to parse AI response.",
            "opportunity_summary": raw[:1000] if raw else "No response",
        }
    result["input_truncated"] = was_truncated
    return result


# ─── Document-role classification ───────────────────────────────────────────
#
# The audit's #1 wrong-source failure was mining an internal lessons-learned
# retrospective (a spreadsheet with a column literally named "RFP Required
# Change") for "requirements" that were never actually asked of an offeror.
# This one cheap call decides, per uploaded document, whether it is something
# an offeror must respond to at all — BEFORE requirement extraction ever runs
# on it.

CLASSIFY_DOCUMENT_ROLE_PROMPT = """Classify the ROLE of this document within a government solicitation package.

FILENAME: {filename}

DOCUMENT EXCERPT — START OF DOCUMENT:
{head}

DOCUMENT EXCERPT — END OF DOCUMENT:
{tail}

Return exactly ONE of these role labels:
- solicitation — the RFP/RFQ/IFB itself, an amendment/addendum, an appendix, a form, or an attachment that is part of what the offeror must read and respond to.
- amendment — a formal amendment/addendum document that modifies an existing solicitation.
- background_reference — internal studies, lessons-learned or pilot-program retrospectives, background one-pagers, meeting notes, or similar material that describes context but does NOT tell an offeror what to submit. Strong signal: a spreadsheet/table with a column like "RFP Required Change" or "Recommendation" describing what a FUTURE solicitation should contain — that is background commentary about a future document, never a submission requirement of THIS one.
- pricing_form — a standalone pricing/cost worksheet or fee-schedule template with no other submittal instructions of its own.
- unknown — you genuinely cannot tell from this excerpt.

Be conservative: if you are not sure whether this document tells an offeror what to submit, answer "solicitation" — missing a real requirement is worse than over-extracting.

Respond with ONLY the single label word (e.g. "solicitation"), nothing else — no punctuation, no explanation."""


# Filenames that state their own role. A model call to decide that
# "TSOOPD2609 Pre-Proposal Sign-In Sheet.docx" is a sign-in sheet is money
# lit on fire — a real 39-file package spent 39 calls on this. Only genuinely
# ambiguous names fall through to the model.
#
# Deliberately conservative in one direction: nothing here can classify a
# document as background_reference on a weak signal, because that SKIPS it
# entirely. Q&A and addenda are authoritative (they change requirements) and
# are matched as "amendment", never skipped.
_FILENAME_ROLE_RULES: List[Tuple[str, str]] = [
    (r"sign[\s\-_]*in[\s\-_]*sheet|attendance\s+(sheet|list)", "background_reference"),
    (r"pre[\s\-_]*proposal.*(slide|agenda|script|presentation)", "background_reference"),
    (r"lessons[\s\-_]*learned|retrospective", "background_reference"),
    # Amendments/addenda/Q&A CHANGE requirements — always authoritative,
    # matched before the form-template rule so an "Addendum #3 - Appendix 5"
    # is never mistaken for a blank form and skipped.
    (r"\bq\s*&\s*a\b|questions?\s+and\s+answers?", "amendment"),
    (r"\bamendment\b|\baddendum\b|\baddenda\b", "amendment"),
    # A standalone "Attachment K", "Appendix 4", "Exhibit 1" file is a blank
    # form the offeror FILLS IN — it is a checklist ITEM, not a source of
    # requirements. The parent RFP enumerates them (e.g. MDOT's "TABLE A -
    # Attachments and Documents Required with the Proposal"), so mining each
    # one re-derives what the RFP already said and was a main source of the
    # 145-item noise pile on a 39-file package.
    (r"\b(attachment|appendix|exhibit)\s*[#]?\s*[a-z0-9]{1,3}\b[\s\.\-–_]", "form_template"),
]
_FILENAME_ROLE_PATTERNS = [(re.compile(p, re.IGNORECASE), role) for p, role in _FILENAME_ROLE_RULES]


def _role_from_filename(filename: str) -> Optional[str]:
    """Role when the filename alone is conclusive, else None (ask the model)."""
    name = filename or ""
    # A .zip is the whole solicitation package, not one document. Classifying
    # it would judge every file inside by whatever happens to sit in the first
    # 6k characters — one leading form or sign-in sheet could mark the entire
    # package skippable and yield an empty checklist. Always authoritative.
    if name.lower().endswith(".zip"):
        return "solicitation"
    for regex, role in _FILENAME_ROLE_PATTERNS:
        if regex.search(name):
            return role
    return None


def classify_document_role(filename: str, text: str) -> str:
    """Filename rules first (free), model only for genuinely ambiguous names.

    Returns exactly one of: solicitation | amendment | background_reference |
    pricing_form | unknown. On ANY exception/parse failure, returns "unknown",
    which the caller treats as authoritative (i.e. NOT skipped — proceeds to
    extraction like "solicitation" would)."""
    from_name = _role_from_filename(filename)
    if from_name:
        return from_name
    text = text or ""
    # Same guard for any bundle of several documents (a zip's contents arrive
    # as repeated "=== filename ===" blocks): a single role cannot describe the
    # whole bundle, and guessing one from the opening pages risks skipping an
    # entire solicitation.
    if text.count("\n=== ") >= 1 or text.count("=== ") >= 2:
        return "solicitation"
    try:
        head = text[:6000]
        tail = text[-2000:] if len(text) > 6000 else ""
        prompt = CLASSIFY_DOCUMENT_ROLE_PROMPT.format(
            filename=filename or "(unnamed document)", head=head, tail=tail,
        )
        raw = call_openai(prompt, max_tokens=20, temperature=0)
        label = (raw or "").strip().strip(".").strip('"').strip("'").lower()
        for candidate in ("background_reference", "pricing_form", "solicitation", "amendment", "unknown"):
            if candidate in label:
                return candidate
        return "unknown"
    except Exception:
        return "unknown"


def _chunk_document(text: str, chunk_chars: int = 35000, overlap: int = 3000) -> List[Tuple[int, str]]:
    """Split `text` into overlapping (start_offset, chunk_text) windows.

    Small windows let the model enumerate requirements reliably; one 161K-char
    blob does not (this is the direct fix for the audit's ~3/31 recall
    collapse). Overlap guarantees a requirement whose statement straddles a
    chunk boundary is still seen whole by at least one chunk. Prefers to break
    on a double newline within the last 2000 chars of a chunk so a
    requirement's sentence isn't sliced mid-line.
    """
    if not text:
        return [(0, "")]
    n = len(text)
    if n <= chunk_chars:
        return [(0, text)]

    chunks: List[Tuple[int, str]] = []
    pos = 0
    while pos < n:
        end = min(pos + chunk_chars, n)
        if end < n:
            search_start = max(pos, end - 2000)
            break_idx = text.rfind("\n\n", search_start, end)
            if break_idx != -1 and break_idx > pos:
                end = break_idx + 2
        chunks.append((pos, text[pos:end]))
        if end >= n:
            break
        next_pos = end - overlap
        pos = next_pos if next_pos > pos else end
    return chunks


# ─── Structured, multi-step compliance-checklist extraction ────────────────
#
# Implements Bernedette Atong's feedback (2026-07-28) about missed/incomplete
# submission checklists on real bids (the MCPS contract had missing
# attachments and an incorrect Volume II structure). Rather than a single-pass
# flat-text extraction, this walks the model through the same multi-step
# process she described: identify sections -> extract requirement statements
# -> classify each into one of 13 categories -> produce one structured record
# per requirement -> flag what's already on file. This runs ALONGSIDE
# review_documents() (not instead of it) — both write to the Opportunity row.

STRUCTURED_CHECKLIST_PROMPT = """You are extracting a structured compliance checklist from ONE EXCERPT of a solicitation document for FaithForge, using a disciplined multi-step process. Do NOT just produce the final JSON from a single read-through — work through these steps in order:

STEP 1 — Identify the proposal's sections visible in THIS excerpt. Scan for section headers such as Proposal Requirements, Submission Instructions, Proposal Format, Required Attachments, Evaluation Criteria, Volume I/II/III, Technical Proposal, Cost Proposal, etc. Use the "Proposal Section Keywords" category below to recognize these even when phrased differently.

STEP 2 — Extract every requirement statement in THIS excerpt. Read looking for obligation language (shall/must/required/mandatory/etc.) using the "Mandatory Requirement Keywords" and "Compliance Language" categories below to recognize it. Each sentence or clause that obligates the offeror to submit, sign, notarize, or include something is a candidate requirement.

STEP 3 — Classify each requirement into EXACTLY ONE of the 13 categories below (use the exact category name as it appears as a key).

STEP 4 — Produce ONE structured record per requirement (not a flat blob) with all the fields in the schema below, INCLUDING a verbatim `source_quote` for each one (see ANTI-FABRICATION below).

STEP 5 — Mark whether FaithForge already holds each item on file. FaithForge keeps the following documents on file and can attach them to any submission without gathering them anew:

{standing_documents}

Set "on_file": true ONLY when THIS EXCERPT itself indicates the item is already held/on file (matches one of the standing documents above by MEANING, not exact wording — e.g. "signed W-9" matches "W-9"). Never set "on_file": true by inferring from general knowledge of what firms typically keep on file — only from what this excerpt actually states. Set "on_file": false for anything that must be newly created, signed, or specifically tailored for this solicitation.

ANTI-FABRICATION — read this twice, it is the most important rule here:
Extract ONLY what THIS EXCERPT literally states. Do NOT add documents merely because they are common in government solicitations. Specifically: never output W-9, SAM registration, DUNS/UEI, or "capability statement" unless those exact terms appear in this excerpt. An invented requirement is a serious error — worse than missing one. Every requirement you emit MUST include a `source_quote`: the verbatim sentence or line from this excerpt that states it. Copy it exactly, character for character — do not paraphrase, summarize, or reconstruct it from memory. If you cannot quote the exact text that states a requirement, DO NOT emit that requirement at all.

ANCHOR ACCOUNTING:
A deterministic keyword scan (not an AI) flagged the lines below in THIS excerpt as likely submittal-requirement language. Account for EACH one: either extract it as a requirement (with its own source_quote), or omit it only because on inspection it is genuinely not something the offeror submits (boilerplate, a definition, an instruction to the agency itself, etc.) — do not omit one just because it's inconvenient to classify.

VENDOR QUESTIONNAIRE / MINIMUM QUALIFICATIONS ITEMS COUNT TOO: a line marked "*Response required" (or similar — "must answer", "must respond") is a checklist requirement EVEN WHEN the required response is a narrative answer, an attestation, a yes/no confirmation, or a list of facts (e.g. years of experience, project history, a non-affiliation attestation) rather than a file upload. Do not silently treat these as "just a question to answer inline" and skip them — emit each one as its own requirement record (document_name can describe the response being required, e.g. "Turnkey AMI Project Experience Documentation", "Non-Affiliation Attestation", "Statement of Years of Firm Experience").
{anchors_text}

FORMAT / STRUCTURAL REQUIREMENTS ARE IN SCOPE — AND ARE THE MOST COMMONLY MISSED. A real FaithForge bid was rejected for a wrong volume structure, not for a missing form. Before you finish, scan this excerpt AGAIN specifically for each of the following, and emit one requirement for every one that appears. Missing these is a failure even if every attachment was found:
  1. Page limits ("shall not exceed N pages", "no more than N single-sided pages")
  2. Page numbering ("consecutively numbered", "numbered from beginning to end", "all pages shall be numbered")
  3. Tab / section structure ("separated by a TAB", "TAB A", "Tab 1", "tabbed into the specified sections", a listing of Tab A..Tab Q)
  4. Volume structure ("Volume I", "Volume II", "separate volumes", "separate envelopes", "double envelope")
  5. Separate submission ("submit separately from", "shall not be included in the Technical Proposal", "omit all pricing from Volume I")
  6. File format ("searchable Adobe PDF", "Excel format", "a second copy with confidential information redacted")
  7. PDF bookmarking ("bookmarked to enable navigation")
  8. Number of copies ("one original and N copies")
  9. Delivery channel ("only via eMMA", "hand delivery only", "email will not be accepted")
Emit each with `"category": "Proposal Section Keywords"` and a `document_name` naming the constraint, e.g. "Technical Proposal — 60 page limit", "Proposal tabbed into TAB A-Q", "All pages consecutively numbered", "Price Proposal submitted separately from Technical Proposal", "Technical Proposal in searchable PDF + redacted copy".

ONE REQUIREMENT PER DOCUMENT, NOT PER FIELD. If several lines are fields, signature blocks, or numbered clauses INSIDE a single named form, emit ONE requirement for that form — not one per line. For example a Bid/Proposal Affidavit containing "Affirmation Regarding Bribery Convictions", "Affirmation Regarding Collusion", "Signature of Authorized Representative" and "Printed Name of Affiant" is ONE requirement ("Bid/Proposal Affidavit"), with the notable sub-parts summarized in `notes`. Splitting a form into its own fields buries the real checklist in noise.

SUBMITTALS ONLY — NOT ONGOING CONTRACT PERFORMANCE. Extract what the offeror submits WITH THE PROPOSAL, plus one-time documents explicitly required upon notice of award (e.g. a Contract Affidavit, an NDA, an insurance certificate due within N days of award) — mark those `"due_before_submission": false` and say so in `notes`. Do NOT emit recurring obligations performed AFTER award during the contract term: monthly invoices, timesheets, quarterly or annual reports, notices of claim, price-adjustment requests, personnel substitution requests, performance-evaluation forms. Those are contract administration, not checklist items.

STRUCTURED KEYWORD LIBRARY (13 categories — use these to recognize and classify requirements):
{keyword_library}

HOW TO USE THE 13 CATEGORIES. Three of them describe LANGUAGE, not document types, and must never be used as a requirement's `category`:
  * "Mandatory Requirement Keywords" (1) and "Compliance Language" (10) are how you RECOGNISE that something is required — they are triggers, not classifications.
  * "Proposal Section Keywords" (2) is the correct `category` ONLY for format/structural requirements (volume split, tab order, page limits, numbering, file format, copies) — not for a document that merely happens to live in one of those sections.
Every requirement naming an actual deliverable must be classified into one of the DOCUMENT-TYPE categories: Administrative Documents (3), Certifications and Compliance Forms (4), Legal and Registration Documents (5), Technical Proposal Documents (6), Experience and Personnel Documents (7), Pricing Documents (8), Attachments and Forms (9), Insurance Requirements (11), Financial Documents (12), or Contract Documents (13). If a deliverable seems to fit only category 1 or 10, you have found the trigger language — name the actual document it demands and classify THAT.

FILL `required_file_format` AND `number_of_copies` ON THE REQUIREMENT THEY APPLY TO. If the solicitation says a submittal must be a searchable PDF, submitted in Excel, provided as a redacted second copy, or supplied as "one original and three copies", record it on that requirement's own field — not only as a standalone structural item. When a format or copy count applies to a whole volume, set it on that volume's requirement. Leave the field null when the document genuinely does not say; never guess a format because it is customary.

EXISTING OPPORTUNITY DATA:
{opportunity_context}

DOCUMENT EXCERPT (this is a PORTION of a larger document — do not assume anything not shown here, and do not worry that a requirement might already be covered by another portion; duplicates across excerpts are merged automatically):
{documents_text}

Respond with ONLY valid JSON, using this exact schema:
{{
  "requirements": [
    {{
      "document_name": "<name of the required document/deliverable>",
      "category": "<one of the 13 category names above, exact string match>",
      "required": true|false,
      "mandatory": true|false,
      "proposal_section": "<which section of the RFP this was found in, or null>",
      "page_number": "<page reference if stated, or null>",
      "due_before_submission": true|false,
      "signature_required": true|false,
      "notarization_required": true|false,
      "template_reference": "<e.g. 'Attachment C' / 'Form B' / 'Exhibit A', or null>",
      "required_file_format": "<e.g. PDF, Word, or null>",
      "number_of_copies": "<e.g. '1 original + 3 copies', or null>",
      "on_file": true|false,
      "source_quote": "<REQUIRED — the verbatim sentence/line from this excerpt stating the requirement. Do not emit the requirement if you cannot quote it exactly.>",
      "notes": "<any additional instruction specific to this item, or null>"
    }}
  ],
  "sections_identified": ["<list of proposal section names found in this excerpt>"],
  "extraction_summary": "<2-3 sentence summary of coverage and any ambiguity in this excerpt>"
}}"""


def extract_structured_checklist(
    opportunity_context: str,
    documents_text: str,
    anchors_text: str = "",
) -> Dict[str, Any]:
    """Multi-step structured requirement extraction over ONE chunk of ONE
    document (see STRUCTURED_CHECKLIST_PROMPT and _chunk_document). Runs on
    EXTRACTION_MODEL, not MODEL — this is the safety-critical path.

    Mirrors review_documents()'s sizing/budget/call/parse pattern — same
    doc_char_budget sizing, same extract_json, same STANDING_DOCS_PREAMBLE-style
    "what's on file" comparison (here reused via load_standing_documents()
    directly, now producing a boolean per-item instead of a text suffix).
    """
    # 8000, not 4096: each requirement costs ~150 output tokens (12 fields plus
    # a verbatim source_quote), so 4096 capped a chunk at ~27 requirements — and
    # a dense one (a Vendor Questionnaire chunk emitted 20 on its own) could hit
    # the ceiling mid-JSON. Truncated JSON does not parse, and an unparseable
    # response now raises, which would cost the entire chunk. Output tokens on
    # mini are cheap; a lost chunk is not.
    max_tokens = 8000
    keyword_library = render_keyword_library_for_prompt()
    standing_documents = load_standing_documents()
    overhead = STRUCTURED_CHECKLIST_PROMPT.format(
        standing_documents=standing_documents,
        keyword_library=keyword_library,
        opportunity_context=opportunity_context,
        documents_text="",
        anchors_text=anchors_text,
    )
    max_doc_chars = doc_char_budget(SYSTEM_PROMPT, overhead, max_tokens)
    fitted_text, was_truncated = fit_documents_to_budget(documents_text, max_doc_chars)
    prompt = STRUCTURED_CHECKLIST_PROMPT.format(
        standing_documents=standing_documents,
        keyword_library=keyword_library,
        opportunity_context=opportunity_context,
        documents_text=fitted_text,
        anchors_text=anchors_text,
    )
    # temperature=0: this is the safety-critical extraction path, and an
    # audit trial run showed default sampling temperature non-deterministically
    # dropping several real requirements (e.g. Minimum-Qualification narrative
    # items) from run to run on the same chunk. Pinning temperature removes
    # that source of recall variance — it does not affect screening,
    # outreach, or packet-building calls, which keep their own defaults.
    raw = call_openai(prompt, max_tokens=max_tokens, model=EXTRACTION_MODEL, temperature=0)
    result = extract_json(raw)
    if not result or "requirements" not in result:
        # RAISE rather than return an empty result. Returning {} here made an
        # unparseable response indistinguishable from "this chunk genuinely
        # contained no requirements" — the chunk vanished from the checklist
        # while the review still reported itself complete. That is the same
        # silent-loss failure a transient connection error caused, and the
        # caller already knows how to handle it: the orchestrator counts a
        # raised chunk in failed_chunks and marks the whole extraction
        # INCOMPLETE, so a human is told to re-run instead of trusting a
        # checklist with a hole in it.
        raise RuntimeError(
            "Structured checklist extraction returned an unparseable response "
            f"({len(raw or '')} chars) — chunk not analyzed."
        )
    result["input_truncated"] = was_truncated
    return result


def _merge_batch(batch: List[Tuple[str, str, str]]) -> Tuple[str, str, str]:
    """Fold several small documents into one work unit for a single call.

    Each keeps a `=== filename ===` header so the model (and the reader of a
    source_quote) can still tell which document a requirement came from. Role
    is "amendment" if any member is one — amendments change requirements, and
    the stricter reading is the safe one.
    """
    if len(batch) == 1:
        return batch[0]
    names = [item[0] for item in batch]
    combined = "\n\n".join(f"=== {name} ===\n{body}" for name, body, _ in batch)
    role = "amendment" if any(item[2] == "amendment" for item in batch) else "solicitation"
    return (f"{len(batch)} small documents ({', '.join(names)})", combined, role)


def _requirement_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


_DOC_HEADER_RE = re.compile(r"^=== (.*?) ===\n", re.DOTALL)


def _split_doc_header(doc_text: str) -> Tuple[str, str]:
    """main.py builds each doc_texts entry as f"=== {filename} ===\\n{text}".
    Peel that header off so anchor-scanning/quote-verification operate on the
    document's actual text (offsets/quotes must refer to real document
    content, not our own header line)."""
    m = _DOC_HEADER_RE.match(doc_text or "")
    if m:
        return m.group(1).strip(), (doc_text or "")[m.end():]
    return "", doc_text or ""


def _normalize_for_match(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().casefold()


def verify_source_quotes(requirements: List[Dict[str, Any]], source_text: str) -> List[Dict[str, Any]]:
    """Deterministic, code-side check that every requirement's source_quote
    really appears in the document it was supposedly extracted from. This is
    the safety-critical line in the whole rebuild: a false "complete" (a
    fabricated requirement nobody questions because it's marked on_file) is
    far more dangerous than a false "unsure" (a requirement flagged
    UNVERIFIED that a human then checks by hand).
    """
    norm_source = _normalize_for_match(source_text)
    out: List[Dict[str, Any]] = []
    for req in requirements:
        r = dict(req)
        quote = (r.get("source_quote") or "").strip()
        verified = False
        if quote:
            norm_quote = _normalize_for_match(quote)
            if norm_quote and norm_quote in norm_source:
                verified = True
            elif norm_quote and len(norm_quote) > 0 and norm_quote[:40] in norm_source:
                verified = True
        r["quote_verified"] = verified
        if not verified:
            # Safety-critical: force on_file False so a fabricated/unverifiable
            # item can never auto-satisfy the downstream gap check.
            r["on_file"] = False
            addition = "UNVERIFIED — could not locate this text in the source document; confirm manually."
            existing_notes = (r.get("notes") or "").strip()
            r["notes"] = f"{existing_notes} {addition}".strip() if existing_notes else addition
        out.append(r)
    return out


def _locate_quote_offset(quote: str, text: str) -> Optional[int]:
    """Best-effort offset of `quote` inside `text`, tolerant of whitespace
    differences (the model may normalize line breaks). Used only for the
    coverage-gap distance check — not part of quote verification itself."""
    quote = (quote or "").strip()
    if not quote:
        return None
    idx = text.find(quote)
    if idx != -1:
        return idx
    tokens = quote.split()
    if not tokens:
        return None
    pattern = r"\s+".join(re.escape(t) for t in tokens[:40])
    try:
        m = re.search(pattern, text, re.IGNORECASE)
    except re.error:
        return None
    return m.start() if m else None


def compute_coverage_gaps(
    anchors: List[Dict[str, Any]],
    requirements: List[Dict[str, Any]],
    text: str,
) -> List[Dict[str, Any]]:
    """For each HIGH-strength anchor, is there a VERIFIED requirement whose
    source_quote occurs within ±2500 chars of that anchor's offset? If not,
    it's a coverage gap — a place the document uses mandatory submittal
    language that produced no checklist item. This is what turns a silent
    miss into a visible pointer a human can go check.
    """
    verified_offsets: List[int] = []
    for r in requirements:
        if not r.get("quote_verified"):
            continue
        offset = _locate_quote_offset(r.get("source_quote", ""), text)
        if offset is not None:
            verified_offsets.append(offset)

    gaps: List[Dict[str, Any]] = []
    for a in anchors:
        if a.get("strength") != "high":
            continue
        if any(abs(a["offset"] - off) <= 2500 for off in verified_offsets):
            continue
        gaps.append({
            "line_no": a["line_no"], "line": a["line"],
            "offset": a["offset"], "patterns": a["patterns"],
        })

    gaps.sort(key=lambda g: g["offset"])
    merged: List[Dict[str, Any]] = []
    for g in gaps:
        if merged and abs(g["offset"] - merged[-1]["offset"]) <= 400:
            continue
        merged.append(g)
    return merged[:40]


def extract_structured_checklist_for_documents(
    opportunity_context: str,
    doc_texts: List[str],
) -> Dict[str, Any]:
    """The real fix for the audit's recall collapse + fabrication + wrong-
    source failures on a real 161K-char RFP. Per document:

    1. classify_document_role() — background_reference / pricing_form
       documents (e.g. an internal lessons-learned retrospective) are skipped
       entirely for requirement extraction, only recorded in
       documents_analyzed. This alone kills wrong-source extraction.
    2. scan_requirement_anchors() — deterministic keyword scan of the whole
       document, independent of the model.
    3. _chunk_document() + extract_structured_checklist() PER CHUNK, each
       call given that chunk's own anchors to account for. Small windows
       enumerate reliably; one enormous blob does not.
    4. Merge requirements across chunks/documents (existing dedupe logic,
       OR-ing boolean flags, filling empty text fields) — preferring a
       VERIFIED source_quote over an unverified one when merging duplicates.
    5. verify_source_quotes() against that document's full text.
    6. compute_coverage_gaps() against that document's anchors + verified
       requirements.

    One chunk failing must not lose the others — same per-document resilience
    pattern this function already had, extended to chunks.
    """
    empty_result = {
        "requirements": [], "sections_identified": [], "extraction_summary": "No documents to analyze.",
        "input_truncated": False, "coverage_gaps": [], "documents_analyzed": [], "unverified_count": 0,
        "failed_chunks": 0, "extraction_incomplete": False,
    }
    if not doc_texts:
        return empty_result

    all_requirements: List[Dict[str, Any]] = []
    seen_keys: Dict[str, int] = {}  # requirement key -> index in all_requirements
    all_sections: List[str] = []
    seen_sections = set()
    summaries = []
    any_truncated = False
    documents_analyzed: List[Dict[str, Any]] = []
    all_coverage_gaps: List[Dict[str, Any]] = []
    failed_chunks_total = 0

    # Classify first, then group. Documents smaller than the extraction
    # prompt's own overhead (~14k chars) are batched together so a 900-char
    # amendment doesn't cost a full call of instructions to read. Batching
    # concatenates text — unlike anchor-narrowing (tried and rejected above),
    # it removes nothing, so recall is unaffected.
    pending: List[Tuple[str, str, str]] = []  # (filename, body_text, role)
    for doc_text in doc_texts:
        filename, body_text = _split_doc_header(doc_text)
        filename = filename or "(unnamed document)"
        role = classify_document_role(filename, body_text)
        if role in ("background_reference", "pricing_form", "form_template"):
            documents_analyzed.append({
                "name": filename, "role": role, "chunks": 0,
                "requirements_found": 0, "chunks_failed": 0,
            })
            continue
        pending.append((filename, body_text, role))

    small = [d for d in pending if len(d[1]) <= SMALL_DOC_CHARS]
    large = [d for d in pending if len(d[1]) > SMALL_DOC_CHARS]

    work_units: List[Tuple[str, str, str]] = list(large)
    batch: List[Tuple[str, str, str]] = []
    batch_len = 0
    for item in small:
        if batch and batch_len + len(item[1]) > SMALL_DOC_BATCH_CHARS:
            work_units.append(_merge_batch(batch))
            batch, batch_len = [], 0
        batch.append(item)
        batch_len += len(item[1])
    if batch:
        work_units.append(_merge_batch(batch))

    for filename, body_text, role in work_units:
        anchors = scan_requirement_anchors(body_text)

        # Send the full document. Two attempts to send less were measured and
        # BOTH cost recall, because the binding constraint is not input size:
        # the model emits a bounded number of requirements per call (~8-20), so
        # recall tracks the NUMBER OF CALLS, not how much text each one sees.
        #   - padding every anchor into ~200 fragments: 28/31 -> 16-21/31
        #   - sending only the dense requirement sections: 28/31 -> 17/31
        #     (15 requirements returned vs 47 — fewer, denser chunks meant
        #      fewer calls, and each call still capped out)
        # Cost is therefore controlled by the model and by not mining documents
        # that state no requirements — not by trimming the text. Do not
        # re-introduce input trimming without re-running ami_ground_truth.md.
        chunks = _chunk_document(body_text, chunk_chars=NARROWED_CHUNK_CHARS)
        doc_requirements: List[Dict[str, Any]] = []
        doc_failed_chunks = 0

        for start, chunk_text in chunks:
            try:
                anchors_text = render_anchors_for_prompt(anchors, start, start + len(chunk_text))
                result = extract_structured_checklist(opportunity_context, chunk_text, anchors_text)
            except Exception as e:
                # A failed chunk is a HOLE in the checklist, not a footnote.
                # Count it so the caller can refuse to present this as a
                # complete review — see extraction_incomplete below.
                doc_failed_chunks += 1
                failed_chunks_total += 1
                summaries.append(f"[A chunk of {filename} failed to analyze: {e}]")
                continue
            if result.get("input_truncated"):
                any_truncated = True
            for section in (result.get("sections_identified") or []):
                key = section.strip().lower()
                if key and key not in seen_sections:
                    seen_sections.add(key)
                    all_sections.append(section)
            summary = (result.get("extraction_summary") or "").strip()
            if summary:
                summaries.append(summary)
            for req in (result.get("requirements") or []):
                name = (req.get("document_name") or "").strip()
                if not name:
                    continue
                doc_requirements.append(req)

        # Code-side verification against this document's FULL text (not just
        # the chunk it was extracted from) — a requirement near a chunk
        # boundary should still verify against the whole document.
        verified_requirements = verify_source_quotes(doc_requirements, body_text)

        for req in verified_requirements:
            name = (req.get("document_name") or "").strip()
            key = _requirement_key(name)
            if key in seen_keys:
                # Same requirement named more than once (e.g. restated across
                # chunks/documents) — merge rather than duplicate. Never let a
                # duplicate silently downgrade a flag another source already set.
                existing = all_requirements[seen_keys[key]]
                for flag in ("required", "mandatory", "due_before_submission",
                             "signature_required", "notarization_required", "on_file"):
                    if req.get(flag):
                        existing[flag] = True
                for text_field in ("proposal_section", "page_number", "template_reference",
                                   "required_file_format", "number_of_copies", "notes"):
                    if not existing.get(text_field) and req.get(text_field):
                        existing[text_field] = req.get(text_field)
                # Keep a verified source_quote over an unverified one.
                if req.get("quote_verified") and not existing.get("quote_verified"):
                    existing["source_quote"] = req.get("source_quote")
                    existing["quote_verified"] = True
            else:
                seen_keys[key] = len(all_requirements)
                all_requirements.append(dict(req))

        documents_analyzed.append({
            "name": filename, "role": role, "chunks": len(chunks),
            "requirements_found": len(verified_requirements),
            "chunks_failed": doc_failed_chunks,
        })

        all_coverage_gaps.extend(compute_coverage_gaps(anchors, verified_requirements, body_text))

    all_coverage_gaps = all_coverage_gaps[:40]
    unverified_count = sum(1 for r in all_requirements if r.get("quote_verified") is False)

    # Never claim a full review when part of a document was lost. The audit
    # that prompted this found a transient connection error destroying the
    # chunk containing an entire Vendor Questionnaire (20 mandatory
    # submittals) while the summary still read "to ensure each was fully
    # reviewed" — reassuring text over a hole in the checklist is exactly how
    # a bid goes out missing forms.
    if failed_chunks_total:
        lead = (
            f"⚠ INCOMPLETE — {failed_chunks_total} section(s) of the uploaded documents could not be "
            "analyzed, so requirements stated in them are MISSING from this checklist. Re-run the AI "
            "review before relying on it. "
        )
    else:
        lead = (
            f"Analyzed {len(doc_texts)} document(s) individually (chunked, with per-document role "
            "classification and code-side source-quote verification) to ensure each was fully reviewed. "
        )
    extraction_summary = (lead + " ".join(summaries)).strip()

    return {
        "requirements": all_requirements,
        "sections_identified": all_sections,
        "extraction_summary": extraction_summary,
        "input_truncated": any_truncated,
        "coverage_gaps": all_coverage_gaps,
        "documents_analyzed": documents_analyzed,
        "unverified_count": unverified_count,
        "failed_chunks": failed_chunks_total,
        "extraction_incomplete": bool(failed_chunks_total),
    }


# ─── Pre-submission gap check (step 5 of Bernedette's workflow) ────────────
#
# Steps 1-4 of her requested workflow (identify sections -> extract
# requirements -> classify -> build checklist) are extract_structured_checklist()
# above. This is the final step: "compare the extracted requirements against
# available proposal documents to identify any gaps before submission." It
# runs against a caller-designated set of RESPONSE materials (NOT the
# solicitation documents extract_structured_checklist reads) — see the
# endpoint in main.py for how those are assembled.
#
# COMPLIANCE SAFETY: a false "satisfied" is far more dangerous than a false
# "missing" here — it stops a human from looking for a document whose absence
# gets a bid rejected. Three verdicts (never two), evidence required for any
# "satisfied", "uncertain" as the default when unsure. Mirrors the same
# discipline packet_builder.ANALYZE_DRAFT_PROMPT's checklist_items_addressed
# note already uses ("never claim satisfied without real evidence"), applied
# here per-requirement across the whole assembled package instead of a single
# draft-vs-gaps narrative.

SUBMISSION_GAP_PROMPT = """You are performing a pre-submission compliance gap check for FaithForge — the final check before a proposal goes out the door. Real FaithForge bids have previously been rejected for missing attachments, so precision matters far more than confidence here.

EXISTING OPPORTUNITY DATA:
{opportunity_context}

EXTRACTED REQUIREMENTS (decide, for EACH one, whether the response materials below satisfy it):
{requirements_json}

ASSEMBLED RESPONSE MATERIALS BEING CHECKED (the actual response package — each source is delimited by a "=== source name ===" header so you can cite it in "found_in"):
{response_materials}

Use THREE verdicts only — never just two:
- "satisfied" — the response materials clearly and concretely address this requirement. You MUST provide real quoted or closely paraphrased evidence from the response materials AND name the source document/section in "found_in". If you cannot point to actual evidence you found in the text, you may NOT use "satisfied".
- "missing" — the response materials do not appear to address this requirement anywhere.
- "uncertain" — you are not confident, the evidence is ambiguous or partial, OR this is a conditional item that a human must judge.

CRITICAL SAFETY RULE — read this twice: when in doubt, ALWAYS choose "uncertain" over "satisfied". Never invent or assume evidence. A false "satisfied" is far more dangerous than a false "missing" or "uncertain": it tells a human to stop looking for a document whose absence could get the whole bid rejected. This is a suggestion for a human to verify before submission, NOT a final determination of compliance.

Special handling (apply before general judgment):
- If a requirement's "on_file" field is true, it is a FaithForge standing document (e.g. signed W-9, certificate of insurance) that FaithForge keeps on file and attaches separately — it will legitimately NOT appear anywhere in the response text. Mark these "satisfied" with reason "held on file by FaithForge" and evidence null. Do not flag these missing just because the text doesn't mention them.
- If a requirement's "required" field is false (a conditional / "if applicable" item), ALWAYS mark it "uncertain" — never "satisfied" and never "missing" — with a reason noting a human must decide whether it applies to this submission.

Respond with ONLY valid JSON (no prose, no markdown fences), using this exact schema:
{{
  "findings": [
    {{
      "document_name": "<must exactly match the requirement's document_name above so the UI can join them>",
      "status": "satisfied" | "missing" | "uncertain",
      "evidence": "<quoted or closely paraphrased text from the response materials, or null>",
      "found_in": "<the source document/section name it was found in, or null>",
      "reason": "<one short sentence explaining the verdict>"
    }}
  ],
  "summary": "<2-3 sentences: overall submission readiness and the most important gaps>"
}}

Return exactly one finding per requirement listed above — never skip one, never merge two requirements into one finding."""


def check_submission_gaps(
    opportunity_context: str,
    requirements: List[Dict[str, Any]],
    response_materials: str,
) -> Dict[str, Any]:
    """Per-requirement satisfied/missing/uncertain verdicts comparing the
    structured checklist's requirements against the assembled response package.

    Mirrors review_documents()/extract_structured_checklist()'s sizing
    (doc_char_budget), call (call_openai), and parse (extract_json) pattern,
    plus the same defensive "never raise past the caller" fallback dict.
    """
    max_tokens = 4096
    # Compact projection — just enough per requirement for the model to judge,
    # not the full record (page_number, copies, format, etc. don't change the
    # verdict and would waste prompt budget better spent on response_materials).
    compact_requirements = [
        {
            "document_name": r.get("document_name"),
            "category": r.get("category"),
            "mandatory": r.get("mandatory"),
            "required": r.get("required"),
            "on_file": r.get("on_file"),
            "template_reference": r.get("template_reference"),
            "notes": r.get("notes"),
        }
        for r in requirements
    ]
    requirements_json = json.dumps(compact_requirements, indent=1)
    overhead = SUBMISSION_GAP_PROMPT.format(
        opportunity_context=opportunity_context,
        requirements_json=requirements_json,
        response_materials="",
    )
    max_doc_chars = doc_char_budget(SYSTEM_PROMPT, overhead, max_tokens)
    fitted_materials, was_truncated = fit_documents_to_budget(response_materials, max_doc_chars)
    prompt = SUBMISSION_GAP_PROMPT.format(
        opportunity_context=opportunity_context,
        requirements_json=requirements_json,
        response_materials=fitted_materials,
    )
    raw = call_openai(prompt, max_tokens=max_tokens)
    result = extract_json(raw)
    if not result or "findings" not in result:
        result = {"findings": [], "summary": "Gap check failed to parse AI response."}
    result["input_truncated"] = was_truncated
    return result
