# Structured compliance-checklist keyword library.
#
# Implements Bernedette Atong's feedback (2026-07-28) that the RFP-review AI
# was missing required documents on real bids (the MCPS contract had missing
# attachments and an incorrect Volume II structure). She asked for a
# structured keyword library, organized into 13 logical categories, so the
# application can identify required deliverables more accurately instead of
# relying on a single freeform extraction pass.
#
# Follows the same plain-list-constant convention as CONTRACT_KEYWORDS,
# FAITHFORGE_SERVICE_KEYWORDS, MARYLAND_KEYWORDS, and EMMA_INDICATORS in
# config.py — this is a scanning/classification reference, not narrative
# content, so it lives as Python constants rather than a knowledge_base
# markdown file.

# 1. Mandatory-language keywords — obligation language that signals a hard requirement.
MANDATORY_LANGUAGE_KEYWORDS = [
    "shall", "must", "required", "mandatory", "shall submit", "shall provide",
    "shall include", "is required to", "will be required", "failure to comply",
    "non-negotiable", "compulsory", "obligatory", "shall be submitted",
    "must be submitted", "required to submit", "shall not exceed",
    "must include", "shall demonstrate", "shall furnish",
]

# 2. Proposal-section keywords — names of the sections an RFP organizes itself into.
PROPOSAL_SECTION_KEYWORDS = [
    "proposal requirements", "submission instructions", "proposal format",
    "required attachments", "evaluation criteria", "volume i", "volume ii",
    "volume iii", "technical proposal", "cost proposal", "price proposal",
    "management proposal", "executive summary", "scope of work",
    "statement of work", "instructions to offerors", "instructions to bidders",
    "proposal organization", "table of contents", "proposal contents",
    "general requirements", "special conditions", "terms and conditions",
]

# 3. Administrative documents.
ADMINISTRATIVE_DOCUMENT_KEYWORDS = [
    "letter of transmittal", "cover letter", "cover sheet", "signature page",
    "acknowledgement of addenda", "addendum acknowledgement", "bid bond",
    "proposal bond", "vendor registration", "company profile",
    "organizational chart", "business license", "conflict of interest disclosure",
    "conflict of interest statement", "letter of intent", "questionnaire",
    "vendor application", "proposal checklist",
]

# 4. Certifications / compliance forms.
CERTIFICATION_COMPLIANCE_KEYWORDS = [
    "non-collusion affidavit", "certificate of non-collusion", "debarment certification",
    "certification regarding debarment", "suspension certification",
    "equal employment opportunity certification", "eeo certification",
    "affirmative action certification", "drug-free workplace certification",
    "lobbying certification", "certification of independent price determination",
    "mbe certification", "wbe certification", "sbe certification", "dbe certification",
    "hipaa compliance certification", "conflict of interest certification",
    "iran certification", "boycott certification", "living wage certification",
]

# 5. Legal / registration documents.
LEGAL_REGISTRATION_KEYWORDS = [
    "w-9", "w9", "articles of incorporation", "articles of organization",
    "certificate of good standing", "business registration", "sam.gov registration",
    "uei", "unique entity id", "cage code", "duns number", "state registration",
    "trade name registration", "operating agreement", "business license number",
    "federal tax id", "ein", "taxpayer identification number",
]

# 6. Technical proposal documents.
TECHNICAL_PROPOSAL_KEYWORDS = [
    "technical approach", "work plan", "project plan", "methodology",
    "implementation plan", "transition plan", "quality assurance plan",
    "risk management plan", "staffing plan", "schedule of deliverables",
    "project timeline", "gantt chart", "technical narrative",
    "solution architecture", "performance work statement",
]

# 7. Experience / personnel documents.
EXPERIENCE_PERSONNEL_KEYWORDS = [
    "resumes", "resumes of key personnel", "key personnel", "staff qualifications",
    "past performance references", "references", "client references",
    "case studies", "organizational experience", "corporate experience",
    "personnel qualifications", "key staff bios", "letters of recommendation",
    "similar project experience", "subcontractor experience",
]

