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
Executive, professional, no contractions. FaithForge is a governance and execution partner, not a traditional consulting vendor — an advisor that helps leaders deliver, not one that advises from the sidelines. Use only the facts, metrics, and key phrases provided in the knowledge base above — do not invent statistics, credentials, or claims. Lean on the target-market pain points and buying triggers to tailor language to this specific client's sector.

## ABSOLUTE ANTI-FABRICATION RULE (this governs everything you write)
This is a real proposal that a real firm will submit to a real government agency. Fabricating facts is a disqualifying liability, not a stylistic flaw. Therefore:
- **People:** Bernedette Atong (Founder & Principal Consultant, MSc, PMP, PgMP) is the ONLY real named person. NEVER invent any other named individual, their years of experience, their bio, or their credentials. Do NOT create a "Senior Consultant", "Domain Expert", or any named team member. When the proposal needs a role other than Bernedette, refer to it by role title only (e.g. "Program Manager", "OCM Specialist") and mark the name as **[TO BE NAMED]**.
- **Named-personnel exception (this proposal only):** The rule above applies UNLESS the "## ADDITIONAL INSTRUCTIONS FROM USER" block below explicitly assigns a real name to a specific role for THIS proposal (e.g. a client-ready team roster the firm supplied for this bid). When it does, use exactly those names for exactly those roles and nothing more — do not invent a bio, credential, or years of experience for them beyond what that block states. Any role the instructions do NOT explicitly name still follows the default rule: role title only, **[TO BE NAMED]** (or the exact placeholder phrase the instructions give, e.g. "To be onboarded upon contract award"). This exception never applies when no such instructions are given.
- **Missing facts:** When a required fact is NOT in the knowledge base or the opportunity data — a specific date, contract value, reference contact, FEIN, certification number, subcontractor name, resume detail, or years of experience — do NOT guess or fabricate a plausible-sounding value. Instead emit an inline placeholder in this exact form: **[NOTE TO BERNEDETTE: <what to insert and why>]**. A placeholder Bernedette can fill in 30 seconds is infinitely better than a confident fabrication that loses the bid.
- **Only real credentials/metrics:** Use ONLY the case studies (Amtrak, Inteleos, ASM Global, iHerb), rates, and credentials exactly as they appear in the knowledge base. Never round up, never invent new clients, never attribute a metric to the wrong client.
- **Firm size honesty:** FaithForge is a lean, executive-led firm. Do not imply a large bench of staff. Frame the lean model as a deliberate strength (direct senior-level involvement), exactly as the real proposals do."""


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
  "client_name": "<agency/client name, or null if the data does not state it>",
  "domain": "<the domain, e.g. Utility Transformation, Education and Training>",
  "engagement_months": <integer>,
  "solicitation_number": "<solicitation/RFP number from the data, or null>",
  "secondary_id": "<eMMA/BPM/Lot or other secondary reference from the data, or null>",
  "procurement_officer": "<the AGENCY's procurement/contracting officer name, from the opportunity data or solicitation excerpt ONLY — this is someone who works for the client agency, never Bernedette Atong or anyone from FaithForge (FaithForge's own bio/contact info appears in your system instructions for writing the proposal, not as a source of agency facts). If the data's 'Contact Person' field is actually FaithForge's own founder or a FaithForge email/phone, treat it as missing and set this to null rather than repeating it.>",
  "procurement_officer_contact": "<the AGENCY officer's email/phone from the data, or null — never info@faithforgetech.com, 410-862-2975, or any other FaithForge contact detail>",
  "prepared_for_address": "<agency mailing address from the data, or null — never FaithForge's own address>",
  "submission_method": "<a SHORT concise phrase for how/where to submit, e.g. 'via eMMA', 'email to procurement@agency.gov', 'sealed hard copy to the address above' — distill this from the data, do not copy a full sentence/paragraph verbatim; null if not stated>",
  "due_datetime": "<full bid due date and time from the data, or null>",
  "evaluation_criteria": "<one-line summary of how proposals are scored, from the data, or null>",
  "minimum_qualifications_text": "<quote the EXACT minimum-qualification criteria from the RFP text (years of experience, certifications, licensure thresholds, etc.) ONLY if such specific language is actually present in the opportunity data or solicitation excerpt above. If the RFP explicitly states there are no minimum qualifications (e.g. 'not applicable', 'no minimum qualifications for this procurement'), or never mentions minimum qualifications at all, or you are unsure because the excerpt doesn't cover it, set this to null — do not paraphrase or guess. A null here is the safe default.>",
  "confidentiality_tab_required": <true if the RFP requires a confidentiality claim/statement, else false>,
  "references_required": <integer count of references the RFP requires, or 0 if not stated>,
  "required_key_personnel": ["<exact Key Personnel role title(s) the RFP itself names, e.g. 'Principal', 'Program Manager', 'Principal Planner' — copy the RFP's own wording verbatim, do NOT substitute FaithForge's internal labor-category names. Empty array if the RFP does not name specific required personnel roles/titles.>"],
  "separate_pricing_volume": <true if the RFP or the ADDITIONAL INSTRUCTIONS below require the technical and price/cost proposals to be prepared or submitted as separate volumes or documents (cues: "Volume I"/"Volume II", "separate sealed price proposal/envelope", "do not include pricing in the technical proposal", a standalone price/cost form). Default false — most solicitations accept one combined document; only set true on a real, stated cue.>,
  "org_chart": [{{"role":"<title>","name":"<a real person's name ONLY if the ADDITIONAL INSTRUCTIONS FROM USER block below explicitly assigns that exact role to that exact name for THIS proposal; otherwise '[TO BE NAMED]', or the exact placeholder phrase the instructions give (e.g. 'To be onboarded upon contract award')>","reports_to":"<the exact 'role' string of the node directly above this one in the chart, or null if this is the top node>"}}],
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
- For every metadata field (solicitation_number, procurement_officer, due_datetime, etc.): copy the value ONLY if it actually appears in the opportunity data or solicitation excerpt above. If it is not present, set the field to null — do NOT invent or guess a plausible value. Downstream sections turn null values into "[NOTE TO BERNEDETTE: ...]" placeholders, which is the correct, safe behavior.
- Include 5-7 workstreams/phases covering mobilization/governance, planning/readiness, oversight/execution, organizational readiness/change, customer/stakeholder engagement, go-live/benefits realization (adapt names to the domain).
- Include 8-12 deliverable_products. Every deliverable, report, plan, or document explicitly required by the RFP — whether named in the Required Forms, Required Attachments, Submission Checklist, or Evaluation Criteria above, or found in the solicitation excerpt — MUST appear as its own deliverable_products entry. Do not omit or merge any RFP-mandated deliverable into a generic catch-all line; name it explicitly (e.g. "Monthly Progress Report", "Risk Register", "Governance Charter") so nothing the RFP requires is missing from this list.
- "labor" MUST use FaithForge's real standard role rates: Program Director $220/hr, Principal Consultant $200/hr, Senior Consultant $185/hr, Project Manager $150/hr, Solution/Technical Architect $150/hr, Solution Developer $145/hr, OCM Specialist $100/hr, Business Analyst $98/hr, PMO Coordinator $95/hr, Administrative Support $65/hr. Select the subset of roles appropriate to this opportunity and choose realistic hours scaled to its size. Do not invent rates.
- 4-5 supporting_costs (PMO Tools & Reporting Platform, Executive Workshops & Governance Facilitation, Travel & Onsite Support, Administrative & Quality Assurance Support).
- 4-5 optional_services.
- required_key_personnel: check the compliance data and solicitation excerpt for a "Key Personnel", "Staffing Plan", or "Personnel Qualifications" section that names specific required roles/titles. If found, list those exact titles (this becomes the Key Personnel table in the proposal, so it must match what the evaluator scores against). If the RFP does not name specific roles, return an empty array — FaithForge's internal labor categories will be used instead.
- org_chart: always include exactly one top node for Bernedette Atong (role = her most senior applicable title for this engagement, matching whichever required_key_personnel/labor title is most principal-level). Add one node per remaining role from required_key_personnel (if non-empty) or plan.labor (if required_key_personnel is empty), each reporting to Bernedette's node unless the additional instructions state a different hierarchy. If the ADDITIONAL INSTRUCTIONS FROM USER block gives an explicit team roster/org chart for this proposal, mirror its exact roles, names, and reporting lines instead of the flat default — this is the one place naming staff other than Bernedette Atong is permitted (see the system instructions' named-personnel exception), and it must be done here consistently with how those names are used elsewhere in the proposal.

CRITICAL: Every numeric field must be a single final integer literal (e.g. 162000). NEVER write arithmetic expressions like "100 + 200". Do not include any total fields — totals are computed separately."""

