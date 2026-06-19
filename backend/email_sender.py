import os
import smtplib
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import Dict, Any, Optional
from config import settings

SUBJECT = "FaithForge Contract Opportunity Packet Ready for Review"


def _fmt_date(d) -> str:
    if not d:
        return "TBD"
    if hasattr(d, "strftime"):
        return d.strftime("%B %d, %Y")
    return str(d)


def _fmt_score(score) -> str:
    if score is None:
        return "N/A"
    return f"{int(score)}/100"


def build_packet_email(opportunity: Dict[str, Any], packet_html: str, pdf_path: Optional[str] = None) -> MIMEMultipart:
    title = opportunity.get("opportunity_title") or opportunity.get("email_subject") or "Unknown Opportunity"
    agency = opportunity.get("agency_name") or "Unknown Agency"
    due_str = _fmt_date(opportunity.get("due_date"))
    score = _fmt_score(opportunity.get("relevance_score"))
    summary = opportunity.get("opportunity_summary") or "See attached packet."
    recommended = opportunity.get("recommended_action") or "Review attached packet and make bid/no-bid decision."

    body_text = f"""FaithForge Contract Opportunity Packet Ready for Review
{"=" * 60}

OPPORTUNITY NAME:   {title}
AGENCY:             {agency}
DUE DATE:           {due_str}
RELEVANCE SCORE:    {score}

SUMMARY:
{summary}

RECOMMENDED DECISION:
{recommended}

ATTACHED DOCUMENTS:
  • Contract Opportunity Packet (PDF) — full analysis, compliance checklist,
    bid/no-bid recommendation, proposed approach, next steps

REQUESTED USER ACTION:
  1. Review the attached packet
  2. Verify extracted fields and AI analysis
  3. Make your bid/no-bid decision in the FaithForge AI tool
  4. If pursuing: assign internal owner and begin proposal preparation

Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

{"=" * 60}
IMPORTANT: This packet is AI-generated for internal review only.
Do not share contract materials externally without authorization.
The AI does not submit proposals or make final decisions.
All bid/no-bid decisions require human review and approval.
"""

    html_email = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 24px; color: #1f2937; }}
  .header {{ background: #1e3a8a; color: white; padding: 20px 24px; border-radius: 8px; margin-bottom: 20px; }}
  .header h1 {{ margin: 0; font-size: 18px; }}
  .header p {{ margin: 6px 0 0; font-size: 13px; opacity: 0.85; }}
  .fields {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 20px; margin: 16px 0; }}
  .field {{ display: flex; gap: 12px; margin: 8px 0; font-size: 14px; }}
  .field-label {{ font-weight: 600; color: #6b7280; min-width: 140px; }}
  .field-value {{ color: #111827; }}
  .section {{ margin: 20px 0; }}
  .section h3 {{ font-size: 14px; font-weight: 700; color: #1e3a8a; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }}
  .section p {{ font-size: 14px; line-height: 1.6; margin: 0; }}
  .actions {{ background: #ecfdf5; border: 1px solid #6ee7b7; border-radius: 8px; padding: 16px 20px; margin: 20px 0; }}
  .actions ol {{ margin: 8px 0 0; padding-left: 20px; font-size: 14px; line-height: 1.8; }}
  .disclaimer {{ background: #fffbeb; border: 1px solid #fcd34d; border-radius: 6px; padding: 12px 16px; font-size: 12px; color: #92400e; margin-top: 20px; }}
  .attachment-note {{ background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 12px 16px; font-size: 13px; color: #1e40af; margin: 16px 0; }}
</style>
</head>
<body>
<div class="header">
  <h1>FaithForge Contract Opportunity Packet Ready for Review</h1>
  <p>Generated {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}</p>
</div>

<div class="fields">
  <div class="field"><span class="field-label">Opportunity</span><span class="field-value"><strong>{title}</strong></span></div>
  <div class="field"><span class="field-label">Agency</span><span class="field-value">{agency}</span></div>
  <div class="field"><span class="field-label">Due Date</span><span class="field-value">{due_str}</span></div>
  <div class="field"><span class="field-label">Relevance Score</span><span class="field-value">{score}</span></div>
  {f'<div class="field"><span class="field-label">EMMA Link</span><span class="field-value"><a href="{opportunity.get("emma_link")}">{opportunity.get("emma_link")}</a></span></div>' if opportunity.get("emma_link") else ""}
  {f'<div class="field"><span class="field-label">Website</span><span class="field-value"><a href="{opportunity.get("website_link")}">{opportunity.get("website_link")}</a></span></div>' if opportunity.get("website_link") else ""}
</div>

<div class="section">
  <h3>Summary of the Opportunity</h3>
  <p>{summary}</p>
</div>

<div class="section">
  <h3>Recommended Decision</h3>
  <p>{recommended}</p>
</div>

<div class="attachment-note">
  📎 <strong>Attached:</strong> Contract Opportunity Packet (PDF) — includes full scope analysis,
  FaithForge fit assessment, compliance checklist, bid/no-bid recommendation, and next steps.
</div>

<div class="actions">
  <strong>Requested User Action:</strong>
  <ol>
    <li>Review the attached PDF packet</li>
    <li>Verify AI-extracted fields and analysis</li>
    <li>Make your bid/no-bid decision in the FaithForge AI tool</li>
    <li>If pursuing: assign internal owner and begin proposal preparation</li>
  </ol>
</div>

<div class="disclaimer">
  ⚠️ <strong>IMPORTANT:</strong> This packet is AI-generated for internal review only.
  Do not share contract materials externally without authorization.
  The AI does not submit proposals, sign documents, or make final decisions.
  All bid/no-bid decisions require human review and approval.
</div>
</body>
</html>"""

    msg = MIMEMultipart("mixed")
    msg["Subject"] = SUBJECT
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = settings.NOTIFICATION_EMAIL

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body_text, "plain"))
    alt.attach(MIMEText(html_email, "html"))
    msg.attach(alt)

    # Attach PDF
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            part = MIMEBase("application", "pdf")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            safe_title = "".join(c for c in title[:40] if c.isalnum() or c in " -_").strip()
            part.add_header("Content-Disposition", "attachment",
                            filename=f"FaithForge_Packet_{safe_title}.pdf")
            msg.attach(part)

    return msg


def _packet_recipients() -> list:
    """Notification address + the SharePoint reviewer, deduped (case-insensitive)."""
    recipients, seen = [], set()
    for addr in (settings.NOTIFICATION_EMAIL, settings.SHAREPOINT_REVIEWER_EMAIL):
        if addr and addr.lower() not in seen:
            recipients.append(addr)
            seen.add(addr.lower())
    return recipients


def send_packet_email(opportunity: Dict[str, Any], packet_html: str, content_json: str = None) -> bool:
    recipients = _packet_recipients()
    if not recipients:
        raise ValueError("No packet recipient configured. Set NOTIFICATION_EMAIL or SHAREPOINT_REVIEWER_EMAIL.")

    # Generate PDF
    pdf_path = None
    try:
        from pdf_generator import packet_to_pdf
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.close()
        pdf_path = packet_to_pdf(content_json or "{}", tmp.name)
    except Exception:
        pdf_path = None

    sharepoint_link = None
    try:
        from ms_graph import get_graph_client
        graph = get_graph_client()

        # Upload to SharePoint if configured
        if graph and settings.SHAREPOINT_SITE and pdf_path and os.path.exists(pdf_path):
            try:
                title = opportunity.get("opportunity_title") or opportunity.get("email_subject") or "Packet"
                safe = "".join(c for c in title[:50] if c.isalnum() or c in " -_").strip()
                filename = f"FaithForge_Packet_{safe}.pdf"
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                sharepoint_link = graph.upload_to_sharepoint(
                    settings.SHAREPOINT_SITE,
                    settings.SHAREPOINT_FOLDER,
                    filename,
                    pdf_bytes,
                    reviewer_email=settings.SHAREPOINT_REVIEWER_EMAIL or None,
                )
            except Exception as sp_err:
                sharepoint_link = None

        # Build email HTML
        html_body = _build_sharepoint_email_html(opportunity, sharepoint_link, packet_html)

        if graph:
            if sharepoint_link:
                # Email just the link — no attachment needed
                return graph.send_email(recipients, SUBJECT, html_body)
            elif pdf_path and os.path.exists(pdf_path):
                # SharePoint failed — fall back to attachment
                return graph.send_email_with_attachment(
                    recipients, SUBJECT, html_body, pdf_path, opportunity
                )
            return graph.send_email(recipients, SUBJECT, html_body)

        # SMTP fallback
        if not settings.SMTP_HOST:
            raise ValueError("Neither Microsoft Graph API nor SMTP is configured.")
        msg = build_packet_email(opportunity, packet_html, None if sharepoint_link else pdf_path)
        msg["To"] = ", ".join(recipients)
        # Inject SharePoint link into body if available
        if sharepoint_link:
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            msg = MIMEMultipart("alternative")
            msg["Subject"] = SUBJECT
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = ", ".join(recipients)
            msg.attach(MIMEText(html_body, "html"))
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.ehlo(); server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, recipients, msg.as_string())
        server.quit()
        return True
    finally:
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.unlink(pdf_path)
            except Exception:
                pass


def _build_sharepoint_email_html(opportunity: Dict[str, Any], sharepoint_link: Optional[str], packet_html: str) -> str:
    title = opportunity.get("opportunity_title") or opportunity.get("email_subject") or "Unknown Opportunity"
    agency = opportunity.get("agency_name") or "Unknown Agency"
    due_str = _fmt_date(opportunity.get("due_date"))
    score = _fmt_score(opportunity.get("relevance_score"))
    summary = opportunity.get("opportunity_summary") or "See packet for details."
    recommended = opportunity.get("recommended_action") or "Review packet and make bid/no-bid decision."

    link_section = f"""
<div style="margin:20px 0;padding:16px 20px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;">
  <p style="margin:0 0 8px;font-weight:700;color:#1e40af;font-size:14px;">📁 Contract Packet — SharePoint</p>
  <a href="{sharepoint_link}" style="display:inline-block;background:#1e3a8a;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">
    Open in SharePoint →
  </a>
  <p style="margin:8px 0 0;font-size:12px;color:#6b7280;">Saved to: {settings.SHAREPOINT_FOLDER}</p>
</div>""" if sharepoint_link else f"""
<div style="margin:20px 0;padding:16px 20px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;">
  <p style="margin:0;font-size:13px;color:#1e40af;">📎 Packet attached as PDF (SharePoint upload unavailable)</p>
</div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:24px;color:#1f2937;}}
  .header {{background:#1e3a8a;color:white;padding:20px 24px;border-radius:8px;margin-bottom:20px;}}
  .header h1 {{margin:0;font-size:18px;}}
  .fields {{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px 20px;margin:16px 0;}}
  .field {{display:flex;gap:12px;margin:8px 0;font-size:14px;}}
  .fl {{font-weight:600;color:#6b7280;min-width:140px;}}
  .fv {{color:#111827;}}
  .section {{margin:16px 0;}}
  .section h3 {{font-size:13px;font-weight:700;color:#1e3a8a;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;}}
  .section p {{font-size:14px;line-height:1.6;margin:0;}}
  .disclaimer {{background:#fffbeb;border:1px solid #fcd34d;border-radius:6px;padding:12px 16px;font-size:12px;color:#92400e;margin-top:20px;}}
</style></head>
<body>
<div class="header">
  <h1>FaithForge Contract Opportunity Packet Ready for Review</h1>
  <p style="margin:6px 0 0;font-size:13px;opacity:.85;">Generated {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}</p>
</div>
<div class="fields">
  <div class="field"><span class="fl">Opportunity</span><span class="fv"><strong>{title}</strong></span></div>
  <div class="field"><span class="fl">Agency</span><span class="fv">{agency}</span></div>
  <div class="field"><span class="fl">Due Date</span><span class="fv">{due_str}</span></div>
  <div class="field"><span class="fl">Relevance Score</span><span class="fv">{score}</span></div>
</div>
{link_section}
<div class="section"><h3>Summary</h3><p>{summary}</p></div>
<div class="section"><h3>Recommended Decision</h3><p>{recommended}</p></div>
<div class="disclaimer">⚠️ AI-generated for internal review only. Do not share externally without authorization. All bid/no-bid decisions require human approval.</div>
</body></html>"""