# 8. Pricing documents.
PRICING_DOCUMENT_KEYWORDS = [
    "price proposal", "cost proposal", "pricing schedule", "rate schedule",
    "fee schedule", "budget narrative", "cost breakdown", "line-item budget",
    "price sheet", "cost/price proposal", "labor rate schedule",
    "cost proposal form", "budget justification",
]

# 9. Attachments and forms.
ATTACHMENT_FORM_KEYWORDS = [
    "attachment a", "attachment b", "attachment c", "attachment d",
    "exhibit a", "exhibit b", "exhibit c", "form a", "form b", "form c",
    "appendix a", "appendix b", "schedule a", "schedule b",
    "required form", "attachment", "exhibit", "appendix", "template",
]

# 10. Compliance language — phrasing used to state general obligations/conditions.
COMPLIANCE_LANGUAGE_KEYWORDS = [
    "in accordance with", "compliance with", "subject to", "as specified herein",
    "pursuant to", "in conformance with", "at a minimum", "no exceptions",
    "responsive and responsible", "responsiveness requirement",
    "non-compliance may result in", "grounds for rejection", "grounds for disqualification",
]

# 11. Insurance requirements.
INSURANCE_KEYWORDS = [
    "certificate of insurance", "coi", "general liability insurance",
    "professional liability insurance", "errors and omissions", "e&o insurance",
    "workers compensation insurance", "workers' compensation", "automobile liability insurance",
    "umbrella liability insurance", "cyber liability insurance",
    "additional insured endorsement", "acord 25", "insurance certificate",
]

# 12. Financial documents.
FINANCIAL_DOCUMENT_KEYWORDS = [
    "audited financial statements", "financial statements", "bank reference letter",
    "line of credit letter", "dun & bradstreet report", "financial capacity",
    "balance sheet", "profit and loss statement", "annual report",
    "bonding capacity letter", "surety letter", "proof of financial stability",
]

# 13. Contract documents.
CONTRACT_DOCUMENT_KEYWORDS = [
    "sample contract", "draft contract", "contract terms and conditions",
    "master services agreement", "teaming agreement", "subcontractor agreement",
    "non-disclosure agreement", "nda", "indemnification clause",
    "termination clause", "contract exhibit", "standard contract provisions",
    "professional services agreement",
]

# Human-readable category name -> keyword list, in Bernedette's original order.
CHECKLIST_KEYWORD_CATEGORIES: dict[str, list[str]] = {
    "Mandatory Requirement Keywords": MANDATORY_LANGUAGE_KEYWORDS,
    "Proposal Section Keywords": PROPOSAL_SECTION_KEYWORDS,
    "Administrative Documents": ADMINISTRATIVE_DOCUMENT_KEYWORDS,
    "Certifications and Compliance Forms": CERTIFICATION_COMPLIANCE_KEYWORDS,
    "Legal and Registration Documents": LEGAL_REGISTRATION_KEYWORDS,
    "Technical Proposal Documents": TECHNICAL_PROPOSAL_KEYWORDS,
    "Experience and Personnel Documents": EXPERIENCE_PERSONNEL_KEYWORDS,
    "Pricing Documents": PRICING_DOCUMENT_KEYWORDS,
    "Attachments and Forms": ATTACHMENT_FORM_KEYWORDS,
    "Compliance Language": COMPLIANCE_LANGUAGE_KEYWORDS,
    "Insurance Requirements": INSURANCE_KEYWORDS,
    "Financial Documents": FINANCIAL_DOCUMENT_KEYWORDS,
    "Contract Documents": CONTRACT_DOCUMENT_KEYWORDS,
}


def render_keyword_library_for_prompt() -> str:
    """Format the 13 categories as a readable numbered-list block for
    interpolation into the structured-extraction prompt, e.g.:

    1. Mandatory Requirement Keywords: shall, must, required, ...
    2. Proposal Section Keywords: proposal requirements, ...
    """
    lines = []
    for i, (category, keywords) in enumerate(CHECKLIST_KEYWORD_CATEGORIES.items(), start=1):
        lines.append(f"{i}. {category}: {', '.join(keywords)}")
    return "\n".join(lines)