# ── Stage 2: Section writers — each expands the plan into rich, submission-ready prose ──
# The title block (solicitation #, procurement officer, submission method, etc.) is assembled
# deterministically in Python by _render_title_block() instead of via LLM template-filling —
# every value it needs already exists in the plan dict, and letting the model "fill in"
# {{mustache}} placeholders proved unreliable (it has echoed the raw {{field}} syntax verbatim,
# and separately misattributed FaithForge's own contact info as the agency's). Likewise the
# Table of Contents (Section 2) is assembled deterministically by _render_toc() from the fixed
# outline below rather than left to the model.
#
# Full outline (mirrors a formal two-volume government technical-proposal structure):
#   0  Internal Decision Brief (internal only — stripped before submission)
#   1  Letter of Transmittal            10 Risk Management Plan
#   2  Table of Contents                11 Communication Management Plan
#   3  Compliance Matrix                12 Organizational Change Management Plan
#   4  Executive Summary                13 Stakeholder Engagement Plan
#   5  Understanding of Mission/Needs   14 Project Controls and Reporting
#   6  Technical Approach               15 Economic Benefit Narrative
#   7  Corporate Qualifications         16 Required Attachments and Certifications
#   8  References                       17 Budget Description (Volume II stub if split)
#   9  Quality Management Plan          18 Signed Acknowledgement and Closing
FRONT_MATTER_PROMPT = """Using the proposal PLAN and compliance data below, write (1) the INTERNAL DECISION BRIEF and (2) the LETTER OF TRANSMITTAL, in markdown. Be specific and substantive.

## PROPOSAL PLAN (JSON)
{plan}

## COMPLIANCE & OPPORTUNITY DATA
{compliance}
{custom_block}

Output EXACTLY this markdown structure, starting directly with the heading below (no title block, no "Prepared for" section — those are handled separately):

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

## SECTION 1: LETTER OF TRANSMITTAL

[A formal business-letter-format Letter of Transmittal, dated with today's date, addressed to the agency's procurement officer (or "Procurement Officer" if the plan gives no name) at {client_hint}, referencing the solicitation number and title. 3-4 paragraphs: (1) formally submits the enclosed proposal in response to the named solicitation, (2) states FaithForge's understanding of the engagement and commitment to the requirements, (3) confirms the proposal is valid for the solicitation's required acceptance period and that Bernedette Atong is authorized to bind the firm, (4) closing courtesy. Then the sign-off:]

Respectfully submitted,

Bernedette Atong
Founder & Principal Consultant
FaithForge Technologies & Consulting LLC
410-862-2975 | info@faithforgetech.com

Output only the markdown."""

COMPLIANCE_MATRIX_PROMPT = """Build the Compliance Matrix for this FaithForge proposal — mapping every requirement in the solicitation to the exact proposal section that addresses it.

## COMPLIANCE & SUBMISSION REQUIREMENTS
{compliance}
{custom_block}

## PROPOSAL TABLE OF CONTENTS (map each requirement to one of these section numbers)
{toc}

Output EXACTLY this markdown, starting with the heading below:

## SECTION 3: COMPLIANCE MATRIX
[One sentence introducing the matrix as a roadmap for the evaluator.]

| RFP Requirement | Addressed In | Status |
|------------------|--------------|--------|
[One row per distinct requirement drawn from the Required Forms, Submission Checklist, Required Qualifications, Evaluation Criteria, Insurance, Certifications, and Compliance fields above. "Addressed In" = the section number + title from the Table of Contents above that covers it (e.g. "7 — Corporate Qualifications"). "Status" = "Included in this volume" for anything the narrative itself covers, or "Provided under separate cover" for signed forms/certificates attached separately rather than written into the narrative. Include 12-20 rows and do not omit anything substantive in the compliance data.]

Output only the markdown."""

