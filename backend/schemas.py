from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DocumentOut(BaseModel):
    id: int
    opportunity_id: int
    filename: str
    original_filename: str
    file_type: Optional[str]
    file_size: Optional[int]
    uploaded_at: datetime
    reviewed: bool
    review_content: Optional[str]

    class Config:
        from_attributes = True


class PacketOut(BaseModel):
    id: int
    opportunity_id: int
    created_at: datetime
    content_json: Optional[str]
    html_content: Optional[str]
    emailed: bool
    emailed_at: Optional[datetime]

    class Config:
        from_attributes = True


class OpportunityBase(BaseModel):
    status: Optional[str] = None
    opportunity_title: Optional[str] = None
    agency_name: Optional[str] = None
    solicitation_number: Optional[str] = None
    due_date: Optional[datetime] = None
    pre_bid_date: Optional[datetime] = None
    submission_method: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    website_link: Optional[str] = None
    emma_link: Optional[str] = None
    has_emma_link: Optional[bool] = None
    opportunity_summary: Optional[str] = None
    required_services: Optional[str] = None
    faithforge_alignment: Optional[str] = None
    recommended_action: Optional[str] = None
    risk_concerns: Optional[str] = None
    estimated_value: Optional[str] = None
    contract_type: Optional[str] = None
    questions_deadline: Optional[str] = None
    eligibility_requirements: Optional[str] = None
    required_qualifications: Optional[str] = None
    required_forms: Optional[str] = None
    submission_checklist: Optional[str] = None
    proposal_format: Optional[str] = None
    evaluation_criteria: Optional[str] = None
    insurance_requirements: Optional[str] = None
    certifications_required: Optional[str] = None
    compliance_requirements: Optional[str] = None
    pricing_requirements: Optional[str] = None
    required_attachments: Optional[str] = None
    disqualifying_requirements: Optional[str] = None


class OpportunityOut(OpportunityBase):
    id: int
    created_at: datetime
    updated_at: datetime
    email_id: Optional[str]
    email_subject: Optional[str]
    email_from: Optional[str]
    email_date: Optional[datetime]
    email_body_preview: Optional[str]
    relevance_classification: Optional[str]
    relevance_score: Optional[float]
    classification_reasoning: Optional[str]
    score_breakdown: Optional[str] = None
    documents: List[DocumentOut] = []
    packets: List[PacketOut] = []

    class Config:
        from_attributes = True


class OpportunityUpdate(OpportunityBase):
    pass


class OpportunityCreate(BaseModel):
    opportunity_title: str = Field(..., min_length=1)
    agency_name: Optional[str] = None
    solicitation_number: Optional[str] = None
    contract_type: Optional[str] = None
    estimated_value: Optional[str] = None
    due_date: Optional[datetime] = None
    emma_link: Optional[str] = None
    opportunity_summary: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str


class PacketBuildRequest(BaseModel):
    custom_instructions: Optional[str] = ""


class CompleteDraftRequest(BaseModel):
    document_id: Optional[int] = None
    draft_text: Optional[str] = None
    custom_instructions: Optional[str] = ""


class CompleteDraftOut(BaseModel):
    packet: PacketOut
    analysis: dict


class RevisePacketRequest(BaseModel):
    instruction: str = Field(..., min_length=1)


class AuditLogOut(BaseModel):
    id: int
    timestamp: datetime
    action: str
    opportunity_id: Optional[int]
    details: Optional[str]

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total: int
    by_status: dict
    recent: List[OpportunityOut]
    upcoming: List[OpportunityOut] = []


class ScanResult(BaseModel):
    scanned: int
    new_found: int
    relevant: int
    possibly_relevant: int
    not_relevant: int
    errors: List[str]


class AppSettingOut(BaseModel):
    key: str
    value: Optional[str]
    is_secret: bool

    class Config:
        from_attributes = True


# ─── CRM Accounts (Build 01) ───────────────────────────────────────────────────

class AccountBase(BaseModel):
    company_name: Optional[str] = None
    segment: Optional[str] = None
    website: Optional[str] = None
    location: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    stage: Optional[str] = None
    priority_score: Optional[float] = None
    priority_reason: Optional[str] = None
    last_contacted_at: Optional[datetime] = None
    next_action: Optional[str] = None
    next_action_date: Optional[datetime] = None
    awaiting_reply: Optional[bool] = None
    pain_points: Optional[str] = None
    entry_offer: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = None


class AccountCreate(AccountBase):
    company_name: str = Field(..., min_length=1)


class AccountUpdate(AccountBase):
    pass


class AccountOut(AccountBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AccountStageUpdate(BaseModel):
    stage: str


class CRMStats(BaseModel):
    total: int
    by_stage: dict
    awaiting_reply: int
    actions_due: List[AccountOut] = []
    top_priority: List[AccountOut] = []


# ─── Cold Email Generator (Build 02) ─────────────────────────────────────────

class ColdEmailRequest(BaseModel):
    company_name: str = Field(..., min_length=1)
    segment: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    pain_points: Optional[str] = None
    entry_offer: Optional[str] = None
    sequence_length: int = Field(default=3, ge=1, le=5)


class ColdEmailItem(BaseModel):
    step: int
    subject: str
    body: str
    send_day: int
    purpose: str


class ColdEmailOut(BaseModel):
    emails: List[ColdEmailItem]


# ─── Bulk Outreach (leads import + cold-email generation + send) ────────────

class OutreachImportPreviewOut(BaseModel):
    columns: List[str]
    mapping: dict
    rows: List[dict]
    row_count: int
    duplicate_count: int
    email_missing_count: int


class OutreachImportCommitRequest(BaseModel):
    rows: List[dict]
    source_filename: str = "leads.xlsx"
    dedupe: str = Field(default="skip", pattern="^(skip|update)$")


class OutreachImportCommitOut(BaseModel):
    created: int
    updated: int
    skipped: int
    account_ids: List[int]


class OutreachGenerateRequest(BaseModel):
    account_ids: List[int] = Field(..., min_length=1)
    method: str = Field(default="sync", pattern="^(sync|batch_api)$")
    model: Optional[str] = None


class OutreachBatchOut(BaseModel):
    id: int
    created_at: datetime
    source_filename: Optional[str]
    method: str
    status: str
    openai_batch_id: Optional[str]
    model_used: Optional[str]
    lead_count: int
    generated_count: int
    error: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


class OutreachEmailOut(BaseModel):
    id: int
    created_at: datetime
    account_id: int
    batch_id: Optional[int]
    to_email: Optional[str]
    subject: Optional[str]
    body: Optional[str]
    status: str
    approved: bool
    edited: bool
    model_used: Optional[str]
    sent_at: Optional[datetime]
    error: Optional[str]
    account_company: Optional[str] = None
    account_contact: Optional[str] = None
    account_has_email: bool = False

    class Config:
        from_attributes = True


class OutreachEmailUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    approved: Optional[bool] = None


class OutreachIdList(BaseModel):
    ids: List[int] = Field(..., min_length=1)


class OutreachSendResult(BaseModel):
    id: int
    ok: bool
    dry_run: Optional[bool] = None
    sent_to: Optional[str] = None
    error: Optional[str] = None


class OutreachSendOut(BaseModel):
    results: List[OutreachSendResult]


# ─── Go/No-Go Assessment (Build 03) ──────────────────────────────────────────

class GoNoGoOut(BaseModel):
    verdict: str
    score: int
    factors: dict
    recommendation: str
    conditions: List[str] = []
    next_steps: List[str] = []
    red_flags: List[str] = []
