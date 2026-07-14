import os
import re
import json
import uuid
import secrets
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import (
    FastAPI, Depends, HTTPException, UploadFile, File, Form,
    BackgroundTasks, Request, Query, Header, Response
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database import get_db, init_db
from models import (
    Opportunity, Document, Packet, AuditLog, AppSetting, VALID_STATUSES,
    Account, ACCOUNT_STAGES, OutreachBatch, OutreachEmail,
)
from schemas import (
    OpportunityOut, OpportunityUpdate, OpportunityCreate, StatusUpdate, DocumentOut,
    PacketOut, AuditLogOut, DashboardStats, ScanResult, AppSettingOut,
    PacketBuildRequest, CompleteDraftRequest, CompleteDraftOut, RevisePacketRequest,
    AccountOut, AccountCreate, AccountUpdate, AccountStageUpdate, CRMStats,
    AccountDeleteAllRequest, AccountDeleteAllOut,
    ColdEmailRequest, ColdEmailFollowUpRequest,
    GoNoGoOut,
    OutreachImportPreviewOut, OutreachImportCommitRequest, OutreachImportCommitOut,
    OutreachGenerateRequest, OutreachBatchOut, OutreachEmailOut, OutreachEmailUpdate,
    OutreachIdList, OutreachSendResult, OutreachSendOut,
    OutreachFollowUpRequest, OutreachFindEmailOut,
)
from config import settings, UPLOAD_PATH, ALLOWED_EXTENSIONS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="FaithForge AI Contract Screener", version="1.0.0")

from passlib.context import CryptContext
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_TTL_DAYS = 30


def _create_session(db: Session, user_id: int) -> str:
    from models import Session as SessionModel
    token = secrets.token_hex(32)
    db.add(SessionModel(
        token=token,
        user_id=user_id,
        expires_at=datetime.utcnow() + timedelta(days=SESSION_TTL_DAYS),
    ))
    db.commit()
    return token