EXEC_SUMMARY_PROMPT = """Write SECTION 4: EXECUTIVE SUMMARY of the FaithForge proposal in rich, executive markdown prose. Use the plan for consistency.

## PROPOSAL PLAN (JSON)
{plan}
{custom_block}

Output this structure (each subsection must be 2-3 substantial paragraphs of specific, non-generic prose adapted to {client_hint}, except 4.3 which is shorter):

## SECTION 4: EXECUTIVE SUMMARY

[Opening: 2-3 paragraphs — what the opportunity is, why FaithForge is the right governance and execution partner, and how FaithForge frames its role helping {client_hint} deliver. Distinguish FaithForge's governance/oversight role from any implementation vendor.]

### 4.1 FaithForge's {domain_hint} Philosophy
[Core principle paragraphs. Include an italicized positioning line beginning "*FaithForge {domain_hint} Positioning:*" followed by key value props separated by em dashes.]

### 4.2 FaithForge Commitment
[A specific closing pledge paragraph for this engagement.]

### 4.3 Proposed Delivery Team
[1 short paragraph: Bernedette Atong, PMP, PgMP, Founder & Principal Consultant, personally leads this engagement, supported by the team detailed in Section 6.9 (Key Personnel Profiles). Frame FaithForge's lean, executive-led model as a deliberate strength — the client works directly with senior leadership rather than a diluted junior team.]

Output only the markdown. No contractions. Executive tone. Never invent a named team member other than Bernedette Atong unless the additional instructions explicitly supplied one for a specific role."""

UNDERSTANDING_PROMPT = """Write SECTION 5: UNDERSTANDING OF {client_hint}'s MISSION AND NEEDS of the FaithForge proposal in rich executive markdown prose.

## PROPOSAL PLAN (JSON)
{plan}
{custom_block}

Output this structure (3-4 substantial paragraphs, specific and non-generic — adapted to {client_hint} and the {domain_hint} domain, not boilerplate that could apply to any agency):

## SECTION 5: UNDERSTANDING OF {client_hint}'s MISSION AND NEEDS

[Paragraph 1: {client_hint}'s mission and mandate as it relates to this opportunity's domain.]
[Paragraph 2: the specific operational challenges, pressures, or gaps this solicitation is responding to.]
[Paragraph 3: what success looks like for {client_hint} on this engagement, and why independent PMO/governance oversight matters here specifically.]
[Paragraph 4 (optional): the stakes involved — regulatory, public-facing, or funding-related — that make disciplined execution critical.]

Output only the markdown. No contractions."""

TECH_APPROACH_PROMPT = """Write SECTION 6: TECHNICAL APPROACH of the FaithForge proposal in rich markdown. Expand the plan's workstreams into a full phased approach, then cover project management, governance, organizational structure, staffing, and key personnel.

## PROPOSAL PLAN (JSON)
{plan}
{custom_block}

Output this structure:

## SECTION 6: TECHNICAL APPROACH

### 6.1 {domain_hint} Methodology
[2 paragraphs on FaithForge's structured, phased, deliverable-driven methodology for this engagement's domain.]

[Then for the first 2-3 workstreams, write a "#### <Workstream Name>" subsection — each with a descriptive paragraph and a bullet list of capabilities/activities.]

[Then for EACH workstream in the plan, write a phase block. Generate 5-6 specific activity bullets and 3-5 key deliverables for each, based on the workstream name and objective:]
**Phase N: <Phase Name>**
Objective: <objective>
- <activity bullets>
Key Deliverables: <comma-separated deliverables>

| Activity Area | FaithForge Responsibilities | {client_hint} Value |
|--------------|----------------------------|----------------|
| <area> | <what FaithForge does> | <benefit> |
[2-4 rows per phase]

### 6.2 Project Lifecycle Overview
[1 paragraph framing the engagement as a disciplined lifecycle from mobilization through closeout.]
[[DIAGRAM:project_lifecycle]]

### 6.3 Deliverable Products
| Deliverable | Description |
|-------------|-------------|
[one row per deliverable_product in the plan — 8-12 rows]

### 6.4 Implementation Schedule and Progress Milestones
| Timeline | Phase & Activities | Key Deliverables | Completion |
|----------|--------------------|------------------|------------|
[one row per schedule entry in the plan]
[[DIAGRAM:gantt_chart]]

### 6.5 Project Management Approach
[2 paragraphs on FaithForge's PM discipline for this engagement: planning rigor, governance cadence, controls, and how the PM structure ties execution back to {client_hint}'s objectives.]

### 6.6 Governance Framework
[1-2 paragraphs describing the governance tiers below and how decisions and escalations flow through them.]
[[DIAGRAM:governance_framework]]

### 6.7 Organizational Structure
[1 paragraph introducing the proposed team structure.]
[[DIAGRAM:org_chart]]

### 6.8 Staffing Plan
[Intro sentence on the staffing model for this engagement.]

| Role | Proposed Staff | Responsibilities |
|------|---------------|-----------------|
[Decide the Role column the same way as plan.required_key_personnel dictates: if non-empty, use those exact titles verbatim; otherwise one row per plan.labor entry. Assign Bernedette Atong to the most senior/principal-level title. Every OTHER row's "Proposed Staff" cell MUST exactly match what plan.org_chart gives for that role (a real name only if the plan explicitly supplied one for this proposal, otherwise "[TO BE NAMED]" or the exact placeholder phrase the plan gives) — never invent a name yourself. Responsibilities = 1-2 sentences specific to this engagement.]

[If any row still reads "[TO BE NAMED]", add: "[NOTE TO BERNEDETTE: confirm and name remaining staff, and attach resumes / letters of intended commitment where the solicitation requires them.]"]

### 6.9 Key Personnel Profiles

**Bernedette Atong, MSc, PMP, PgMP**
*Founder & Principal Consultant — FaithForge Technologies & Consulting LLC*
**Years of Experience: 8+**
**Education:** MSc Information Technology | BBA | BSc Economics
**Certifications:** Project Management Professional (PMP) | Program Management Professional (PgMP) | Professional Scrum Master (PSM) | Lean Six Sigma | AI Prompting
**Industry Expertise:**
- Transportation & Digital Technology: Led cross-functional teams of 14+ members delivering complex digital initiatives
- E-Commerce & Global Data: Managed end-to-end lifecycle of a $12M+ unified data analytics platform; introduced PMBOK standards improving delivery predictability
- Program & Portfolio Governance: Managed $12M+ program portfolios across enterprise systems
- Government & Healthcare: Compliance-focused governance across HIPAA, SOC2, and public-sector regulatory frameworks
**Relevant Experience:**
[2-paragraph narrative tying Bernedette's real documented background (from the knowledge base bio) directly to this engagement's domain and {client_hint}'s specific challenges. Use only credentials and facts present in the knowledge base. End with her commitment to serve as the lead identified in the Staffing Plan above.]

[For every OTHER individual named in plan.org_chart (i.e. any role whose name is not "[TO BE NAMED]" or a placeholder phrase — this only happens when the additional instructions explicitly supplied that name for this proposal), add a short profile block in this exact form, using ONLY the role/name/status given, never inventing credentials or years of experience:]
**<Name>**
*<Role>*
[1 sentence: "Proposed to serve as <Role> for this engagement." Do not add any biographical detail not supplied in the additional instructions.]

[For every remaining "[TO BE NAMED]" or "to be onboarded"-style role, add one line: "**<Role>** — [TO BE NAMED]. Resume and letter of intended commitment to be provided upon staff confirmation."]

Output only the markdown. Be specific and detailed. No contractions. Never invent a name, bio, or credential for anyone other than Bernedette Atong unless the additional instructions explicitly supplied it for that exact role."""

