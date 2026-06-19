import json
import re
from typing import Optional, Dict, Any
from groq import Groq
from config import settings

MODEL = "llama-3.1-70b-versatile"

SYSTEM_PROMPT = """You are an AI assistant for FaithForge, a consulting and services organization based in the Maryland/DC area.

FaithForge's core value proposition is serving as an INDEPENDENT, VENDOR-NEUTRAL program management and consulting overlay for organizations. FaithForge does NOT deliver trade/vocational skills instruction, construction, IT infrastructure, or direct clinical services. FaithForge consults ON programs — it does not execute them.

FaithForge's IDEAL opportunities (score 70-100):
- Government agencies or large nonprofits needing independent PMO, governance, or program oversight
- Organizations managing large-scale change, transformation, or multi-year initiatives needing a management consulting partner
- Workforce development or training PROGRAM MANAGEMENT (designing/managing a program, not delivering trade skills)
- Grants management consulting, technical assistance, or capacity building for nonprofits/public sector
- Curriculum design for professional development, certifications, or public-sector training programs
- DEI consulting, organizational readiness, or change management engagements

FaithForge's WEAK matches (score 40-69 — still worth seeing, but lower priority):
- Vocational or trade skill instruction (cosmetology, barbering, CDL, construction trades, etc.) unless the client is a government agency seeking program management consulting, not instructors
- IT procurement, hardware/software purchases, or infrastructure with no management consulting component
- Opportunities outside Maryland/DC/federal area unless remote/national scope is clear
- Very small dollar value or highly specialized technical work outside FaithForge's domain

FaithForge primarily targets:
- Maryland and DC area government agencies (State, County, City)
- Nonprofits and community organizations
- Educational institutions (K-12, higher ed, workforce programs)
- Healthcare organizations
- Federal agencies with regional offices

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

Respond with ONLY a valid JSON object using this exact schema:
{{
  "classification": "relevant" | "possibly_relevant" | "not_relevant",
  "relevance_score": <integer 0-100>,
  "classification_reasoning": "<brief explanation>",
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
  "contact_person": "<name and title>",
  "contact_email": "<email>",
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
  "submission_checklist": "<complete checklist of everything that must be submitted>",
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


# Groq on_demand (free) tier caps llama-3.3-70b at 12,000 tokens/min, enforced
# per-request. Keep total (system + prompt + completion) safely under that.
TPM_LIMIT = 12000
TPM_SAFETY = 800


def est_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token)."""
    return len(text) // 4 + 1


def fit_prompt_to_budget(system: str, prompt: str, max_tokens: int) -> str:
    """Trim `prompt` so system + prompt + completion stays under the TPM limit."""
    budget = TPM_LIMIT - TPM_SAFETY - max_tokens - est_tokens(system)
    if budget < 400:
        budget = 400
    max_chars = budget * 4
    if len(prompt) > max_chars:
        prompt = prompt[:max_chars] + "\n\n[...input truncated to fit model token limit...]"
    return prompt


def doc_char_budget(system: str, prompt_overhead: str, max_tokens: int) -> int:
    """Max characters of document text that fit, given fixed prompt parts + completion."""
    used = est_tokens(system) + est_tokens(prompt_overhead) + max_tokens + TPM_SAFETY
    return max(400, TPM_LIMIT - used) * 4


def call_groq(prompt: str, system: str = SYSTEM_PROMPT, max_tokens: int = 4096) -> str:
    prompt = fit_prompt_to_budget(system, prompt, max_tokens)
    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
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
    raw = call_groq(prompt)
    result = extract_json(raw)
    if not result:
        result = {
            "classification": "not_relevant",
            "relevance_score": 0,
            "classification_reasoning": "AI analysis failed to parse response",
        }
    return result


def review_documents(
    opportunity_context: str,
    documents_text: str,
) -> Dict[str, Any]:
    max_tokens = 4096
    overhead = DOCUMENT_REVIEW_PROMPT.format(
        opportunity_context=opportunity_context, documents_text=""
    )
    max_doc_chars = doc_char_budget(SYSTEM_PROMPT, overhead, max_tokens)
    prompt = DOCUMENT_REVIEW_PROMPT.format(
        opportunity_context=opportunity_context,
        documents_text=documents_text[:max_doc_chars],
    )
    raw = call_groq(prompt, max_tokens=max_tokens)
    result = extract_json(raw)
    if not result:
        result = {
            "review_summary": "Document review failed to parse AI response.",
            "opportunity_summary": raw[:1000] if raw else "No response",
        }
    return result
