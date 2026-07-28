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
# Bernedette Atong's exact terms, verbatim from her 2026-07-28 feedback email.
MANDATORY_LANGUAGE_KEYWORDS = [
    "required", "shall", "must", "mandatory", "submit", "include", "provide",
    "complete", "attach", "furnish", "enclose", "deliver", "upload",
    "proposal shall contain", "required documents", "required forms",
    "failure to provide", "non-responsive", "responsive bidder",
    "submission requirements",
]

# 2. Proposal-section keywords — names of the sections an RFP organizes itself into.
# Bernedette Atong's exact terms, verbatim from her 2026-07-28 feedback email.
PROPOSAL_SECTION_KEYWORDS = [
    "proposal requirements", "submission instructions", "proposal format",
    "proposal organization", "proposal contents", "required attachments",
    "required forms", "administrative requirements", "compliance requirements",
    "technical proposal", "cost proposal", "qualifications",
    "evaluation criteria", "appendices", "exhibits", "attachments", "forms",
    "schedules",
]

# 3. Administrative documents.
# Bernedette Atong's exact terms, verbatim from her 2026-07-28 feedback email.
ADMINISTRATIVE_DOCUMENT_KEYWORDS = [
    "cover letter", "letter of transmittal", "executive summary",
    "company profile", "firm profile", "capability statement",
    "corporate overview", "business information", "organization information",
]

# 4. Certifications / compliance forms.
# Bernedette Atong's exact terms, verbatim from her 2026-07-28 feedback email.
CERTIFICATION_COMPLIANCE_KEYWORDS = [
    "equal opportunity certification", "non-collusion affidavit",
    "conflict of interest certification", "ethics certification",
    "debarment certification", "anti-lobbying certification",
    "drug-free workplace certification", "compliance certification",
    "disclosure statements",
]

# 5. Legal / registration documents.
# Bernedette Atong's exact terms, verbatim from her 2026-07-28 feedback email.
LEGAL_REGISTRATION_KEYWORDS = [
    "business license", "articles of incorporation", "articles of organization",
    "certificate of good standing", "w-9", "ein", "uei", "sam registration",
    "duns", "mbe", "dbe", "wbe", "sbe certifications",
    "certificates of insurance", "bonding documentation", "performance bonds",
    "bid bonds", "payment bonds",
]

# 6. Technical proposal documents.
# Bernedette Atong's exact terms, verbatim from her 2026-07-28 feedback email.
TECHNICAL_PROPOSAL_KEYWORDS = [
    "technical proposal", "technical approach", "management approach",
    "methodology", "project plan", "work plan", "staffing plan",
    "organizational chart", "communication plan", "quality assurance plan",
    "risk management plan", "change management plan", "transition plan",
    "implementation plan", "project schedule", "gantt chart", "deliverables",
    "milestones",
]

# 7. Experience / personnel documents.
# Bernedette Atong's exact terms, verbatim from her 2026-07-28 feedback email.
EXPERIENCE_PERSONNEL_KEYWORDS = [
    "relevant experience", "past performance", "references",
    "client references", "similar projects", "case studies", "key personnel",
    "staff qualifications", "team resumes", "professional certifications",
    "organizational experience",
]

# 8. Pricing documents.
# Bernedette Atong's exact terms, verbatim from her 2026-07-28 feedback email.
PRICING_DOCUMENT_KEYWORDS = [
    "price proposal", "cost proposal", "financial proposal", "pricing sheet",
    "fee schedule", "budget", "labor rates", "rate card", "cost breakdown",
    "compensation schedule", "bid forms",
]

# 9. Attachments and forms.
# Bernedette Atong's exact terms, verbatim from her 2026-07-28 feedback email.
ATTACHMENT_FORM_KEYWORDS = [
    "attachment a", "attachment b", "attachment c", "exhibit a", "exhibit b",
    "schedule a", "appendix a", "form a", "form b", "required forms",
    "signature pages", "acknowledgement forms",
]

# 10. Compliance language — phrasing used to state general obligations/conditions.
# Bernedette Atong's exact terms, verbatim from her 2026-07-28 feedback email.
COMPLIANCE_LANGUAGE_KEYWORDS = [
    "completed and signed", "executed copy", "duly executed",
    "original signature", "authorized representative", "must be completed",
    "complete and return", "failure to submit", "proposal may be rejected",
    "proposal will be deemed non-responsive", "include at a minimum",
    "submit the following",
]

# 11. Insurance requirements.
# Bernedette Atong's exact terms, verbatim from her 2026-07-28 feedback email.
INSURANCE_KEYWORDS = [
    "general liability", "professional liability", "errors and omissions",
    "cyber liability", "workers compensation", "automobile liability",
    "umbrella coverage", "certificate of insurance",
]

# 12. Financial documents.
# Bernedette Atong's exact terms, verbatim from her 2026-07-28 feedback email.
FINANCIAL_DOCUMENT_KEYWORDS = [
    "financial statements", "audited financial statements", "balance sheet",
    "income statement", "bank letter", "financial capacity", "bonding letter",
]

# 13. Contract documents.
# Bernedette Atong's exact terms, verbatim from her 2026-07-28 feedback email.
CONTRACT_DOCUMENT_KEYWORDS = [
    "sample contract", "terms and conditions", "contract exceptions",
    "redlines", "contract acceptance", "exceptions matrix",
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