CORPORATE_QUALS_PROMPT = """Write SECTION 7: CORPORATE QUALIFICATIONS and SECTION 8: REFERENCES of the FaithForge proposal in rich markdown. Use the plan.

## PROPOSAL PLAN (JSON)
{plan}
{custom_block}

Output this structure:

## SECTION 7: CORPORATE QUALIFICATIONS

[IF the plan's "min_qualifications_required" is true, FIRST output a "### 7.0 Minimum Qualifications Narrative" subsection: an intro sentence affirming FaithForge meets the solicitation's minimum qualifications, then address EXACTLY the qualification criteria quoted in plan.minimum_qualifications_text (do not invent additional criteria beyond what is quoted there) using ONLY real knowledge-base facts. Where a qualification needs a specific fact not in the knowledge base, insert a "[NOTE TO BERNEDETTE: ...]" placeholder rather than a fabricated claim. If min_qualifications_required is false, skip this subsection entirely.]

### 7.1 Company Registration & Certifications
[A short intro sentence, then a table using ONLY the registration facts present in the knowledge base's Standing Documents (legal name, UEI, CAGE code, DUNS number, SAM.gov registration status/expiration, EIN, minority-owned business status):]
| Item | Value |
|------|-------|
| Legal Name | <from knowledge base> |
| Unique Entity ID (UEI) | <from knowledge base> |
| CAGE/NCAGE Code | <from knowledge base> |
| DUNS Number | <from knowledge base> |
| SAM.gov Registration | <status and expiration from knowledge base> |
| EIN | <from knowledge base> |
| Business Certification | <minority-owned status from knowledge base> |
[If the solicitation or additional instructions reference a state/local small-business certification (e.g. a Certified Small Business / MBE / SBR number) that is NOT present in the knowledge base, add one more row: "| <the certification type named> | [NOTE TO BERNEDETTE: insert the certification number] |" — never fabricate a number.]

### 7.2 {domain_hint} & Program Governance Experience
[2-3 paragraphs. Open with FaithForge's identity: a governance and execution partner that installs structure, governance, and execution discipline where complexity and accountability intersect. Reference the 4-Tier engagement model. Then a bullet list of 5-6 relevant experience areas specific to this domain.]

### 7.3 Relevant Project Experience
[Intro sentence noting these are FaithForge's documented past engagements. Then, for EACH of FaithForge's four case studies in the knowledge base (Amtrak, Inteleos, ASM Global, iHerb), write a full case study in this exact structure:]

#### Case Study: <Client Name>
**Client Overview:** [1-2 sentences on the client, drawn only from the knowledge base.]
**Business Challenge:** [1-2 sentences on the problem FaithForge was engaged to solve, drawn only from the knowledge base scope description.]
**FaithForge Solution:** [2-3 sentences on the approach FaithForge took, drawn only from the knowledge base scope.]
**Methodology:** [1-2 sentences connecting the engagement to FaithForge's 4-Tier model / governance-first execution model.]
**Deliverables:** [Bullet list of 3-4 deliverables inferable from the knowledge base scope description — frameworks, SOPs, dashboards, governance structures, etc. Do not invent deliverables not implied by the real scope text.]
**Results:** [Bullet list of the REAL measurable results from the knowledge base for this client — cite them exactly, do not round or invent.]
**Quantifiable Outcomes:** [Restate the 2-3 most compelling metrics from Results as a short bolded callout line, e.g. "**86% faster contract cycle time | 70% better vendor onboarding**".]
**Relevance to {client_hint}:** [1-2 sentences explicitly connecting this case study's outcomes to {client_hint}'s needs on THIS opportunity.]

### 7.4 Experience with Governance, PMO, and {domain_hint} Programs
[Intro sentence + 6-7 capability bullets. Draw from FaithForge's documented capabilities: PMO maturity audits; governance framework design; multi-stakeholder coordination; regulatory compliance and audit readiness; executive reporting and KPI dashboards; workflow automation; organizational change management (OCM). Adapt to domain.]

### 7.5 Knowledge of Organizational Change, Customer/Stakeholder Adoption, and Readiness
[2 paragraphs emphasizing organizational change management and stakeholder adoption. Reference FaithForge's documented execution model: assess execution risk -> install governance and structure -> enable teams with clarity and tools -> transfer ownership and capability.]

### 7.6 Experience with Program Controls, Data Assessment, and Executive Reporting
[Intro line + 6-7 bullets including KPI reporting and dashboards, data quality and reporting integrity, executive dashboard cadence, RAID/risk registers, performance baselines, weekly status reporting.]

## SECTION 8: REFERENCES
[Intro sentence noting FaithForge provides references attesting to work of similar complexity. Then present the same four case studies from 7.3 (or note if the RFP requires more references than that — see plan.references_required) as reference entries. For EACH reference use this format:]
**Reference — <Client Name>**
<1-2 sentence description of the scope and the most relevant measurable result, drawn ONLY from the case study.> [NOTE TO BERNEDETTE: add reference contact name, title, phone, email, and exact contract dates for <Client> to complete the required reference form.]
[Do NOT invent contact names, phone numbers, emails, or dates. If plan.references_required is greater than 4, add: "[NOTE TO BERNEDETTE: the solicitation requires N references — confirm which additional engagements to include]".]

Output only the markdown. No contractions. Never invent a statistic, deliverable, or contact detail not present in the knowledge base."""

