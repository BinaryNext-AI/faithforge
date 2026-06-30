from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float,
    ForeignKey, JSON, LargeBinary
)
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

VALID_STATUSES = [
    "New",
    "Under Review",
    "Relevant",
    "Possibly Relevant",
    "Not Relevant",
    "EMMA Documents Needed",
    "Documents Uploaded",
    "Packet Building",
    "Packet Ready",
    "Reviewed by User",
    "Approved to Pursue",
    "Declined",
]


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Email source metadata
    email_id = Column(String, unique=True, index=True)
    email_subject = Column(String)
    email_from = Column(String)
    email_date = Column(DateTime)
    email_body_preview = Column(Text)  # first 2000 chars only

    # Status
    status = Column(String, default="New", index=True)

    # AI classification
    relevance_classification = Column(String)  # relevant | possibly_relevant | not_relevant
    relevance_score = Column(Float)
    classification_reasoning = Column(Text)
    score_breakdown = Column(Text)  # per-factor sub-scores justifying relevance_score

    # Extracted fields
    opportunity_title = Column(String)
    agency_name = Column(String)
    solicitation_number = Column(String)
    due_date = Column(DateTime)
    pre_bid_date = Column(DateTime)
    submission_method = Column(String)
    contact_person = Column(String)
    contact_email = Column(String)
    website_link = Column(String)
    emma_link = Column(String)
    has_emma_link = Column(Boolean, default=False)
    opportunity_summary = Column(Text)
    required_services = Column(Text)
    faithforge_alignment = Column(Text)
    recommended_action = Column(Text)
    risk_concerns = Column(Text)
    estimated_value = Column(String)
    contract_type = Column(String)

    # Document review — compliance & submission fields
    questions_deadline = Column(String)
    eligibility_requirements = Column(Text)
    required_qualifications = Column(Text)
    required_forms = Column(Text)
    submission_checklist = Column(Text)
    proposal_format = Column(Text)
    evaluation_criteria = Column(Text)
    insurance_requirements = Column(Text)
    certifications_required = Column(Text)
    compliance_requirements = Column(Text)
    pricing_requirements = Column(Text)
    required_attachments = Column(Text)
    disqualifying_requirements = Column(Text)

    documents = relationship("Document", back_populates="opportunity", cascade="all, delete-orphan")
    packets = relationship("Packet", back_populates="opportunity", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="opportunity")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String)
    file_size = Column(Integer)
    file_content = Column(LargeBinary, nullable=True)  # stored in DB for cloud deploys
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    reviewed = Column(Boolean, default=False)
    review_content = Column(Text)

    opportunity = relationship("Opportunity", back_populates="documents")


class Packet(Base):
    __tablename__ = "packets"

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    content_json = Column(Text)  # JSON string with all sections
    html_content = Column(Text)
    emailed = Column(Boolean, default=False)
    emailed_at = Column(DateTime)

    opportunity = relationship("Opportunity", back_populates="packets")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    action = Column(String, nullable=False)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True)
    details = Column(Text)

    opportunity = relationship("Opportunity", back_populates="audit_logs")


class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text)
    is_secret = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class Session(Base):
    __tablename__ = "sessions"

    token = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class SeenEmail(Base):
    __tablename__ = "seen_emails"

    email_id = Column(String, primary_key=True, index=True)
    seen_at = Column(DateTime, default=datetime.utcnow)
    outcome = Column(String)  # keyword_skip | not_relevant | relevant | possibly_relevant | error


# ─── CRM: outbound target accounts (Build 01) ──────────────────────────────────

ACCOUNT_STAGES = [
    "Not Contacted",
    "Contacted",
    "Replied",
    "Meeting Scheduled",
    "Proposal Sent",
    "Negotiation",
    "Won",
    "Lost",
]

ACCOUNT_SEGMENTS = [
    "Government / Public Sector",
    "Nonprofit",
    "Healthcare",
    "Education",
    "Enterprise / Mid-Market",
    "Other",
]


class Account(Base):
    """An outbound target account in the client-acquisition pipeline.

    Distinct from Opportunity (which is an inbound solicitation detected from
    email). An Account is a company FaithForge is actively prospecting.
    """
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Company
    company_name = Column(String, nullable=False, index=True)
    segment = Column(String, index=True)  # one of ACCOUNT_SEGMENTS
    website = Column(String)
    location = Column(String)

    # Primary contact
    contact_name = Column(String)
    contact_title = Column(String)
    contact_email = Column(String)
    contact_phone = Column(String)

    # Pipeline
    stage = Column(String, default="Not Contacted", index=True)  # one of ACCOUNT_STAGES
    priority_score = Column(Float)            # 0-100, AI-assigned
    priority_reason = Column(Text)            # justification for the score

    # Next-action tracking
    last_contacted_at = Column(DateTime)
    next_action = Column(Text)
    next_action_date = Column(DateTime)
    awaiting_reply = Column(Boolean, default=False)

    # Context for outreach
    pain_points = Column(Text)
    entry_offer = Column(Text)
    notes = Column(Text)
    source = Column(String)