def require_auth(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    from models import Session as SessionModel
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.removeprefix("Bearer ").strip()
    sess = db.query(SessionModel).filter(SessionModel.token == token).first()
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if sess.expires_at < datetime.utcnow():
        db.delete(sess)
        db.commit()
        raise HTTPException(status_code=401, detail="Session expired")

_cors_origins = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]
if settings.ALLOWED_ORIGINS:
    _cors_origins += [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()
    _load_persisted_settings()
    logger.info("FaithForge AI Contract Screener started.")


def _load_persisted_settings():
    """Settings saved via PUT /api/settings only live-patch the running
    process's memory — on a restart (redeploy, free-tier spin-down/up,
    crash) that patch is gone and the app silently falls back to whatever
    is in the environment/.env file. Re-apply every persisted override from
    the database on every boot so a saved setting (e.g. OUTREACH_SEND_MODE
    = live) actually survives a restart instead of reverting to the code
    default."""
    from database import SessionLocal as _SessionLocal
    db = _SessionLocal()
    try:
        for setting in db.query(AppSetting).all():
            if setting.value and hasattr(settings, setting.key):
                try:
                    object.__setattr__(settings, setting.key, setting.value)
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Could not load persisted settings on startup: %s", e)
    finally:
        db.close()


def log_action(db: Session, action: str, opportunity_id: Optional[int] = None, details: str = None):
    entry = AuditLog(action=action, opportunity_id=opportunity_id, details=details)
    db.add(entry)
    db.commit()


# ─── Auth ────────────────────────────────────────────────────────────────────

@app.post("/api/auth/register")
def register(body: dict, db: Session = Depends(get_db)):
    from models import User
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not name or not email or not password:
        raise HTTPException(status_code=400, detail="Name, email, and password are required")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    user = User(name=name, email=email, hashed_password=_pwd_context.hash(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = _create_session(db, user.id)
    return {"token": token, "name": user.name, "email": user.email}


@app.post("/api/auth/login")
def login(body: dict, db: Session = Depends(get_db)):
    from models import User
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    user = db.query(User).filter(User.email == email).first()
    if not user or not _pwd_context.verify(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = _create_session(db, user.id)
    return {"token": token, "name": user.name, "email": user.email}


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    from models import Session as SessionModel
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        sess = db.query(SessionModel).filter(SessionModel.token == token).first()
        if sess:
            db.delete(sess)
            db.commit()
    return {"message": "Logged out"}


# ─── Health ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ─── Dashboard ───────────────────────────────────────────────────────────────

@app.get("/api/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    total = db.query(Opportunity).count()
    status_counts = (
        db.query(Opportunity.status, func.count(Opportunity.id))
        .group_by(Opportunity.status)
        .all()
    )
    by_status = {status: count for status, count in status_counts}
    recent = (
        db.query(Opportunity)
        .filter(Opportunity.status.notin_(["Not Relevant", "Declined"]))
        .order_by(desc(Opportunity.created_at))
        .limit(10)
        .all()
    )
    upcoming = (
        db.query(Opportunity)
        .filter(
            Opportunity.due_date.isnot(None),
            Opportunity.due_date >= datetime.utcnow(),
            Opportunity.status.notin_(["Not Relevant", "Declined"]),
        )
        .order_by(Opportunity.due_date.asc())
        .limit(8)
        .all()
    )
    return DashboardStats(total=total, by_status=by_status, recent=recent, upcoming=upcoming)


# ─── Opportunities ────────────────────────────────────────────────────────────

@app.get("/api/opportunities", response_model=List[OpportunityOut])
def list_opportunities(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    classification: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    q = db.query(Opportunity)
    if status:
        q = q.filter(Opportunity.status == status)
    if classification:
        q = q.filter(Opportunity.relevance_classification == classification)
    if search:
        term = f"%{search}%"
        q = q.filter(
            Opportunity.email_subject.ilike(term)
            | Opportunity.opportunity_title.ilike(term)
            | Opportunity.agency_name.ilike(term)
            | Opportunity.solicitation_number.ilike(term)
        )
    return q.order_by(desc(Opportunity.created_at)).offset(skip).limit(limit).all()


@app.post("/api/opportunities", response_model=OpportunityOut)
def create_opportunity(
    body: OpportunityCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Manually add an opportunity that wasn't found via email scan (e.g. spotted
    on a portal). It enters the same pipeline as an email-discovered opportunity:
    upload documents (including anything pulled from EMMA) → AI Review → checklist
    → build proposal."""
    opp = Opportunity(
        email_id=f"manual-{uuid.uuid4().hex}",
        email_subject=body.opportunity_title,
        email_from="Manual Entry",
        opportunity_title=body.opportunity_title,
        agency_name=body.agency_name,
        solicitation_number=body.solicitation_number,
        contract_type=body.contract_type,
        estimated_value=body.estimated_value,
        due_date=body.due_date,
        emma_link=body.emma_link,
        has_emma_link=bool(body.emma_link),
        opportunity_summary=body.opportunity_summary,
        status="New",
    )
    db.add(opp)
    db.commit()
    db.refresh(opp)
    log_action(db, "opportunity_created_manually", opp.id, json.dumps({"title": body.opportunity_title}))
    return opp


@app.get("/api/opportunities/{opportunity_id}", response_model=OpportunityOut)
def get_opportunity(opportunity_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opp


@app.put("/api/opportunities/{opportunity_id}", response_model=OpportunityOut)
def update_opportunity(
    opportunity_id: int,
    update: OpportunityUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    for field, val in update.model_dump(exclude_none=True).items():
        setattr(opp, field, val)
    opp.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(opp)
    log_action(db, "opportunity_updated", opportunity_id, json.dumps({"fields": list(update.model_dump(exclude_none=True).keys())}))
    return opp


@app.put("/api/opportunities/{opportunity_id}/status", response_model=OpportunityOut)
def update_status(
    opportunity_id: int,
    status_update: StatusUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    if status_update.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}")
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    old_status = opp.status
    opp.status = status_update.status
    opp.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(opp)
    log_action(db, "status_changed", opportunity_id, json.dumps({"from": old_status, "to": status_update.status}))
    return opp


@app.delete("/api/opportunities/{opportunity_id}")
def delete_opportunity(opportunity_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    # Delete associated files
    for doc in opp.documents:
        try:
            if os.path.exists(doc.file_path):
                os.remove(doc.file_path)
        except Exception:
            pass
    log_action(db, "opportunity_deleted", opportunity_id, json.dumps({"title": opp.opportunity_title or opp.email_subject}))
    db.delete(opp)
    db.commit()
    return {"message": "Opportunity deleted"}


# ─── Email Scan ───────────────────────────────────────────────────────────────

scan_status = {"running": False, "last_result": None}


def run_email_scan(db_session_factory, days_back: int):
    global scan_status
    scan_status["running"] = True
    result = {"scanned": 0, "new_found": 0, "relevant": 0, "possibly_relevant": 0, "not_relevant": 0, "errors": []}
    try:
        from email_scanner import scan_emails
        from ai_screener import screen_email
        emails = scan_emails(days_back)
        db = db_session_factory()
        from models import SeenEmail
        try:
            for em in emails:
                result["scanned"] += 1
                email_id = em["email_id"]
                # Skip emails already in Opportunities table
                if db.query(Opportunity).filter(Opportunity.email_id == email_id).first():
                    continue
                # Skip emails already processed in a previous scan (not_relevant, errors, etc.)
                if db.query(SeenEmail).filter(SeenEmail.email_id == email_id).first():
                    continue
                # Also deduplicate by subject to avoid multiple EMMA reminders for same RFP
                subj = (em.get("email_subject") or "").strip()
                if subj:
                    title_dup = db.query(Opportunity).filter(
                        Opportunity.email_subject == subj
                    ).first()
                    if title_dup:
                        db.add(SeenEmail(email_id=email_id, outcome="subject_dup"))
                        db.commit()
                        continue
                try:
                    if not em.get("passes_keyword_check"):
                        result["not_relevant"] += 1
                        db.add(SeenEmail(email_id=email_id, outcome="keyword_skip"))
                        db.commit()
                        continue  # skip — don't store pure spam/marketing
                    else:
                        screening = screen_email(
                            subject=em["email_subject"] or "",
                            sender=em["email_from"] or "",
                            date=str(em["email_date"]) if em.get("email_date") else "",
                            body=em["email_body"] or "",
                        )
                    classification = screening.get("classification", "not_relevant")
                    # Drop not-relevant emails — mark as seen so they're skipped next scan
                    if classification == "not_relevant":
                        result["not_relevant"] += 1
                        db.add(SeenEmail(email_id=email_id, outcome="not_relevant"))
                        db.commit()
                        continue
                    # Dedup by solicitation number (same RFP, different email notices)
                    sol_num = screening.get("solicitation_number")
                    if sol_num:
                        sol_dup = db.query(Opportunity).filter(
                            Opportunity.solicitation_number == sol_num
                        ).first()
                        if sol_dup:
                            db.add(SeenEmail(email_id=email_id, outcome="sol_dup"))
                            db.commit()
                            continue
                    # Map classification to status
                    if classification == "relevant":
                        status = "Relevant"
                        result["relevant"] += 1
                    else:
                        status = "Possibly Relevant"
                        result["possibly_relevant"] += 1
                    # Override status if EMMA needed
                    if screening.get("has_emma_link") or em.get("has_emma_link"):
                        status = "EMMA Documents Needed"
                    # Parse dates
                    from dateutil.parser import parse as parse_date
                    due_date = None
                    pre_bid_date = None
                    if screening.get("due_date"):
                        try:
                            due_date = parse_date(screening["due_date"])
                        except Exception:
                            pass
                    if screening.get("pre_bid_date"):
                        try:
                            pre_bid_date = parse_date(screening["pre_bid_date"])
                        except Exception:
                            pass
                    opp = Opportunity(
                        email_id=email_id,
                        email_subject=em["email_subject"],
                        email_from=em["email_from"],
                        email_date=em["email_date"],
                        email_body_preview=em["email_body_preview"],
                        status=status,
                        relevance_classification=classification,
                        relevance_score=screening.get("relevance_score"),
                        classification_reasoning=screening.get("classification_reasoning"),
                        score_breakdown=screening.get("score_breakdown"),
                        opportunity_title=screening.get("opportunity_title"),
                        agency_name=screening.get("agency_name"),
                        solicitation_number=screening.get("solicitation_number"),
                        due_date=due_date,
                        pre_bid_date=pre_bid_date,
                        submission_method=screening.get("submission_method"),
                        contact_person=screening.get("contact_person"),
                        contact_email=screening.get("contact_email"),
                        website_link=screening.get("website_link"),
                        emma_link=screening.get("emma_link") or em.get("emma_link"),
                        has_emma_link=screening.get("has_emma_link") or em.get("has_emma_link", False),
                        opportunity_summary=screening.get("opportunity_summary"),
                        required_services=screening.get("required_services"),
                        faithforge_alignment=screening.get("faithforge_alignment"),
                        recommended_action=screening.get("recommended_action"),
                        risk_concerns=screening.get("risk_concerns"),
                        estimated_value=screening.get("estimated_value"),
                        contract_type=screening.get("contract_type"),
                    )
                    db.add(opp)
                    db.add(SeenEmail(email_id=email_id, outcome=classification))
                    db.commit()
                    db.refresh(opp)
                    log_action(db, "email_scanned", opp.id, json.dumps({"classification": classification, "subject": em["email_subject"]}))
                    result["new_found"] += 1
                except Exception as e:
                    import traceback
                    tb = traceback.format_exc()
                    print(f"\n{'='*60}\nEMAIL ERROR: {em.get('email_subject', '')}\n{tb}{'='*60}\n", flush=True)
                    result["errors"].append(f"Error processing email '{em.get('email_subject', '')}': {str(e)}")
                    logger.error(f"Email processing error: {e}\n{tb}")
        finally:
            db.close()
        # Send notification email if new relevant opportunities found
        if result["relevant"] > 0 or result["possibly_relevant"] > 0:
            try:
                _send_scan_notification(result)
            except Exception as e:
                logger.warning(f"Scan notification email failed: {e}")
    except Exception as e:
        result["errors"].append(f"Scan error: {str(e)}")
        logger.error(f"Email scan error: {e}")
    finally:
        scan_status["running"] = False
        scan_status["last_result"] = result


def _send_scan_notification(result: dict):
    """Send a summary email when the scan finds new relevant opportunities."""
    if not settings.NOTIFICATION_EMAIL:
        return
    subject = f"FaithForge: {result['relevant'] + result['possibly_relevant']} New Contract Opportunities Found"
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #1f2937; }}
  .header {{ background: #1e3a8a; color: white; padding: 20px 24px; border-radius: 8px; margin-bottom: 20px; }}
  .header h1 {{ margin: 0; font-size: 18px; }}
  .stat {{ display: inline-block; background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 12px 20px; margin: 6px; text-align: center; }}
  .stat .num {{ font-size: 28px; font-weight: 700; color: #0369a1; }}
  .stat .label {{ font-size: 12px; color: #6b7280; margin-top: 2px; }}
  .relevant {{ border-color: #86efac; background: #f0fdf4; }}
  .relevant .num {{ color: #16a34a; }}
  .possibly {{ border-color: #fde68a; background: #fffbeb; }}
  .possibly .num {{ color: #d97706; }}
  .btn {{ display: inline-block; background: #1e3a8a; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600; margin-top: 16px; }}
</style>
</head>
<body>
<div class="header"><h1>FaithForge Email Scan Complete</h1></div>
<p>Your inbox scan has finished. Here's what was found:</p>
<div>
  <div class="stat relevant"><div class="num">{result['relevant']}</div><div class="label">Relevant</div></div>
  <div class="stat possibly"><div class="num">{result['possibly_relevant']}</div><div class="label">Possibly Relevant</div></div>
  <div class="stat"><div class="num">{result['scanned']}</div><div class="label">Emails Scanned</div></div>
</div>
<p style="margin-top:20px;">Log into the FaithForge AI tool to review these opportunities, upload any EMMA documents, and build your contract packets.</p>
<p style="font-size:12px;color:#9ca3af;margin-top:24px;">Generated {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}</p>
</body></html>"""

    from ms_graph import get_graph_client
    graph = get_graph_client()
    if graph:
        graph.send_email(settings.NOTIFICATION_EMAIL, subject, html)
        return
    if not settings.SMTP_HOST:
        return
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import smtplib
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = settings.NOTIFICATION_EMAIL
    msg.attach(MIMEText(html, "html"))
    if settings.SMTP_USE_TLS:
        srv = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        srv.ehlo(); srv.starttls()
    else:
        srv = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
    if settings.SMTP_USERNAME:
        srv.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
    srv.sendmail(settings.SMTP_FROM_EMAIL, settings.NOTIFICATION_EMAIL, msg.as_string())
    srv.quit()


@app.post("/api/scan/email")
def scan_email(
    background_tasks: BackgroundTasks,
    days_back: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    if scan_status["running"]:
        raise HTTPException(status_code=409, detail="Scan already in progress")
    background_tasks.add_task(run_email_scan, lambda: SessionLocal(), days_back)
    log_action(db, "email_scan_started", details=json.dumps({"days_back": days_back}))
    return {"message": "Email scan started", "days_back": days_back}


@app.get("/api/scan/status")
def get_scan_status():
    return scan_status


# ─── Documents ────────────────────────────────────────────────────────────────

@app.post("/api/opportunities/{opportunity_id}/documents", response_model=DocumentOut)
async def upload_document(
    opportunity_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
    safe_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_PATH, safe_name)
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    with open(file_path, "wb") as f:
        f.write(content)
    doc = Document(
        opportunity_id=opportunity_id,
        filename=safe_name,
        original_filename=file.filename,
        file_path=file_path,
        file_type=ext.lstrip("."),
        file_size=len(content),
        file_content=content,  # persisted in DB so files survive server restarts
    )
    db.add(doc)
    if opp.status in ("Relevant", "Possibly Relevant", "EMMA Documents Needed"):
        opp.status = "Documents Uploaded"
    opp.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(doc)
    log_action(db, "document_uploaded", opportunity_id, json.dumps({"filename": file.filename, "size": len(content)}))
    return doc


@app.get("/api/opportunities/{opportunity_id}/documents", response_model=List[DocumentOut])
def list_documents(opportunity_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opp.documents


@app.delete("/api/opportunities/{opportunity_id}/documents/{document_id}")
def delete_document(
    opportunity_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.opportunity_id == opportunity_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except Exception as e:
        logger.warning(f"Could not delete file {doc.file_path}: {e}")
    log_action(db, "document_deleted", opportunity_id, json.dumps({"filename": doc.original_filename}))
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted"}


@app.post("/api/opportunities/{opportunity_id}/documents/review", response_model=OpportunityOut)
def review_documents_endpoint(
    opportunity_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if not opp.documents:
        raise HTTPException(status_code=400, detail="No documents uploaded to review")
    from document_processor import process_document, truncate_for_ai
    from ai_screener import review_documents
    doc_texts = []
    for doc in opp.documents:
        text = process_document(doc.file_path, UPLOAD_PATH, doc.file_content)
        doc_texts.append(f"=== {doc.original_filename} ===\n{truncate_for_ai(text, 200000)}")
    opp_context = f"""Title: {opp.opportunity_title or opp.email_subject}
Agency: {opp.agency_name}
Solicitation: {opp.solicitation_number}
Summary: {opp.opportunity_summary}
Status: {opp.status}"""
    result = review_documents(opp_context, "\n\n".join(doc_texts))
    # Update opportunity fields from review
    updatable = [
        "opportunity_title", "agency_name", "solicitation_number",
        "submission_method", "contact_person", "contact_email",
        "website_link", "emma_link", "opportunity_summary",
        "required_services", "faithforge_alignment", "recommended_action",
        "risk_concerns", "estimated_value", "contract_type",
        "questions_deadline", "eligibility_requirements", "required_qualifications",
        "required_forms", "submission_checklist", "proposal_format", "evaluation_criteria",
        "insurance_requirements", "certifications_required", "compliance_requirements",
        "pricing_requirements", "required_attachments", "disqualifying_requirements",
    ]
    for field in updatable:
        val = result.get(field)
        if val:
            setattr(opp, field, val)
    for field in ("due_date", "pre_bid_date"):
        val = result.get(field)
        if val:
            try:
                from dateutil.parser import parse as parse_date
                setattr(opp, field, parse_date(val))
            except Exception:
                pass
    if result.get("has_emma_link"):
        opp.has_emma_link = True
    if result.get("emma_link"):
        opp.emma_link = result["emma_link"]
    # Store review in first document
    review_summary = result.get("review_summary", "")
    for doc in opp.documents:
        doc.reviewed = True
        if not doc.review_content:
            doc.review_content = json.dumps(result)
    opp.status = "Under Review"
    opp.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(opp)
    log_action(db, "documents_reviewed", opportunity_id)
    return opp


# ─── Packets ─────────────────────────────────────────────────────────────────

@app.post("/api/opportunities/{opportunity_id}/packet", response_model=PacketOut)
def build_packet_endpoint(
    opportunity_id: int,
    body: PacketBuildRequest = PacketBuildRequest(),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    from document_processor import process_document, truncate_for_ai
    from packet_builder import build_packet, format_opportunity_context
    opp.status = "Packet Building"
    opp.updated_at = datetime.utcnow()
    db.commit()
    doc_texts = []
    for doc in opp.documents:
        text = process_document(doc.file_path, UPLOAD_PATH, doc.file_content)
        doc_texts.append(f"=== {doc.original_filename} ===\n{truncate_for_ai(text, 200000)}")
    opp_dict = {
        col.name: getattr(opp, col.name)
        for col in opp.__table__.columns
    }
    try:
        result = build_packet(opp_dict, doc_texts, custom_instructions=body.custom_instructions)
    except Exception as e:
        opp.status = "Under Review"
        db.commit()
        msg = str(e)
        logger.exception("Packet build failed for opportunity %d (%s): %s",
                         opportunity_id, opp.opportunity_title or opp.email_subject, msg)
        if "rate_limit" in msg or "429" in msg or "tokens per minute" in msg or "RateLimitError" in msg:
            msg = ("OpenAI rate limit reached. Wait ~1 minute and retry, "
                   "or check your API key has an active balance at platform.openai.com/usage.")
        raise HTTPException(status_code=500, detail=f"Packet build failed: {msg}")
    # Remove existing packets
    db.query(Packet).filter(Packet.opportunity_id == opportunity_id).delete()
    packet = Packet(
        opportunity_id=opportunity_id,
        content_json=result["content_json"],
        html_content=result["html_content"],
    )
    db.add(packet)
    opp.status = "Packet Ready"
    opp.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(packet)
    log_action(db, "packet_built", opportunity_id)
    return packet


@app.post("/api/opportunities/{opportunity_id}/proposal/complete-draft", response_model=CompleteDraftOut)
def complete_draft_endpoint(
    opportunity_id: int,
    body: CompleteDraftRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    from document_processor import process_document, truncate_for_ai
    from packet_builder import complete_draft_packet

    draft_text = (body.draft_text or "").strip()
    draft_document_id = body.document_id

    if not draft_text and draft_document_id is None:
        raise HTTPException(status_code=400, detail="Provide either draft_text or document_id.")

    if not draft_text and draft_document_id is not None:
        draft_doc = next((d for d in opp.documents if d.id == draft_document_id), None)
        if not draft_doc:
            raise HTTPException(status_code=404, detail="Draft document not found on this opportunity.")
        draft_text = truncate_for_ai(process_document(draft_doc.file_path, UPLOAD_PATH, draft_doc.file_content), 150000)

    if not draft_text:
        raise HTTPException(status_code=400, detail="Draft is empty — nothing to analyze.")

    # RFP context comes from every OTHER uploaded document (exclude the draft itself)
    rfp_texts = []
    for doc in opp.documents:
        if doc.id == draft_document_id:
            continue
        text = process_document(doc.file_path, UPLOAD_PATH, doc.file_content)
        rfp_texts.append(f"=== {doc.original_filename} ===\n{truncate_for_ai(text, 150000)}")

    opp.status = "Packet Building"
    opp.updated_at = datetime.utcnow()
    db.commit()
    opp_dict = {col.name: getattr(opp, col.name) for col in opp.__table__.columns}
    try:
        result = complete_draft_packet(opp_dict, rfp_texts, draft_text, custom_instructions=body.custom_instructions or "")
    except Exception as e:
        opp.status = "Under Review"
        db.commit()
        msg = str(e)
        logger.exception("Draft completion failed for opportunity %d (%s): %s",
                         opportunity_id, opp.opportunity_title or opp.email_subject, msg)
        if "rate_limit" in msg or "429" in msg or "tokens per minute" in msg or "RateLimitError" in msg:
            msg = ("OpenAI rate limit reached. Wait ~1 minute and retry, "
                   "or check your API key has an active balance at platform.openai.com/usage.")
        raise HTTPException(status_code=500, detail=f"Draft completion failed: {msg}")

    db.query(Packet).filter(Packet.opportunity_id == opportunity_id).delete()
    packet = Packet(
        opportunity_id=opportunity_id,
        content_json=result["content_json"],
        html_content=result["html_content"],
    )
    db.add(packet)
    opp.status = "Packet Ready"
    opp.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(packet)
    log_action(db, "draft_completed", opportunity_id, json.dumps({"document_id": draft_document_id}))
    return {"packet": packet, "analysis": result["analysis"]}


@app.get("/api/opportunities/{opportunity_id}/packet", response_model=PacketOut)
def get_packet(opportunity_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    packet = db.query(Packet).filter(Packet.opportunity_id == opportunity_id).order_by(desc(Packet.created_at)).first()
    if not packet:
        raise HTTPException(status_code=404, detail="No packet found for this opportunity")
    return packet


@app.post("/api/opportunities/{opportunity_id}/packet/email")
def email_packet_endpoint(
    opportunity_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    packet = db.query(Packet).filter(Packet.opportunity_id == opportunity_id).order_by(desc(Packet.created_at)).first()
    if not packet:
        raise HTTPException(status_code=404, detail="No packet found. Build the packet first.")
    from email_sender import send_packet_email
    opp_dict = {col.name: getattr(opp, col.name) for col in opp.__table__.columns}
    try:
        send_packet_email(opp_dict, packet.html_content or "", packet.content_json or "{}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email send failed: {str(e)}")
    packet.emailed = True
    packet.emailed_at = datetime.utcnow()
    opp.status = "Reviewed by User"
    opp.updated_at = datetime.utcnow()
    db.commit()
    from email_sender import _packet_recipients
    recipients = _packet_recipients()
    to_str = ", ".join(recipients)
    log_action(db, "packet_emailed", opportunity_id, json.dumps({"to": recipients}))
    return {"message": "Packet emailed successfully", "to": to_str}


@app.get("/api/opportunities/{opportunity_id}/packet/export")
def export_packet_endpoint(
    opportunity_id: int,
    format: str = Query("docx", pattern="^(docx|pdf)$"),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    packet = db.query(Packet).filter(Packet.opportunity_id == opportunity_id).order_by(desc(Packet.created_at)).first()
    if not packet:
        raise HTTPException(status_code=404, detail="No packet found. Build the packet first.")
    try:
        content = json.loads(packet.content_json or "{}")
    except Exception:
        content = {}
    markdown = content.get("markdown", "")
    plan = content.get("plan") if isinstance(content.get("plan"), dict) else None
    title = opp.opportunity_title or opp.email_subject or "FaithForge Proposal"
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()[:60] or "proposal"

    from packet_export import markdown_to_docx_bytes, markdown_to_pdf_bytes
    try:
        if format == "docx":
            data = markdown_to_docx_bytes(markdown, title, client_name=opp.agency_name, plan=plan)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = f"{slug}-proposal.docx"
        else:
            data = markdown_to_pdf_bytes(markdown, title, client_name=opp.agency_name, plan=plan)
            media_type = "application/pdf"
            filename = f"{slug}-proposal.pdf"
    except Exception as e:
        logger.exception("Packet export failed for opportunity %d (%s): %s", opportunity_id, format, e)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

    log_action(db, "packet_exported", opportunity_id, json.dumps({"format": format}))
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/opportunities/{opportunity_id}/packet/revise", response_model=PacketOut)
def revise_packet_endpoint(
    opportunity_id: int,
    body: RevisePacketRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    packet = db.query(Packet).filter(Packet.opportunity_id == opportunity_id).order_by(desc(Packet.created_at)).first()
    if not packet:
        raise HTTPException(status_code=404, detail="No packet found. Build the packet first.")
    try:
        current = json.loads(packet.content_json or "{}")
    except Exception:
        current = {}
    current_markdown = current.get("markdown", "")
    if not current_markdown:
        raise HTTPException(status_code=400, detail="Current packet has no content to revise.")

    from packet_builder import revise_packet
    opp_dict = {col.name: getattr(opp, col.name) for col in opp.__table__.columns}
    try:
        result = revise_packet(opp_dict, current_markdown, body.instruction)
    except Exception as e:
        logger.exception("Packet revision failed for opportunity %d: %s", opportunity_id, e)
        raise HTTPException(status_code=500, detail=f"Revision failed: {str(e)}")

    new_packet = Packet(
        opportunity_id=opportunity_id,
        content_json=result["content_json"],
        html_content=result["html_content"],
    )
    db.add(new_packet)
    opp.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(new_packet)
    log_action(db, "packet_revised", opportunity_id, json.dumps({"instruction": body.instruction}))
    return new_packet


# ─── Audit Log ────────────────────────────────────────────────────────────────

@app.get("/api/audit", response_model=List[AuditLogOut])
def get_audit_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    opportunity_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    q = db.query(AuditLog)
    if opportunity_id:
        q = q.filter(AuditLog.opportunity_id == opportunity_id)
    return q.order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit).all()


# ─── CRM Accounts (Build 01) ───────────────────────────────────────────────────

@app.get("/api/crm/stats", response_model=CRMStats)
def crm_stats(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    total = db.query(Account).count()
    stage_counts = (
        db.query(Account.stage, func.count(Account.id))
        .group_by(Account.stage)
        .all()
    )
    by_stage = {stage: count for stage, count in stage_counts}
    awaiting = db.query(Account).filter(Account.awaiting_reply == True).count()  # noqa: E712
    actions_due = (
        db.query(Account)
        .filter(
            Account.next_action_date.isnot(None),
            Account.stage.notin_(["Won", "Lost"]),
        )
        .order_by(Account.next_action_date.asc())
        .limit(10)
        .all()
    )
    top_priority = (
        db.query(Account)
        .filter(Account.stage.notin_(["Won", "Lost"]))
        .order_by(desc(Account.priority_score))
        .limit(10)
        .all()
    )
    return CRMStats(
        total=total, by_stage=by_stage, awaiting_reply=awaiting,
        actions_due=actions_due, top_priority=top_priority,
    )


@app.get("/api/accounts", response_model=List[AccountOut])
def list_accounts(
    stage: Optional[str] = Query(None),
    segment: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: str = Query("priority"),  # priority | recent | next_action
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    q = db.query(Account)
    if stage:
        q = q.filter(Account.stage == stage)
    if segment:
        q = q.filter(Account.segment == segment)
    if search:
        term = f"%{search}%"
        q = q.filter(
            Account.company_name.ilike(term)
            | Account.contact_name.ilike(term)
            | Account.contact_email.ilike(term)
        )
    if sort == "recent":
        q = q.order_by(desc(Account.created_at))
    elif sort == "next_action":
        q = q.order_by(Account.next_action_date.asc().nullslast())
    else:
        q = q.order_by(desc(Account.priority_score), desc(Account.created_at))
    return q.offset(skip).limit(limit).all()


@app.post("/api/accounts", response_model=AccountOut)
def create_account(body: AccountCreate, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    data = body.model_dump(exclude_none=True)
    acc = Account(**data)
    if not acc.stage:
        acc.stage = "Not Contacted"
    db.add(acc)
    db.commit()
    db.refresh(acc)
    log_action(db, "account_created", details=json.dumps({"company": acc.company_name}))
    return acc


@app.get("/api/accounts/{account_id}", response_model=AccountOut)
def get_account(account_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    return acc


@app.put("/api/accounts/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int,
    update: AccountUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    for field, val in update.model_dump(exclude_unset=True).items():
        setattr(acc, field, val)
    acc.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(acc)
    return acc


@app.put("/api/accounts/{account_id}/stage", response_model=AccountOut)
def update_account_stage(
    account_id: int,
    body: AccountStageUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    if body.stage not in ACCOUNT_STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {', '.join(ACCOUNT_STAGES)}")
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    old = acc.stage
    acc.stage = body.stage
    # Auto-manage contact/reply tracking as the stage advances
    if body.stage == "Contacted" and not acc.last_contacted_at:
        acc.last_contacted_at = datetime.utcnow()
        acc.awaiting_reply = True
    if body.stage in ("Replied", "Meeting Scheduled", "Won", "Lost"):
        acc.awaiting_reply = False
    acc.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(acc)
    log_action(db, "account_stage_changed", details=json.dumps({"company": acc.company_name, "from": old, "to": body.stage}))
    return acc


@app.delete("/api/accounts", response_model=AccountDeleteAllOut)
def delete_all_accounts(
    body: AccountDeleteAllRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Wipes every Account (and their outreach emails via cascade). Requires
    an exact confirmation phrase so this can never fire by accident."""
    if body.confirm != "DELETE ALL ACCOUNTS":
        raise HTTPException(status_code=400, detail='Confirmation phrase must be exactly "DELETE ALL ACCOUNTS".')
    accounts = db.query(Account).all()
    count = len(accounts)
    for acc in accounts:
        db.delete(acc)  # per-row delete (not bulk .delete()) so the OutreachEmail cascade fires
    db.commit()
    log_action(db, "accounts_deleted_all", details=json.dumps({"count": count}))
    return AccountDeleteAllOut(deleted=count)


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    log_action(db, "account_deleted", details=json.dumps({"company": acc.company_name}))
    db.delete(acc)
    db.commit()
    return {"message": "Account deleted"}


@app.post("/api/accounts/{account_id}/score", response_model=AccountOut)
def score_account_endpoint(account_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    from ai_screener import score_account
    try:
        result = score_account(
            company_name=acc.company_name or "",
            segment=acc.segment or "",
            location=acc.location or "",
            contact_name=acc.contact_name or "",
            contact_title=acc.contact_title or "",
            pain_points=acc.pain_points or "",
            notes=acc.notes or "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI scoring failed: {str(e)}")
    acc.priority_score = result.get("priority_score")
    acc.priority_reason = result.get("priority_reason")
    if not acc.pain_points and result.get("suggested_pain_points"):
        acc.pain_points = result["suggested_pain_points"]
    if not acc.entry_offer and result.get("suggested_entry_offer"):
        acc.entry_offer = result["suggested_entry_offer"]
    acc.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(acc)
    log_action(db, "account_scored", details=json.dumps({"company": acc.company_name, "score": acc.priority_score}))
    return acc


# ─── Cold Email Generator (Build 02) ────────────────────────────────────────
# One email drafted and saved per click — never a speculative multi-email
# sequence up front. Every draft is a real OutreachEmail row tied to a
# found-or-created Account, so it survives a refresh and uses the exact same
# approve/send pipeline as Bulk Outreach (dry-run/live, BCC, daily cap,
# opt-out check) via the existing /api/outreach/emails/{id}/* endpoints.

def _find_or_create_account_for_contact(
    company_name: str, segment: Optional[str], contact_name: Optional[str],
    contact_title: Optional[str], contact_email: str, pain_points: Optional[str],
    entry_offer: Optional[str], db: Session,
) -> Account:
    import re as _re
    email = contact_email.strip()
    if not _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="That doesn't look like a valid email address.")

    acc = db.query(Account).filter(Account.contact_email.ilike(email)).first()
    if not acc and contact_name:
        acc = (db.query(Account)
               .filter(Account.company_name.ilike(company_name.strip()),
                       Account.contact_name.ilike(contact_name.strip()))
               .first())

    if acc:
        # The address just typed into this form is authoritative for this
        # contact going forward — always sync it, not just fill a blank,
        # otherwise a stale on-file email silently wins over a correction.
        acc.contact_email = email
        if segment and not acc.segment:
            acc.segment = segment
        if contact_name and not acc.contact_name:
            acc.contact_name = contact_name
        if contact_title and not acc.contact_title:
            acc.contact_title = contact_title
        if pain_points and not acc.pain_points:
            acc.pain_points = pain_points
        if entry_offer and not acc.entry_offer:
            acc.entry_offer = entry_offer
        acc.updated_at = datetime.utcnow()
    else:
        acc = Account(
            company_name=company_name.strip(), segment=segment or None,
            contact_name=contact_name or None, contact_title=contact_title or None,
            contact_email=email, pain_points=pain_points or None, entry_offer=entry_offer or None,
            stage="Not Contacted", source="cold_email_single",
        )
        db.add(acc)
    db.flush()
    return acc


@app.post("/api/cold-email/generate", response_model=OutreachEmailOut)
def generate_cold_email_endpoint(
    body: ColdEmailRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    acc = _find_or_create_account_for_contact(
        body.company_name, body.segment, body.contact_name, body.contact_title,
        body.contact_email, body.pain_points, body.entry_offer, db,
    )
    if acc.do_not_contact:
        raise HTTPException(status_code=400, detail="This contact has opted out (Do Not Contact) — cannot draft or send.")

    # Use the SAME generator as Bulk Outreach — it's grounded in real emails
    # Bernedette actually sent (warm, 60-90 words, soft ask), so single-lead
    # drafts match that proven voice instead of the older, blunter cold-email
    # prompt that read as presumptuous.
    import outreach_generator as og
    try:
        results = og.generate_sync([acc])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cold email generation failed: {str(e)}")

    if not results or results[0].get("error"):
        detail = results[0]["error"] if results and results[0].get("error") else "The model didn't return a usable draft — try again."
        raise HTTPException(status_code=500, detail=detail)
    drafted = results[0]

    row = OutreachEmail(
        account_id=acc.id, subject=drafted.get("subject", ""), body=drafted.get("body", ""),
        status="draft", model_used=drafted.get("model_used") or "cold-email-single",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_action(db, "cold_email_single_drafted", details=json.dumps({"account_id": acc.id, "email_id": row.id}))
    return _outreach_email_to_out(row, acc)


@app.post("/api/cold-email/follow-up", response_model=OutreachEmailOut)
def generate_cold_email_follow_up(
    body: ColdEmailFollowUpRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Explicit, manual follow-up for ONE contact — no eligibility/day gating
    (that's for the bulk auto-follow-up sweep). Drafts referencing whatever
    was most recently written for this account, regardless of send status."""
    acc = db.query(Account).filter(Account.id == body.account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    if acc.do_not_contact:
        raise HTTPException(status_code=400, detail="This contact has opted out (Do Not Contact) — cannot draft or send.")

    original = (db.query(OutreachEmail)
                .filter(OutreachEmail.account_id == acc.id)
                .order_by(desc(OutreachEmail.created_at))
                .first())
    if not original:
        raise HTTPException(status_code=400, detail="No previous email on file for this contact to follow up on — generate an intro first.")

    import outreach_generator as og
    try:
        results = og.generate_follow_ups([{"account": acc, "original_body": original.body or ""}])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Follow-up generation failed: {e}")

    if not results or results[0].get("error"):
        raise HTTPException(status_code=500, detail=(results[0]["error"] if results else "The model didn't return a usable follow-up — try again."))

    drafted = results[0]
    row = OutreachEmail(
        account_id=acc.id, subject=drafted.get("subject", ""), body=drafted.get("body", ""),
        status="draft", model_used="cold-email-single", is_follow_up=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_action(db, "cold_email_single_follow_up_drafted", details=json.dumps({"account_id": acc.id, "email_id": row.id}))
    return _outreach_email_to_out(row, acc)


# ─── Bulk Outreach (Build 04) ────────────────────────────────────────────────
# Upload a leads file -> AI drafts one cold email per lead -> human approves ->
# send from a dedicated mailbox (never Bernedette's personal inbox, and never
# a status other than "approved"). See lead_import.py, outreach_generator.py,
# outreach_sender.py.

def _outreach_email_to_out(email_row: OutreachEmail, account: Optional[Account]) -> OutreachEmailOut:
    return OutreachEmailOut(
        id=email_row.id,
        created_at=email_row.created_at,
        account_id=email_row.account_id,
        batch_id=email_row.batch_id,
        to_email=email_row.to_email,
        subject=email_row.subject,
        body=email_row.body,
        status=email_row.status,
        approved=email_row.approved,
        edited=email_row.edited,
        model_used=email_row.model_used,
        sent_at=email_row.sent_at,
        error=email_row.error,
        is_follow_up=bool(email_row.is_follow_up),
        account_company=account.company_name if account else None,
        account_contact=account.contact_name if account else None,
        account_has_email=bool(account.contact_email) if account else False,
        account_do_not_contact=bool(account.do_not_contact) if account else False,
    )


@app.post("/api/outreach/import/preview", response_model=OutreachImportPreviewOut)
async def outreach_import_preview(
    file: Optional[UploadFile] = File(None),
    google_sheet_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    import lead_import
    try:
        if file is not None:
            content = await file.read()
            result = lead_import.preview(content, file.filename, db)
        elif google_sheet_url:
            result = lead_import.preview_google_sheet(google_sheet_url, db)
        else:
            raise HTTPException(status_code=400, detail="Upload a file or provide a Google Sheet link.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.post("/api/outreach/import/commit", response_model=OutreachImportCommitOut)
def outreach_import_commit(
    body: OutreachImportCommitRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    import lead_import
    result = lead_import.commit(body.rows, body.source_filename, db, dedupe=body.dedupe)
    log_action(db, "outreach_leads_imported", details=json.dumps({
        "source": body.source_filename, "created": result["created"], "updated": result["updated"],
    }))
    return result


@app.post("/api/outreach/generate")
def outreach_generate(
    body: OutreachGenerateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    accounts = db.query(Account).filter(Account.id.in_(body.account_ids)).all()
    if not accounts:
        raise HTTPException(status_code=404, detail="No matching accounts found.")

    # Never draft intros for opted-out leads; skip already-contacted ones by
    # default so nobody gets the same intro twice (override with include_contacted).
    skipped_dnc = [a for a in accounts if a.do_not_contact]
    accounts = [a for a in accounts if not a.do_not_contact]
    skipped_contacted = []
    if not body.include_contacted:
        skipped_contacted = [a for a in accounts if a.stage and a.stage != "Not Contacted"]
        accounts = [a for a in accounts if not (a.stage and a.stage != "Not Contacted")]
    if not accounts:
        raise HTTPException(status_code=400, detail=(
            f"All selected leads were skipped ({len(skipped_contacted)} already contacted, "
            f"{len(skipped_dnc)} opted out). Re-run with include_contacted to draft for contacted leads anyway."))

    model = body.model or settings.OUTREACH_MODEL
    batch = OutreachBatch(
        method=body.method,
        status="generating",
        model_used=model,
        lead_count=len(accounts),
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    import outreach_generator as og

    if body.method == "batch_api":
        try:
            openai_batch_id = og.submit_batch(accounts, model=model)
            batch.openai_batch_id = openai_batch_id
        except Exception as e:
            batch.status = "failed"
            batch.error = str(e)
        db.commit()
        db.refresh(batch)
        log_action(db, "outreach_batch_submitted", details=json.dumps(
            {"batch_id": batch.id, "method": "batch_api", "count": len(accounts)}))
        return {"batch": OutreachBatchOut.model_validate(batch), "emails": [],
                "skipped_contacted": len(skipped_contacted), "skipped_do_not_contact": len(skipped_dnc)}

    # sync mode — generate immediately
    try:
        results = og.generate_sync(accounts, model=model)
    except Exception as e:
        batch.status = "failed"
        batch.error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    accounts_by_id = {a.id: a for a in accounts}
    created_emails = []
    generated_count = 0
    for r in results:
        acc = accounts_by_id.get(r["account_id"])
        row = OutreachEmail(
            account_id=r["account_id"],
            batch_id=batch.id,
            to_email=acc.contact_email if acc else None,
            subject=r["subject"],
            body=r["body"],
            status="draft",
            model_used=r["model_used"],
            error=r["error"],
        )
        db.add(row)
        if not r["error"]:
            generated_count += 1
        created_emails.append(row)

    batch.status = "ready"
    batch.generated_count = generated_count
    db.commit()
    for row in created_emails:
        db.refresh(row)
    db.refresh(batch)

    log_action(db, "outreach_generated", details=json.dumps(
        {"batch_id": batch.id, "method": "sync", "generated": generated_count, "total": len(accounts)}))

    emails_out = [_outreach_email_to_out(row, accounts_by_id.get(row.account_id)) for row in created_emails]
    return {"batch": OutreachBatchOut.model_validate(batch), "emails": emails_out,
            "skipped_contacted": len(skipped_contacted), "skipped_do_not_contact": len(skipped_dnc)}


@app.get("/api/outreach/batches", response_model=List[OutreachBatchOut])
def outreach_list_batches(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    return db.query(OutreachBatch).order_by(desc(OutreachBatch.created_at)).all()


@app.get("/api/outreach/batches/{batch_id}")
def outreach_get_batch(batch_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    batch = db.query(OutreachBatch).filter(OutreachBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    emails = db.query(OutreachEmail).filter(OutreachEmail.batch_id == batch_id).all()
    account_ids = [e.account_id for e in emails]
    accounts_by_id = ({a.id: a for a in db.query(Account).filter(Account.id.in_(account_ids)).all()}
                       if account_ids else {})
    return {
        "batch": OutreachBatchOut.model_validate(batch),
        "emails": [_outreach_email_to_out(e, accounts_by_id.get(e.account_id)) for e in emails],
    }


@app.post("/api/outreach/batches/{batch_id}/refresh")
def outreach_refresh_batch(batch_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    batch = db.query(OutreachBatch).filter(OutreachBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.method != "batch_api" or not batch.openai_batch_id:
        raise HTTPException(status_code=400, detail="This batch was not submitted via the Batch API.")
    if batch.status == "ready":
        return {"batch": OutreachBatchOut.model_validate(batch), "emails": []}

    import outreach_generator as og
    try:
        poll = og.poll_batch(batch.openai_batch_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not poll OpenAI batch: {e}")

    if poll["results"] is None:
        if poll["status"] in ("failed", "expired", "cancelled"):
            batch.status = "failed"
            batch.error = f"OpenAI batch {poll['status']}"
        db.commit()
        db.refresh(batch)
        return {"batch": OutreachBatchOut.model_validate(batch), "emails": []}

    account_ids = [r["account_id"] for r in poll["results"] if r["account_id"]]
    accounts_by_id = ({a.id: a for a in db.query(Account).filter(Account.id.in_(account_ids)).all()}
                       if account_ids else {})
    created_emails = []
    generated_count = 0
    for r in poll["results"]:
        acc_id = r["account_id"]
        if not acc_id:
            continue
        acc = accounts_by_id.get(acc_id)
        row = OutreachEmail(
            account_id=acc_id,
            batch_id=batch.id,
            to_email=acc.contact_email if acc else None,
            subject=r["subject"],
            body=r["body"],
            status="draft",
            model_used=batch.model_used,
            error=r["error"],
        )
        db.add(row)
        if not r["error"]:
            generated_count += 1
        created_emails.append(row)

    batch.status = "ready"
    batch.generated_count = generated_count
    db.commit()
    for row in created_emails:
        db.refresh(row)
    db.refresh(batch)

    log_action(db, "outreach_batch_ingested", details=json.dumps({"batch_id": batch.id, "generated": generated_count}))
    emails_out = [_outreach_email_to_out(row, accounts_by_id.get(row.account_id)) for row in created_emails]
    return {"batch": OutreachBatchOut.model_validate(batch), "emails": emails_out}


@app.get("/api/outreach/emails", response_model=List[OutreachEmailOut])
def outreach_list_emails(
    status: Optional[str] = Query(None),
    batch_id: Optional[int] = Query(None),
    account_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    q = db.query(OutreachEmail)
    if status:
        q = q.filter(OutreachEmail.status == status)
    if batch_id:
        q = q.filter(OutreachEmail.batch_id == batch_id)
    if account_id:
        q = q.filter(OutreachEmail.account_id == account_id)
    rows = q.order_by(desc(OutreachEmail.created_at)).all()
    account_ids = [r.account_id for r in rows]
    accounts_by_id = ({a.id: a for a in db.query(Account).filter(Account.id.in_(account_ids)).all()}
                       if account_ids else {})
    return [_outreach_email_to_out(r, accounts_by_id.get(r.account_id)) for r in rows]


@app.patch("/api/outreach/emails/{email_id}", response_model=OutreachEmailOut)
def outreach_update_email(
    email_id: int,
    body: OutreachEmailUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    row = db.query(OutreachEmail).filter(OutreachEmail.id == email_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Outreach email not found")
    if row.status not in ("draft", "approved"):
        raise HTTPException(status_code=400, detail=f"Cannot edit an email with status '{row.status}'.")
    if body.subject is not None and body.subject != row.subject:
        row.subject = body.subject
        row.edited = True
    if body.body is not None and body.body != row.body:
        row.body = body.body
        row.edited = True
    if body.approved is not None:
        row.approved = body.approved
        row.status = "approved" if body.approved else "draft"
    db.commit()
    db.refresh(row)
    account = db.query(Account).filter(Account.id == row.account_id).first()
    return _outreach_email_to_out(row, account)


@app.post("/api/outreach/emails/{email_id}/approve", response_model=OutreachEmailOut)
def outreach_approve_email(email_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    row = db.query(OutreachEmail).filter(OutreachEmail.id == email_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Outreach email not found")
    row.approved = True
    row.status = "approved"
    db.commit()
    db.refresh(row)
    account = db.query(Account).filter(Account.id == row.account_id).first()
    return _outreach_email_to_out(row, account)


@app.post("/api/outreach/emails/{email_id}/unapprove", response_model=OutreachEmailOut)
def outreach_unapprove_email(email_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    row = db.query(OutreachEmail).filter(OutreachEmail.id == email_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Outreach email not found")
    if row.status in ("sent", "sending"):
        raise HTTPException(status_code=400, detail="Cannot unapprove an email that has already been sent.")
    row.approved = False
    row.status = "draft"
    db.commit()
    db.refresh(row)
    account = db.query(Account).filter(Account.id == row.account_id).first()
    return _outreach_email_to_out(row, account)


@app.post("/api/outreach/emails/bulk-approve", response_model=List[OutreachEmailOut])
def outreach_bulk_approve(body: OutreachIdList, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    rows = db.query(OutreachEmail).filter(OutreachEmail.id.in_(body.ids)).all()
    for row in rows:
        if row.status == "draft":
            row.approved = True
            row.status = "approved"
    db.commit()
    account_ids = [r.account_id for r in rows]
    accounts_by_id = ({a.id: a for a in db.query(Account).filter(Account.id.in_(account_ids)).all()}
                       if account_ids else {})
    for row in rows:
        db.refresh(row)
    log_action(db, "outreach_bulk_approved", details=json.dumps({"count": len(rows)}))
    return [_outreach_email_to_out(r, accounts_by_id.get(r.account_id)) for r in rows]


@app.post("/api/outreach/emails/{email_id}/send", response_model=OutreachSendResult)
def outreach_send_one(email_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    row = db.query(OutreachEmail).filter(OutreachEmail.id == email_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Outreach email not found")
    account = db.query(Account).filter(Account.id == row.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Linked account not found")
    import outreach_sender
    result = outreach_sender.send_outreach_email(row, account, db)
    action = "outreach_sent" if (result.get("ok") and not result.get("dry_run")) else \
             "outreach_dry_run" if result.get("ok") else "outreach_send_failed"
    log_action(db, action, details=json.dumps(
        {"email_id": row.id, "account_id": account.id, "error": result.get("error")}))
    return OutreachSendResult(id=row.id, **{k: v for k, v in result.items() if k in ("ok", "dry_run", "sent_to", "error")})


def _outreach_spacing_seconds(dry_run: bool) -> int:
    if dry_run:
        return 2  # all dry-run mail goes to one internal inbox — no reputation risk
    try:
        return max(int(settings.OUTREACH_SEND_SPACING_SECONDS), 2)
    except (TypeError, ValueError):
        return 75


def _drain_outreach_queue(email_ids: List[int]):
    """Background worker: sends queued emails one at a time with spacing so a
    fresh mailbox never bursts. Stops early if the daily cap is hit and
    releases the rest back to 'approved' for tomorrow."""
    import time
    import outreach_sender
    db = SessionLocal()
    try:
        for i, email_id in enumerate(email_ids):
            row = db.query(OutreachEmail).filter(OutreachEmail.id == email_id).first()
            if not row or row.status != "queued":
                continue
            account = db.query(Account).filter(Account.id == row.account_id).first()
            if not account:
                row.status = "failed"
                row.error = "Linked account not found"
                db.commit()
                continue
            result = outreach_sender.send_outreach_email(row, account, db)
            if result.get("cap_reached"):
                # release everything still queued back to approved and stop
                remaining = (db.query(OutreachEmail)
                             .filter(OutreachEmail.id.in_(email_ids[i + 1:]), OutreachEmail.status == "queued")
                             .all())
                for rest in remaining:
                    rest.status = "approved"
                    rest.error = result.get("error")
                db.commit()
                logger.info("[outreach] daily cap reached — %d email(s) released back to approved", len(remaining))
                break
            if i < len(email_ids) - 1:
                time.sleep(_outreach_spacing_seconds(bool(result.get("dry_run"))))
        sent = db.query(OutreachEmail).filter(OutreachEmail.id.in_(email_ids), OutreachEmail.status == "sent").count()
        failed = db.query(OutreachEmail).filter(OutreachEmail.id.in_(email_ids), OutreachEmail.status == "failed").count()
        log_action(db, "outreach_bulk_send_finished", details=json.dumps(
            {"requested": len(email_ids), "sent": sent, "failed": failed}))
    except Exception as e:
        logger.exception("[outreach] queue drain crashed: %s", e)
    finally:
        db.close()


@app.post("/api/outreach/send", response_model=OutreachSendOut)
def outreach_send_bulk(
    body: OutreachIdList,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    rows = db.query(OutreachEmail).filter(
        OutreachEmail.id.in_(body.ids), OutreachEmail.status == "approved").all()
    if not rows:
        raise HTTPException(status_code=400, detail="None of the selected emails are approved and ready to send.")

    for row in rows:
        row.status = "queued"
    db.commit()

    dry_run = settings.OUTREACH_SEND_MODE != "live"
    spacing = _outreach_spacing_seconds(dry_run)
    email_ids = [r.id for r in rows]
    background_tasks.add_task(_drain_outreach_queue, email_ids)

    log_action(db, "outreach_bulk_send_queued", details=json.dumps(
        {"queued": len(email_ids), "dry_run": dry_run, "spacing_seconds": spacing}))
    return OutreachSendOut(
        queued=len(email_ids),
        spacing_seconds=spacing,
        message=(f"{len(email_ids)} email(s) queued — sending one every {spacing}s in the background. "
                 "This page updates automatically."),
    )


@app.post("/api/outreach/follow-ups/generate")
def outreach_generate_follow_ups(
    body: OutreachFollowUpRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Drafts one short follow-up for every lead who got a real (live) intro
    N+ days ago and hasn't replied. Drafts only — human approval still required."""
    try:
        days = body.days if body.days is not None else int(settings.OUTREACH_FOLLOW_UP_DAYS)
    except (TypeError, ValueError):
        days = 4
    cutoff = datetime.utcnow() - timedelta(days=days)

    candidates = (db.query(Account)
                  .filter(Account.stage == "Contacted",
                          Account.awaiting_reply.is_(True),
                          Account.do_not_contact.is_(False),
                          Account.last_contacted_at <= cutoff)
                  .all())

    items = []
    for acc in candidates:
        # one follow-up per lead, ever — skip anyone who already has one
        existing_fu = (db.query(OutreachEmail)
                       .filter(OutreachEmail.account_id == acc.id,
                               OutreachEmail.is_follow_up.is_(True),
                               OutreachEmail.status.notin_(["failed", "skipped"]))
                       .first())
        if existing_fu:
            continue
        original = (db.query(OutreachEmail)
                    .filter(OutreachEmail.account_id == acc.id,
                            OutreachEmail.status == "sent",
                            OutreachEmail.was_dry_run.is_(False))
                    .order_by(desc(OutreachEmail.sent_at))
                    .first())
        if not original:
            continue  # only follow up on emails that actually reached the prospect
        items.append({"account": acc, "original_body": original.body or ""})

    if not items:
        return {"batch": None, "emails": [], "eligible": 0,
                "message": f"No leads need a follow-up yet (contacted {days}+ days ago, no reply, none pending). Checked {len(candidates)} contacted lead(s)."}

    model = body.model or settings.OUTREACH_MODEL
    batch = OutreachBatch(method="follow_up", status="generating", model_used=model, lead_count=len(items))
    db.add(batch)
    db.commit()
    db.refresh(batch)

    import outreach_generator as og
    try:
        results = og.generate_follow_ups(items, model=model)
    except Exception as e:
        batch.status = "failed"
        batch.error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Follow-up generation failed: {e}")

    accounts_by_id = {item["account"].id: item["account"] for item in items}
    created, generated_count = [], 0
    for r in results:
        acc = accounts_by_id.get(r["account_id"])
        row = OutreachEmail(
            account_id=r["account_id"],
            batch_id=batch.id,
            to_email=acc.contact_email if acc else None,
            subject=r["subject"],
            body=r["body"],
            status="draft",
            model_used=r["model_used"],
            error=r["error"],
            is_follow_up=True,
        )
        db.add(row)
        if not r["error"]:
            generated_count += 1
        created.append(row)

    batch.status = "ready"
    batch.generated_count = generated_count
    db.commit()
    for row in created:
        db.refresh(row)
    db.refresh(batch)

    log_action(db, "outreach_follow_ups_generated", details=json.dumps(
        {"batch_id": batch.id, "generated": generated_count, "eligible": len(items)}))
    emails_out = [_outreach_email_to_out(row, accounts_by_id.get(row.account_id)) for row in created]
    return {"batch": OutreachBatchOut.model_validate(batch), "emails": emails_out, "eligible": len(items)}


@app.post("/api/outreach/accounts/{account_id}/find-email", response_model=OutreachFindEmailOut)
def outreach_find_email(account_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    """Asks Apollo.io for a verified work email for this lead. Returns a
    suggestion only — the frontend saves it to the account after the user confirms."""
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    import apollo_enrich
    result = apollo_enrich.find_email(acc)
    log_action(db, "outreach_email_lookup", details=json.dumps(
        {"account_id": account_id, "company": acc.company_name,
         "found": bool(result.get("email")), "error": result.get("error")}))
    return OutreachFindEmailOut(**result)


# ─── Go/No-Go Assessment (Build 03) ─────────────────────────────────────────

@app.post("/api/opportunities/{opportunity_id}/gonogo", response_model=GoNoGoOut)
def gonogo_assessment(opportunity_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    from ai_screener import score_gonogo
    fields = [
        ("Title", opp.opportunity_title or opp.email_subject),
        ("Agency", opp.agency_name),
        ("Summary", opp.opportunity_summary),
        ("Required Services", opp.required_services),
        ("FaithForge Alignment", opp.faithforge_alignment),
        ("Eligibility Requirements", opp.eligibility_requirements),
        ("Certifications Required", opp.certifications_required),
        ("Insurance Requirements", opp.insurance_requirements),
        ("Disqualifying Requirements", opp.disqualifying_requirements),
        ("Risk Concerns", opp.risk_concerns),
        ("Estimated Value", opp.estimated_value),
        ("Compliance Requirements", opp.compliance_requirements),
        ("Submission Checklist (excerpt)", (opp.submission_checklist or "")[:400]),
    ]
    opportunity_data = "\n".join(f"{label}: {val}" for label, val in fields if val)
    try:
        result = score_gonogo(opportunity_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Go/No-Go assessment failed: {str(e)}")
    log_action(db, "gonogo_assessed", opportunity_id,
               json.dumps({"verdict": result.get("verdict"), "score": result.get("score")}))
    return result


# ─── Microsoft Graph Auth ────────────────────────────────────────────────────

@app.get("/api/auth/microsoft/status")
def ms_auth_status():
    """Check if Microsoft Graph API is configured and working."""
    from ms_graph import get_graph_client
    import os
    client = get_graph_client()
    if not client:
        return {"configured": False, "message": "Microsoft Graph credentials not set"}
    has_token_cache = os.path.exists(
        os.path.join(os.path.dirname(__file__), "ms_token.json")
    )
    if client.auth_mode == "device_code" and not has_token_cache:
        return {"configured": True, "authenticated": False,
                "message": "Device code login required. Call /api/auth/microsoft/login to authenticate."}
    try:
        client.get_access_token()
        return {"configured": True, "authenticated": True,
                "auth_mode": client.auth_mode, "email": client.email_address}
    except Exception as e:
        return {"configured": True, "authenticated": False, "message": str(e)}


@app.post("/api/auth/microsoft/login")
def ms_auth_login():
    """
    Initiate device code flow for personal/delegated accounts.
    Returns the URL and code for the user to visit in a browser.
    Not needed for client_credentials (M365 enterprise) mode.
    """
    from ms_graph import get_graph_client, DELEGATED_SCOPES
    import msal
    client = get_graph_client()
    if not client:
        raise HTTPException(status_code=400, detail="Microsoft Graph credentials not configured")
    if client.auth_mode != "device_code":
        raise HTTPException(status_code=400, detail="Device code flow only applies to device_code auth mode")
    authority = f"https://login.microsoftonline.com/{client.tenant_id}"
    app = msal.PublicClientApplication(client.client_id, authority=authority)
    flow = app.initiate_device_flow(scopes=DELEGATED_SCOPES)
    if "user_code" not in flow:
        raise HTTPException(status_code=500, detail=f"Device flow init failed: {flow}")
    return {
        "verification_uri": flow["verification_uri"],
        "user_code": flow["user_code"],
        "message": f"Go to {flow['verification_uri']} and enter code {flow['user_code']}",
        "expires_in": flow.get("expires_in", 900),
    }


# ─── Settings ─────────────────────────────────────────────────────────────────

SECRET_KEYS = {"OPENAI_API_KEY", "IMAP_PASSWORD", "SMTP_PASSWORD", "MS_CLIENT_SECRET", "OUTREACH_SMTP_PASSWORD", "APOLLO_API_KEY"}

DEFAULT_SETTINGS = [
    ("OPENAI_API_KEY", ""),
    # Microsoft Graph API
    ("MS_CLIENT_ID", ""),
    ("MS_CLIENT_SECRET", ""),
    ("MS_TENANT_ID", ""),
    ("MS_EMAIL_ADDRESS", ""),
    ("MS_AUTH_MODE", "client_credentials"),
    ("MS_MAIL_FOLDER", ""),
    # IMAP fallback
    ("IMAP_HOST", ""),
    ("IMAP_PORT", "993"),
    ("IMAP_USERNAME", ""),
    ("IMAP_PASSWORD", ""),
    ("IMAP_FOLDER", "INBOX"),
    ("IMAP_SCAN_DAYS", "30"),
    # SMTP fallback
    ("SMTP_HOST", ""),
    ("SMTP_PORT", "587"),
    ("SMTP_USERNAME", ""),
    ("SMTP_PASSWORD", ""),
    ("SMTP_FROM_EMAIL", ""),
    ("SMTP_FROM_NAME", "FaithForge AI"),
    ("NOTIFICATION_EMAIL", ""),
    # SharePoint
    ("SHAREPOINT_SITE", ""),
    ("SHAREPOINT_FOLDER", "Documents ready for Review"),
    ("SHAREPOINT_REVIEWER_EMAIL", "bernedette.atong@faithforgetech.com"),
    # Bulk cold-email outreach — independent of the packet mailbox above
    ("OUTREACH_SEND_MODE", "dry_run"),
    ("OUTREACH_TEST_ADDRESS", ""),
    ("OUTREACH_FROM_EMAIL", "operations@faithforgetech.com"),
    ("OUTREACH_FROM_NAME", "Bernedette Atong - FaithForge"),
    ("OUTREACH_BCC_EMAIL", "Bernedette.atong@faithforgetech.com"),
    ("OUTREACH_TRANSPORT", "graph"),
    ("OUTREACH_MODEL", "gpt-4o"),
    ("OUTREACH_DAILY_SEND_CAP", "15"),
    ("OUTREACH_SEND_SPACING_SECONDS", "75"),
    ("OUTREACH_FOLLOW_UP_DAYS", "4"),
    ("APOLLO_API_KEY", ""),
    ("OUTREACH_SMTP_HOST", ""),
    ("OUTREACH_SMTP_PORT", "587"),
    ("OUTREACH_SMTP_USERNAME", ""),
    ("OUTREACH_SMTP_PASSWORD", ""),
]


@app.get("/api/settings", response_model=List[AppSettingOut])
def get_settings(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    existing = {s.key: s for s in db.query(AppSetting).all()}
    result = []
    for key, default in DEFAULT_SETTINGS:
        if key in existing:
            setting = existing[key]
        else:
            env_val = getattr(settings, key, default)
            setting = AppSetting(key=key, value=str(env_val) if env_val else default, is_secret=(key in SECRET_KEYS))
            db.add(setting)
        if setting.is_secret and setting.value:
            setting_out = AppSettingOut(key=setting.key, value="••••••••", is_secret=True)
        else:
            setting_out = AppSettingOut(key=setting.key, value=setting.value, is_secret=setting.is_secret)
        result.append(setting_out)
    db.commit()
    return result


@app.put("/api/settings")
def update_settings(updates: dict, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    for key, value in updates.items():
        if key not in {k for k, _ in DEFAULT_SETTINGS}:
            continue
        setting = db.query(AppSetting).filter(AppSetting.key == key).first()
        if setting:
            if value and value != "••••••••":
                setting.value = str(value)
                setting.updated_at = datetime.utcnow()
        else:
            setting = AppSetting(key=key, value=str(value), is_secret=(key in SECRET_KEYS))
            db.add(setting)
        # Also update live settings object
        try:
            if hasattr(settings, key) and value and value != "••••••••":
                object.__setattr__(settings, key, value)
        except Exception:
            pass
    db.commit()
    log_action(db, "settings_updated", details=json.dumps({"keys": [k for k in updates.keys() if k not in SECRET_KEYS]}))
    return {"message": "Settings updated"}


# Fix circular import in background task
from database import SessionLocal