QUALITY_RISK_PROMPT = """Write SECTION 9: QUALITY MANAGEMENT PLAN and SECTION 10: RISK MANAGEMENT PLAN of the FaithForge proposal in rich, fully-developed markdown — detailed narrative plans, not bare tables. Use the plan for consistency.

## PROPOSAL PLAN (JSON)
{plan}
{custom_block}

Output this structure:

## SECTION 9: QUALITY MANAGEMENT PLAN

### 9.1 Quality Management Approach
[2 paragraphs on FaithForge's approach to quality for this engagement: standards-setting, review cadence, and how quality ties back to {client_hint}'s acceptance criteria.]

### 9.2 Quality Standards and Acceptance Criteria
[1 paragraph + bullet list of 5-6 quality standards/criteria specific to this engagement's deliverables (e.g. deliverable completeness, stakeholder sign-off, data accuracy, documentation standards, regulatory alignment).]

### 9.3 Quality Assurance Process
[1 paragraph describing the review-and-approval cycle below.]
[[DIAGRAM:qa_process]]

### 9.4 Roles and Responsibilities for Quality
| Role | Quality Responsibility |
|------|------------------------|
[3-5 rows: Program Director, Project Manager, QA lead/role, Client reviewer, etc.]

## SECTION 10: RISK MANAGEMENT PLAN

### 10.1 Risk Management Approach
[2 paragraphs on FaithForge's proactive, governance-first approach to risk for this engagement — identification, RAID logging, ownership, and executive visibility.]

### 10.2 Risk Identification and Categories
[1 paragraph + bullet list of 5-6 realistic risk categories for this engagement's domain (schedule, scope, stakeholder alignment, data/technical, resource, regulatory/compliance).]

### 10.3 Risk Register Approach
| Risk Category | Likelihood | Impact | Mitigation Strategy | Owner |
|----------------|-----------|--------|---------------------|-------|
[5-7 illustrative rows specific to this engagement's domain and workstreams — realistic, not generic filler.]

### 10.4 Issue Escalation Process
[1 paragraph describing the escalation path below.]
[[DIAGRAM:risk_escalation]]

Output only the markdown. No contractions. Each subsection must be genuine, substantive prose — not a single-line placeholder."""

COMM_OCM_STAKEHOLDER_PROMPT = """Write SECTION 11: COMMUNICATION MANAGEMENT PLAN, SECTION 12: ORGANIZATIONAL CHANGE MANAGEMENT PLAN, and SECTION 13: STAKEHOLDER ENGAGEMENT PLAN of the FaithForge proposal in rich, fully-developed markdown — detailed narrative plans, not bare tables. Use the plan for consistency.

## PROPOSAL PLAN (JSON)
{plan}
{custom_block}

Output this structure:

## SECTION 11: COMMUNICATION MANAGEMENT PLAN

### 11.1 Communication Approach
[2 paragraphs on how FaithForge structures communication for this engagement — cadence, audiences, and how reporting ties to governance and decision-making.]

### 11.2 Communication Framework and Cadence
[1 paragraph describing the cadence below.]
[[DIAGRAM:communication_framework]]

### 11.3 Reporting Structure
| Report/Touchpoint | Audience | Frequency | Purpose |
|--------------------|----------|-----------|---------|
[4-6 rows: status report, steering committee, executive briefing, dashboard, etc.]

## SECTION 12: ORGANIZATIONAL CHANGE MANAGEMENT PLAN

### 12.1 Change Management Approach
[2 paragraphs describing FaithForge's OCM philosophy for this engagement: assess readiness, build structured adoption plans, and transfer capability rather than create dependency. Reference FaithForge's documented execution model.]

### 12.2 Change Readiness and Impact Assessment
[1 paragraph + bullet list of 4-5 activities FaithForge will use to assess organizational readiness and change impact for {client_hint}.]

### 12.3 Training, Communication, and Adoption Support
[1 paragraph + bullet list of 4-5 specific OCM deliverables (training plans, job aids, change champions network, adoption metrics, feedback loops).]

## SECTION 13: STAKEHOLDER ENGAGEMENT PLAN

### 13.1 Stakeholder Engagement Approach
[1-2 paragraphs on how FaithForge identifies, segments, and engages stakeholders for this engagement.]

### 13.2 Stakeholder Engagement Model
[1 paragraph describing the tiers below.]
[[DIAGRAM:stakeholder_engagement]]

### 13.3 Stakeholder Engagement Activities
| Stakeholder Group | Engagement Method | Frequency |
|--------------------|--------------------|-----------|
[4-6 rows tailored to {client_hint} and {domain_hint}.]

Output only the markdown. No contractions. Each subsection must be genuine, substantive prose — not a single-line placeholder."""

PROJECT_CONTROLS_PROMPT = """Write SECTION 14: PROJECT CONTROLS AND REPORTING and SECTION 15: ECONOMIC BENEFIT NARRATIVE of the FaithForge proposal in rich, fully-developed markdown. Use the plan for consistency — do not invent numbers not already in the plan.

## PROPOSAL PLAN (JSON)
{plan}
{custom_block}

Output this structure:

## SECTION 14: PROJECT CONTROLS AND REPORTING

### 14.1 Deliverables Management
[1-2 paragraphs on how FaithForge tracks, reviews, and formally accepts deliverables for this engagement, referencing the deliverable list already defined in Section 6.]

### 14.2 Schedule Management
[1 paragraph on FaithForge's schedule governance approach for this engagement.]
[[DIAGRAM:gantt_chart]]

### 14.3 Performance Measurement Framework
[1-2 paragraphs on how FaithForge measures and reports program performance for {client_hint}.]
[[DIAGRAM:raci_matrix]]
[[DIAGRAM:executive_dashboard]]

## SECTION 15: ECONOMIC BENEFIT NARRATIVE
[2-3 paragraphs on the broader economic/operational benefit of this engagement to {client_hint} — efficiency gains, risk reduction, capability transfer. If plan.separate_pricing_volume is true, frame benefit entirely in terms of outcomes, risk avoidance, and delivery efficiency — do NOT restate or reference any dollar figure, since pricing is submitted under separate cover for this solicitation. If plan.separate_pricing_volume is false, you may reference value delivered relative to the investment described in Section 17.]

Output only the markdown. No contractions."""

