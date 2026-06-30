from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import (
        Opportunity, Document, Packet, AuditLog, AppSetting, User, Session, SeenEmail, Account
    )
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns()
    _backfill_seen_emails()


def _backfill_seen_emails():
    """Mark every email already saved as an Opportunity as 'seen' so a scan
    never re-processes (and re-pays for) emails that are already on the
    dashboard. Idempotent — only inserts email_ids not already tracked."""
    from models import Opportunity, SeenEmail
    db = SessionLocal()
    try:
        seen_ids = {row[0] for row in db.query(SeenEmail.email_id).all()}
        rows = db.query(Opportunity.email_id, Opportunity.relevance_classification).all()
        added = 0
        for email_id, classification in rows:
            if email_id and email_id not in seen_ids:
                db.add(SeenEmail(email_id=email_id, outcome=classification or "existing"))
                seen_ids.add(email_id)
                added += 1
        if added:
            db.commit()
            print(f"[backfill] marked {added} existing dashboard email(s) as seen", flush=True)
    except Exception as e:
        db.rollback()
        print(f"[backfill] seen_emails backfill failed: {e}", flush=True)
    finally:
        db.close()


def _migrate_add_columns():
    """Add new columns to existing SQLite DBs. Postgres uses create_all instead."""
    if not _is_sqlite:
        return
    from sqlalchemy import text
    new_columns = [
        ("score_breakdown", "TEXT"),
        ("questions_deadline", "VARCHAR"),
        ("eligibility_requirements", "TEXT"),
        ("required_qualifications", "TEXT"),
        ("required_forms", "TEXT"),
        ("submission_checklist", "TEXT"),
        ("proposal_format", "TEXT"),
        ("evaluation_criteria", "TEXT"),
        ("insurance_requirements", "TEXT"),
        ("certifications_required", "TEXT"),
        ("compliance_requirements", "TEXT"),
        ("pricing_requirements", "TEXT"),
        ("required_attachments", "TEXT"),
        ("disqualifying_requirements", "TEXT"),
        ("file_content", "BLOB"),
    ]
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(opportunities)")).fetchall()
        opp_existing = {row[1] for row in rows}
        for col_name, col_type in new_columns:
            if col_name not in opp_existing:
                conn.execute(text(f"ALTER TABLE opportunities ADD COLUMN {col_name} {col_type}"))
        # documents table
        doc_cols = [
            ("file_content", "BLOB"),
        ]
        rows = conn.execute(text("PRAGMA table_info(documents)")).fetchall()
        doc_existing = {row[1] for row in rows}
        for col_name, col_type in doc_cols:
            if col_name not in doc_existing:
                conn.execute(text(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}"))
        conn.commit()
