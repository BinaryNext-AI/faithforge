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


class StatusUpdate(BaseModel):
    status: str


class PacketBuildRequest(BaseModel):
    custom_instructions: Optional[str] = ""


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