REQUIRED_ATTACHMENTS_PROMPT = """Write SECTION 16: REQUIRED ATTACHMENTS AND CERTIFICATIONS of the FaithForge proposal in markdown — a checklist of every attachment/certification/form the solicitation requires, noting which FaithForge already holds on file.

## COMPLIANCE & SUBMISSION REQUIREMENTS
{compliance}
{custom_block}

Output EXACTLY this markdown, starting with the heading below:

## SECTION 16: REQUIRED ATTACHMENTS AND CERTIFICATIONS
[1-sentence intro.]

[One "- [ ]" checklist line per required form/attachment/certification found in the Required Forms, Submission Checklist, Required Attachments, Certifications Required, and Insurance fields above. Append " — on file, attach directly" to any item that matches something FaithForge already holds per the knowledge base's Standing Documents (SAM.gov/UEI/CAGE registration, DUNS, W-9, EIN, Articles of Organization, Certificate of Insurance, PMP/PgMP certificates, minority-owned business status, past performance references, rate card). Leave unmarked anything that must be newly prepared, signed, or tailored specifically for this solicitation.]

Output only the markdown. Do not invent a requirement not present in the compliance data above."""

BUDGET_PROMPT = """Write SECTION 17: BUDGET DESCRIPTION of the FaithForge proposal in rich markdown. Use the EXACT numbers from the plan — do not invent new numbers; every total must match the plan.

## PROPOSAL PLAN (JSON)
{plan}
{custom_block}

Output this structure:

## SECTION 17: BUDGET DESCRIPTION

### 17.1 Staffing Classifications and Labor Rates
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

### 17.1.1 Basis of Estimate
[2 paragraphs on the staffing model and rationale.]

### 17.2 Program Management Services Pricing Strategy
[2 paragraphs on the value delivery model.]

**Base Services Total:**
| Cost Component | Amount |
|----------------|--------|
| Direct Labor | ${direct_labor_total} |
[supporting cost rows]
| **Total Base Services** | **${base_total}** |

### 17.3 Cost by Workstream and Total Potential Contract Value
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

### 17.3.1 Optional Service Labor Assumptions
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

### 17.4 Plans for Subcontracting and Specialized Advisory Support
[1-2 paragraphs. FaithForge does not anticipate major subcontracting for the base scope; all core services are delivered directly by FaithForge under Bernedette Atong's leadership. State that if specialized subject-matter support is required, FaithForge will identify and manage such support under its direct oversight, held to the same standards of quality and accountability. Do NOT name a specific subcontractor or individual — if the solicitation requires a subcontractor list, add "[NOTE TO BERNEDETTE: list any confirmed subcontractors and their certifications if required by the solicitation]".]

Output only the markdown. No contractions."""


CLOSING_PROMPT = """Write SECTION 18: SIGNED ACKNOWLEDGEMENT AND CLOSING of the FaithForge proposal in markdown. Every FaithForge submission ends with this section. Use the plan for the client name and solicitation number.

## PROPOSAL PLAN (JSON)
{plan}
{custom_block}

Output this structure:

## SECTION 18: SIGNED ACKNOWLEDGEMENT OF SOLICITATION TERMS AND CONDITIONS

[One paragraph: FaithForge Technologies & Consulting LLC acknowledges and understands the requirements associated with providing <the proposed services> for <client>, and is committed to complying with the solicitation's requirements, maintaining ethical business practices, and delivering professional, mission-aligned services.]

[If the plan has a solicitation_number, add a sentence acknowledging receipt of the solicitation and any addenda, followed by: "[NOTE TO BERNEDETTE: confirm all issued amendments/addenda on the procurement portal and attach signed acknowledgement of receipt for each before submitting.]"]

**Acknowledged and Agreed:**

Signature: ________________________________________
Printed Name: Bernedette Atong
Title: Founder & Principal Consultant
Firm Name: FaithForge Technologies & Consulting LLC
City, State: Elkridge, MD
Phone: 410-862-2975
Email: info@faithforgetech.com
Date: [NOTE TO BERNEDETTE: sign and date at submission]

### Closing Statement
[2 paragraphs. First: FaithForge's commitment to delivering for this specific client and engagement, tied to the client's stated goals. Second: reinforce the governance-first, executive-led, outcome-focused approach and express that FaithForge is honored by the opportunity. Then:]

Respectfully submitted,
Bernedette Atong
Founder & Principal Consultant
FaithForge Technologies & Consulting LLC

Output only the markdown. No contractions. Bernedette Atong is the only person you may name unless the additional instructions explicitly supplied another name for a specific role."""


# ── Table of Contents (deterministic — no LLM) ───────────────────────────────

_TOC_TEMPLATE = [
    ("1", "Letter of Transmittal"),
    ("2", "Table of Contents"),
    ("3", "Compliance Matrix"),
    ("4", "Executive Summary"),
    ("5", "Understanding of {client}'s Mission and Needs"),
    ("6", "Technical Approach"),
    ("7", "Corporate Qualifications"),
    ("8", "References"),
    ("9", "Quality Management Plan"),
    ("10", "Risk Management Plan"),
    ("11", "Communication Management Plan"),
    ("12", "Organizational Change Management Plan"),
    ("13", "Stakeholder Engagement Plan"),
    ("14", "Project Controls and Reporting"),
    ("15", "Economic Benefit Narrative"),
    ("16", "Required Attachments and Certifications"),
    ("17", "Budget Description"),
    ("18", "Signed Acknowledgement and Closing"),
]


def _toc_entries(plan: Dict[str, Any]) -> list:
    client = plan.get("client_name") or "the Agency"
    entries = []
    for num, title in _TOC_TEMPLATE:
        t = title.format(client=client) if "{client}" in title else title
        if num == "17" and plan.get("separate_pricing_volume"):
            t = "Financial Proposal — Volume II (Submitted Under Separate Cover)"
        entries.append((num, t))
    return entries


def _render_toc(plan: Dict[str, Any]) -> str:
    lines = ["## SECTION 2: TABLE OF CONTENTS", "", "| Section | Title |", "|---------|-------|"]
    for num, title in _toc_entries(plan):
        lines.append(f"| {num} | {title} |")
    return "\n".join(lines)


def _toc_plaintext(plan: Dict[str, Any]) -> str:
    return "\n".join(f"{num}. {title}" for num, title in _toc_entries(plan))


# ── Diagram sentinel insertion (deterministic safety net) ────────────────────
# Section prompts above already embed literal `[[DIAGRAM:key]]` lines in their
# output templates, but a model can occasionally fail to reproduce a literal
# token verbatim. This guarantees the sentinel exists by inserting it right
# after the matching heading if the model dropped it.

def _ensure_diagram(text: str, key: str, after_heading: str) -> str:
    marker = f"[[DIAGRAM:{key}]]"
    if marker in text:
        return text
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith("#") and after_heading.lower() in line.lower():
            lines.insert(i + 1, f"\n{marker}\n")
            return "\n".join(lines)
    return text + f"\n\n{marker}\n"


def _fmt_field_value(val) -> str:
    """Render a field value for prompt context. datetime columns come back
    from the DB as raw datetime objects — str()'ing one with an unknown
    time-of-day produces a literal "2026-07-14 00:00:00" that the model then
    echoes verbatim into the proposal. Format dates human-readable instead."""
    if isinstance(val, datetime):
        if val.hour == 0 and val.minute == 0 and val.second == 0:
            return val.strftime("%B %d, %Y")
        return val.strftime("%B %d, %Y, %I:%M %p")
    return str(val)


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
            lines.append(f"{label}: {_fmt_field_value(val)}")
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
            lines.append(f"{label}: {_fmt_field_value(val)}")
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


def _note(field_label: str) -> str:
    return f"[NOTE TO BERNEDETTE: confirm {field_label} from the solicitation]"


def _render_title_block(plan: Dict[str, Any]) -> str:
    """Build the proposal title block from the plan dict directly, in Python.
    Every value here already exists in the plan after the planner stage — assembling
    it deterministically avoids relying on the model to correctly fill in template
    placeholders (it has echoed raw {{field}} syntax verbatim) or to keep FaithForge's
    own contact info separate from the agency's."""
    lines = ["# REQUEST FOR PROPOSAL RESPONSE", ""]
    if plan.get("separate_pricing_volume"):
        lines.append("## VOLUME I — TECHNICAL PROPOSAL")
        lines.append("")
    lines.append(f"# {plan.get('title') or 'Untitled Opportunity'}")
    if plan.get("subtitle"):
        lines.append(f"## {plan['subtitle']}")
    lines.append("")

    solicitation_number = plan.get("solicitation_number")
    secondary_id = plan.get("secondary_id")
    if solicitation_number or secondary_id:
        parts = [f"Solicitation # {solicitation_number}" if solicitation_number else _note("the solicitation number")]
        if secondary_id:
            parts.append(secondary_id)
        lines.append(f"**{'  |  '.join(parts)}**")
    else:
        lines.append(f"**{_note('the solicitation number')}**")
    lines.append("")

    lines.append("**Prepared for**")
    lines.append(plan.get("client_name") or _note("the client/agency name"))
    lines.append(plan.get("prepared_for_address") or _note("prepared_for_address"))
    if plan.get("procurement_officer"):
        contact = plan.get("procurement_officer_contact") or "[NOTE TO BERNEDETTE: confirm procurement officer contact info]"
        lines.append(f"Procurement Officer: {plan['procurement_officer']}  |  {contact}")
    else:
        lines.append(_note("the procurement/contracting officer name and contact"))
    lines.append("")

    lines.append("**Submitted by**")
    lines.append("FaithForge Technologies & Consulting LLC")
    lines.append("Bernedette Atong, PMP, PgMP — Founder & Principal Consultant")
    lines.append("410-862-2975  |  info@faithforgetech.com  |  www.faithforgetech.com")
    lines.append("")

    lines.append("| Field | Response |")
    lines.append("|-------|----------|")
    lines.append(f"| Proposal Type | {plan.get('proposal_type') or '—'} |")
    lines.append(f"| Date | {datetime.now().strftime('%B %d, %Y')} |")
    lines.append(f"| Bid Due | {plan.get('due_datetime') or _note('the bid due date')} |")
    lines.append(f"| Submission Method | {plan.get('submission_method') or _note('the submission method')} |")
    lines.append("")
    if plan.get("separate_pricing_volume"):
        lines.append("*Pricing is submitted separately as Volume II — Financial Proposal, per the solicitation's submission requirements. No pricing information appears in this Technical Proposal.*")
        lines.append("")
    lines.append("---")
    return "\n".join(lines)


def build_packet(
    opportunity: Dict[str, Any],
    document_texts: list[str],
    custom_instructions: str = "",
) -> Dict[str, Any]:
    """
    Multi-pass proposal generation producing a full two-volume-style technical
    proposal (see the outline comment above the section prompts):
      1) Planner call builds a consistent skeleton (structure + budget math +
         org chart + volume-split decision).
      2) A series of section-writer calls expand the plan into rich,
         submission-ready prose, each followed by a deterministic diagram
         safety-net pass (see _ensure_diagram).
      3) The Table of Contents is assembled deterministically in Python, and
         the Budget section is replaced with a short Volume II stub whenever
         the RFP requires pricing to be submitted under separate cover.
    Each call stays within the model's per-request token budget; rate limits
    are retried with backoff.
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
    logger.info("[packet] stage 1: planner")
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
    # Decide min_qualifications_required from Python, not the model's own boolean judgment —
    # gate it strictly on whether the model actually quoted real qualification text.
    plan["min_qualifications_required"] = bool((plan.get("minimum_qualifications_text") or "").strip())
    if not isinstance(plan.get("org_chart"), list) or not plan["org_chart"]:
        from diagrams import default_org_chart
        plan["org_chart"] = default_org_chart(plan)
    plan["separate_pricing_volume"] = bool(plan.get("separate_pricing_volume"))
    plan_json = json.dumps(plan, indent=1)
    logger.info("[packet] plan OK — %d workstreams, %d labor rows, total_value=$%s, separate_pricing_volume=%s",
                len(plan.get("workstreams", [])), len(plan.get("labor", [])),
                f"{plan.get('total_value', 0):,}", plan["separate_pricing_volume"])

    client_hint = plan.get("client_name") or opportunity.get("agency_name") or "the Agency"
    domain_hint = plan.get("domain") or "Program Management"

    fmt = {
        "plan": plan_json,
        "custom_block": custom_block,
        "client_hint": client_hint,
        "domain_hint": domain_hint,
        "compliance": compliance,
        "toc": _toc_plaintext(plan),
        "direct_labor_total": f"{plan.get('direct_labor_total', 0):,}",
        "base_total": f"{plan.get('base_total', 0):,}",
        "optional_total": f"{plan.get('optional_total', 0):,}",
        "total_value": f"{plan.get('total_value', 0):,}",
    }

    # ── Stage 2: Sections ────────────────────────────────────────────────────
    # Each entry: (label, prompt template, max_tokens, [(diagram_key, heading_substring), ...])
    SECTION_LABELS = [
        ("front-matter", FRONT_MATTER_PROMPT, 3000, []),
        ("compliance-matrix", COMPLIANCE_MATRIX_PROMPT, 1800, []),
        ("exec-summary", EXEC_SUMMARY_PROMPT, 2200, []),
        ("understanding", UNDERSTANDING_PROMPT, 1400, []),
        ("technical-approach", TECH_APPROACH_PROMPT, 5500, [
            ("project_lifecycle", "Project Lifecycle"),
            ("gantt_chart", "Implementation Schedule"),
            ("governance_framework", "Governance Framework"),
            ("org_chart", "Organizational Structure"),
        ]),
        ("corporate-qualifications", CORPORATE_QUALS_PROMPT, 6500, []),
        ("quality-risk", QUALITY_RISK_PROMPT, 3000, [
            ("qa_process", "Quality Assurance Process"),
            ("risk_escalation", "Issue Escalation Process"),
        ]),
        ("comm-ocm-stakeholder", COMM_OCM_STAKEHOLDER_PROMPT, 3200, [
            ("communication_framework", "Communication Framework"),
            ("stakeholder_engagement", "Stakeholder Engagement Model"),
        ]),
        ("project-controls-economic", PROJECT_CONTROLS_PROMPT, 2800, [
            ("gantt_chart", "Schedule Management"),
            ("raci_matrix", "Performance Measurement Framework"),
            ("executive_dashboard", "Performance Measurement Framework"),
        ]),
        ("required-attachments", REQUIRED_ATTACHMENTS_PROMPT, 1200, []),
        ("closing", CLOSING_PROMPT, 1500, []),
    ]

    results: Dict[str, str] = {}
    total_stages = len(SECTION_LABELS) + 2  # + planner + budget/stub
    for i, (label, prompt_tmpl, max_tokens, diagram_specs) in enumerate(SECTION_LABELS, start=2):
        logger.info("[packet] stage %d/%d: %s", i, total_stages, label)
        result = _openai_chat(client, packet_system, _safe_format(prompt_tmpl, fmt),
                            max_tokens=max_tokens, label=label)
        if not result or not result.strip():
            logger.warning("[packet] %s returned empty content — section will be omitted", label)
        else:
            for key, heading in diagram_specs:
                result = _ensure_diagram(result, key, heading)
            logger.info("[packet] %s complete — %d chars", label, len(result))
        results[label] = result

    # ── Budget (Section 17) — real budget prose, or a Volume II stub when the
    # RFP requires pricing to be submitted under separate cover ─────────────
    if plan["separate_pricing_volume"]:
        logger.info("[packet] stage %d/%d: budget — skipped (separate_pricing_volume)", total_stages, total_stages)
        results["budget"] = (
            "## SECTION 17: BUDGET DESCRIPTION\n\n"
            "*Per the solicitation's requirement that technical and price proposals be submitted as separate volumes, "
            "FaithForge's pricing, labor rates, and cost breakdown are provided exclusively in the accompanying "
            "**Volume II — Financial Proposal**. No pricing information is included in this Technical Proposal.*"
        )
    else:
        logger.info("[packet] stage %d/%d: budget", total_stages, total_stages)
        results["budget"] = _openai_chat(client, packet_system, _safe_format(BUDGET_PROMPT, fmt),
                                          max_tokens=4000, label="budget")

    # ── Assemble in final document order ────────────────────────────────────
    title_block = _render_title_block(plan)
    front_matter = results.get("front-matter", "")
    parts = [
        f"{title_block}\n\n{front_matter}" if front_matter.strip() else title_block,
        _render_toc(plan),
        results.get("compliance-matrix", ""),
        results.get("exec-summary", ""),
        results.get("understanding", ""),
        results.get("technical-approach", ""),
        results.get("corporate-qualifications", ""),
        results.get("quality-risk", ""),
        results.get("comm-ocm-stakeholder", ""),
        results.get("project-controls-economic", ""),
        results.get("required-attachments", ""),
        results.get("budget", ""),
        results.get("closing", ""),
    ]

    non_empty = [p.strip() for p in parts if p and p.strip()]
    logger.info("[packet] all stages done in %.1fs — %d/%d parts have content",
                _time.monotonic() - t_start, len(non_empty), len(parts))

    full_text = "\n\n---\n\n".join(non_empty)
    html_content = markdown_to_html(full_text, plan)
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


def markdown_to_html(text: str, plan: Optional[dict] = None) -> str:
    try:
        import re
        from diagrams import _DIAGRAM_RE, render_diagram
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

            # Diagram sentinel — rendered as an embedded base64 PNG
            diagram_match = _DIAGRAM_RE.match(s)
            if diagram_match:
                close_lists()
                i += 1
                if plan:
                    try:
                        import base64
                        png = render_diagram(diagram_match.group(1), plan)
                        if png:
                            b64 = base64.b64encode(png).decode("ascii")
                            output.append(
                                f'<div style="text-align:center;margin:16px 0;">'
                                f'<img src="data:image/png;base64,{b64}" '
                                f'style="max-width:100%;height:auto;border:1px solid #e2e8f0;border-radius:4px;"/>'
                                f'</div>'
                            )
                    except Exception:
                        pass
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
